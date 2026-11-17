"""Download de VOD/clipe (yt-dlp) e do chat (chat-downloader)."""
import json
import os
import re

from .util import log


def eh_url(texto: str) -> bool:
    return bool(re.match(r"^https?://", texto.strip(), re.I))


def _ydl(opts: dict):
    import yt_dlp

    base = {"quiet": True, "no_warnings": True, "noprogress": True}
    base.update(opts)
    return yt_dlp.YoutubeDL(base)


def info_url(url: str) -> dict:
    with _ydl({}) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "titulo": info.get("title") or "",
        "canal": info.get("uploader") or info.get("channel") or "",
        "duracao": float(info.get("duration") or 0),
    }


def baixar_audio(url: str, pasta: str) -> str:
    """Baixa so o audio (bem mais leve que o video) para achar os momentos."""
    os.makedirs(pasta, exist_ok=True)
    existente = [f for f in os.listdir(pasta) if f.startswith("audio.")]
    if existente:
        return os.path.join(pasta, existente[0])
    log("Baixando o audio da live (pode demorar em lives longas)...")
    opts = {
        "format": "bestaudio/Audio_Only/audio_only/worst",
        "outtmpl": os.path.join(pasta, "audio.%(ext)s"),
    }
    with _ydl(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


def baixar_video(url: str, pasta: str, nome: str = "video", inicio: float | None = None,
                 fim: float | None = None) -> str:
    """Baixa o video inteiro ou so um trecho (inicio/fim em segundos)."""
    os.makedirs(pasta, exist_ok=True)
    opts = {
        "format": "bv*[height<=1080]+ba/b[height<=1080]/best",
        "outtmpl": os.path.join(pasta, f"{nome}.%(ext)s"),
        "merge_output_format": "mp4",
    }
    if inicio is not None and fim is not None:
        from yt_dlp.utils import download_range_func

        opts["download_ranges"] = download_range_func(None, [(inicio, fim)])
        opts["force_keyframes_at_cuts"] = False
    with _ydl(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        caminho = ydl.prepare_filename(info)
    if not os.path.exists(caminho):  # extensao trocada pelo merge
        base = os.path.splitext(caminho)[0]
        for ext in (".mp4", ".mkv", ".webm"):
            if os.path.exists(base + ext):
                return base + ext
    return caminho


def baixar_chat(url: str, destino: str) -> str | None:
    """Baixa o chat da VOD (funciona bem na Twitch). Retorna o caminho do JSON ou None."""
    if os.path.exists(destino):
        return destino
    log("Baixando o chat da VOD...")
    try:
        from chat_downloader import ChatDownloader

        msgs = []
        for m in ChatDownloader().get_chat(url):
            t = m.get("time_in_seconds")
            if t is not None:
                msgs.append({"t": float(t), "msg": m.get("message") or ""})
    except Exception as e:  # chat e opcional: segue so com audio
        log(f"Nao consegui baixar o chat ({type(e).__name__}). Vou usar so o audio.")
        return None
    if not msgs:
        log("Chat vazio. Vou usar so o audio.")
        return None
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(msgs, f, ensure_ascii=False)
    log(f"Chat baixado: {len(msgs)} mensagens.")
    return destino


def carregar_chat(caminho: str) -> list[dict]:
    """Aceita o JSON do chat-downloader, o formato {t,msg} ou um .txt '[h:mm:ss] usuario: msg'."""
    if caminho.lower().endswith(".json"):
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        out = []
        for m in dados:
            t = m.get("t", m.get("time_in_seconds"))
            if t is not None:
                out.append({"t": float(t), "msg": m.get("msg", m.get("message", "")) or ""})
        return out
    padrao = re.compile(r"^\[?(\d+):(\d{1,2}):(\d{1,2})\]?\s*(.*)$")
    out = []
    with open(caminho, encoding="utf-8", errors="replace") as f:
        for linha in f:
            m = padrao.match(linha.strip())
            if m:
                h, mi, s, resto = m.groups()
                out.append({"t": int(h) * 3600 + int(mi) * 60 + int(s), "msg": resto})
    return out
