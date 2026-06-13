# -*- coding: utf-8 -*-
"""
CONTROLE DO PC POR GESTOS
Detecta gestos da mao via webcam e executa acoes no PC.

Gestos disponiveis:
  2 dedos (paz)         -> Play / Pause midia
  1 dedo (indicador)    -> Proxima faixa
  3 dedos               -> Faixa anterior
  Polegar para cima     -> Volume +
  Polegar para baixo    -> Volume -
  Punho fechado         -> Mute / Unmute
  Mao aberta (5 dedos)  -> Print Screen
  Pinca (polegar+index) -> Bloquear tela

Pressione 'Q' ou ESC para sair.
"""

import cv2
import time
import threading
import math
import os
import sys
import ctypes
import datetime
import urllib.request

# ── Imports opcionais com fallback ──────────────────────────
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    print("[AVISO] pyautogui nao instalado - acoes de teclado desabilitadas.")

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False
    print("[AVISO] pycaw/comtypes nao instalado - controle de volume desabilitado.")

# MediaPipe Tasks API
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker,
    HandLandmarkerOptions,
    RunningMode,
)


# ════════════════════════════════════════════════════════════════
#  DOWNLOAD DO MODELO
# ════════════════════════════════════════════════════════════════
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
# Usar pasta temp para evitar problemas com acentos no caminho
MODEL_DIR = os.path.join(os.environ.get("TEMP", os.environ.get("TMP", "C:\\Temp")), "gesture_ctrl")
MODEL_PATH = os.path.join(MODEL_DIR, "hand_landmarker.task")


