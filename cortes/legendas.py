"""Gera o arquivo de legenda .ass: titulo em caixa branca + legenda palavra por palavra."""

LARG, ALT = 1080, 1920

CAB = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Titulo,{fonte},56,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,16,0,5,90,90,0,1
Style: Legenda,{fonte},80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,7,3,5,70,70,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

AMARELO = "&H0000FFFF&"  # formato BGR do ASS
BRANCO = "&H00FFFFFF&"


def _t(seg: float) -> str:
    seg = max(seg, 0)
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _limpa(txt: str) -> str:
    return txt.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _quebrar(txt: str, max_chars: int = 26) -> str:
    """Quebra o titulo em linhas curtas para caber na caixa."""
    linhas, atual = [], ""
    for p in txt.split():
        if atual and len(atual) + 1 + len(p) > max_chars:
            linhas.append(atual)
            atual = p
        else:
            atual = f"{atual} {p}".strip()
    if atual:
        linhas.append(atual)
    return "\\N".join(linhas)


def agrupar(palavras: list[dict], max_palavras: int = 3, max_pausa: float = 0.6) -> list[list[dict]]:
    grupos, atual = [], []
    for w in palavras:
        if atual and (len(atual) >= max_palavras or w["ini"] - atual[-1]["fim"] > max_pausa
                      or atual[-1]["p"][-1:] in ".?!,"):
            grupos.append(atual)
            atual = []
        atual.append(w)
    if atual:
        grupos.append(atual)
    return grupos


def gerar_ass(palavras: list[dict], titulo: str | None, y_titulo: int, y_legenda: int,
              duracao: float, fonte: str = "Arial", titulo_ate: float | None = None) -> str:
    """palavras: [{ini, fim, p}] com tempos relativos ao inicio do clipe."""
    linhas = [CAB.format(fonte=fonte)]
    if titulo:
        fim = duracao if titulo_ate is None else min(titulo_ate, duracao)
        linhas.append(
            f"Dialogue: 2,{_t(0)},{_t(fim)},Titulo,,0,0,0,,{{\\pos({LARG // 2},{y_titulo})}}{_quebrar(_limpa(titulo))}"
        )
    for grupo in agrupar(palavras):
        textos = [_limpa(w["p"]).upper().strip(",.") for w in grupo]
        for i, w in enumerate(grupo):
            ini = w["ini"]
            fim = grupo[i + 1]["ini"] if i + 1 < len(grupo) else max(w["fim"], w["ini"] + 0.25)
            partes = []
            for j, tx in enumerate(textos):
                if j == i:
                    partes.append(f"{{\\c{AMARELO}}}{tx}{{\\c{BRANCO}}}")
                else:
                    partes.append(tx)
            pop = "{\\fscx108\\fscy108\\t(0,90,\\fscx100\\fscy100)}" if i == 0 else ""
            linhas.append(
                f"Dialogue: 1,{_t(ini)},{_t(fim)},Legenda,,0,0,0,,{{\\pos({LARG // 2},{y_legenda})}}{pop}{' '.join(partes)}"
            )
    return "\n".join(linhas) + "\n"
