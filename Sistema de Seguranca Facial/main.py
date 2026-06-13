# -*- coding: utf-8 -*-
"""
SISTEMA DE SEGURANCA FACIAL QUE APRENDE
========================================

- Ve seu rosto -> destrava. Rosto some -> trava SUAVE (overlay, sem bloquear
  o Windows de verdade).
- APRENDE com o tempo (galeria que cresce) e com os erros (quando voce corrige
  um falso bloqueio, ele guarda aquilo como "isso era eu").
- Pausa sozinho: audio tocando, voce deitado, app em tela cheia, camera ocupada.
- Teclas de seguranca + senha de emergencia SEMPRE funcionam (voce nunca trava fora).

Arquitetura de threads:
  - Thread principal : janela Tkinter (overlay) + loop de eventos
  - Thread worker    : camera + reconhecimento + maquina de estados
  - Thread bandeja   : icone pystray
  - Thread teclado   : hooks globais (lib keyboard)
Tudo conversa por um "estado" compartilhado protegido por lock.
"""

import os
import sys
import time
import threading
from collections import deque

import cv2
import tkinter as tk

import config as cfgmod
from reconhecimento import Reconhecedor, cadastro_guiado, registrar
from contexto import ContextoDetector
from overlay import Overlay
from seguranca_teclas import TeclasSeguranca

# ── Imports opcionais com fallback (estilo do gestos.py) ──
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

try:
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False
    print("[AVISO] pystray/Pillow indisponivel - icone de bandeja desativado.")


# Estados possiveis
DESATIVADO        = "DESATIVADO"
ATIVO_DESTRAVADO  = "ATIVO_DESTRAVADO"
ATIVO_TRAVADO     = "ATIVO_TRAVADO"
PAUSADO           = "PAUSADO"


