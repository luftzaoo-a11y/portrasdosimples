import json
import os
import re
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_TRABALHO = os.path.join(RAIZ, "trabalho")
PASTA_CLIPES = os.path.join(RAIZ, "clipes")
ARQ_LAYOUTS = os.path.join(RAIZ, "layouts.json")
ARQ_STREAMERS = os.path.join(RAIZ, "streamers.txt")


def layout(streamer: str | None) -> dict:
    """Configuracao do streamer misturada com a padrao."""
    try:
        with open(ARQ_LAYOUTS, encoding="utf-8") as f:
            dados = json.load(f)
    except FileNotFoundError:
        dados = {}
    cfg = {"facecam": None, "jogo": None, "proporcao_cam": 0.4, "idioma": "pt", "fonte": "Arial"}
    cfg.update(dados.get("padrao", {}))
    if streamer:
        chave = next((k for k in dados if k.lower() == streamer.lower()), None)
        if chave:
            cfg.update(dados[chave])
    return cfg


def slug(texto: str, limite: int = 50) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:limite].strip("-") or "live"


def ler_json(caminho: str, padrao=None):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return padrao


def salvar_json(caminho: str, dados) -> None:
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