def baixar_modelo():
    """Baixa o modelo se nao existir localmente."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    if os.path.exists(MODEL_PATH):
        return
    print("[INFO] Baixando modelo de deteccao de maos...")
    print(f"  URL: {MODEL_URL}")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[OK] Modelo baixado com sucesso!")
    except Exception as e:
        print(f"[ERRO] Falha ao baixar modelo: {e}")
        sys.exit(1)


# ════════════════════════════════════════════════════════════════
#  FEEDBACK SONORO
# ════════════════════════════════════════════════════════════════
class SoundFeedback:
    """Gera beeps em threads separadas para nao travar o video."""

    @staticmethod
    def _beep(freq, duration_ms):
        if HAS_WINSOUND:
            try:
                winsound.Beep(freq, duration_ms)
            except Exception:
                pass

    @staticmethod
    def play(sound_name):
        """Toca um som associado a uma acao."""
        sounds = {
            'play_pause':  lambda: SoundFeedback._beep(800, 150),
            'next':        lambda: SoundFeedback._beep(1000, 100),
            'prev':        lambda: SoundFeedback._beep(600, 100),
            'volume_up':   lambda: (SoundFeedback._beep(700, 80), SoundFeedback._beep(900, 80)),
            'volume_down': lambda: (SoundFeedback._beep(900, 80), SoundFeedback._beep(700, 80)),
            'mute':        lambda: (SoundFeedback._beep(500, 100), time.sleep(0.05), SoundFeedback._beep(500, 100)),
            'screenshot':  lambda: (SoundFeedback._beep(1200, 60), SoundFeedback._beep(1500, 60), SoundFeedback._beep(1800, 80)),
            'lock':        lambda: (SoundFeedback._beep(400, 200), SoundFeedback._beep(300, 300)),
            'startup':     lambda: (SoundFeedback._beep(523, 100), SoundFeedback._beep(659, 100), SoundFeedback._beep(784, 150)),
            'shutdown':    lambda: (SoundFeedback._beep(784, 100), SoundFeedback._beep(659, 100), SoundFeedback._beep(523, 150)),
        }
        fn = sounds.get(sound_name)
        if fn:
            t = threading.Thread(target=fn, daemon=True)
            t.start()


# ════════════════════════════════════════════════════════════════
#  CONTROLADOR DO PC
# ════════════════════════════════════════════════════════════════
class PCController:
    """Executa acoes no Windows."""

    def __init__(self):
        self.volume_interface = None
        self.is_muted = False
        self._init_volume()

    def _init_volume(self):
        if not HAS_PYCAW:
            return
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volume_interface = cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as e:
            print(f"[AVISO] Nao foi possivel inicializar controle de volume: {e}")

    def get_volume(self):
        """Retorna volume atual de 0 a 100."""
        if self.volume_interface:
            try:
                vol = self.volume_interface.GetMasterVolumeLevelScalar()
                return int(vol * 100)
            except Exception:
                return 50
        return 50

    def set_volume(self, level):
        """Define volume (0-100)."""
        if self.volume_interface:
            try:
                level = max(0, min(100, level))
                self.volume_interface.SetMasterVolumeLevelScalar(level / 100.0, None)
            except Exception:
                pass

    def volume_up(self):
        vol = self.get_volume()
        new_vol = min(100, vol + 10)
        self.set_volume(new_vol)
        SoundFeedback.play('volume_up')
        return new_vol

    def volume_down(self):
        vol = self.get_volume()
        new_vol = max(0, vol - 10)
        self.set_volume(new_vol)
        SoundFeedback.play('volume_down')
        return new_vol

    def toggle_mute(self):
        if self.volume_interface:
            try:
                self.is_muted = not self.is_muted
                self.volume_interface.SetMute(self.is_muted, None)
                SoundFeedback.play('mute')
                return self.is_muted
            except Exception:
                pass
        return False

    def play_pause(self):
        if HAS_PYAUTOGUI:
            try:
                pyautogui.press('playpause')
                SoundFeedback.play('play_pause')
            except Exception:
                pass

    def next_track(self):
        if HAS_PYAUTOGUI:
            try:
                pyautogui.press('nexttrack')
                SoundFeedback.play('next')
            except Exception:
                pass

    def prev_track(self):
        if HAS_PYAUTOGUI:
            try:
                pyautogui.press('prevtrack')
                SoundFeedback.play('prev')
            except Exception:
                pass

    def screenshot(self):
        if HAS_PYAUTOGUI:
            try:
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(desktop, f"screenshot_{ts}.png")
                img = pyautogui.screenshot()
                img.save(path)
                SoundFeedback.play('screenshot')
                return path
            except Exception as e:
                print(f"[ERRO] Screenshot: {e}")
        return None

    def lock_screen(self):
        try:
            SoundFeedback.play('lock')
            time.sleep(0.5)
            ctypes.windll.user32.LockWorkStation()
        except Exception as e:
            print(f"[ERRO] Lock: {e}")


# ════════════════════════════════════════════════════════════════
#  DETECTOR DE GESTOS (MediaPipe Tasks API)
# ════════════════════════════════════════════════════════════════
class GestureDetector:
    """Usa MediaPipe HandLandmarker (Tasks API) para detectar e classificar gestos."""

    # Nomes dos gestos
    GESTO_NENHUM        = "nenhum"
    GESTO_PUNHO         = "punho"
    GESTO_INDICADOR     = "indicador"
    GESTO_PAZ           = "paz"
    GESTO_TRES          = "tres_dedos"
    GESTO_MAO_ABERTA    = "mao_aberta"
    GESTO_POLEGAR_CIMA  = "polegar_cima"
    GESTO_POLEGAR_BAIXO = "polegar_baixo"
    GESTO_PINCA         = "pinca"

    def __init__(self):
        baixar_modelo()

        # Resultados compartilhados via callback
        self._latest_result = None
        self._result_lock = threading.Lock()

        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=RunningMode.LIVE_STREAM,
            num_hands=1,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6,
            result_callback=self._on_result,
        )
        self.landmarker = HandLandmarker.create_from_options(options)

    def _on_result(self, result, output_image, timestamp_ms):
        """Callback do MediaPipe - recebe resultados assincronamente."""
        with self._result_lock:
            self._latest_result = result

    def classify(self, landmarks, handedness="Right"):
        """Classifica o gesto baseado na POSE da mao (invariante a rotacao)."""
        if not landmarks:
            return self.GESTO_NENHUM, 0

        lm = landmarks

        # ══════════════════════════════════════════════
        # HELPER: distancia entre dois landmarks
        # ══════════════════════════════════════════════
        def dist(a, b):
            return math.hypot(lm[a].x - lm[b].x, lm[a].y - lm[b].y)

        # ══════════════════════════════════════════════
        # 1) Estado de cada dedo — INVARIANTE A ROTACAO
        #    Um dedo esta ESTENDIDO se sua ponta (TIP) esta
        #    MAIS LONGE do punho (landmark 0) do que sua
        #    junta PIP. Quando o dedo esta fechado, a ponta
        #    volta pra palma, ficando mais perto do punho.
        # ══════════════════════════════════════════════
        index_up  = dist(8, 0)  > dist(6, 0)   # TIP vs PIP do indicador
        medio_up  = dist(12, 0) > dist(10, 0)   # TIP vs PIP do medio
        anelar_up = dist(16, 0) > dist(14, 0)   # TIP vs PIP do anelar
        minimo_up = dist(20, 0) > dist(18, 0)   # TIP vs PIP do minimo

        other_fingers_count = sum([index_up, medio_up, anelar_up, minimo_up])

        # ══════════════════════════════════════════════
        # 2) Analise detalhada do POLEGAR
        # ══════════════════════════════════════════════
        thumb_tip = lm[4]
        thumb_ip  = lm[3]
        thumb_mcp = lm[2]
        wrist     = lm[0]
        mid_mcp   = lm[9]   # base do dedo medio (referencia do eixo da mao)

        # Eixo principal da mao: do punho ate a base do medio
        hand_dx = mid_mcp.x - wrist.x
        hand_dy = mid_mcp.y - wrist.y
        hand_len = math.hypot(hand_dx, hand_dy) or 0.001

        # Direcao normalizada do eixo da mao
        hux = hand_dx / hand_len
        huy = hand_dy / hand_len

        # Vetor perpendicular ao eixo da mao (aponta pro lado do polegar)
        # Perpendicular = rotacao 90 graus
        perp_x = -huy
        perp_y = hux

        # Vetor do MCP do polegar ate a ponta
        thumb_dx = thumb_tip.x - thumb_mcp.x
        thumb_dy = thumb_tip.y - thumb_mcp.y
        thumb_len = math.hypot(thumb_dx, thumb_dy) or 0.001

        # Projecao do polegar no eixo da mao (positivo = mesma direcao dos dedos)
        proj_along = thumb_dx * hux + thumb_dy * huy
        # Projecao do polegar na perpendicular (positivo = pro lado do polegar)
        proj_perp = thumb_dx * perp_x + thumb_dy * perp_y

        # Polegar esta estendido? (ponta longe da base)
        thumb_extended = thumb_len > hand_len * 0.15

        # Direcao do polegar relativa ao eixo da mao:
        # "up" = polegar aponta na direcao OPOSTA aos dedos (contra o eixo)
        # "down" = polegar aponta na MESMA direcao dos dedos
        # Usamos proj_along: negativo = contra os dedos = "cima", positivo = "baixo"
        thumb_points_up = False
        thumb_points_down = False

        if thumb_extended and other_fingers_count == 0:
            # Calcular angulo do polegar vs eixo da mao
            ratio = abs(proj_along) / (abs(proj_perp) + 0.001)
            # Se a projecao ao longo do eixo e significativa
            if ratio > 0.3:
                if proj_along < -hand_len * 0.05:
                    thumb_points_up = True
                elif proj_along > hand_len * 0.05:
                    thumb_points_down = True
            # Fallback: usar posicao Y absoluta
            if not thumb_points_up and not thumb_points_down:
                thumb_vert = thumb_mcp.y - thumb_tip.y
                if thumb_vert > 0.04:
                    thumb_points_up = True
                elif thumb_vert < -0.04:
                    thumb_points_down = True

        # Polegar "ativo" (estendido de alguma forma)
        thumb_active = thumb_extended

        # Total de dedos
        fingers_up = other_fingers_count + (1 if thumb_active else 0)

        # ══════════════════════════════════════════════
        # 3) PINCA: polegar e indicador muito proximos, outros fechados
        # ══════════════════════════════════════════════
        pinch_dist = math.hypot(thumb_tip.x - lm[8].x, thumb_tip.y - lm[8].y)
        if pinch_dist < 0.05 and not medio_up and not anelar_up and not minimo_up:
            return self.GESTO_PINCA, 0

        # ══════════════════════════════════════════════
        # 4) PRIORIDADE: Gestos do POLEGAR (outros dedos fechados)
        # ══════════════════════════════════════════════
        if other_fingers_count == 0:
            if thumb_points_up:
                return self.GESTO_POLEGAR_CIMA, 1
            if thumb_points_down:
                return self.GESTO_POLEGAR_BAIXO, 1
            # Punho: tudo fechado
            return self.GESTO_PUNHO, 0

        # ══════════════════════════════════════════════
        # 5) Gestos por COMBINACAO de dedos
        # ══════════════════════════════════════════════

        # 1 dedo: apenas indicador levantado
        if index_up and not medio_up and not anelar_up and not minimo_up:
            return self.GESTO_INDICADOR, 1

        # 2 dedos (paz): indicador + medio
        if index_up and medio_up and not anelar_up and not minimo_up:
            return self.GESTO_PAZ, 2

        # 3 dedos: indicador + medio + anelar
        if index_up and medio_up and anelar_up and not minimo_up:
            return self.GESTO_TRES, 3

        # Mao aberta: todos os 4 dedos + polegar
        if other_fingers_count == 4 and thumb_active:
            return self.GESTO_MAO_ABERTA, 5

        return self.GESTO_NENHUM, fingers_up

    def detect(self, frame_rgb, timestamp_ms):
        """Envia frame para deteccao e retorna ultimo resultado disponivel."""
        # Converter para mp.Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        try:
            self.landmarker.detect_async(mp_image, timestamp_ms)
        except Exception:
            pass

        # Ler ultimo resultado
        with self._result_lock:
            result = self._latest_result

        if result and result.hand_landmarks and result.handedness:
            landmarks = result.hand_landmarks[0]
            handedness = result.handedness[0][0].category_name
            gesto, fingers = self.classify(landmarks, handedness)
            return landmarks, handedness, gesto, fingers

        return None, None, self.GESTO_NENHUM, 0

    def draw_landmarks(self, frame, landmarks):
        """Desenha os landmarks da mao no frame usando OpenCV."""
        if not landmarks:
            return

        h, w = frame.shape[:2]

        # Conexoes dos dedos (MediaPipe hand connections)
        CONNECTIONS = [
            (0, 1), (1, 2), (2, 3), (3, 4),       # Polegar
            (0, 5), (5, 6), (6, 7), (7, 8),       # Indicador
            (0, 9), (9, 10), (10, 11), (11, 12),   # Medio
            (0, 13), (13, 14), (14, 15), (15, 16), # Anelar
            (0, 17), (17, 18), (18, 19), (19, 20), # Minimo
            (5, 9), (9, 13), (13, 17),             # Palma
        ]

        # Desenhar conexoes
        for start, end in CONNECTIONS:
            x1, y1 = int(landmarks[start].x * w), int(landmarks[start].y * h)
            x2, y2 = int(landmarks[end].x * w), int(landmarks[end].y * h)
            cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 128), 2, cv2.LINE_AA)

        # Desenhar pontos
        for i, lm in enumerate(landmarks):
            x, y = int(lm.x * w), int(lm.y * h)
            cor = (0, 0, 255) if i in [4, 8, 12, 16, 20] else (255, 128, 0)
            cv2.circle(frame, (x, y), 5, cor, -1, cv2.LINE_AA)
            cv2.circle(frame, (x, y), 5, (255, 255, 255), 1, cv2.LINE_AA)

    def close(self):
        """Libera recursos do landmarker."""
        try:
            self.landmarker.close()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════
#  OVERLAY UI
# ════════════════════════════════════════════════════════════════
class OverlayUI:
    """Desenha informacoes visuais sobre o frame da camera."""

    COR_FUNDO       = (30, 30, 30)
    COR_TEXTO       = (255, 255, 255)
    COR_DESTAQUE    = (0, 220, 120)
    COR_ALERTA      = (0, 100, 255)
    COR_VOLUME_BAR  = (255, 180, 0)
    COR_VOLUME_BG   = (60, 60, 60)
    COR_ACAO        = (0, 255, 255)
    COR_PAINEL      = (40, 35, 50)

    GESTO_INFO = {
        "nenhum":        {"icone": "...",  "nome": "Aguardando...",       "cor": (150, 150, 150)},
        "punho":         {"icone": "[0]",  "nome": "MUTE / UNMUTE",      "cor": (0, 0, 255)},
        "indicador":     {"icone": "[1]",  "nome": "PROXIMA FAIXA",      "cor": (255, 180, 0)},
        "paz":           {"icone": "[2]",  "nome": "PLAY / PAUSE",       "cor": (0, 220, 120)},
        "tres_dedos":    {"icone": "[3]",  "nome": "FAIXA ANTERIOR",     "cor": (200, 100, 255)},
        "mao_aberta":    {"icone": "[5]",  "nome": "SCREENSHOT",         "cor": (0, 200, 255)},
        "polegar_cima":  {"icone": "[+]",  "nome": "VOLUME +",           "cor": (100, 255, 100)},
        "polegar_baixo": {"icone": "[-]",  "nome": "VOLUME -",           "cor": (100, 100, 255)},
        "pinca":         {"icone": "[P]",  "nome": "BLOQUEAR TELA",      "cor": (0, 100, 255)},
    }

    def __init__(self):
        self.flash_alpha = 0.0
        self.flash_text = ""
        self.flash_time = 0

    def trigger_flash(self, text):
        self.flash_text = text
        self.flash_alpha = 1.0
        self.flash_time = time.time()

    def _draw_rounded_rect(self, frame, x, y, w, h, color, alpha=0.7):
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    def draw(self, frame, gesto, fingers_up, volume, is_muted):
        h, w = frame.shape[:2]
        info = self.GESTO_INFO.get(gesto, self.GESTO_INFO["nenhum"])

        # Painel superior
        panel_h = 70
        self._draw_rounded_rect(frame, 0, 0, w, panel_h, self.COR_PAINEL, 0.65)

        cv2.putText(frame, info["nome"], (15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, info["cor"], 2, cv2.LINE_AA)

        dedos_text = f"Dedos: {fingers_up}"
        cv2.putText(frame, dedos_text, (15, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)

        status = "MAO DETECTADA" if gesto != "nenhum" else "SEM MAO"
        status_color = self.COR_DESTAQUE if gesto != "nenhum" else (100, 100, 100)
        cv2.circle(frame, (w - 25, 18), 8, status_color, -1)
        cv2.putText(frame, status, (w - 220, 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 1, cv2.LINE_AA)

        # Barra de volume
        bar_x = w - 40
        bar_y_top = panel_h + 20
        bar_h = h - panel_h - 120
        bar_w = 20

        self._draw_rounded_rect(frame, bar_x - 2, bar_y_top - 2, bar_w + 4, bar_h + 4,
                                self.COR_VOLUME_BG, 0.5)

        fill_h = int(bar_h * (volume / 100))
        fill_y = bar_y_top + (bar_h - fill_h)
        cor_vol = (0, 0, 200) if is_muted else self.COR_VOLUME_BAR
        if fill_h > 0:
            cv2.rectangle(frame, (bar_x, fill_y), (bar_x + bar_w, bar_y_top + bar_h),
                          cor_vol, -1)

        vol_text = "MUDO" if is_muted else f"{volume}%"
        cv2.putText(frame, vol_text, (bar_x - 15, bar_y_top + bar_h + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COR_TEXTO, 1, cv2.LINE_AA)

        cv2.putText(frame, "VOL", (bar_x - 5, bar_y_top - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1, cv2.LINE_AA)

        # Legenda de gestos
        legend_h = 75
        self._draw_rounded_rect(frame, 0, h - legend_h, w, legend_h, self.COR_PAINEL, 0.7)

        gestos_legenda = [
            ("Punho=Mute", (150, 150, 255)),
            ("1d=Next", (255, 200, 100)),
            ("2d=Play", (100, 240, 150)),
            ("3d=Prev", (220, 150, 255)),
            ("5d=Print", (100, 220, 255)),
            ("Up=Vol+", (150, 255, 150)),
            ("Dn=Vol-", (150, 150, 255)),
            ("Pinch=Lock", (100, 150, 255)),
        ]

        y_line1 = h - legend_h + 25
        y_line2 = h - legend_h + 55

        for i, (txt, cor) in enumerate(gestos_legenda):
            y = y_line1 if i < 4 else y_line2
            x = 10 + (i % 4) * (w // 4)
            cv2.putText(frame, txt, (x, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, cor, 1, cv2.LINE_AA)

        # Flash de confirmacao
        if self.flash_alpha > 0.05:
            elapsed = time.time() - self.flash_time
            self.flash_alpha = max(0, 1.0 - elapsed * 1.5)

            overlay = frame.copy()
            cx, cy = w // 2, h // 2
            cv2.rectangle(overlay, (cx - 200, cy - 40), (cx + 200, cy + 40),
                          self.COR_ACAO, -1)
            cv2.addWeighted(overlay, self.flash_alpha * 0.6, frame,
                            1 - self.flash_alpha * 0.6, 0, frame)

            cv2.putText(frame, self.flash_text, (cx - 180, cy + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (0, int(255 * self.flash_alpha), int(255 * self.flash_alpha)),
                        2, cv2.LINE_AA)

        return frame


# ════════════════════════════════════════════════════════════════
#  APLICACAO PRINCIPAL
# ════════════════════════════════════════════════════════════════
class GestureApp:
    """Aplicacao principal que integra todos os modulos."""

    COOLDOWN = 1.8

    def __init__(self):
        print("\n" + "=" * 60)
        print("  CONTROLE DO PC POR GESTOS")
        print("  Pressione Q ou ESC para sair")
        print("=" * 60 + "\n")

        self.detector = GestureDetector()
        self.controller = PCController()
        self.ui = OverlayUI()

        self.ultimo_gesto = GestureDetector.GESTO_NENHUM
        self.ultimo_tempo = {}
        self.gesto_confirmado = GestureDetector.GESTO_NENHUM
        self.frames_gesto = 0
        self.FRAMES_PARA_CONFIRMAR = 8
        self.frame_count = 0

    def _pode_executar(self, gesto):
        agora = time.time()
        ultimo = self.ultimo_tempo.get(gesto, 0)
        if agora - ultimo >= self.COOLDOWN:
            self.ultimo_tempo[gesto] = agora
            return True
        return False

    def _executar_acao(self, gesto):
        if not self._pode_executar(gesto):
            return

        if gesto == GestureDetector.GESTO_PAZ:
            self.controller.play_pause()
            self.ui.trigger_flash(">> PLAY / PAUSE <<")

        elif gesto == GestureDetector.GESTO_INDICADOR:
            self.controller.next_track()
            self.ui.trigger_flash(">> PROXIMA FAIXA >>")

        elif gesto == GestureDetector.GESTO_TRES:
            self.controller.prev_track()
            self.ui.trigger_flash("<< FAIXA ANTERIOR <<")

        elif gesto == GestureDetector.GESTO_POLEGAR_CIMA:
            new_vol = self.controller.volume_up()
            self.ui.trigger_flash(f"VOLUME + ({new_vol}%)")

        elif gesto == GestureDetector.GESTO_POLEGAR_BAIXO:
            new_vol = self.controller.volume_down()
            self.ui.trigger_flash(f"VOLUME - ({new_vol}%)")

        elif gesto == GestureDetector.GESTO_PUNHO:
            is_muted = self.controller.toggle_mute()
            txt = "MUDO ATIVADO" if is_muted else "MUDO DESATIVADO"
            self.ui.trigger_flash(txt)

        elif gesto == GestureDetector.GESTO_MAO_ABERTA:
            path = self.controller.screenshot()
            if path:
                self.ui.trigger_flash("SCREENSHOT SALVO!")
            else:
                self.ui.trigger_flash("ERRO AO SALVAR SCREENSHOT")

        elif gesto == GestureDetector.GESTO_PINCA:
            self.ui.trigger_flash("BLOQUEANDO TELA...")
            self.controller.lock_screen()

    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[ERRO] Nao foi possivel abrir a webcam!")
            print("  -> Verifique se a camera esta conectada e nao esta em uso.")
            SoundFeedback.play('shutdown')
            input("Pressione Enter para sair...")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)

        SoundFeedback.play('startup')
        print("[OK] Webcam aberta com sucesso!")
        print("[OK] Mostre a mao para a camera...\n")

        window_name = "Controle por Gestos - Pressione Q para sair"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 960, 540)

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("[ERRO] Falha ao capturar frame da webcam.")
                    break

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Timestamp monotonicamente crescente
                self.frame_count += 1
                timestamp_ms = int(time.time() * 1000)

                # Detectar mao e gesto
                hand_lm, handedness, gesto, fingers = self.detector.detect(rgb, timestamp_ms)

                # Desenhar landmarks
                if hand_lm:
                    self.detector.draw_landmarks(frame, hand_lm)

                # Sistema de confirmacao (anti-falso positivo)
                if gesto != GestureDetector.GESTO_NENHUM:
                    if gesto == self.ultimo_gesto:
                        self.frames_gesto += 1
                    else:
                        self.frames_gesto = 1
                        self.ultimo_gesto = gesto

                    if self.frames_gesto == self.FRAMES_PARA_CONFIRMAR:
                        self.gesto_confirmado = gesto
                        self._executar_acao(gesto)
                else:
                    self.frames_gesto = 0
                    self.ultimo_gesto = GestureDetector.GESTO_NENHUM
                    self.gesto_confirmado = GestureDetector.GESTO_NENHUM

                # Desenhar overlay
                volume = self.controller.get_volume()
                is_muted = self.controller.is_muted
                gesto_display = self.gesto_confirmado if self.gesto_confirmado != GestureDetector.GESTO_NENHUM else gesto
                frame = self.ui.draw(frame, gesto_display, fingers, volume, is_muted)

                # Barra de progresso de confirmacao
                if 0 < self.frames_gesto < self.FRAMES_PARA_CONFIRMAR:
                    h_frame, w_frame = frame.shape[:2]
                    progress = self.frames_gesto / self.FRAMES_PARA_CONFIRMAR
                    bar_w = int(w_frame * 0.5 * progress)
                    bar_x = (w_frame - int(w_frame * 0.5)) // 2
                    bar_y = 72
                    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 6),
                                  (0, 220, 120), -1)
                    cv2.rectangle(frame, (bar_x, bar_y),
                                  (bar_x + int(w_frame * 0.5), bar_y + 6),
                                  (100, 100, 100), 1)

                cv2.imshow(window_name, frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == ord('Q') or key == 27:
                    print("\n[INFO] Encerrando...")
                    SoundFeedback.play('shutdown')
                    time.sleep(0.5)
                    break

        except KeyboardInterrupt:
            print("\n[INFO] Interrompido pelo usuario.")
        except Exception as e:
            print(f"\n[ERRO] Erro inesperado: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.detector.close()
            cap.release()
            cv2.destroyAllWindows()
            print("[OK] Programa encerrado.")


# ════════════════════════════════════════════════════════════════
#  PONTO DE ENTRADA
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = GestureApp()
    app.run()
