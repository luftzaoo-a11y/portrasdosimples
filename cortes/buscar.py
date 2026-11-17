"""Acha lives/VODs recentes de GTA: dos streamers da sua lista e os maiores ao vivo na Twitch."""
import json
import re
import time
import urllib.request

from . import config
from .util import log, tempo_hms

GQL = "https://gql.twitch.tv/gql"
CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # id publico do site da Twitch (o mesmo que o yt-dlp usa)
JOGOS = ["Grand Theft Auto VI", "Grand Theft Auto V"]
GTA = re.compile(r"gta|grand theft|\brp\b|roleplay|cidade alta|complexo", re.I)


def ler_lista() -> list[tuple[str, str]]:
    itens = []
    try:
        with open(config.ARQ_STREAMERS, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith("#"):
                    continue
                if linha.startswith("http"):
                    plat = "kick" if "kick.com" in linha else "youtube" if "youtu" in linha else "twitch"
                    nome = linha.rstrip("/").split("/")[-1]
                elif ":" in linha:
                    plat, nome = linha.split(":", 1)
                else:
                    plat, nome = "twitch", linha
                itens.append((plat.strip().lower(), nome.strip()))
    except FileNotFoundError:
        pass
    return itens


def _gql(query: str) -> dict:
    req = urllib.request.Request(GQL, data=json.dumps({"query": query}).encode(),
                                 headers={"Client-ID": CLIENT_ID, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def maiores_ao_vivo(quantidade: int = 15, so_pt: bool = True) -> list[dict]:
    """Maiores lives de GTA agora na Twitch (sem precisar de conta)."""
    out = []
    for jogo in JOGOS:
        q = ('query { game(name: "%s") { streams(first: 50, options: {sort: VIEWER_COUNT}) { edges { node { '
             'title viewersCount language broadcaster { login displayName } } } } } }') % jogo
        try:
            dados = _gql(q)
        except Exception as e:
            log(f"Nao consegui consultar a Twitch ({type(e).__name__}).")
            continue
        jogo_d = (dados.get("data") or {}).get("game") or {}
        for e in ((jogo_d.get("streams") or {}).get("edges") or []):
            n = e["node"]
            if so_pt and n.get("language") and n["language"].lower() not in ("pt", "pt-br", "pt_br"):
                continue
            login = n["broadcaster"]["login"]
            out.append({"plataforma": "twitch", "streamer": login, "titulo": n.get("title", ""),
                        "espectadores": n.get("viewersCount", 0), "jogo": jogo, "ao_vivo": True,
                        "url": f"https://www.twitch.tv/{login}"})
    out.sort(key=lambda x: -x["espectadores"])
    return out[:quantidade]


def _vods(plat: str, nome: str, limite: int = 5) -> list[dict]:
    import yt_dlp

    urls = {
        "twitch": f"https://www.twitch.tv/{nome}/videos?filter=archives&sort=time",
        "youtube": f"https://www.youtube.com/{nome if nome.startswith('@') else '@' + nome}/streams",
        "kick": f"https://kick.com/{nome}/videos",
    }
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "playlistend": limite}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(urls[plat], download=False)
    except Exception as e:
        log(f"  {plat}:{nome}: nao consegui listar os videos ({type(e).__name__})")
        return []
    out = []
    for e in (info.get("entries") or [])[:limite]:
        out.append({"plataforma": plat, "streamer": nome, "titulo": e.get("title") or "",
                    "duracao": e.get("duration"), "data": e.get("timestamp") or e.get("upload_date"),
                    "url": e.get("url") or e.get("webpage_url"), "ao_vivo": False})
    return out


def buscar(horas: int = 48, ao_vivo: bool = True) -> list[dict]:
    resultados = []
    lista = ler_lista()
    if lista:
        log(f"Olhando os VODs recentes de {len(lista)} streamers da sua lista...")
        limite_ts = time.time() - horas * 3600
        for plat, nome in lista:
            for v in _vods(plat, nome):
                ts = v["data"]
                if isinstance(ts, (int, float)) and ts < limite_ts:
                    continue
                v["gta"] = bool(GTA.search(v["titulo"]))
                resultados.append(v)
    if ao_vivo:
        log("Procurando as maiores lives de GTA em portugues agora na Twitch...")
        resultados.extend(maiores_ao_vivo())
    return resultados


def imprimir(resultados: list[dict]) -> None:
    if not resultados:
        print("Nada encontrado. Adicione streamers em streamers.txt ou tente mais tarde.")
        return
    for i, r in enumerate(resultados, 1):
        if r.get("ao_vivo"):
            extra = f"AO VIVO, {r.get('espectadores', 0)} assistindo"
        else:
            extra = f"VOD {tempo_hms(r['duracao'])}" if r.get("duracao") else "VOD"
            if not r.get("gta"):
                extra += " (titulo sem GTA)"
        print(f"{i:2d}. [{r['plataforma']}] {r['streamer']} | {extra}\n    {r['titulo'][:90]}\n    {r['url']}")
