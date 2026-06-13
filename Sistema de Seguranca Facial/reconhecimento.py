# -*- coding: utf-8 -*-
"""
RECONHECIMENTO FACIAL QUE APRENDE

- Deteccao: YuNet (cv2.FaceDetectorYN) -> caixa + 5 pontos (olhos, nariz, boca).
- Identidade: SFace (cv2.FaceRecognizerSF) -> vetor 128-d, comparado por cosseno.
- Galeria: varios vetores seus. O reconhecimento compara com a media dos
  mais parecidos (robusto a um vetor ruim).
- APRENDE: adiciona vistas novas (alta confianca, mas ainda nao guardadas) e
  aprende com erros (quando voce corrige um falso bloqueio).
- Limiar AUTO-CALIBRADO a partir do seu proprio cadastro (sem numero magico).

Embeddings sao guardados ja normalizados (L2=1), entao cosseno = produto escalar.
"""

import os
import math
import time
import threading

import cv2
import numpy as np

from modelos import garantir_modelos
import config as cfgmod


# ── Colunas do resultado do YuNet (cada rosto = 15 valores) ──
C_X, C_Y, C_W, C_H = 0, 1, 2, 3
C_OLHO_DIR = (4, 5)
C_OLHO_ESQ = (6, 7)
C_NARIZ    = (8, 9)
C_SCORE    = 14

# Resolucao interna de processamento (deteccao + embedding).
# Frame grande vira lento; 640 de largura e um bom equilibrio e mantem o
# embedding identico entre cadastro e uso (ambos passam por aqui).
PROC_LARGURA = 640


def _norm(v):
    n = float(np.linalg.norm(v))
    return (v / n).astype(np.float32) if n > 1e-8 else v.astype(np.float32)


def angulo_roll(face):
    """Inclinacao da linha dos olhos em graus. ~0 = reto, ~90 = deitado de lado."""
    rex, rey = face[C_OLHO_DIR[0]], face[C_OLHO_DIR[1]]
    lex, ley = face[C_OLHO_ESQ[0]], face[C_OLHO_ESQ[1]]
    ang = math.degrees(math.atan2(ley - rey, lex - rex))
    # Normaliza pra [-90, 90] (nao importa qual olho e "primeiro")
    if ang > 90:
        ang -= 180
    elif ang < -90:
        ang += 180
    return ang