class App:
    def __init__(self):
        self.cfg = cfgmod.Config()
        self.rec = Reconhecedor(self.cfg)
        self.contexto = ContextoDetector(self.cfg)

        # ── Estado compartilhado (protegido por lock) ──
        self._lock = threading.Lock()
        self.rodando = True
        self.ativo = True                 # False = DESATIVADO (panico)
        self.travado = False
        self.estado = ATIVO_DESTRAVADO
        self.status = "Iniciando..."
        self.score = 0.0
        self.limiar = self.cfg.get("limiar")
        self.frame_preview = None

        # Controle interno da maquina
        self.ultimo_reconhecido = time.time()
        self.ultimo_emb = None
        self.ultimo_emb_tempo = 0.0
        self.pausa_ate = 0.0              # pausa manual (timestamp)
        self.pedido_recadastro = False
        self.camera_ocupada = False
        self.buffer_rec = deque(maxlen=int(self.cfg.get("janela_frames")))
        self._ultima_saudacao = 0.0

        # ── Teclas de seguranca ──
        callbacks = {
            "destravar": lambda: self._destravar("tecla", aprender=True),
            "pausar":    self.pausar_manual,
            "panico":    self.toggle_ativo,
            "sair":      self.sair,
            "senha":     lambda: self._destravar("senha", aprender=True),
        }
        self.teclas = TeclasSeguranca(self.cfg, callbacks, self._esta_travado)

        # ── Bandeja ──
        self.icon = None
        if HAS_TRAY:
            self._montar_tray()

    # ════════════════════════════════════════════════════════════
    #  SOM
    # ════════════════════════════════════════════════════════════
    def _som(self, nome):
        if not self.cfg.get("som_ativo") or not HAS_WINSOUND:
            return
        seqs = {
            "inicio":    [(523, 90), (659, 90), (784, 140)],
            "travou":    [(440, 160), (330, 220)],
            "destravou": [(660, 90), (880, 120)],
            "pausa":     [(500, 80), (500, 80)],
            "fim":       [(784, 90), (659, 90), (523, 140)],
        }
        seq = seqs.get(nome)
        if not seq:
            return
        def _toca():
            for f, d in seq:
                try:
                    winsound.Beep(f, d)
                except Exception:
                    pass
        threading.Thread(target=_toca, daemon=True).start()

    # ════════════════════════════════════════════════════════════
    #  VOZ (saudacao falada via SAPI do Windows)
    # ════════════════════════════════════════════════════════════
    def _falar(self, texto):
        if not self.cfg.get("saudacao_ativa") or not texto:
            return
        def _f():
            try:
                import comtypes.client as cc
                v = cc.CreateObject("SAPI.SpVoice")
                try:  # tenta usar uma voz em portugues, se houver
                    toks = v.GetVoices()
                    for i in range(toks.Count):
                        if "Portug" in toks.Item(i).GetDescription():
                            v.Voice = toks.Item(i)
                            break
                except Exception:
                    pass
                v.Speak(texto)
            except Exception as e:
                print(f"[AVISO] Voz (TTS) indisponivel: {e}")
        threading.Thread(target=_f, daemon=True).start()

    def _saudar(self):
        """Fala a saudacao ao desbloquear (com cooldown pra nao repetir toda hora)."""
        if not self.cfg.get("saudacao_ativa"):
            return
        agora = time.time()
        if agora - self._ultima_saudacao < 8.0:
            return
        self._ultima_saudacao = agora
        nome = self.cfg.get("nome_usuario") or ""
        texto = (self.cfg.get("saudacao_texto") or "Bem-vindo, {nome}!")
        self._falar(texto.replace("{nome}", nome).strip())

    # ════════════════════════════════════════════════════════════
    #  SNAPSHOT PRO OVERLAY
    # ════════════════════════════════════════════════════════════
    def ler_estado(self):
        with self._lock:
            return {
                "rodando": self.rodando,
                "travado": self.travado,
                "status": self.status,
                "score": self.score,
                "limiar": self.limiar,
                "frame_preview": self.frame_preview,
            }

    def _esta_travado(self):
        with self._lock:
            return self.travado

    # ════════════════════════════════════════════════════════════
    #  ACOES (teclas / bandeja)
    # ════════════════════════════════════════════════════════════
    def _destravar(self, motivo, aprender=True):
        with self._lock:
            era_travado = self.travado
            self.travado = False
            self.estado = ATIVO_DESTRAVADO
            self.ultimo_reconhecido = time.time()
            self.buffer_rec.clear()
            self.status = f"Destravado ({motivo})"
            emb = self.ultimo_emb if (time.time() - self.ultimo_emb_tempo < 2.5) else None
        if era_travado:
            self._som("destravou")
            self._saudar()
            registrar(f"destravado manualmente: {motivo}")
            # APRENDE COM O ERRO: se havia um rosto na hora, era voce.
            if aprender and emb is not None:
                self.rec.aprender_correcao(emb)
        self._atualizar_icone()

    def pausar_manual(self):
        minutos = int(self.cfg.get("pausa_manual_minutos"))
        with self._lock:
            self.pausa_ate = time.time() + minutos * 60
            self.travado = False
            self.estado = PAUSADO
            self.status = f"Pausado manualmente ({minutos} min)"
        self._som("pausa")
        registrar(f"pausa manual de {minutos} min")
        self._atualizar_icone()

    def toggle_ativo(self):
        with self._lock:
            self.ativo = not self.ativo
            self.travado = False
            if self.ativo:
                self.estado = ATIVO_DESTRAVADO
                self.ultimo_reconhecido = time.time()
                self.buffer_rec.clear()
                self.status = "Ativado"
            else:
                self.estado = DESATIVADO
                self.status = "Desativado"
            ativo = self.ativo
        registrar("ativado" if ativo else "desativado (panico)")
        self._atualizar_icone()

    def solicitar_recadastro(self):
        with self._lock:
            self.pedido_recadastro = True
            self.travado = False
            self.status = "Preparando recadastro..."
        registrar("recadastro solicitado")

    def sair(self):
        with self._lock:
            self.rodando = False
        registrar("encerrando")
        self._som("fim")
        # Para a bandeja; o mainloop do Tk sai pelo _tick vendo rodando=False
        try:
            if self.icon:
                self.icon.stop()
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════
    #  CAMERA
    # ════════════════════════════════════════════════════════════
    def _abrir_camera(self):
        try:
            idx = int(self.cfg.get("camera_index"))
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not cap or not cap.isOpened():
                if cap:
                    cap.release()
                return None
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.cfg.get("camera_largura")))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.cfg.get("camera_altura")))
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.release()
                return None
            return cap
        except Exception:
            return None

    def _fechar_camera(self, cap):
        try:
            if cap:
                cap.release()
        except Exception:
            pass

    def _pausa_por_camera(self):
        """Camera indisponivel: respeita a escolha do usuario."""
        with self._lock:
            if self.cfg.get("pausa_camera_ocupada"):
                self.travado = False
                self.estado = PAUSADO
                self.status = "Pausado: camera ocupada por outro app"
            elif self.cfg.get("fail_open"):
                self.travado = False
                self.status = "Camera indisponivel (liberado)"
            else:
                self.travado = True
                self.estado = ATIVO_TRAVADO
                self.status = "Camera indisponivel - use a saida de emergencia"
        self._atualizar_icone()

    # ════════════════════════════════════════════════════════════
    #  WORKER (camera + reconhecimento + maquina de estados)
    # ════════════════════════════════════════════════════════════
    def _worker(self):
        cap = None
        falhas = 0
        ult_contexto = 0.0
        ctx_pausar, ctx_motivos = False, []

        while True:
            with self._lock:
                if not self.rodando:
                    break
                ativo = self.ativo
                recad = self.pedido_recadastro

            if not ativo:
                cap = self._fechar_e_zerar(cap)
                time.sleep(0.3)
                continue

            # Garantir camera
            if cap is None or not cap.isOpened():
                cap = self._abrir_camera()
                if cap is None:
                    with self._lock:
                        self.camera_ocupada = True
                    self._pausa_por_camera()
                    time.sleep(1.0)
                    continue
                with self._lock:
                    self.camera_ocupada = False

            # Recadastro pedido pela bandeja (usa a camera ja aberta)
            if recad:
                with self._lock:
                    self.pedido_recadastro = False
                    self.status = "Recadastrando..."
                try:
                    cadastro_guiado(self.cfg, self.rec, cap=cap)
                except Exception as e:
                    registrar(f"erro no recadastro: {e}")
                with self._lock:
                    self.ultimo_reconhecido = time.time()
                    self.limiar = self.cfg.get("limiar")
                continue

            try:
                ret, frame = cap.read()
            except Exception:
                ret, frame = False, None
            if not ret or frame is None:
                falhas += 1
                if falhas >= 10:
                    # Webcam caiu/desconectou: solta e tenta reabrir depois
                    cap = self._fechar_e_zerar(cap)
                    with self._lock:
                        self.camera_ocupada = True
                    self._pausa_por_camera()
                    falhas = 0
                time.sleep(0.05)
                continue
            falhas = 0

            if self.cfg.get("espelhar_camera"):
                frame = cv2.flip(frame, 1)

            # ── Analise (deteccao + reconhecimento) ──
            res = self.rec.analisar(frame)
            agora = time.time()

            # ── Contexto (a cada ~0.4s; e caro) ──
            if agora - ult_contexto > 0.4:
                ctx_pausar, ctx_motivos = self.contexto.avaliar()
                ult_contexto = agora

            deitado = (res["tem_rosto"] and self.cfg.get("pausa_deitado")
                       and abs(res["roll"]) >= self.cfg.get("roll_deitado_graus"))
            pausa_manual = agora < self.pausa_ate
            pausar = ctx_pausar or deitado or pausa_manual
            motivos = list(ctx_motivos)
            if deitado:
                motivos.append("deitado")
            if pausa_manual:
                motivos.append("pausa manual")

            # ── Buffer anti-flicker ──
            self.buffer_rec.append(bool(res["eh_voce"]))
            estavel = sum(self.buffer_rec) >= int(self.cfg.get("frames_confirmar"))

            with self._lock:
                self.score = res["score"]
                self.limiar = self.cfg.get("limiar")
                if res["emb"] is not None:
                    self.ultimo_emb = res["emb"]
                    self.ultimo_emb_tempo = agora
                if res["eh_voce"]:
                    self.ultimo_reconhecido = agora

            # ── Maquina de estados ──
            self._maquina(agora, res, estavel, pausar, motivos)

            # ── Aprendizado online ──
            if not self._esta_travado() and not pausar and estavel:
                self.rec.talvez_aprender(res)

            # ── Consciencia de impostor (opcional) ──
            if (self.cfg.get("impostor_ativo") and res["tem_rosto"]
                    and not res["eh_voce"] and sum(self.buffer_rec) == 0):
                self.rec.registrar_impostor(res["emb"])

            # ── Preview pro overlay (so quando travado) ──
            if self._esta_travado():
                self._set_preview(frame, res)

            time.sleep(0.01)

        self._fechar_camera(cap)

    def _fechar_e_zerar(self, cap):
        self._fechar_camera(cap)
        return None

    def _maquina(self, agora, res, estavel, pausar, motivos):
        with self._lock:
            if pausar:
                self.travado = False
                self.estado = PAUSADO
                self.status = "Pausado: " + ", ".join(motivos)
                trans = None
            elif self.travado:
                if estavel:
                    self.travado = False
                    self.estado = ATIVO_DESTRAVADO
                    self.status = "Bem-vindo de volta!"
                    trans = "destravou"
                else:
                    self.estado = ATIVO_TRAVADO
                    self.status = ("Rosto nao reconhecido..." if res["tem_rosto"]
                                   else "Procurando seu rosto...")
                    trans = None
            else:
                sem_recon = agora - self.ultimo_reconhecido
                if sem_recon > float(self.cfg.get("carencia_travar_seg")):
                    self.travado = True
                    self.estado = ATIVO_TRAVADO
                    self.status = "Travado"
                    trans = "travou"
                else:
                    self.estado = ATIVO_DESTRAVADO
                    self.status = "Tudo certo"
                    trans = None

        if trans == "travou":
            self._som("travou")
            registrar("travado (rosto ausente alem da carencia)")
            self._atualizar_icone()
        elif trans == "destravou":
            self._som("destravou")
            self._saudar()
            registrar(f"destravado por reconhecimento (score {res['score']:.2f})")
            self._atualizar_icone()

    def _set_preview(self, frame, res):
        H, W = frame.shape[:2]
        pw = 360
        ph = max(1, int(pw * H / W))
        prev = cv2.resize(frame, (pw, ph))
        if res["face"] is not None:
            esc = res["escala"] or 1.0
            bx, by, bw, bh = (res["face"][:4] / esc)
            sx, sy = pw / W, ph / H
            cor = (122, 208, 39) if res["eh_voce"] else (100, 100, 255)
            cv2.rectangle(prev, (int(bx * sx), int(by * sy)),
                          (int((bx + bw) * sx), int((by + bh) * sy)), cor, 2)
        with self._lock:
            self.frame_preview = prev

    # ════════════════════════════════════════════════════════════
    #  BANDEJA (pystray)
    # ════════════════════════════════════════════════════════════
    def _icone_img(self, cor):
        img = Image.new("RGB", (64, 64), "#101018")
        d = ImageDraw.Draw(img)
        d.ellipse((10, 10, 54, 54), fill=cor)
        d.ellipse((24, 22, 40, 38), fill="#101018")  # "olho"
        return img

    def _cor_estado(self):
        with self._lock:
            if not self.ativo:
                return "#888899"
            if self.estado == PAUSADO:
                return "#ffd166"
            if self.travado:
                return "#ff6464"
            return "#27d07a"

    def _montar_tray(self):
        def txt_ativo(item):
            return "Desativar" if self.ativo else "Ativar"
        menu = Menu(
            MenuItem(txt_ativo, lambda i, it: self.toggle_ativo()),
            MenuItem("Pausar agora", lambda i, it: self.pausar_manual()),
            MenuItem("Recadastrar rosto", lambda i, it: self.solicitar_recadastro()),
            MenuItem("Abrir pasta de dados",
                     lambda i, it: os.startfile(cfgmod.APP_DIR)),
            Menu.SEPARATOR,
            MenuItem("Sair", lambda i, it: self.sair()),
        )
        self.icon = Icon("SegurancaFacial", self._icone_img("#27d07a"),
                         "Seguranca Facial", menu)

    def _atualizar_icone(self):
        if not self.icon:
            return
        try:
            self.icon.icon = self._icone_img(self._cor_estado())
            self.icon.title = f"Seguranca Facial - {self.estado}"
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════
    #  EXECUCAO
    # ════════════════════════════════════════════════════════════
    def run(self):
        print("\n" + "=" * 64)
        print("  SISTEMA DE SEGURANCA FACIAL QUE APRENDE")
        print("=" * 64)
        print(f"  Dados em: {cfgmod.APP_DIR}")
        print(f"  Saidas:   {self.cfg.get('tecla_destravar')} destrava | "
              f"{self.cfg.get('tecla_panico')} desativa | "
              f"{self.cfg.get('tecla_sair')} sai")
        print(f"  Senha de emergencia: '{self.cfg.get('senha_emergencia')}' "
              f"(troque no config.json!)")
        print("=" * 64 + "\n")

        # 1) Cadastro inicial (na thread principal, antes do Tk)
        if not self.rec.tem_cadastro():
            print("[INFO] Nenhum rosto cadastrado. Vamos cadastrar agora.")
            ok = cadastro_guiado(self.cfg, self.rec)
            if not ok or not self.rec.tem_cadastro():
                print("[ERRO] Cadastro nao concluido. Encerrando.")
                self.teclas.encerrar()
                return
            with self._lock:
                self.limiar = self.cfg.get("limiar")
                self.ultimo_reconhecido = time.time()

        self._som("inicio")

        # 2) Threads de fundo
        tw = threading.Thread(target=self._worker, daemon=True)
        tw.start()
        if self.icon:
            threading.Thread(target=self.icon.run, daemon=True).start()

        # 3) Overlay na thread principal (Tk)
        root = tk.Tk()
        self.overlay = Overlay(root, self.ler_estado, self.cfg)
        try:
            root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            with self._lock:
                self.rodando = False
            self.teclas.encerrar()
            try:
                if self.icon:
                    self.icon.stop()
            except Exception:
                pass
            time.sleep(0.3)
            print("[OK] Encerrado.")


if __name__ == "__main__":
    try:
        App().run()
    except Exception as e:
        print(f"\n[ERRO FATAL] {e}")
        import traceback
        traceback.print_exc()
        input("\nPressione Enter para sair...")
        sys.exit(1)
