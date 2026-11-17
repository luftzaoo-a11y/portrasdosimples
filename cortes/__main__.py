"""Linha de comando: python -m cortes <comando> ..."""
import argparse
import os
import shutil
import sys


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def cmd_setup(_):
    from . import config
    from .facecam import baixar_yunet

    ok = "✓"
    falta = "✗"
    tudo_ok = True

    def item(cond, txt, dica=""):
        nonlocal tudo_ok
        print(f"{ok if cond else falta} {txt}" + ("" if cond or not dica else f"  -> {dica}"))
        tudo_ok &= bool(cond)

    print("Clipador GTA - verificando o computador\n")
    item(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]}", "instale o Python 3.10 ou mais novo")
    item(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg", "Windows: winget install Gyan.FFmpeg")
    js = shutil.which("deno") or shutil.which("node")
    item(js, "JavaScript runtime (o YouTube exige)", "Windows: winget install DenoLand.Deno")
    livre = shutil.disk_usage(config.RAIZ).free / 1e9
    item(livre > 10, f"Disco: {livre:.0f} GB livres", "libere pelo menos 10 GB")
    pacotes = []
    for p in ("yt_dlp", "chat_downloader", "faster_whisper", "cv2", "numpy"):
        try:
            __import__(p)
        except ImportError:
            pacotes.append(p)
    item(not pacotes, "Pacotes Python", f"faltando {pacotes}: rode o setup.bat de novo")
    if pacotes:
        sys.exit(1)

    try:
        import ctranslate2

        gpus = ctranslate2.get_cuda_device_count()
    except Exception:
        gpus = 0
    print(f"{ok} Placa de video NVIDIA para o Whisper: {'sim' if gpus else 'nao (vai usar o processador)'}")

    try:
        baixar_yunet()
        item(True, "Detector de camera (OpenCV YuNet, 0.2 MB)")
    except Exception as e:
        item(False, "Detector de camera", str(e))

    from . import transcricao

    for nome in ("base", "small"):
        try:
            transcricao._carregar(nome)
            item(True, f"Whisper '{nome}' ({'ouvir a live' if nome == 'base' else 'legendas'})")
        except Exception as e:
            item(False, f"Whisper '{nome}'", str(e)[:200])

    item(os.path.exists(config.ARQ_STREAMERS), f"Lista de streamers: {config.ARQ_STREAMERS}")
    print("\nTudo pronto!" if tudo_ok else "\nArrume os itens com ✗ e rode de novo.")
    print("Experimente:  python -m cortes buscar")


def cmd_buscar(a):
    from . import buscar

    buscar.imprimir(buscar.buscar(horas=a.horas, ao_vivo=not a.sem_ao_vivo))


def cmd_analisar(a):
    from .analisar import analisar

    pasta = analisar(a.fonte, a.streamer, a.chat, a.modelo, a.idioma, a.sem_chat)
    print(f"\nPASTA={pasta}")


def cmd_renderizar(a):
    from .clipes import renderizar_momentos

    somente = [int(x) for x in a.somente.split(",")] if a.somente else None
    renderizar_momentos(a.pasta, a.nota_minima, a.modelo_legenda, somente, not a.titulo_curto)


def cmd_calibrar(a):
    from . import config, facecam
    from .util import info_video

    dur = info_video(a.video)["duracao"]
    cfg = config.layout(a.streamer)
    ini = min(a.tempo, max(dur - 5, 0))
    regiao = facecam.detectar(a.video, ini, min(120, dur - ini), proporcao=1080 / (1920 * cfg["proporcao_cam"]))
    destino = os.path.abspath(a.saida)
    facecam.salvar_previa(a.video, ini + 1, regiao, destino)
    if regiao:
        print(f"Camera encontrada: {regiao}")
        print(f'Para fixar, coloque em layouts.json:  "{a.streamer or "nome"}": {{"facecam": {regiao}}}')
    else:
        print("Nao achei a camera automaticamente. Veja a imagem (tem uma grade de 10%) e preencha na mao.")
    print(f"Imagem de conferencia: {destino}")


def main():
    _utf8()
    p = argparse.ArgumentParser(prog="cortes", description="Clipador automatico de lives de GTA (Twitch/Kick/YouTube)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="verifica e prepara tudo no computador")
    s.set_defaults(f=cmd_setup)

    s = sub.add_parser("buscar", help="acha lives/VODs de GTA recentes")
    s.add_argument("--horas", type=int, default=48)
    s.add_argument("--sem-ao-vivo", action="store_true", help="nao procurar os maiores ao vivo na Twitch")
    s.set_defaults(f=cmd_buscar)

    s = sub.add_parser("analisar", help="etapa 1: baixa audio, transcreve, marca gritos e chat")
    s.add_argument("fonte", help="link da VOD/clipe ou arquivo de video")
    s.add_argument("--streamer")
    s.add_argument("--chat", help="arquivo de chat (.json ou .txt) se tiver")
    s.add_argument("--sem-chat", action="store_true")
    s.add_argument("--modelo", default="base", help="whisper para ouvir a live: tiny, base, small")
    s.add_argument("--idioma", help="pt, en... (padrao: layouts.json)")
    s.set_defaults(f=cmd_analisar)

    s = sub.add_parser("renderizar", help="etapa 3: gera os clipes do momentos.json")
    s.add_argument("pasta", help="pasta em trabalho/ criada pelo analisar")
    s.add_argument("--nota-minima", type=int, default=7)
    s.add_argument("--modelo-legenda", default="small", help="tiny, base, small, medium ou nenhum")
    s.add_argument("--somente", help="ex: 1,3 para refazer so esses clipes")
    s.add_argument("--titulo-curto", action="store_true", help="titulo so nos 4 primeiros segundos")
    s.set_defaults(f=cmd_renderizar)

    s = sub.add_parser("calibrar", help="acha a camera do streamer e salva uma imagem para conferir")
    s.add_argument("video")
    s.add_argument("--tempo", type=float, default=60)
    s.add_argument("--streamer")
    s.add_argument("--saida", default="calibracao.png")
    s.set_defaults(f=cmd_calibrar)

    a = p.parse_args()
    from .util import checar_ffmpeg

    if a.cmd != "setup":
        checar_ffmpeg()
    a.f(a)


if __name__ == "__main__":
    main()
