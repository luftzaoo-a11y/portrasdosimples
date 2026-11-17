"""Sinais por segundo: volume do audio (gritos/surtos) e velocidade do chat."""
import re
import subprocess

import numpy as np

TAXA = 8000  # Hz, suficiente para medir volume

RISADAS = re.compile(
    r"(k{3,}|kkk|hah|hue|rsrs|lul|kekw|omegalul|lmao|lol|icant|pog|wtf|caralho|mds|"
    r"meu deus|clip|clipa|w+\b|\?{2,}|!{2,}|💀|😂|🤣|😭)",
    re.I,
)


def volume_por_segundo(caminho: str) -> np.ndarray:
    """Volume (dB) de cada segundo do audio, lendo aos poucos (serve para lives de horas)."""
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", caminho, "-vn", "-ac", "1", "-ar", str(TAXA), "-f", "s16le", "-"],
        stdout=subprocess.PIPE,
    )
    valores = []
    bloco = TAXA * 2 * 60  # 60 s por leitura
    resto = b""
    while True:
        dados = proc.stdout.read(bloco)
        if not dados:
            break
        dados = resto + dados
        n = len(dados) // (TAXA * 2) * (TAXA * 2)
        resto = dados[n:]
        if n:
            a = np.frombuffer(dados[:n], dtype=np.int16).astype(np.float32).reshape(-1, TAXA)
            rms = np.sqrt((a ** 2).mean(axis=1)) + 1.0
            valores.extend((20 * np.log10(rms / 32768)).tolist())
    proc.wait()
    return np.array(valores, dtype=np.float32)


def chat_por_segundo(mensagens: list[dict], duracao: int) -> np.ndarray:
    """Peso do chat por segundo: 1 por mensagem, +1 se for risada/hype."""
    v = np.zeros(max(duracao, 1), dtype=np.float32)
    for m in mensagens:
        t = int(m["t"])
        if 0 <= t < len(v):
            v[t] += 1.0 + (1.0 if RISADAS.search(m["msg"]) else 0.0)
    return v


def _media_movel(v: np.ndarray, janela: int) -> np.ndarray:
    if janela <= 1 or len(v) == 0:
        return v
    k = np.ones(janela, dtype=np.float32) / janela
    pad = janela // 2
    vp = np.pad(v, (pad, janela - 1 - pad), mode="edge")  # repete a borda (evita pico falso no inicio/fim)
    return np.convolve(vp, k, mode="valid")


def _linha_base(v: np.ndarray, janela: int = 300) -> np.ndarray:
    """Mediana local (janela de ~5 min) para comparar cada momento com o 'normal' daquele trecho."""
    if len(v) == 0:
        return v
    passo = 30
    centros, medianas = [], []
    for c in range(0, len(v), passo):
        ini, fim = max(0, c - janela // 2), min(len(v), c + janela // 2)
        centros.append(c)
        medianas.append(float(np.median(v[ini:fim])))
    return np.interp(np.arange(len(v)), centros, medianas).astype(np.float32)


def destaque(v: np.ndarray, suavizar: int, escala_min: float) -> np.ndarray:
    """Quanto cada segundo esta acima do normal, em 'desvios' (0 = normal)."""
    if len(v) == 0:
        return v
    s = _media_movel(v, suavizar)
    excesso = s - _linha_base(s)
    escala = max(float(np.median(np.abs(excesso - np.median(excesso)))) * 1.4826, escala_min)
    return np.clip(excesso / escala, 0, None)


def calcular(volume: np.ndarray, chat: np.ndarray | None, atraso_chat: int = 6) -> dict:
    """Retorna os destaques de audio, chat e a pontuacao combinada por segundo."""
    a = destaque(volume, 3, escala_min=1.5)  # dB
    c = None
    if chat is not None and chat.sum() > 0:
        n = len(a)
        chat = np.pad(chat, (0, max(0, n - len(chat))))[:n]
        # o chat reage alguns segundos depois do acontecimento: puxa para tras
        chat = np.concatenate([chat[atraso_chat:], np.zeros(atraso_chat, dtype=np.float32)])
        c = destaque(chat, 10, escala_min=0.3)  # mensagens/s
        total = 0.45 * a + 0.55 * c
    else:
        total = a
    return {"audio": a, "chat": c, "total": total}


def picos(total: np.ndarray, quantidade: int = 40, distancia: int = 60, margem: int = 20) -> list[int]:
    """Segundos com maior pontuacao, separados por pelo menos 'distancia' segundos."""
    if len(total) == 0:
        return []
    ordem = np.argsort(total)[::-1]
    escolhidos: list[int] = []
    for i in ordem:
        if total[i] <= 0.5 or len(escolhidos) >= quantidade:
            break
        if i < margem or i > len(total) - margem:
            continue
        if all(abs(int(i) - e) >= distancia for e in escolhidos):
            escolhidos.append(int(i))
    return sorted(escolhidos)
