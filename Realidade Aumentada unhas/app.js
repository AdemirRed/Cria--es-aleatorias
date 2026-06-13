// Provador de Unhas AR — MediaPipe HandLandmarker (gratuito) + Canvas 2D
import { HandLandmarker, FilesetResolver } from
  'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs';

// ── Elementos ──────────────────────────────────────────────
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const statusEl = document.getElementById('status');
const overlayMsg = document.getElementById('overlayMsg');
const btnIniciar = document.getElementById('btnIniciar');
const btnCapturar = document.getElementById('btnCapturar');

// Controles
const corEl = document.getElementById('cor');
const comprimentoEl = document.getElementById('comprimento');
const larguraEl = document.getElementById('largura');
const opacidadeEl = document.getElementById('opacidade');
const glossEl = document.getElementById('gloss');
const francesEl = document.getElementById('frances');
const glitterEl = document.getElementById('glitter');
const espelharEl = document.getElementById('espelhar');
const flashEl = document.getElementById('flash');
const debugEl = document.getElementById('debug');

// Estado
let handLandmarker = null;
let videoTrack = null;
let rodando = false;
let ultimoTs = -1;
let formaAtual = 'quadrada';

// ── Paleta de presets ──────────────────────────────────────
const PRESETS = ['#e11d74', '#ff5fa2', '#c81d4e', '#7c3aed', '#3b0764', '#111827',
  '#f5d0c5', '#d9a679', '#b76e79', '#ffd1dc', '#ffffff', '#ff2e63'];
const paleta = document.getElementById('paleta');
PRESETS.forEach(c => {
  const s = document.createElement('span');
  s.style.background = c;
  s.title = c;
  s.onclick = () => { corEl.value = c; };
  paleta.appendChild(s);
});

// Formato
document.getElementById('formas').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-forma]');
  if (!b) return;
  formaAtual = b.dataset.forma;
  document.querySelectorAll('#formas button').forEach(x => x.classList.toggle('ativo', x === b));
});

// Sliders → labels
const liga = (el, alvo, fmt) => { const upd = () => document.getElementById(alvo).textContent = fmt(el.value); el.addEventListener('input', upd); upd(); };
liga(comprimentoEl, 'vComprimento', v => Number(v).toFixed(2));
liga(larguraEl, 'vLargura', v => Number(v).toFixed(2));
liga(opacidadeEl, 'vOpacidade', v => v + '%');

// ── Inicialização do modelo ────────────────────────────────
async function carregarModelo() {
  statusEl.textContent = 'Carregando IA...';
  const vision = await FilesetResolver.forVisionTasks(
    'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm'
  );
  const opts = {
    baseOptions: {
      modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
    },
    runningMode: 'VIDEO',
    numHands: 2,
  };
  try {
    handLandmarker = await HandLandmarker.createFromOptions(vision, { ...opts, baseOptions: { ...opts.baseOptions, delegate: 'GPU' } });
  } catch {
    handLandmarker = await HandLandmarker.createFromOptions(vision, { ...opts, baseOptions: { ...opts.baseOptions, delegate: 'CPU' } });
  }
  statusEl.textContent = 'IA pronta';
}

// ── Câmera ─────────────────────────────────────────────────
async function iniciarCamera() {
  try {
    btnIniciar.disabled = true;
    if (!handLandmarker) await carregarModelo();
    statusEl.textContent = 'Abrindo câmera...';
    const stream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: false,
    });
    video.srcObject = stream;
    videoTrack = stream.getVideoTracks()[0];
    await video.play();

    // Flash/lanterna: só habilita se o aparelho suportar 'torch'
    const cap = videoTrack.getCapabilities ? videoTrack.getCapabilities() : {};
    if (!('torch' in cap)) {
      flashEl.disabled = true;
      flashEl.parentElement.title = 'Flash não suportado neste aparelho/câmera';
      flashEl.parentElement.style.opacity = .45;
    } else {
      flashEl.disabled = false;
      flashEl.parentElement.style.opacity = 1;
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    overlayMsg.classList.add('hidden');
    btnCapturar.disabled = false;
    rodando = true;
    statusEl.textContent = 'Ao vivo';
    loop();
  } catch (e) {
    console.error(e);
    statusEl.textContent = 'Erro';
    overlayMsg.querySelector('p').innerHTML = '❌ Não consegui acessar a câmera.<br>Permita o acesso e rode em <b>localhost</b> (não file://).';
    overlayMsg.classList.remove('hidden');
    btnIniciar.disabled = false;
  }
}

