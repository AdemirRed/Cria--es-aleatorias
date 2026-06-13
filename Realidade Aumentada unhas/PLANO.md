# Plano — Protótipo de Realidade Aumentada para Unhas (local, gratuito)

## Contexto
O usuário quer testar localmente a ideia de **try-on de unhas em realidade aumentada** no navegador: a câmera detecta a mão/dedos e desenha unhas artificiais sobre cada unha, em tempo real, com a manicure podendo ajustar **cor, formato, tamanho, opacidade, brilho**. Deve usar **apenas tecnologias gratuitas** e rodar **localmente** (sem build/npm).

Pasta de destino (vazia, já existe):
`C:\Users\RedBlack-PC\Desktop\Criações aleatorias\Realidade Aumentada unhas`

## Abordagem (100% gratuita, sem build)
- **MediaPipe Tasks Vision — HandLandmarker** (Google, grátis, via CDN jsDelivr): detecta **21 pontos por mão** em tempo real (GPU/WASM). Sem chave de API, sem servidor de ML.
- **HTML + CSS + JavaScript puro** (sem npm, sem bundler) — basta servir em `localhost` e abrir no Chrome.
- **Canvas 2D** sobreposto ao `<video>` da webcam (`getUserMedia`) para desenhar as unhas.

> Ressalva (documentada no README): é um protótipo "para ter noção" — posicionamento é estimado pelas pontas dos dedos (não há segmentação real da unha), então não fica fotorrealista. Melhor com a mão de frente, boa luz e fundo neutro.

## Arquivos a criar (na pasta de destino)
- `index.html` — estrutura: área de vídeo+canvas + painel de controles (editor da manicure) + scripts MediaPipe via CDN (`type="module"`).
- `style.css` — tema escuro rosa/roxo, responsivo (desktop e celular), painel lateral/inferior.
- `app.js` — toda a lógica:
  - Inicia câmera (`navigator.mediaDevices.getUserMedia`, câmera frontal, espelhada).
  - Carrega `HandLandmarker` (modelo `hand_landmarker.task` + wasm via CDN), `runningMode: VIDEO`, `numHands: 2`.
  - Loop `requestAnimationFrame`: detecta mãos e redesenha o canvas (vídeo + unhas).
  - Cálculo da unha por dedo: pontas `[4,8,12,16,20]` e juntas `[3,7,11,15,19]`; direção = ponta − junta; comprimento ∝ distância × fator; ângulo = `atan2`; centro deslocado para a ponta.
  - Desenho da unha (path rotacionado) por **formato**: quadrada (retângulo arredondado), redonda (cantos altos), amendoada e stiletto (path em "gota"/triângulo arredondado).
  - Efeitos: preenchimento com **cor + opacidade**, **brilho/gloss** (realce branco em gradiente), **francesinha** (faixa branca na ponta), **glitter** (pontos cintilantes) — todos opcionais.
- `README.md` — como rodar + permissões + ressalvas.
- `run.bat` — atalho Windows: sobe um servidor estático (tenta `python -m http.server 8000`, senão `npx serve`) e abre `http://localhost:8000`.

## Controles do editor (painel)
- 🎨 **Cor** (color picker) + paleta de presets (nudes, vermelho, rosa, preto, etc.)
- 🔶 **Formato**: Quadrada · Redonda · Amendoada · Stiletto
- 📏 **Comprimento** (slider) e **Largura** (slider)
- 🌫️ **Opacidade** (slider)
- ✨ **Brilho/Gloss** (toggle)
- 🤍 **Francesinha** (toggle) · **Glitter** (toggle)
- 🔁 **Espelhar** câmera (toggle)
- 🐞 **Mostrar pontos da mão** (debug, toggle)
- ▶️ **Iniciar/Parar câmera** · 📸 **Capturar** (salva PNG do resultado)

## Como rodar (a câmera exige contexto seguro → `localhost`)
1. Abrir a pasta no terminal e rodar `run.bat` (ou `python -m http.server 8000`).
2. Acessar `http://localhost:8000` no **Chrome/Edge**.
3. Permitir o uso da câmera.
> `file://` não funciona para câmera (Chrome bloqueia) — por isso o servidor local. Precisa de internet na 1ª vez (baixa modelo/wasm do CDN; o navegador faz cache depois).

## Verificação (teste end-to-end)
1. `run.bat` → abre `localhost:8000`, pede permissão de câmera.
2. Mostrar a mão de frente → aparecem unhas coloridas sobre as pontas dos dedos, acompanhando o movimento em tempo real.
3. Trocar **cor/formato/comprimento/opacidade** → muda na hora.
4. Ativar **gloss/francesinha/glitter** → efeitos visíveis.
5. **📸 Capturar** → baixa um PNG com o resultado.
6. Testar no **celular** (mesma rede, `http://IP-do-PC:8000`) — opcional.

## Observações
- Tudo gratuito e offline após o 1º carregamento (CDN em cache).
- Caminho de evolução (fora do escopo do protótipo): para realismo fotográfico, trocar a sobreposição por **segmentação de unha** (SDK pago: Perfect Corp/Banuba) — não necessário agora.
- Projeto é independente do sistema Belora (Front/BackEnd) — fica só nesta pasta.
