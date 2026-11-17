"""Etapa 1: baixa o audio, transcreve e marca gritos/chat. Gera blocos de 12 min para o Claude ler."""
import os
import time

from . import config, download, sinais, transcricao
from .util import info_video, log, tempo_hms

BLOCO = 12 * 60  # segundos por bloco de leitura


def _streamer_da_url(url: str) -> str | None:
    import re

    m = re.search(r"(?:twitch\.tv|kick\.com)/(?!videos)([A-Za-z0-9_]+)", url)
    return m.group(1) if m else None


def analisar(fonte: str, streamer: str | None = None, chat: str | None = None,
             modelo: str = "base", idioma: str | None = None, sem_chat: bool = False) -> str:
    inicio_relogio = time.time()
    eh_url = download.eh_url(fonte)
    if eh_url:
        info = download.info_url(fonte)
        streamer = streamer or _streamer_da_url(fonte) or info["canal"]
        nome = info["titulo"] or "live"
    else:
        fonte = os.path.abspath(fonte)
        if not os.path.exists(fonte):
            raise SystemExit(f"Arquivo nao encontrado: {fonte}")
        info = {"titulo": os.path.splitext(os.path.basename(fonte))[0], "canal": streamer or ""}
        nome = info["titulo"]
    cfg = config.layout(streamer)
    idioma = idioma or cfg["idioma"]

    ident = f"{time.strftime('%Y%m%d')}-{config.slug(streamer or '', 20)}-{config.slug(nome, 40)}".replace("--", "-")
    pasta = os.path.join(config.PASTA_TRABALHO, ident)
    os.makedirs(pasta, exist_ok=True)
    log(f"Pasta de trabalho: {pasta}")

    # 1) audio
    audio = download.baixar_audio(fonte, pasta) if eh_url else fonte
    duracao = info_video(audio)["duracao"]
    log(f"Duracao: {tempo_hms(duracao)}")

    # 2) chat
    mensagens = []
    if chat:
        mensagens = download.carregar_chat(chat)
    elif eh_url and not sem_chat:
        arq = download.baixar_chat(fonte, os.path.join(pasta, "chat.json"))
        if arq:
            mensagens = download.carregar_chat(arq)

    # 3) volume + chat -> pontuacao
    log("Medindo o volume da live (gritos, risadas, surtos)...")
    volume = sinais.volume_por_segundo(audio)
    vchat = sinais.chat_por_segundo(mensagens, len(volume)) if mensagens else None
    s = sinais.calcular(volume, vchat)
    picos = sinais.picos(s["total"])
    log(f"{len(picos)} picos de empolgacao encontrados.")

    # 4) transcricao
    log(f"Transcrevendo com Whisper '{modelo}' (a parte mais demorada)...")
    segs = transcricao.transcrever_longo(audio, os.path.join(pasta, "transcricao.json"), modelo, idioma, duracao)

    # 5) blocos para leitura
    pasta_blocos = os.path.join(pasta, "blocos")
    os.makedirs(pasta_blocos, exist_ok=True)
    for f in os.listdir(pasta_blocos):
        os.remove(os.path.join(pasta_blocos, f))

    def marca(t0: float, t1: float) -> str:
        a = s["audio"][int(t0):max(int(t1), int(t0) + 1)]
        txt = ""
        if len(a) and a.max() >= 2.0:
            txt += f" 🔊{a.max():.1f}"
        if s["chat"] is not None:
            c = s["chat"][int(t0):max(int(t1), int(t0) + 1)]
            if len(c) and c.max() >= 2.0:
                txt += f" 💬{c.max():.1f}"
        return txt

    n_blocos = max(1, int((duracao + BLOCO - 1) // BLOCO))
    for b in range(n_blocos):
        t0, t1 = b * BLOCO, min((b + 1) * BLOCO, duracao)
        linhas = [f"# Bloco {b + 1}/{n_blocos} — {tempo_hms(t0)} a {tempo_hms(t1)}", ""]
        pk = [p for p in picos if t0 <= p < t1]
        if pk:
            linhas.append("Picos de empolgacao neste bloco: " + ", ".join(f"{p}s ({tempo_hms(p)})" for p in pk))
            linhas.append("")
        for sg in segs:
            if t0 <= sg["ini"] < t1:
                linhas.append(f"[{sg['ini']:.0f}s] {sg['texto']}{marca(sg['ini'], sg['fim'])}")
        with open(os.path.join(pasta_blocos, f"bloco_{b + 1:02d}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")

    config.salvar_json(os.path.join(pasta, "fonte.json"), {
        "fonte": fonte, "eh_url": eh_url, "titulo": info.get("titulo"), "streamer": streamer,
        "duracao": duracao, "idioma": idioma, "picos": picos,
        "chat_mensagens": len(mensagens), "blocos": n_blocos,
    })
    log(f"Pronto em {tempo_hms(time.time() - inicio_relogio)}. {n_blocos} blocos em {pasta_blocos}")
    log(f"Proximo passo: ler os blocos e escrever {os.path.join(pasta, 'momentos.json')}")
    return pasta
