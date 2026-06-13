# -*- coding: utf-8 -*-
"""
DETECCAO DE CONTEXTO

Decide quando o sistema deve se PAUSAR sozinho:
  - Audio tocando (video/musica): pico de saida do alto-falante via pycaw.
  - App em tela cheia (filme/jogo): janela em primeiro plano cobrindo o monitor.

("Deitado" sai do angulo dos olhos, calculado no reconhecimento; "camera
ocupada" e tratado no main quando a captura falha.)
"""

import time
import ctypes
from ctypes import wintypes

# ── pycaw (medicao de audio) com fallback ──
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
    HAS_PYCAW = True
except Exception:
    HAS_PYCAW = False
    print("[AVISO] pycaw indisponivel - pausa por audio desativada.")

# Pico de saida acima disso (suavizado) = tem som saindo.
LIMIAR_AUDIO = 0.02
# Audio precisa ser SUSTENTADO por isso (s) pra valer como "midia tocando".
# Assim, bipes do proprio sistema e "dings" de notificacao NAO disparam a pausa.
AUDIO_SUSTENTADO_SEG = 2.0

_user32 = ctypes.windll.user32

# Janelas nossas que NUNCA devem contar como "app em tela cheia" (o overlay e
# fullscreen; se contasse, entraria em loop: pausa -> some -> trava -> pausa...).
JANELAS_PROPRIAS = ("Seguranca Facial", "Cadastro do Rosto", "TELA PROTEGIDA")


class ContextoDetector:
    """Mede audio e tela cheia, com suavizacao pra nao ficar piscando."""

    def __init__(self, cfg):
        self.cfg = cfg
        self._meter = None
        self._audio_ema = 0.0
        self._audio_desde = 0.0   # quando o som comecou (pra exigir sustentacao)
        self._init_meter()

    # ── Audio ────────────────────────────────────────────────────
    def _init_meter(self):
        if not HAS_PYCAW:
            return
        try:
            sp = AudioUtilities.GetSpeakers()
            dev = getattr(sp, "_dev", sp)  # pycaw novo: ._dev | antigo: o proprio
            itf = dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
            self._meter = cast(itf, POINTER(IAudioMeterInformation))
        except Exception as e:
            print(f"[AVISO] Nao deu pra iniciar o medidor de audio: {e}")
            self._meter = None

    def _pico_audio(self):
        if not self._meter:
            return 0.0
        try:
            return float(self._meter.GetPeakValue())
        except Exception:
            return 0.0

    def audio_tocando(self):
        """True so se ha som saindo de forma SUSTENTADA (>= AUDIO_SUSTENTADO_SEG).

        Isso evita o tiro no pe: o bipe que o proprio sistema toca ao travar
        (ou um 'ding' de notificacao) e curto e nao conta como midia tocando.
        """
        if not self.cfg.get("pausa_audio") or not self._meter:
            return False
        pico = self._pico_audio()
        # EMA: suaviza os silencios curtos entre batidas/falas
        self._audio_ema = 0.6 * self._audio_ema + 0.4 * pico
        agora = time.time()
        if self._audio_ema > LIMIAR_AUDIO:
            if self._audio_desde == 0.0:
                self._audio_desde = agora
            return (agora - self._audio_desde) >= AUDIO_SUSTENTADO_SEG
        self._audio_desde = 0.0
        return False

    # ── Tela cheia ───────────────────────────────────────────────
    def app_tela_cheia(self):
        """True se a janela em primeiro plano cobre o monitor principal."""
        if not self.cfg.get("pausa_tela_cheia"):
            return False
        try:
            hwnd = _user32.GetForegroundWindow()
            if not hwnd:
                return False

            # Ignora a area de trabalho / barra de tarefas
            buf = ctypes.create_unicode_buffer(256)
            _user32.GetClassNameW(hwnd, buf, 256)
            if buf.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Button"):
                return False

            # Ignora as NOSSAS janelas (overlay/cadastro) -> evita o loop de piscar
            titulo = ctypes.create_unicode_buffer(512)
            _user32.GetWindowTextW(hwnd, titulo, 512)
            for nome in JANELAS_PROPRIAS:
                if nome in titulo.value:
                    return False

            rect = wintypes.RECT()
            _user32.GetWindowRect(hwnd, ctypes.byref(rect))
            sw = _user32.GetSystemMetrics(0)  # SM_CXSCREEN
            sh = _user32.GetSystemMetrics(1)  # SM_CYSCREEN
            tol = 2
            cobre = (rect.left <= tol and rect.top <= tol and
                     rect.right >= sw - tol and rect.bottom >= sh - tol)
            return bool(cobre)
        except Exception:
            return False

    # ── Resumo ───────────────────────────────────────────────────
    def avaliar(self):
        """Retorna (pausar, motivos) considerando audio e tela cheia."""
        motivos = []
        if self.audio_tocando():
            motivos.append("audio")
        if self.app_tela_cheia():
            motivos.append("tela cheia")
        return (len(motivos) > 0), motivos
