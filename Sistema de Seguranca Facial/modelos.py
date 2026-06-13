# -*- coding: utf-8 -*-
"""
DOWNLOAD DOS MODELOS ONNX (YuNet + SFace)

Baixa pra %TEMP%\\seguranca_facial (caminho SEM acento — o loader C++ do
OpenCV nao abre arquivo em caminho com acento, e a pasta do projeto tem).

Os arquivos do opencv_zoo ficam em Git LFS, entao a URL precisa ser a de
"media" (senao baixa so um ponteiro de texto). Por seguranca, tentamos
varias URLs e validamos o tamanho do que veio.
"""

import os
import sys
import urllib.request

MODEL_DIR = os.path.join(
    os.environ.get("TEMP", os.environ.get("TMP", "C:\\Temp")),
    "seguranca_facial",
)

# Detector (YuNet) e Reconhecedor (SFace).
# 'min_bytes' serve pra rejeitar ponteiro de LFS / pagina de erro.
MODELOS = {
    "yunet": {
        "arquivo": "face_detection_yunet_2023mar.onnx",
        "min_bytes": 50_000,
        "urls": [
            "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
            "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
            "https://media.githubusercontent.com/media/opencv/opencv_zoo/4.x/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        ],
    },
    "sface": {
        "arquivo": "face_recognition_sface_2021dec.onnx",
        "min_bytes": 1_000_000,
        "urls": [
            "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
            "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
            "https://media.githubusercontent.com/media/opencv/opencv_zoo/4.x/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        ],
    },
}


def _baixar_url(url, destino):
    """Baixa uma URL pra um arquivo temporario e retorna o tamanho, ou levanta."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    tmp = destino + ".parcial"
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
        tamanho = 0
        while True:
            bloco = resp.read(1024 * 256)
            if not bloco:
                break
            f.write(bloco)
            tamanho += len(bloco)
    os.replace(tmp, destino)
    return tamanho


def _garantir_modelo(chave):
    """Garante que o modelo 'chave' exista e seja valido. Retorna o caminho."""
    info = MODELOS[chave]
    destino = os.path.join(MODEL_DIR, info["arquivo"])

    # Ja existe e tem tamanho plausivel?
    if os.path.exists(destino) and os.path.getsize(destino) >= info["min_bytes"]:
        return destino

    print(f"[INFO] Baixando modelo '{chave}' ({info['arquivo']})...")
    ultimo_erro = None
    for url in info["urls"]:
        try:
            tamanho = _baixar_url(url, destino)
            if tamanho < info["min_bytes"]:
                print(f"  [AVISO] Arquivo pequeno demais ({tamanho} bytes), "
                      f"provavelmente um ponteiro LFS. Tentando outra URL...")
                continue
            print(f"  [OK] Baixado: {tamanho/1_000_000:.1f} MB")
            return destino
        except Exception as e:
            ultimo_erro = e
            print(f"  [AVISO] Falhou em {url[:60]}... ({e})")

    # Sobrou um parcial invalido? Limpa.
    if os.path.exists(destino) and os.path.getsize(destino) < info["min_bytes"]:
        try:
            os.remove(destino)
        except OSError:
            pass
    raise RuntimeError(
        f"Nao consegui baixar o modelo '{chave}'. Ultimo erro: {ultimo_erro}\n"
        f"  -> Baixe manualmente '{info['arquivo']}' e coloque em:\n     {MODEL_DIR}"
    )


def garantir_modelos():
    """Garante YuNet e SFace baixados. Retorna (caminho_yunet, caminho_sface)."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    try:
        yunet = _garantir_modelo("yunet")
        sface = _garantir_modelo("sface")
    except Exception as e:
        print(f"[ERRO] {e}")
        sys.exit(1)
    return yunet, sface


if __name__ == "__main__":
    y, s = garantir_modelos()
    print("YuNet:", y)
    print("SFace:", s)
