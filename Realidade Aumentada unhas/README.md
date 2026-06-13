# 💅 Provador de Unhas AR (protótipo local e gratuito)

Try-on de unhas em **realidade aumentada** no navegador: a câmera detecta a mão e
desenha unhas artificiais sobre as pontas dos dedos, em tempo real. A manicure pode
ajustar **cor, formato, comprimento, largura, opacidade, brilho, francesinha e glitter**.

100% gratuito, sem cadastro e sem chave de API:
- **MediaPipe HandLandmarker** (Google) — detecção de 21 pontos da mão, via CDN.
- **HTML + CSS + JavaScript puro** — sem npm, sem build.
- **Canvas 2D** sobreposto à webcam.

---

## ▶️ Como rodar

A câmera só funciona em **contexto seguro** (`localhost` ou `https`). Abrir o
`index.html` direto com duplo clique (`file://`) **não funciona** — use o servidor local.

### Opção 1 — atalho (Windows)
1. Dê duplo clique em **`run.bat`**.
2. Ele sobe um servidor e abre `http://localhost:8000` no navegador.

### Opção 2 — manual
Tendo Python instalado, na pasta do projeto:
```
python -m http.server 8000
```
Sem Python, com Node:
```
npx serve -l 8000
```
Depois abra **http://localhost:8000** no **Chrome** ou **Edge**.

3. Clique em **▶️ Iniciar câmera** e **permita** o acesso.
4. Mostre a mão de frente → aparecem as unhas. Ajuste no painel à direita.
5. **📸 Capturar** salva um PNG do resultado.

> 1ª vez precisa de internet (baixa o modelo + wasm do CDN). Depois o navegador faz cache.

### Testar no celular (opcional)
Na mesma rede Wi-Fi, descubra o IP do PC (`ipconfig`) e acesse no celular
`http://SEU-IP:8000`. Obs.: alguns celulares exigem `https` para liberar a câmera;
nesse caso use o PC.

---

## 🎛️ Controles
- **Cor** + paleta de presets (nudes, vermelho, rosa, roxo, preto, branco…)
- **Formato**: Quadrada · Redonda · Amendoada · Stiletto
- **Comprimento** e **Largura** (sliders)
- **Opacidade** (slider)
- **Brilho**, **Francesinha**, **Glitter** (toggles)
- **Espelhar** câmera · **Pontos da mão** (debug)
- **Iniciar câmera** · **Capturar** (PNG)

---

## ⚠️ Importante (expectativa realista)
Este é um **protótipo para ter a noção** do efeito. A posição da unha é **estimada
pelas pontas dos dedos** (o MediaPipe não segmenta a unha real), então:
- Funciona melhor com a **mão de frente**, **boa luz** e **fundo neutro**.
- Não é fotorrealista — é uma simulação rápida e leve.

Para realismo de nível comercial seria preciso **segmentação de unha** (SDKs pagos
como Perfect Corp / Banuba). Fora do escopo deste teste gratuito.

---

## 📁 Arquivos
- `index.html` — estrutura da página
- `style.css` — tema escuro rosa/roxo
- `app.js` — câmera + detecção + desenho das unhas
- `run.bat` — sobe o servidor local e abre o navegador
- `PLANO.md` — plano técnico do protótipo
