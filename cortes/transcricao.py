"""Transcricao local com faster-whisper (usa a placa de video se der, senao o processador)."""
import json
import os

from .util import log

_modelos: dict = {}


def _ler_trecho(caminho: str, inicio: float = 0.0, duracao: float | None = None):
    """Decodifica so o trecho pedido (16 kHz mono) sem carregar a live inteira na memoria."""
    import subprocess

    import numpy as np

    cmd = ["ffmpeg", "-v", "error"]
    if inicio:
        cmd += ["-ss", f"{inicio:.3f}"]
    cmd += ["-i", caminho]
    if duracao:
        cmd += ["-t", f"{duracao:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    dados = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(dados, dtype=np.int16).astype(np.float32) / 32768.0


def _carregar(nome: str):
    if nome in _modelos:
        return _modelos[nome]
    from faster_whisper import WhisperModel

    dispositivo = os.environ.get("CORTES_DISPOSITIVO", "auto")
    tentativas = []
    if dispositivo in ("auto", "cuda"):
        tentativas.append(("cuda", "int8_float16"))
        tentativas.append(("cuda", "int8"))
    tentativas.append(("cpu", "int8"))
    erro = None
    for disp, tipo in tentativas:
        try:
            modelo = WhisperModel(nome, device=disp, compute_type=tipo)
            log(f"Whisper '{nome}' carregado em {disp.upper()} ({tipo}).")
            _modelos[nome] = modelo
            return modelo
        except Exception as e:  # sem CUDA instalada etc.
            erro = e
    raise RuntimeError(f"Nao consegui carregar o Whisper '{nome}': {erro}")


def transcrever(audio: str, modelo: str = "base", idioma: str = "pt", inicio: float = 0.0,
                duracao: float | None = None, palavras: bool = False) -> list[dict]:
    """Lista de segmentos {ini, fim, texto[, palavras:[{ini,fim,p}]]}. Tempos ja somados a 'inicio'."""
    m = _carregar(modelo)
    entrada = _ler_trecho(audio, inicio, duracao)
    if len(entrada) < 1600:
        return []
    segs, _ = m.transcribe(
        entrada, language=idioma or None, word_timestamps=palavras, vad_filter=True,
        beam_size=1 if not palavras else 5, condition_on_previous_text=False,
    )
    saida = []
    for s in segs:
        item = {"ini": round(s.start + inicio, 2), "fim": round(s.end + inicio, 2), "texto": s.text.strip()}
        if palavras and s.words:
            item["palavras"] = [
                {"ini": round(w.start + inicio, 2), "fim": round(w.end + inicio, 2), "p": w.word.strip()}
                for w in s.words if w.word.strip()
            ]
        saida.append(item)
    return saida


def transcrever_longo(audio: str, destino: str, modelo: str, idioma: str, duracao: float) -> list[dict]:
    """Transcreve a live inteira salvando o progresso (se cair, continua de onde parou)."""
    segs: list[dict] = []
    feito = 0.0
    if os.path.exists(destino):
        with open(destino, encoding="utf-8") as f:
            dados = json.load(f)
        segs, feito = dados["segmentos"], dados["feito"]
        if dados.get("completo"):
            return segs
        log(f"Continuando transcricao a partir de {feito / 60:.0f} min...")
    pedaco = 600.0  # 10 min por vez
    while feito < duracao:
        dur = min(pedaco, duracao - feito)
        segs.extend(transcrever(audio, modelo, idioma, inicio=feito, duracao=dur))
        feito += dur
        with open(destino, "w", encoding="utf-8") as f:
            json.dump({"segmentos": segs, "feito": feito, "completo": feito >= duracao}, f, ensure_ascii=False)
        log(f"Transcrito: {feito / 60:.0f} de {duracao / 60:.0f} min")
    return segs
