"""Acha a camera do streamer (o quadradinho com o rosto) usando o detector YuNet do OpenCV."""
import os
import urllib.request

import numpy as np

from .util import log

URL_YUNET = ("https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
             "face_detection_yunet/face_detection_yunet_2023mar.onnx")
PASTA_MODELOS = os.path.join(os.path.expanduser("~"), ".cortes-gta", "modelos")
ARQ_YUNET = os.path.join(PASTA_MODELOS, "yunet.onnx")


def baixar_yunet() -> str:
    if os.path.exists(ARQ_YUNET) and os.path.getsize(ARQ_YUNET) > 100_000:
        return ARQ_YUNET
    os.makedirs(PASTA_MODELOS, exist_ok=True)
    log("Baixando detector de rosto (YuNet, 0.2 MB)...")
    urllib.request.urlretrieve(URL_YUNET, ARQ_YUNET)
    return ARQ_YUNET


def _rostos(frame, detector) -> list[tuple[float, float, float, float, float]]:
    """Rostos no quadro como (x, y, l, a, confianca) em fracao da tela."""
    h, w = frame.shape[:2]
    escala = 960 / w if w > 960 else 1.0
    import cv2

    img = cv2.resize(frame, (int(w * escala), int(h * escala))) if escala != 1.0 else frame
    detector.setInputSize((img.shape[1], img.shape[0]))
    _, faces = detector.detect(img)
    out = []
    if faces is not None:
        for f in faces:
            x, y, fw, fh, conf = f[0], f[1], f[2], f[3], f[14]
            out.append((x / img.shape[1], y / img.shape[0], fw / img.shape[1], fh / img.shape[0], float(conf)))
    return out


def detectar(video: str, inicio: float = 0.0, duracao: float | None = None, amostras: int = 16,
             proporcao: float = 1080 / 768) -> list[float] | None:
    """Retorna [x, y, l, a] (fracoes) da regiao da camera, ou None se nao achar um rosto fixo.

    'proporcao' = largura/altura do painel de cima do video final, para recortar sem distorcer.
    """
    import cv2

    detector = cv2.FaceDetectorYN.create(baixar_yunet(), "", (320, 320), 0.75, 0.3, 50)
    cap = cv2.VideoCapture(video)
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1)
    if duracao is None:
        duracao = max(total - inicio, 1)
    deteccoes: list[list] = []
    W = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920
    H = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080
    for i in range(amostras):
        t = inicio + duracao * (i + 0.5) / amostras
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if ok:
            deteccoes.append(_rostos(frame, detector))
    cap.release()
    quadros = len(deteccoes)
    if quadros == 0:
        return None

    # A camera fica parada no mesmo lugar: escolhe o rosto que aparece na mesma posicao em mais quadros.
    # (rostos de NPC do jogo mudam de lugar o tempo todo)
    todos = [r for q in deteccoes for r in q]
    melhor, apoio_melhor = None, 0
    for r in todos:
        cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
        grupo = []
        for q in deteccoes:
            perto = [s for s in q if abs(s[0] + s[2] / 2 - cx) < 0.06 and abs(s[1] + s[3] / 2 - cy) < 0.08
                     and 0.6 < s[3] / max(r[3], 1e-6) < 1.6]
            if perto:
                grupo.append(max(perto, key=lambda s: s[4]))
        if len(grupo) > apoio_melhor:
            melhor, apoio_melhor = grupo, len(grupo)
    if not melhor or apoio_melhor < max(3, int(quadros * 0.35)):
        return None

    fx, fy, fw, fh = (float(np.median([g[k] for g in melhor])) for k in range(4))
    # converte para pixels para manter a proporcao certa
    cx, cy = (fx + fw / 2) * W, (fy + fh / 2) * H
    alt = fh * H * 3.0  # pega cabeca, ombros e um pouco do fundo
    larg = alt * proporcao
    if larg > W * 0.6:  # rosto muito grande (camera ocupa muita tela)
        larg = W * 0.6
        alt = larg / proporcao
    cy += fh * H * 0.35  # desce um pouco para enquadrar ombros
    x = min(max(cx - larg / 2, 0), W - larg)
    y = min(max(cy - alt / 2, 0), H - alt)
    return [round(x / W, 4), round(y / H, 4), round(larg / W, 4), round(alt / H, 4)]


def salvar_previa(video: str, tempo: float, regiao: list[float] | None, destino: str) -> None:
    """Salva uma imagem do video com a regiao da camera marcada (para conferir)."""
    import cv2

    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_MSEC, tempo * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return
    h, w = frame.shape[:2]
    for i in range(1, 10):  # grade de 10% para ajudar a ajustar na mao
        cv2.line(frame, (int(w * i / 10), 0), (int(w * i / 10), h), (90, 90, 90), 1)
        cv2.line(frame, (0, int(h * i / 10)), (w, int(h * i / 10)), (90, 90, 90), 1)
        cv2.putText(frame, f"{i / 10:.1f}", (int(w * i / 10) + 3, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, f"{i / 10:.1f}", (3, int(h * i / 10) - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    if regiao:
        x, y, rw, rh = regiao
        cv2.rectangle(frame, (int(x * w), int(y * h)), (int((x + rw) * w), int((y + rh) * h)), (0, 255, 255), 4)
    cv2.imwrite(destino, frame)