// ── Loop de detecção ───────────────────────────────────────
function loop() {
  if (!rodando) return;
  const ts = performance.now();
  let resultado = null;
  if (video.readyState >= 2 && ts !== ultimoTs) {
    ultimoTs = ts;
    try { resultado = handLandmarker.detectForVideo(video, ts); } catch {}
  }
  desenhar(resultado);
  requestAnimationFrame(loop);
}

// ════════════════════════════════════════════════════════════
//  RENDERIZAÇÃO DAS UNHAS (anatomia + silhueta bézier + 3D)
// ════════════════════════════════════════════════════════════

// Dedos: ponta (TIP) e junta distal (DIP) — a unha fica na falange distal.
// ratio = largura da unha relativa à escala da mão (punho→nó do médio).
const DEDOS = [
  { tip: 4,  dip: 3,  ratio: 0.135 }, // polegar (mais larga)
  { tip: 8,  dip: 7,  ratio: 0.112 }, // indicador
  { tip: 12, dip: 11, ratio: 0.118 }, // médio
  { tip: 16, dip: 15, ratio: 0.104 }, // anelar
  { tip: 20, dip: 19, ratio: 0.082 }, // mínimo
];

// ── Helpers de cor ─────────────────────────────────────────
function hex2rgb(h) {
  h = h.replace('#', '');
  if (h.length === 3) h = h.split('').map(c => c + c).join('');
  const n = parseInt(h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
const _clamp = v => v < 0 ? 0 : v > 255 ? 255 : v;
function mixCor(c, t, a) { return [c[0] + (t[0] - c[0]) * a, c[1] + (t[1] - c[1]) * a, c[2] + (t[2] - c[2]) * a]; }
function rgba(c, a) { return `rgba(${_clamp(c[0]) | 0},${_clamp(c[1]) | 0},${_clamp(c[2]) | 0},${a == null ? 1 : a})`; }
const claro = (c, a) => mixCor(c, [255, 255, 255], a);
const escuro = (c, a) => mixCor(c, [0, 0, 0], a);
const frac = v => { v = v - Math.floor(v); return v < 0 ? v + 1 : v; };

function desenhar(resultado) {
  const w = canvas.width, h = canvas.height;
  if (!w) return;
  ctx.clearRect(0, 0, w, h);

  ctx.save();
  if (espelharEl.checked) { ctx.translate(w, 0); ctx.scale(-1, 1); }
  ctx.drawImage(video, 0, 0, w, h);

  if (resultado && resultado.landmarks) {
    const opts = {
      cor: corEl.value,
      comprimento: parseFloat(comprimentoEl.value),
      largura: parseFloat(larguraEl.value),
      opacidade: parseFloat(opacidadeEl.value),
      gloss: glossEl.checked,
      frances: francesEl.checked,
      glitter: glitterEl.checked,
      forma: formaAtual,
      debug: debugEl.checked,
    };
    for (const mao of resultado.landmarks) desenharMao(ctx, mao, w, h, opts);
  }
  ctx.restore();
}

// Desenha as 5 unhas de uma mão
function desenharMao(ctx, lm, w, h, opts) {
  if (!lm || lm.length < 21) return;
  const op = Math.max(0, Math.min(1, opts.opacidade / 100));
  const base = hex2rgb(opts.cor);
  const px = i => lm[i].x * w, py = i => lm[i].y * h;

  // Escala estável da mão (punho → nó do médio)
  const handScale = Math.hypot(px(9) - px(0), py(9) - py(0)) || 1;

  if (opts.debug) {
    ctx.save();
    ctx.fillStyle = 'rgba(124,58,237,.9)';
    for (const p of lm) { ctx.beginPath(); ctx.arc(p.x * w, p.y * h, 3, 0, Math.PI * 2); ctx.fill(); }
    ctx.restore();
  }

  for (let fi = 0; fi < DEDOS.length; fi++) {
    const f = DEDOS[fi];
    const tx = px(f.tip), ty = py(f.tip);
    const dx = tx - px(f.dip), dy = ty - py(f.dip);
    const Lp = Math.hypot(dx, dy);
    if (Lp < 2) continue;
    const ux = dx / Lp, uy = dy / Lp;          // direção dedo (DIP→TIP)
    const ang = Math.atan2(dy, dx);

    const largura = handScale * f.ratio * opts.largura;
    const natLen = Lp * 0.50;                       // comprimento natural (proporcional à ponta)
    const comprimento = natLen * opts.comprimento;
    const half = largura / 2, hl = comprimento / 2;

    // Base (cutícula) ancorada bem perto da ponta do dedo (75% da distância da falange)
    const baseX = px(f.dip) + ux * (Lp * 0.75);
    const baseY = py(f.dip) + uy * (Lp * 0.75);
    const cx = baseX + ux * hl, cy = baseY + uy * hl;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(ang); // +x = direção da ponta
    desenharUnha(ctx, hl, half, comprimento, opts, base, op, fi);
    ctx.restore();
  }
  ctx.globalAlpha = 1;
}

// Silhueta da unha em coords locais: cutícula em -hl, borda livre em +hl
function caminhoUnha(ctx, hl, half, forma) {
  const len = hl * 2;
  const xC = -hl;                    // linha da cutícula
  const xW = -hl + len * 0.30;       // ponto mais largo
  const xS = -hl + len * 0.72;       // "ombro" onde começa a borda livre
  let xT = hl;                       // ápice da ponta
  const Wc = half * 0.82;            // largura na cutícula (mais estreita)
  const Wmax = half;                 // largura máxima
  let Ws;                            // largura no ombro (depende do formato)

  if (forma === 'redonda') { Ws = half * 0.90; }
  else if (forma === 'amendoada') { Ws = half * 0.60; }
  else if (forma === 'stiletto') { Ws = half * 0.42; xT = hl * 1.18; }
  else { Ws = half * 0.97; }         // quadrada (squoval)

  ctx.beginPath();
  ctx.moveTo(xC, -Wc);                                  // cutícula topo
  ctx.quadraticCurveTo(xW, -Wmax, xS, -Ws);            // parede lateral (topo)

  if (forma === 'quadrada') {                           // borda reta + cantos suaves
    ctx.lineTo(xT - half * 0.20, -Ws * 0.99);
    ctx.quadraticCurveTo(xT, -Ws * 0.82, xT, -Ws * 0.42);
    ctx.lineTo(xT, Ws * 0.42);
    ctx.quadraticCurveTo(xT, Ws * 0.82, xT - half * 0.20, Ws * 0.99);
    ctx.lineTo(xS, Ws);
  } else if (forma === 'redonda') {                      // arco suave
    ctx.quadraticCurveTo(xT, -Ws * 0.55, xT, 0);
    ctx.quadraticCurveTo(xT, Ws * 0.55, xS, Ws);
  } else {                                               // amendoada / stiletto (ponta)
    ctx.quadraticCurveTo(xT * 0.90, -Ws * 0.5, xT, 0);
    ctx.quadraticCurveTo(xT * 0.90, Ws * 0.5, xS, Ws);
  }

  ctx.quadraticCurveTo(xW, Wmax, xC, Wc);               // parede lateral (base)
  ctx.quadraticCurveTo(xC - Wc * 0.55, 0, xC, -Wc);     // cutícula convexa
  ctx.closePath();
}

function desenharUnha(ctx, hl, half, len, opts, base, op, fi) {
  const forma = opts.forma;
  const xT = hl * (forma === 'stiletto' ? 1.18 : 1);
  const W = half * 1.5, area = () => ctx.fillRect(-hl * 1.7, -W, hl * 3.4, W * 2);

  // ── Camadas de pintura (recortadas na silhueta) ──
  caminhoUnha(ctx, hl, half, forma);
  ctx.save();
  ctx.clip();

  // 1) Gradiente transversal (barril): centro claro, laterais escuras → volume 3D
  const gb = ctx.createLinearGradient(0, -half, 0, half);
  gb.addColorStop(0, rgba(escuro(base, 0.34)));
  gb.addColorStop(0.5, rgba(claro(base, 0.16)));
  gb.addColorStop(1, rgba(escuro(base, 0.40)));
  ctx.globalAlpha = op; ctx.fillStyle = gb; area();

  // 2) Gradiente longitudinal: sombra na cutícula + leve translucidez na ponta
  const gl = ctx.createLinearGradient(-hl, 0, xT, 0);
  gl.addColorStop(0, 'rgba(0,0,0,0.30)');
  gl.addColorStop(0.20, 'rgba(0,0,0,0)');
  gl.addColorStop(0.82, 'rgba(255,255,255,0)');
  gl.addColorStop(1, 'rgba(255,255,255,0.16)');
  ctx.globalAlpha = op; ctx.fillStyle = gl; area();

  // 3) Lúnula (meia-lua na base)
  ctx.globalAlpha = 0.30 * op; ctx.fillStyle = rgba(claro(base, 0.42));
  ctx.beginPath(); ctx.ellipse(-hl + len * 0.12, 0, len * 0.11, half * 0.60, 0, 0, Math.PI * 2); ctx.fill();

  // 4) Francesinha (sorriso curvo branco na ponta)
  if (opts.frances) {
    const sx = hl - len * 0.30;
    ctx.beginPath();
    ctx.moveTo(sx, -half * 1.3);
    ctx.quadraticCurveTo(sx - len * 0.15, 0, sx, half * 1.3);
    ctx.lineTo(hl * 1.4, half * 1.3); ctx.lineTo(hl * 1.4, -half * 1.3);
    ctx.closePath();
    ctx.globalAlpha = 0.92 * op; ctx.fillStyle = '#ffffff'; ctx.fill();
  }

  // 5) Glitter (determinístico, sem random)
  if (opts.glitter) {
    for (let i = 1; i <= 28; i++) {
      const r1 = frac(Math.sin(i * 12.9898 + fi * 7.13) * 43758.5453);
      const r2 = frac(Math.sin(i * 78.233 + fi * 3.71) * 12543.123);
      const r3 = frac(Math.sin(i * 39.425 + fi * 1.97) * 9817.317);
      const gx = (r1 * 2 - 1) * hl * 0.82;
      const gy = (r2 * 2 - 1) * half * 0.82;
      const rad = Math.max(0.6, half * (0.05 + 0.06 * r3));
      ctx.globalAlpha = (0.35 + 0.65 * r3) * op;
      ctx.fillStyle = r3 > 0.5 ? 'rgba(255,255,255,1)' : 'rgba(255,236,176,1)';
      ctx.beginPath(); ctx.arc(gx, gy, rad, 0, Math.PI * 2); ctx.fill();
    }
  }

  // 6) Brilho especular (mancha suave deslocada p/ cima)
  const sa = opts.gloss ? 0.55 : 0.20;
  const sg = ctx.createRadialGradient(-hl + len * 0.40, -half * 0.42, half * 0.05,
                                      -hl + len * 0.40, -half * 0.42, half * 1.15);
  sg.addColorStop(0, `rgba(255,255,255,${sa})`);
  sg.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.globalAlpha = op; ctx.fillStyle = sg;
  ctx.beginPath(); ctx.ellipse(-hl + len * 0.40, -half * 0.35, len * 0.34, half * 0.52, 0, 0, Math.PI * 2); ctx.fill();

  if (opts.gloss) { // segundo glint perto da ponta (efeito molhado)
    const sg2 = ctx.createRadialGradient(hl * 0.55, half * 0.20, 0, hl * 0.55, half * 0.20, half * 0.55);
    sg2.addColorStop(0, 'rgba(255,255,255,0.40)');
    sg2.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.globalAlpha = op; ctx.fillStyle = sg2;
    ctx.beginPath(); ctx.ellipse(hl * 0.55, half * 0.20, len * 0.12, half * 0.30, 0, 0, Math.PI * 2); ctx.fill();
  }

  ctx.restore(); // fim do clip

  // ── Bordas (fora do clip p/ ficarem nítidas) ──
  caminhoUnha(ctx, hl, half, forma);
  ctx.globalAlpha = op; ctx.lineWidth = Math.max(0.8, half * 0.06);
  ctx.strokeStyle = 'rgba(255,255,255,0.30)'; ctx.stroke();   // rim light

  caminhoUnha(ctx, hl, half, forma);
  ctx.globalAlpha = 0.5 * op; ctx.lineWidth = Math.max(0.6, half * 0.03);
  ctx.strokeStyle = 'rgba(0,0,0,0.22)'; ctx.stroke();          // contorno
  ctx.globalAlpha = 1;
}

// ── Captura ────────────────────────────────────────────────
btnCapturar.addEventListener('click', () => {
  const a = document.createElement('a');
  a.download = `unhas-ar-${Date.now()}.png`;
  a.href = canvas.toDataURL('image/png');
  a.click();
});

// ── Flash / lanterna ───────────────────────────────────────
flashEl.addEventListener('change', async () => {
  if (!videoTrack) return;
  try {
    await videoTrack.applyConstraints({ advanced: [{ torch: flashEl.checked }] });
  } catch (e) {
    console.error('Flash não suportado:', e);
    flashEl.checked = false;
    alert('Este aparelho/câmera não permite ligar o flash pelo navegador.');
  }
});

btnIniciar.addEventListener('click', iniciarCamera);