class Reconhecedor:
    """Detecta, identifica e APRENDE o rosto do dono."""

    def __init__(self, cfg: cfgmod.Config):
        self.cfg = cfg
        yunet_path, sface_path = garantir_modelos()

        self.detector = cv2.FaceDetectorYN.create(
            yunet_path, "", (320, 320),
            score_threshold=0.75, nms_threshold=0.3, top_k=50,
        )
        self.recognizer = cv2.FaceRecognizerSF.create(sface_path, "")

        self._lock = threading.Lock()
        self.galeria = np.empty((0, 128), dtype=np.float32)    # suas vistas
        self.impostores = np.empty((0, 128), dtype=np.float32)  # "nao-eu" (opcional)
        self._ultimo_aprendizado = 0.0

        self._carregar()

    # ════════════════════════════════════════════════════════════
    #  PERSISTENCIA
    # ════════════════════════════════════════════════════════════
    def _carregar(self):
        if os.path.exists(cfgmod.GALERIA_PATH):
            try:
                g = np.load(cfgmod.GALERIA_PATH)
                if g.ndim == 2 and g.shape[1] == 128:
                    self.galeria = g.astype(np.float32)
            except Exception as e:
                print(f"[AVISO] Falha ao ler galeria: {e}")
        if os.path.exists(cfgmod.IMPOSTOR_PATH):
            try:
                self.impostores = np.load(cfgmod.IMPOSTOR_PATH).astype(np.float32)
            except Exception:
                pass
        print(f"[INFO] Galeria carregada: {len(self.galeria)} vista(s) suas.")

    def salvar(self):
        with self._lock:
            try:
                np.save(cfgmod.GALERIA_PATH, self.galeria)
                if len(self.impostores):
                    np.save(cfgmod.IMPOSTOR_PATH, self.impostores)
            except Exception as e:
                print(f"[ERRO] Falha ao salvar galeria: {e}")

    def tem_cadastro(self):
        return len(self.galeria) >= 3

    # ════════════════════════════════════════════════════════════
    #  DETECCAO + EMBEDDING
    # ════════════════════════════════════════════════════════════
    def _preparar(self, frame_bgr):
        """Reduz pra largura de processamento. Retorna (frame_proc, escala)."""
        h, w = frame_bgr.shape[:2]
        if w > PROC_LARGURA:
            escala = PROC_LARGURA / w
            proc = cv2.resize(frame_bgr, (PROC_LARGURA, int(h * escala)))
        else:
            escala = 1.0
            proc = frame_bgr
        return proc, escala

    def detectar(self, frame_proc):
        """Retorna array Nx15 com os rostos (vazio se nenhum)."""
        h, w = frame_proc.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame_proc)
        if faces is None:
            return np.empty((0, 15), dtype=np.float32)
        return faces

    def _embedding(self, frame_proc, face):
        aligned = self.recognizer.alignCrop(frame_proc, face)
        feat = self.recognizer.feature(aligned)
        return _norm(np.asarray(feat).flatten())

    @staticmethod
    def maior_rosto(faces):
        """Indice do maior rosto (mais perto da camera)."""
        if len(faces) == 0:
            return -1
        areas = faces[:, C_W] * faces[:, C_H]
        return int(np.argmax(areas))

    # ════════════════════════════════════════════════════════════
    #  RECONHECIMENTO
    # ════════════════════════════════════════════════════════════
    def pontuar(self, emb):
        """
        Compara um embedding com a galeria.
        Retorna (score_decisao, score_max):
          - score_decisao: media dos K mais parecidos (robusto) -> usado pra decidir
          - score_max: parecido com o vizinho mais proximo -> usado pra novidade
        """
        with self._lock:
            if len(self.galeria) == 0:
                return -1.0, -1.0
            sims = self.galeria @ emb  # cosseno (tudo normalizado)
            score_max = float(np.max(sims))
            k = min(3, len(sims))
            score_dec = float(np.mean(np.sort(sims)[-k:]))
        return score_dec, score_max

    def melhor_impostor(self, emb):
        with self._lock:
            if len(self.impostores) == 0:
                return -1.0
            return float(np.max(self.impostores @ emb))

    def analisar(self, frame_bgr):
        """
        Processa um frame inteiro. Retorna um dict com o resultado do MAIOR rosto:
          {
            'tem_rosto': bool, 'n_rostos': int,
            'score': float, 'score_max': float, 'roll': float,
            'emb': np.array|None, 'face': np.array|None, 'escala': float,
            'eh_voce': bool, 'forte': bool,
          }
        Coordenadas em 'face' estao no espaco do frame REDUZIDO (multiplique
        por 1/escala pra desenhar no frame original).
        """
        proc, escala = self._preparar(frame_bgr)
        faces = self.detectar(proc)
        res = {
            "tem_rosto": False, "n_rostos": int(len(faces)),
            "score": -1.0, "score_max": -1.0, "roll": 0.0,
            "emb": None, "face": None, "escala": escala,
            "eh_voce": False, "forte": False,
        }
        if len(faces) == 0:
            return res

        i = self.maior_rosto(faces)
        face = faces[i]
        try:
            emb = self._embedding(proc, face)
        except Exception:
            # Rosto muito no canto / recorte invalido: trata como "rosto sem id"
            res["tem_rosto"] = True
            res["roll"] = angulo_roll(face)
            res["face"] = face
            return res
        score, score_max = self.pontuar(emb)

        limiar = self.cfg.get("limiar")
        limiar_forte = self.cfg.get("limiar_forte")
        eh_voce = score >= limiar

        # Consciencia de impostor (opcional): tem que vencer o melhor "nao-eu"
        if eh_voce and self.cfg.get("impostor_ativo") and len(self.impostores):
            margem = self.cfg.get("margem_impostor")
            if score < self.melhor_impostor(emb) + margem:
                eh_voce = False

        res.update({
            "tem_rosto": True, "score": score, "score_max": score_max,
            "roll": angulo_roll(face), "emb": emb, "face": face,
            "eh_voce": eh_voce, "forte": eh_voce and score >= limiar_forte,
        })
        return res

    # ════════════════════════════════════════════════════════════
    #  APRENDIZADO
    # ════════════════════════════════════════════════════════════
    def adicionar(self, emb, motivo="auto"):
        """Adiciona uma vista a galeria (com teto e descarte do mais redundante)."""
        with self._lock:
            self.galeria = np.vstack([self.galeria, emb.reshape(1, -1)])
            teto = int(self.cfg.get("galeria_max"))
            if len(self.galeria) > teto:
                # Remove o vetor mais "redundante" (mais parecido com os outros)
                G = self.galeria @ self.galeria.T
                np.fill_diagonal(G, -1.0)
                redundante = int(np.argmax(G.sum(axis=1)))
                self.galeria = np.delete(self.galeria, redundante, axis=0)
        self.salvar()
        registrar(f"aprendeu vista nova ({motivo}); galeria={len(self.galeria)}")

    def talvez_aprender(self, res):
        """
        Aprendizado online: se for voce com alta confianca e a vista for NOVA
        (nem identica ao que ja temos, nem duvidosa), guarda. Respeita cooldown.
        Deve ser chamado so quando o estado e 'destravado confiante, 1 rosto'.
        """
        if not self.cfg.get("aprendizado_ativo"):
            return
        if res["emb"] is None or res["n_rostos"] != 1 or not res["forte"]:
            return
        agora = time.time()
        if agora - self._ultimo_aprendizado < self.cfg.get("intervalo_aprendizado_seg"):
            return
        nmin = self.cfg.get("novidade_min")
        nmax = self.cfg.get("novidade_max")
        # score_max alto demais = duplicata (nao agrega). Baixo demais = arriscado.
        if nmin <= res["score_max"] <= nmax:
            self._ultimo_aprendizado = agora
            self.adicionar(res["emb"], motivo="auto")

    def aprender_correcao(self, emb):
        """Voce corrigiu um falso bloqueio: guarda como amostra positiva."""
        if emb is not None:
            self.adicionar(emb, motivo="correcao")

    def registrar_impostor(self, emb):
        """Guarda um rosto que NAO e voce (se a consciencia de impostor estiver on)."""
        if not self.cfg.get("impostor_ativo") or emb is None:
            return
        with self._lock:
            self.impostores = np.vstack([self.impostores, emb.reshape(1, -1)])
            teto = int(self.cfg.get("impostor_max"))
            if len(self.impostores) > teto:
                self.impostores = self.impostores[-teto:]

    # ════════════════════════════════════════════════════════════
    #  CALIBRACAO DO LIMIAR (a partir do seu proprio cadastro)
    # ════════════════════════════════════════════════════════════
    def calibrar_limiar(self):
        """Define limiar/limiar_forte pela distribuicao de similaridade das suas vistas."""
        with self._lock:
            n = len(self.galeria)
            if n < 4:
                return  # poucos dados; mantem os padroes
            G = self.galeria @ self.galeria.T
            iu = np.triu_indices(n, k=1)
            sims = G[iu]
        media = float(np.mean(sims))
        desvio = float(np.std(sims))
        limiar = float(np.clip(media - 2.0 * desvio, 0.34, 0.42))
        forte  = float(np.clip(media - 0.5 * desvio, max(limiar + 0.06, 0.44), 0.62))
        self.cfg.set("limiar", round(limiar, 3), salvar=False)
        self.cfg.set("limiar_forte", round(forte, 3))
        registrar(f"limiar calibrado: {limiar:.3f} (forte {forte:.3f}) "
                  f"de {n} vistas; media={media:.3f} desvio={desvio:.3f}")
        print(f"[OK] Limiar calibrado: {limiar:.3f} / forte {forte:.3f}")


