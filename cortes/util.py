import json
import shutil
import subprocess
import sys


def log(msg: str) -> None:
    print(f"[cortes] {msg}", flush=True)


def checar_ffmpeg() -> None:
    for prog in ("ffmpeg", "ffprobe"):
        if shutil.which(prog) is None:
            sys.exit(f"Nao achei o '{prog}'. Instale o FFmpeg e coloque no PATH (veja o README).")


def rodar(cmd: list[str], cwd: str | None = None) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"Comando falhou: {' '.join(cmd[:4])}...\n{proc.stderr[-2000:]}")


def info_video(caminho: str) -> dict:
    """Retorna largura, altura e duracao do video."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", caminho],
        capture_output=True, text=True, check=True,
    ).stdout
    dados = json.loads(out)
    video = next((s for s in dados["streams"] if s.get("codec_type") == "video"), None)
    tem_audio = any(s.get("codec_type") == "audio" for s in dados["streams"])
    return {
        "largura": int(video["width"]) if video else 0,
        "altura": int(video["height"]) if video else 0,
        "duracao": float(dados["format"].get("duration", 0)),
        "tem_audio": tem_audio,
    }


def tempo_hms(segundos: float) -> str:
    s = int(segundos)
    return f"{s // 3600:d}h{(s % 3600) // 60:02d}m{s % 60:02d}s"
