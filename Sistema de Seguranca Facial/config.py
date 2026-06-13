# -*- coding: utf-8 -*-
"""
CONFIGURACAO E PASTAS DE DADOS
Carrega/salva o config.json e define onde ficam os dados que o sistema
aprende (galeria de rostos, log, etc.).

Tudo fica em %LOCALAPPDATA%\\SegurancaFacial — caminho SEM acento, que
sobrevive mesmo se voce mover a pasta do projeto.
"""

import os
import json
import threading


# ════════════════════════════════════════════════════════════════
#  PASTAS DE DADOS (sem acento, persistem entre execucoes)
# ════════════════════════════════════════════════════════════════
APP_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "SegurancaFacial",
)
os.makedirs(APP_DIR, exist_ok=True)

CONFIG_PATH  = os.path.join(APP_DIR, "config.json")
GALERIA_PATH = os.path.join(APP_DIR, "galeria.npy")
META_PATH    = os.path.join(APP_DIR, "meta.json")
IMPOSTOR_PATH = os.path.join(APP_DIR, "impostores.npy")
LOG_PATH     = os.path.join(APP_DIR, "eventos.log")


# ════════════════════════════════════════════════════════════════
#  VALORES PADRAO
# ════════════════════════════════════════════════════════════════
PADRAO = {
    # ── Camera ──
    "camera_index": 0,
    "camera_largura": 1920,
    "camera_altura": 1080,

    # ── Reconhecimento (limiares de cosseno; sao auto-calibrados no cadastro) ──
    "limiar": 0.36,            # acima disso = "e voce" (calibrado depois)
    "limiar_forte": 0.46,      # confianca alta (usado pra aprender sozinho)
    "margem_impostor": 0.06,   # voce tem que vencer o melhor "nao-eu" por isso

    # ── Anti-flicker / histerese ──
    "janela_frames": 7,           # N: tamanho do buffer de decisao
    "frames_confirmar": 3,        # M: reconhecido em M de N frames -> destrava
    "carencia_travar_seg": 6.0,   # rosto sumido por X s -> trava

    # ── "Deitado" ──
    "roll_deitado_graus": 48.0,   # inclinacao dos olhos pra considerar deitado

    # ── Condicoes de pausa automatica ──
    "pausa_audio": True,
    "pausa_deitado": True,
    "pausa_tela_cheia": True,
    "pausa_camera_ocupada": True,
    "pausa_manual_minutos": 5,    # duracao do "Pausar" da bandeja/tecla

    # ── Comportamento em erro ──
    "fail_open": False,           # False = trava na duvida (com saida facil)

    # ── Aprendizado adaptativo ──
    "aprendizado_ativo": True,
    "intervalo_aprendizado_seg": 8.0,   # de quanto em quanto tempo pode aprender
    "novidade_min": 0.62,   # so aprende se a vista nova for MENOS parecida que isso
    "novidade_max": 0.92,   # ...e MAIS parecida que isso (ainda claramente voce)
    "galeria_max": 200,     # teto de vetores guardados

    # ── Consciencia de impostor (opcional) ──
    "impostor_ativo": False,
    "impostor_max": 80,

    # ── Seguranca / saida ──
    "senha_emergencia": "abrir",   # TROQUE! digite isso pra destravar na marra
    "tecla_destravar": "ctrl+alt+home",
    "tecla_pausar":    "ctrl+alt+p",
    "tecla_panico":    "ctrl+alt+end",
    "tecla_sair":      "ctrl+alt+q",
    "bloquear_alt_tab": False,     # bloquear Alt+Tab/Win com a tela travada (arriscado)

    # ── Saudacao falada (voz do Windows / SAPI) ──
    "saudacao_ativa": True,
    "nome_usuario": "Ademir",
    "saudacao_texto": "Bem-vindo, {nome}!",   # {nome} vira nome_usuario

    # ── Geral ──
    "som_ativo": True,
    "espelhar_camera": True,       # flip horizontal (espelho), como no gestos.py
}


_lock = threading.Lock()


class Config:
    """Acesso thread-safe ao config.json (carrega na criacao, salva sob demanda)."""

    def __init__(self):
        self._dados = dict(PADRAO)
        self.carregar()

    def carregar(self):
        with _lock:
            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        salvo = json.load(f)
                    # Mescla: mantem padroes e sobrescreve com o que estiver salvo
                    for k, v in salvo.items():
                        self._dados[k] = v
                except Exception as e:
                    print(f"[AVISO] Falha ao ler config ({e}); usando padroes.")
            # Garante que chaves novas (de versoes futuras) existam
            for k, v in PADRAO.items():
                self._dados.setdefault(k, v)

    def salvar(self):
        with _lock:
            try:
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(self._dados, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[ERRO] Falha ao salvar config: {e}")

    def get(self, chave, padrao=None):
        with _lock:
            if padrao is None:
                padrao = PADRAO.get(chave)
            return self._dados.get(chave, padrao)

    def set(self, chave, valor, salvar=True):
        with _lock:
            self._dados[chave] = valor
        if salvar:
            self.salvar()

    def como_dict(self):
        with _lock:
            return dict(self._dados)
