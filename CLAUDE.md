# Clipador GTA (cortes automaticos de lives)

Projeto do usuario: transformar lives de GTA (Twitch/Kick/YouTube) em clipes verticais 9:16 prontos para TikTok, Shorts e Reels. Ele responde em portugues (pt-BR). Os streamers clipados autorizam (campanhas de clipadores).

## Referencia de estilo (video "How to Make Money Clipping GTA 6")
- Fluxo: baixa SO o audio -> transcreve local (Whisper) -> marca gritos/surtos (volume) e picos de chat ->
  a IA (o proprio Claude Code, pela assinatura Pro, sem API) le a transcricao em blocos de 12 min e escolhe
  os momentos com nota rigorosa (descarta o que precisa de contexto ou comeca com "e... entao") ->
  baixa so os minutos escolhidos -> acha a facecam sozinho -> camera em cima (~40%), jogo embaixo ->
  titulo em caixa branca com texto preto na divisa + legenda palavra por palavra (palavra atual amarela) ->
  texto do post com hashtags.
- Exemplo do video: live de 4h09 -> 39 momentos -> 3 clipes em 13 min.

## Estado atual
- Codigo em `cortes/` (Python): `analisar` (etapa 1), `renderizar` (etapa 3), `buscar`, `calibrar`, `setup`.
- Testado na nuvem com live sintetica: picos, layout, legendas e fundo desfocado OK.
- NAO testado ainda: download real da Kick/Twitch, Whisper real em pt-BR, deteccao de rosto real (YuNet).
- Kick exige `yt-dlp[curl-cffi]` (impersonation). Ja esta no requirements.txt.

## PC do usuario
Windows, 16 GB RAM, GTX 1650 (4 GB). Usa Claude Code Pro.

## Falta fazer
1. `setup.bat` (Windows): checar/instalar Python, FFmpeg (winget Gyan.FFmpeg), Deno, criar `.venv`,
   `pip install -r requirements.txt` (+ `nvidia-cublas-cu12 nvidia-cudnn-cu12` se tiver `nvidia-smi`),
   rodar `python -m cortes setup`.
2. Skill em `.claude/skills/clipador-gta/SKILL.md` com o fluxo acima (etapa 2 = Claude le `trabalho/<id>/blocos/*.md`
   e escreve `trabalho/<id>/momentos.json`).
3. README em portugues.
4. Primeiro teste real: https://kick.com/dona/videos/01a1e689-9250-7d8c-83f9-222b005e54cc (GTA V a partir de ~2h).

## Formato do momentos.json
```json
[{"inicio": 7325, "fim": 7370, "nota": 9, "categoria": "surto",
  "titulo": "Ele NAO esperava isso 💀", "post": "texto do post", "hashtags": ["#gta", "#gtarp"],
  "motivo": "por que e bom"}]
```
