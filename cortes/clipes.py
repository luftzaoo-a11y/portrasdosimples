"""Etapa 3: transforma os momentos escolhidos (momentos.json) em clipes verticais prontos."""
import os

from . import config, download, facecam, render, transcricao
from .util import info_video, log, tempo_hms

FOLGA = 3.0  # segundos extras baixados antes/depois do trecho


def _validar(m: dict, duracao: float) -> dict:
    ini, fim = float(m["inicio"]), float(m["fim"])
    ini = max(0.0, ini)
    fim = min(fim, duracao) if duracao else fim
    if fim - ini < 5:
        raise ValueError(f"Momento curto demais: {m}")
    if fim - ini > 180:
        fim = ini + 180
    return {**m, "inicio": ini, "fim": fim}


def renderizar_momentos(pasta: str, nota_minima: int = 7, modelo_legenda: str = "small",
                        somente: list[int] | None = None, titulo_fixo: bool = True) -> list[str]:
    fonte_info = config.ler_json(os.path.join(pasta, "fonte.json"))
    if not fonte_info:
        raise SystemExit(f"Nao achei {pasta}/fonte.json. Rode 'analisar' primeiro.")
    momentos = config.ler_json(os.path.join(pasta, "momentos.json"))
    if not momentos:
        raise SystemExit(f"Nao achei {pasta}/momentos.json (ele e escrito depois de ler os blocos).")

    cfg = config.layout(fonte_info.get("streamer"))
    idioma = fonte_info.get("idioma") or cfg["idioma"]
    escolhidos = [m for m in momentos if int(m.get("nota", 0)) >= nota_minima]
    escolhidos.sort(key=lambda m: -int(m.get("nota", 0)))
    if somente:
        escolhidos = [m for i, m in enumerate(escolhidos, 1) if i in somente]
    if not escolhidos:
        raise SystemExit(f"Nenhum momento com nota >= {nota_minima}.")

    saida = os.path.join(config.PASTA_CLIPES, os.path.basename(pasta.rstrip("/\\")))
    os.makedirs(saida, exist_ok=True)
    cam_detectada = fonte_info.get("facecam_detectada")
    feitos = []
    for n, m in enumerate(escolhidos, 1):
        m = _validar(m, fonte_info.get("duracao") or 0)
        dur = m["fim"] - m["inicio"]
        log(f"[{n}/{len(escolhidos)}] {tempo_hms(m['inicio'])} ({dur:.0f}s) nota {m.get('nota')}: {m.get('titulo', '')}")

        # video do trecho
        if fonte_info["eh_url"]:
            ini_dl = max(0.0, m["inicio"] - FOLGA)
            video = download.baixar_video(fonte_info["fonte"], os.path.join(pasta, "trechos"),
                                          f"trecho_{int(m['inicio'])}", ini_dl, m["fim"] + FOLGA)
            deslocamento = m["inicio"] - ini_dl
        else:
            video = fonte_info["fonte"]
            deslocamento = m["inicio"]
        if info_video(video)["largura"] == 0:
            raise RuntimeError(f"O arquivo {video} nao tem video.")

        # camera do streamer
        cam = m.get("facecam") or cfg.get("facecam") or cam_detectada
        if cam is None:
            cam = facecam.detectar(video, deslocamento, dur, proporcao=1080 / (1920 * cfg["proporcao_cam"]))
            if cam:
                cam_detectada = cam
                fonte_info["facecam_detectada"] = cam
                config.salvar_json(os.path.join(pasta, "fonte.json"), fonte_info)
                log(f"Camera encontrada em {cam}")
            else:
                log("Nao achei camera fixa: vou usar o jogo no meio com fundo desfocado.")

        # legenda palavra por palavra
        palavras = []
        if modelo_legenda != "nenhum":
            segs = transcricao.transcrever(video, modelo_legenda, idioma, inicio=deslocamento,
                                           duracao=dur, palavras=True)
            for sg in segs:
                for w in sg.get("palavras", []):
                    palavras.append({"ini": w["ini"] - deslocamento, "fim": w["fim"] - deslocamento, "p": w["p"]})

        base = f"{n:02d}_nota{m.get('nota', 0)}_{config.slug(m.get('titulo', 'clipe'), 40)}"
        destino = os.path.join(saida, base + ".mp4")
        render.renderizar(video, destino, deslocamento, dur, cam, cfg.get("jogo"), palavras,
                          m.get("titulo"), cfg["proporcao_cam"], cfg.get("fonte", "Arial"),
                          None if titulo_fixo else 4.0)

        hashtags = " ".join(m.get("hashtags", []))
        link = fonte_info["fonte"] if fonte_info["eh_url"] else os.path.basename(fonte_info["fonte"])
        with open(os.path.join(saida, base + ".txt"), "w", encoding="utf-8") as f:
            f.write(f"TITULO: {m.get('titulo', '')}\n\n")
            f.write(f"LEGENDA DO POST:\n{m.get('post', '')}\n{hashtags}\n\n")
            f.write(f"Categoria: {m.get('categoria', '')} | Nota: {m.get('nota')}\n")
            f.write(f"Original: {link} em {tempo_hms(m['inicio'])}\n")
            if m.get("motivo"):
                f.write(f"Por que: {m['motivo']}\n")
        feitos.append(destino)
        log(f"   -> {destino}")
    log(f"{len(feitos)} clipes prontos em {saida}")
    return feitos