# ════════════════════════════════════════════════════════════════
#  LOG DE EVENTOS (compartilhado)
# ════════════════════════════════════════════════════════════════
def registrar(msg):
    """Escreve uma linha no log com data/hora."""
    import datetime
    linha = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    try:
        with open(cfgmod.LOG_PATH, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass
    print(f"[LOG] {msg}")


# ════════════════════════════════════════════════════════════════
#  CADASTRO GUIADO (abre janela OpenCV e captura varias vistas)
# ════════════════════════════════════════════════════════════════
ETAPAS_CADASTRO = [
    ("Olhe de FRENTE pra camera",            12),
    ("Vire um pouco pra ESQUERDA",            8),
    ("Vire um pouco pra DIREITA",             8),
    ("Incline o rosto pra CIMA",              6),
    ("Incline o rosto pra BAIXO",             6),
    ("Deite a cabeca de LADO (como deitado)", 8),
    ("Se usar oculos: TIRE e olhe de frente",  8),
    ("Aproxime e afaste um pouco o rosto",     8),
]


def cadastro_guiado(cfg: cfgmod.Config, rec: Reconhecedor, cap=None):
    """
    Captura interativa. Mostra instrucoes e coleta embeddings de varias vistas.
    Retorna True se cadastrou o suficiente. Usa 'cap' se passado, senao abre a 0.
    """
    fechar_cap = False
    if cap is None:
        cap = cv2.VideoCapture(cfg.get("camera_index"), cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.get("camera_largura"))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.get("camera_altura"))
        fechar_cap = True

    if not cap or not cap.isOpened():
        print("[ERRO] Camera nao disponivel para o cadastro.")
        return False

    janela = "Cadastro do Rosto - ESPACO captura | N proxima | ESC cancela"
    cv2.namedWindow(janela, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(janela, 960, 540)

    novos = []
    etapa = 0
    coletadas_etapa = 0
    ult_auto = 0.0
    completo_em = 0.0

    print("\n[CADASTRO] Siga as instrucoes na tela. ESPACO captura, N pula, ESC cancela.\n")

    try:
        while etapa < len(ETAPAS_CADASTRO):
            ret, frame = cap.read()
            if not ret:
                cv2.waitKey(30)
                continue
            if cfg.get("espelhar_camera"):
                frame = cv2.flip(frame, 1)

            proc, escala = rec._preparar(frame)
            faces = rec.detectar(proc)
            instrucao, meta = ETAPAS_CADASTRO[etapa]

            tem = len(faces) > 0
            face = faces[rec.maior_rosto(faces)] if tem else None

            # Captura automatica: o rosto detectado pelo YuNet ja passou pelo
            # limiar de qualidade, entao captura 1 a cada ~0.3s ate completar.
            agora = time.time()
            if tem and (agora - ult_auto) > 0.3 and coletadas_etapa < meta:
                try:
                    novos.append(rec._embedding(proc, face))
                    coletadas_etapa += 1
                    ult_auto = agora
                except Exception:
                    pass

            # ── Desenho ──
            h, w = frame.shape[:2]
            if tem:
                x, y, fw, fh = (face[:4] / escala).astype(int)
                cv2.rectangle(frame, (x, y), (x + fw, y + fh), (0, 220, 120), 2)

            cv2.rectangle(frame, (0, 0), (w, 90), (40, 35, 50), -1)
            cv2.putText(frame, f"Etapa {etapa+1}/{len(ETAPAS_CADASTRO)}: {instrucao}",
                        (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, f"Capturadas nesta etapa: {coletadas_etapa}/{meta}   "
                               f"(total {len(novos)})",
                        (15, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 220, 120) if coletadas_etapa >= meta else (200, 200, 200),
                        2, cv2.LINE_AA)
            if not tem:
                cv2.putText(frame, "Nenhum rosto detectado", (15, h - 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 100, 255), 2, cv2.LINE_AA)

            # Ao completar a etapa, mostra "PRONTO" e segura 0.6s antes de avancar
            if coletadas_etapa >= meta:
                if completo_em == 0.0:
                    completo_em = time.time()
                cv2.putText(frame, ">> PRONTO! proxima etapa...", (15, h - 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 120), 2, cv2.LINE_AA)

            cv2.imshow(janela, frame)
            tecla = cv2.waitKey(1) & 0xFF

            avancar = False
            if tecla == 27:                       # ESC = encerra (salva o que ja tem)
                break
            elif tecla in (ord('n'), ord('N')):   # N = pular etapa
                avancar = True
            elif tecla == 32 and tem:             # ESPACO = captura manual extra
                try:
                    novos.append(rec._embedding(proc, face))
                    coletadas_etapa += 1
                except Exception:
                    pass

            # Avanca sozinho 0.6s depois de completar (da tempo de ver o "PRONTO")
            if completo_em and (time.time() - completo_em) > 0.6:
                avancar = True
            if avancar:
                etapa += 1
                coletadas_etapa = 0
                completo_em = 0.0
                ult_auto = 0.0
    finally:
        cv2.destroyWindow(janela)
        if fechar_cap:
            cap.release()

    if len(novos) < 8:
        print(f"[CADASTRO] Poucas amostras ({len(novos)}). Cadastro nao salvo.")
        return False

    # Salva (substitui a galeria antiga pela nova base + mantem o que ja havia aprendido)
    with rec._lock:
        base = np.array(novos, dtype=np.float32)
        if len(rec.galeria):
            rec.galeria = np.vstack([rec.galeria, base])
        else:
            rec.galeria = base
    rec.salvar()
    rec.calibrar_limiar()
    registrar(f"cadastro concluido: +{len(novos)} vistas; galeria={len(rec.galeria)}")
    print(f"[OK] Cadastro salvo: {len(novos)} vistas novas (galeria total {len(rec.galeria)}).")
    return True
