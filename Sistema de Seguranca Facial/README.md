# Sistema de Segurança Facial que Aprende

Um "guarda" do PC pela webcam: **vê seu rosto → destrava**; **rosto some → trava suave**
(uma tela escura por cima de tudo, **sem** bloquear o Windows de verdade — você nunca
fica trancado fora). E o principal: **ele aprende com o tempo**.

## Como rodar

1. Dê dois cliques em **`iniciar.bat`** (instala as dependências e abre o programa).
2. Na primeira vez, faça o **cadastro guiado** (siga as instruções na tela: frente,
   lados, cima/baixo, deitado, com/sem óculos). Quanto mais variado, melhor ele aprende.
3. Pronto. Ele fica na **bandeja** do Windows (ícone redondo) vigiando.

## Saídas de emergência (sempre funcionam, mesmo se a câmera falhar)

| Atalho | Ação |
|---|---|
| `Ctrl+Alt+Home` | Destravar agora |
| `Ctrl+Alt+P` | Pausar |
| `Ctrl+Alt+End` | Desativar tudo (pânico) |
| `Ctrl+Alt+Q` | Sair |
| **Digitar a senha** | Com a tela travada, digite sua senha de emergência → destrava |

> A senha padrão é `abrir`. **Troque** em `config.json` (veja abaixo).

## Como ele APRENDE (não é "match de foto burro")

- **Galeria que cresce:** quando te reconhece com alta confiança, guarda **vistas novas**
  (barba, corte, luz diferente). Não guarda duplicatas nem nada duvidoso.
- **Aprende com os erros:** se ele te travar por engano e você destravar (tecla/senha)
  com o rosto na frente, ele guarda aquilo como *"isso era eu"* — e acerta na próxima.
- **Limiar auto-calibrado:** o ponto de corte é calculado a partir do **seu** cadastro
  e da **sua** câmera, não é um número mágico.
- **Anti-piscar:** destrava rápido quando confia, mas só trava depois de alguns segundos
  sem te ver (olhar de relance pro lado não trava; alguém passando atrás não destrava).

## Pausa automática (não trava nessas horas)

- 🎵 **Áudio tocando** (vídeo/música)
- 🛏️ **Você deitado** (rosto muito inclinado)
- 🖥️ **App em tela cheia** (filme/jogo)
- 📷 **Câmera ocupada** por outro app (Zoom, OBS...)

Cada uma pode ser ligada/desligada no `config.json`.

## Configuração

Tudo fica em `%LOCALAPPDATA%\SegurancaFacial\`:

- `config.json` — todos os ajustes (limiares, carência pra travar, senha, atalhos,
  condições de pausa, aprendizado on/off, etc.). Use **bandeja → Abrir pasta de dados**.
- `galeria.npy` — as vistas do seu rosto que ele aprendeu.
- `eventos.log` — histórico (travou, destravou, aprendeu, etc.).

Ajustes úteis no `config.json`:

| Chave | O que faz |
|---|---|
| `senha_emergencia` | **Troque já.** Palavra que destrava se você digitar |
| `carencia_travar_seg` | Segundos sem rosto até travar (padrão 6) |
| `limiar` | Quão exigente é o reconhecimento (auto-calibrado no cadastro) |
| `fail_open` | `true` = na dúvida destrava; `false` = na dúvida trava (padrão) |
| `impostor_ativo` | Liga a "consciência de impostor" (rejeita rostos parecidos) |
| `camera_index` | Troque se tiver mais de uma webcam |

## Limites honestos

- A trava é **de conveniência**: alguém poderia dar `Alt+Tab`/`Win` (a janela volta pro
  topo, mas não é um cofre). Combina com a ideia de "sem bloquear de verdade".
- **Sem prova de vida** por padrão — uma foto sua poderia enganar. Dá pra evoluir depois.
- Overlay cobre o **monitor principal** (multi-monitor fica pra uma versão futura).

## Recadastrar

Bandeja → **Recadastrar rosto**. Ele soma as novas vistas ao que já aprendeu e
recalibra o limiar.
