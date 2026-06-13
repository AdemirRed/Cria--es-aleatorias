# -*- coding: utf-8 -*-
"""
OVERLAY DA TRAVA SUAVE (Tkinter)

Janela em tela cheia, sempre no topo, escura, que cobre o que voce estava
fazendo quando o rosto some. NAO usa o bloqueio real do Windows -> voce nunca
fica trancado fora.

Roda na THREAD PRINCIPAL (exigencia do Tk). A thread da camera so atualiza um
"estado" compartilhado; este overlay le esse estado a cada ~60ms e se mostra,
se esconde e se atualiza sozinho.

Sempre mostra, bem visivel, as formas de SAIR (teclas + senha).
"""

import time
import tkinter as tk

import cv2
from PIL import Image, ImageTk


COR_FUNDO   = "#0a0a14"
COR_TITULO  = "#e8e8f0"
COR_OK      = "#27d07a"
COR_ALERTA  = "#ff6464"
COR_INFO    = "#7aa2ff"
COR_FRACO   = "#888899"


class Overlay:
    """
    ler_estado(): funcao que devolve um dict-snapshot com:
        rodando(bool), travado(bool), status(str), score(float),
        limiar(float), frame_preview(np.array BGR|None), motivo(str)
    """

    def __init__(self, root: tk.Tk, ler_estado, cfg):
        self.root = root
        self.ler = ler_estado
        self.cfg = cfg
        self._visivel = False
        self._tk_img = None
        self._ultimo_topo = 0.0
        self._quer_esconder_em = 0.0
        self._construir()
        self.root.after(60, self._tick)

    # ════════════════════════════════════════════════════════════
    def _construir(self):
        self.root.title("Seguranca Facial")
        self.root.configure(bg=COR_FUNDO)
        try:
            self.root.attributes("-fullscreen", True)
            self.root.attributes("-topmost", True)
            self.root.attributes("-alpha", 0.97)
        except tk.TclError:
            pass

        wrap = tk.Frame(self.root, bg=COR_FUNDO)
        wrap.place(relx=0.5, rely=0.5, anchor="center")

        self.lbl_cadeado = tk.Label(wrap, text="\U0001F512  TELA PROTEGIDA",
                                    font=("Segoe UI", 30, "bold"),
                                    fg=COR_TITULO, bg=COR_FUNDO)
        self.lbl_cadeado.pack(pady=(0, 6))

        self.lbl_status = tk.Label(wrap, text="Procurando seu rosto...",
                                   font=("Segoe UI", 15),
                                   fg=COR_INFO, bg=COR_FUNDO)
        self.lbl_status.pack(pady=(0, 14))

        # Preview da camera (ajuda voce a se posicionar)
        self.lbl_preview = tk.Label(wrap, bg="#000000", bd=0)
        self.lbl_preview.pack()

        # Barra de confianca
        self.canvas = tk.Canvas(wrap, width=420, height=16, bg="#1c1c2a",
                                highlightthickness=0)
        self.canvas.pack(pady=(14, 4))
        self._barra = self.canvas.create_rectangle(0, 0, 0, 16,
                                                   fill=COR_OK, width=0)
        self._marca = self.canvas.create_line(0, 0, 0, 16, fill="#ffffff")
        self.lbl_score = tk.Label(wrap, text="", font=("Consolas", 11),
                                  fg=COR_FRACO, bg=COR_FUNDO)
        self.lbl_score.pack()

        # Caixa de saida de emergencia (sempre visivel)
        cx = tk.Frame(self.root, bg="#14141f", bd=0)
        cx.place(relx=0.5, rely=0.97, anchor="s")
        tk.Label(cx, text="  SAIDA DE EMERGENCIA  ", font=("Segoe UI", 11, "bold"),
                 fg="#ffd166", bg="#14141f").pack(pady=(8, 2))
        self.lbl_saida = tk.Label(cx, text="", font=("Consolas", 11),
                                  fg="#cfcfe0", bg="#14141f", justify="center")
        self.lbl_saida.pack(padx=18, pady=(0, 10))
        self._atualizar_saida()

        self.root.withdraw()  # comeca escondido (destravado)

    def _atualizar_saida(self):
        senha = self.cfg.get("senha_emergencia")
        txt = (f"Destravar: {self.cfg.get('tecla_destravar').upper()}     "
               f"Pausar: {self.cfg.get('tecla_pausar').upper()}     "
               f"Desativar: {self.cfg.get('tecla_panico').upper()}     "
               f"Sair: {self.cfg.get('tecla_sair').upper()}\n"
               f"...ou apenas DIGITE sua senha de emergencia para destravar")
        self.lbl_saida.configure(text=txt)

    # ════════════════════════════════════════════════════════════
    def _mostrar(self):
        self._atualizar_saida()
        self.root.deiconify()
        try:
            self.root.attributes("-fullscreen", True)
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.root.lift()
        self._visivel = True

    def _esconder(self):
        self.root.withdraw()
        self._visivel = False

    def _atualizar(self, st):
        # NAO reafirmar topo aqui! Chamar lift()/topmost a cada 60ms faz a tela
        # PISCAR no Windows. O topo e garantido no _mostrar e reafirmado devagar.
        self.lbl_status.configure(text=st.get("status") or "Procurando seu rosto...")

        # Preview
        frame = st.get("frame_preview")
        if frame is not None:
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil = Image.fromarray(rgb)
                self._tk_img = ImageTk.PhotoImage(pil)
                self.lbl_preview.configure(image=self._tk_img)
            except Exception:
                pass

        # Barra de confianca: mapeia score em [0, limiar*2]
        score = float(st.get("score", 0.0))
        limiar = float(st.get("limiar", 0.36)) or 0.36
        frac = max(0.0, min(1.0, score / (limiar * 2.0)))
        largura = int(420 * frac)
        cor = COR_OK if score >= limiar else COR_ALERTA
        self.canvas.coords(self._barra, 0, 0, largura, 16)
        self.canvas.itemconfigure(self._barra, fill=cor)
        marca_x = int(420 * 0.5)  # limiar fica no meio da barra
        self.canvas.coords(self._marca, marca_x, 0, marca_x, 16)
        if score >= 0:
            self.lbl_score.configure(
                text=f"confianca {score:.2f}  /  precisa de {limiar:.2f}")
        else:
            self.lbl_score.configure(text="nenhum rosto detectado")

    # ════════════════════════════════════════════════════════════
    def _tick(self):
        try:
            st = self.ler()
        except Exception:
            st = {"rodando": True, "travado": False}

        if not st.get("rodando", True):
            try:
                self.root.quit()
            except tk.TclError:
                pass
            return

        travado = st.get("travado", False)
        if travado:
            self._quer_esconder_em = 0.0
            if not self._visivel:
                self._mostrar()
        else:
            # Esconder so depois de 0.3s destravado -> blinda contra piscadas
            if self._visivel:
                if self._quer_esconder_em == 0.0:
                    self._quer_esconder_em = time.time()
                elif time.time() - self._quer_esconder_em > 0.3:
                    self._esconder()
                    self._quer_esconder_em = 0.0

        if self._visivel:
            self._atualizar(st)
            # Reafirma "no topo" devagar (a cada 2s), SEM lift -> nao pisca
            agora = time.time()
            if agora - self._ultimo_topo > 2.0:
                self._ultimo_topo = agora
                try:
                    self.root.attributes("-topmost", True)
                except tk.TclError:
                    pass

        self.root.after(60, self._tick)
