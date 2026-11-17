"""Monta o video vertical 1080x1920: camera em cima, jogo embaixo, titulo e legenda."""
import os

from .legendas import ALT, LARG, gerar_ass
from .util import info_video, rodar


def _par(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def _recorte_proporcao(x, y, w, h, proporcao):
    """Recorta (x,y,w,h) em pixels no centro para ficar com largura/altura = proporcao."""
    if w / h > proporcao:
        nw = h * proporcao
        x += (w - nw) / 2
        w = nw
    else:
        nh = w / proporcao
        y += (h - nh) / 2
        h = nh
    return _par(w), _par(h), _par(x), _par(y)


def filtro(W: int, H: int, facecam: list[float] | None, jogo: list[float] | None,
           alt_cam: int, com_legenda: bool) -> str:
    alt_jogo = ALT - alt_cam
    if jogo:
        gx, gy, gw, gh = jogo[0] * W, jogo[1] * H, jogo[2] * W, jogo[3] * H
    else:
        gx, gy, gw, gh = 0, 0, W, H
    if facecam:
        cx, cy, cw, ch = facecam[0] * W, facecam[1] * H, facecam[2] * W, facecam[3] * H
        cw2, ch2, cx2, cy2 = _recorte_proporcao(cx, cy, cw, ch, LARG / alt_cam)
        gw2, gh2, gx2, gy2 = _recorte_proporcao(gx, gy, gw, gh, LARG / alt_jogo)
        f = (
            f"[0:v]crop={cw2}:{ch2}:{cx2}:{cy2},scale={LARG}:{alt_cam}:flags=lanczos,setsar=1[cam];"
            f"[0:v]crop={gw2}:{gh2}:{gx2}:{gy2},scale={LARG}:{alt_jogo}:flags=lanczos,setsar=1[jogo];"
            f"[cam][jogo]vstack=inputs=2,"
            f"drawbox=x=0:y={alt_cam - 3}:w={LARG}:h=6:color=black:t=fill[v0]"
        )
    else:
        # sem camera: jogo no meio com fundo desfocado
        f = (
            f"[0:v]crop={_par(gw)}:{_par(gh)}:{_par(gx)}:{_par(gy)},split[a][b];"
            f"[a]scale={LARG}:{ALT}:force_original_aspect_ratio=increase,crop={LARG}:{ALT},boxblur=25:2[fundo];"
            f"[b]scale={LARG}:-2:flags=lanczos[frente];"
            f"[fundo][frente]overlay=(W-w)/2:(H-h)/2[v0]"
        )
    if com_legenda:
        f += ";[v0]ass=legenda.ass,format=yuv420p[v]"
    else:
        f += ";[v0]format=yuv420p[v]"
    return f


def renderizar(video: str, destino: str, inicio: float, duracao: float, facecam: list[float] | None,
               jogo: list[float] | None, palavras: list[dict], titulo: str | None,
               proporcao_cam: float = 0.4, fonte: str = "Arial", titulo_ate: float | None = None) -> str:
    """Gera o clipe final. 'palavras' com tempos relativos ao inicio do clipe."""
    video = os.path.abspath(video)
    destino = os.path.abspath(destino)
    pasta = os.path.dirname(destino)
    os.makedirs(pasta, exist_ok=True)
    info = info_video(video)
    alt_cam = _par(ALT * proporcao_cam) if facecam else 0
    y_titulo = alt_cam if facecam else int(ALT * 0.2)
    y_legenda = int(alt_cam + (ALT - alt_cam) * 0.42) if facecam else int(ALT * 0.72)

    com_legenda = bool(palavras or titulo)
    if com_legenda:
        ass = gerar_ass(palavras, titulo, y_titulo, y_legenda, duracao, fonte, titulo_ate)
        with open(os.path.join(pasta, "legenda.ass"), "w", encoding="utf-8") as f:
            f.write(ass)

    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{inicio:.3f}", "-i", video, "-t", f"{duracao:.3f}",
           "-filter_complex", filtro(info["largura"], info["altura"], facecam, jogo, alt_cam, com_legenda),
           "-map", "[v]"]
    if info["tem_audio"]:
        cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30",
            "-movflags", "+faststart", os.path.basename(destino)]
    # roda dentro da pasta do clipe: assim o caminho da legenda funciona no Windows (sem 'C:')
    rodar(cmd, cwd=pasta)
    if com_legenda:
        os.remove(os.path.join(pasta, "legenda.ass"))
    return destino
