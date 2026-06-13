# -*- coding: utf-8 -*-
"""
TECLAS DE SEGURANCA + SENHA DE EMERGENCIA

Hooks globais (lib 'keyboard') que rodam numa thread propria, independentes
da camera e do overlay. Mesmo que tudo trave, ISSO continua funcionando ->
voce NUNCA fica preso.

  - Destravar agora   (padrao Ctrl+Alt+Home)
  - Pausar X min      (padrao Ctrl+Alt+P)
  - Desativar tudo    (padrao Ctrl+Alt+End)  [panico]
  - Sair              (padrao Ctrl+Alt+Q)
  - Senha de emergencia: digite a palavra secreta com a tela travada -> destrava.
"""

try:
    import keyboard
    HAS_KEYBOARD = True
except Exception:
    HAS_KEYBOARD = False
    print("[AVISO] lib 'keyboard' indisponivel - teclas de seguranca DESATIVADAS!")


class TeclasSeguranca:
    """
    callbacks: dict com funcoes 'destravar', 'pausar', 'panico', 'sair', 'senha'.
    esta_travado: funcao que retorna True quando a tela esta travada
                  (a senha so e ouvida nesse estado).
    """

    def __init__(self, cfg, callbacks, esta_travado):
        self.cfg = cfg
        self.cb = callbacks
        self.esta_travado = esta_travado
        self._buffer = ""
        self._ok = False
        if HAS_KEYBOARD:
            self._registrar()

    def _registrar(self):
        try:
            keyboard.add_hotkey(self.cfg.get("tecla_destravar"),
                                lambda: self._chamar("destravar"))
            keyboard.add_hotkey(self.cfg.get("tecla_pausar"),
                                lambda: self._chamar("pausar"))
            keyboard.add_hotkey(self.cfg.get("tecla_panico"),
                                lambda: self._chamar("panico"))
            keyboard.add_hotkey(self.cfg.get("tecla_sair"),
                                lambda: self._chamar("sair"))
            keyboard.on_press(self._on_press)
            self._ok = True
            print("[OK] Teclas de seguranca ativas: "
                  f"destravar={self.cfg.get('tecla_destravar')} | "
                  f"pausar={self.cfg.get('tecla_pausar')} | "
                  f"panico={self.cfg.get('tecla_panico')} | "
                  f"sair={self.cfg.get('tecla_sair')}")
        except Exception as e:
            print(f"[ERRO] Falha ao registrar teclas de seguranca: {e}")
            self._ok = False

    def _chamar(self, nome):
        fn = self.cb.get(nome)
        if fn:
            try:
                fn()
            except Exception as e:
                print(f"[ERRO] callback '{nome}': {e}")

    def _on_press(self, event):
        """Acumula digitacao SO quando travado, pra detectar a senha."""
        try:
            if not self.esta_travado():
                if self._buffer:
                    self._buffer = ""
                return
            nome = getattr(event, "name", None)
            if not nome:
                return
            if len(nome) == 1:               # caractere visivel
                self._buffer = (self._buffer + nome)[-40:]
            elif nome == "space":
                self._buffer = (self._buffer + " ")[-40:]
            elif nome == "backspace":
                self._buffer = self._buffer[:-1]
            else:
                return

            senha = (self.cfg.get("senha_emergencia") or "").lower()
            if senha and self._buffer.lower().endswith(senha):
                self._buffer = ""
                self._chamar("senha")
        except Exception:
            pass

    @property
    def ativo(self):
        return self._ok

    def encerrar(self):
        if HAS_KEYBOARD:
            try:
                keyboard.unhook_all()
            except Exception:
                pass
