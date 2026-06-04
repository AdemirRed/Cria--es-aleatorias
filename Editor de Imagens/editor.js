/**
 * Explorar Locais — Image Editor
 * Canvas-based image compositor with layers, transforms, and high-quality export
 * Features: drag-and-drop, layers, resize/rotate, canvas resize, save/restore, HD export
 */

(function () {
    'use strict';

    // ===== State =====
    const state = {
        layers: [],          // Array of layer objects
        selectedLayerId: null,
        canvasWidth: 1080,
        canvasHeight: 1080,
        zoom: 1,
        panX: 0,
        panY: 0,
        lockRatio: true,
        isDragging: false,
        isResizing: false,
        isRotating: false,
        isPanning: false,
        isCanvasResizing: false,   // NEW: canvas edge resize
        canvasResizeEdge: null,    // NEW: which edge/corner
        dragStart: { x: 0, y: 0 },
        resizeHandle: null,
        layerStartState: null,
        idCounter: 0,
        isFirstImage: true,        // NEW: track if first image was added
        autoSaveTimer: null,       // NEW: auto-save debounce
    };

    const SAVE_KEY = 'explorarLocaisEditor_project';
    const AUTOSAVE_DELAY = 2000; // 2 seconds debounce

    // ===== DOM References =====
    const canvas = document.getElementById('editor-canvas');
    const ctx = canvas.getContext('2d');
    const canvasContainer = document.getElementById('canvas-container');
    const canvasArea = document.getElementById('canvas-area');
    const canvasViewport = document.getElementById('canvas-viewport');
    const transformOverlay = document.getElementById('transform-overlay');
    const layersList = document.getElementById('layers-list');
    const fileInput = document.getElementById('file-input');
    const dropOverlay = document.getElementById('drop-overlay');

    // Props
    const propX = document.getElementById('prop-x');
    const propY = document.getElementById('prop-y');
    const propWidth = document.getElementById('prop-width');
    const propHeight = document.getElementById('prop-height');
    const propRotation = document.getElementById('prop-rotation');
    const propRotationSlider = document.getElementById('prop-rotation-slider');
    const propOpacity = document.getElementById('prop-opacity');
    const propOpacitySlider = document.getElementById('prop-opacity-slider');
    const propsContent = document.getElementById('props-content');
    const noSelection = document.querySelector('.no-selection');
    const canvasWidthInput = document.getElementById('canvas-width');
    const canvasHeightInput = document.getElementById('canvas-height');

    // ===== Layer Class =====
    function createLayer(image, name, x, y, w, h, dataUrl) {
        return {
            id: ++state.idCounter,
            name: name || 'Camada ' + state.idCounter,
            image: image,
            dataUrl: dataUrl || '',  // Store base64 for save/restore and clean export
            x: x || 0,
            y: y || 0,
            width: w || image.naturalWidth,
            height: h || image.naturalHeight,
            rotation: 0,
            opacity: 100,
            visible: true,
            flipH: false,
            flipV: false,
            originalWidth: image.naturalWidth,
            originalHeight: image.naturalHeight,
            aspectRatio: image.naturalWidth / image.naturalHeight,
        };
    }

    // ===== Convert any image to dataURL safely =====
    function imageToDataUrl(image) {
        const c = document.createElement('canvas');
        c.width = image.naturalWidth;
        c.height = image.naturalHeight;
        const cx = c.getContext('2d');
        cx.drawImage(image, 0, 0);
        try {
            return c.toDataURL('image/png');
        } catch (e) {
            // If tainted, return empty — shouldn't happen with our flow
            console.warn('Could not convert image to dataURL:', e);
            return '';
        }
    }

    // ===== Canvas Setup =====
    function initCanvas() {
        canvas.width = state.canvasWidth;
        canvas.height = state.canvasHeight;
        canvasContainer.style.width = state.canvasWidth + 'px';
        canvasContainer.style.height = state.canvasHeight + 'px';
        updateExportInfo();
        fitCanvasToView();
        render();
    }

    function setCanvasSize(w, h) {
        state.canvasWidth = Math.max(50, Math.round(w));
        state.canvasHeight = Math.max(50, Math.round(h));
        canvasWidthInput.value = state.canvasWidth;
        canvasHeightInput.value = state.canvasHeight;
        initCanvas();
        scheduleAutoSave();
    }

    function fitCanvasToView() {
        const area = canvasArea.getBoundingClientRect();
        const padding = 80;
        const scaleX = (area.width - padding * 2) / state.canvasWidth;
        const scaleY = (area.height - padding * 2) / state.canvasHeight;
        state.zoom = Math.min(scaleX, scaleY, 1);
        state.panX = 0;
        state.panY = 0;
        applyZoom();
    }

    function applyZoom() {
        canvasContainer.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
        document.getElementById('zoom-level').textContent = Math.round(state.zoom * 100) + '%';
    }

    // ===== Rendering =====
    function render() {
        ctx.clearRect(0, 0, state.canvasWidth, state.canvasHeight);
        
        // White background
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, state.canvasWidth, state.canvasHeight);

        // Draw layers from bottom to top
        for (let i = 0; i < state.layers.length; i++) {
            const layer = state.layers[i];
            if (!layer.visible) continue;

            ctx.save();
            ctx.globalAlpha = layer.opacity / 100;

            // Move to layer center
            const cx = layer.x + layer.width / 2;
            const cy = layer.y + layer.height / 2;
            ctx.translate(cx, cy);
            ctx.rotate((layer.rotation * Math.PI) / 180);
            ctx.scale(layer.flipH ? -1 : 1, layer.flipV ? -1 : 1);

            // Draw image
            ctx.drawImage(
                layer.image,
                -layer.width / 2,
                -layer.height / 2,
                layer.width,
                layer.height
            );

            ctx.restore();
        }

        updateTransformOverlay();
    }

    // ===== Transform Overlay =====
    function updateTransformOverlay() {
        transformOverlay.innerHTML = '';
        
        const selected = getSelectedLayer();
        if (!selected) return;

        const layer = selected;
        
        // Create selection box div
        const box = document.createElement('div');
        box.className = 'selection-box';
        
        box.style.width = layer.width + 'px';
        box.style.height = layer.height + 'px';
        box.style.left = layer.x + 'px';
        box.style.top = layer.y + 'px';
        box.style.transformOrigin = 'center center';
        box.style.transform = `rotate(${layer.rotation}deg)`;

        // Resize handles
        const handles = ['tl', 'tr', 'bl', 'br', 'tm', 'bm', 'ml', 'mr'];
        handles.forEach(pos => {
            const handle = document.createElement('div');
            handle.className = 'handle ' + pos;
            handle.dataset.handle = pos;
            handle.addEventListener('mousedown', onResizeStart);
            box.appendChild(handle);
        });

        // Rotation handle
        const rotHandle = document.createElement('div');
        rotHandle.className = 'handle-rotate';
        rotHandle.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>';
        rotHandle.addEventListener('mousedown', onRotateStart);
        box.appendChild(rotHandle);

        transformOverlay.appendChild(box);
    }

    // ===== Layer Management =====
    function addLayer(image, name, dataUrl) {
        // If first image, resize canvas to match image dimensions
        if (state.isFirstImage && state.layers.length === 0) {
            state.isFirstImage = false;
            const imgW = image.naturalWidth;
            const imgH = image.naturalHeight;
            // Cap canvas to reasonable maxes (8000px)
            const maxDim = 8000;
            let cw = imgW;
            let ch = imgH;
            if (cw > maxDim || ch > maxDim) {
                const scale = Math.min(maxDim / cw, maxDim / ch);
                cw = Math.round(cw * scale);
                ch = Math.round(ch * scale);
            }
            state.canvasWidth = cw;
            state.canvasHeight = ch;
            canvasWidthInput.value = cw;
            canvasHeightInput.value = ch;
            canvas.width = cw;
            canvas.height = ch;
            canvasContainer.style.width = cw + 'px';
            canvasContainer.style.height = ch + 'px';
            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            updateExportInfo();
            fitCanvasToView();
        }

        // Fit image to canvas if larger
        let w = image.naturalWidth;
        let h = image.naturalHeight;
        
        if (w > state.canvasWidth || h > state.canvasHeight) {
            const scale = Math.min(state.canvasWidth / w, state.canvasHeight / h);
            w = Math.round(w * scale);
            h = Math.round(h * scale);
        }

        const x = Math.round((state.canvasWidth - w) / 2);
        const y = Math.round((state.canvasHeight - h) / 2);

        // Ensure we have a dataUrl for save/restore
        if (!dataUrl) {
            dataUrl = imageToDataUrl(image);
        }

        const layer = createLayer(image, name, x, y, w, h, dataUrl);
        state.layers.push(layer);
        selectLayer(layer.id);
        updateLayersList();
        render();
        scheduleAutoSave();
        return layer;
    }

    function removeLayer(id) {
        const index = state.layers.findIndex(l => l.id === id);
        if (index === -1) return;
        
        state.layers.splice(index, 1);
        
        if (state.selectedLayerId === id) {
            state.selectedLayerId = state.layers.length > 0 ? state.layers[state.layers.length - 1].id : null;
        }
        
        updateLayersList();
        updatePropertiesPanel();
        render();
        scheduleAutoSave();
    }

    function selectLayer(id) {
        state.selectedLayerId = id;
        updateLayersList();
        updatePropertiesPanel();
        render();
    }

    function getSelectedLayer() {
        return state.layers.find(l => l.id === state.selectedLayerId) || null;
    }

    function moveLayerOrder(id, direction) {
        const index = state.layers.findIndex(l => l.id === id);
        if (index === -1) return;

        let newIndex;
        if (direction === 'up') newIndex = Math.min(index + 1, state.layers.length - 1);
        else if (direction === 'down') newIndex = Math.max(index - 1, 0);
        else if (direction === 'top') newIndex = state.layers.length - 1;
        else if (direction === 'bottom') newIndex = 0;

        const [layer] = state.layers.splice(index, 1);
        state.layers.splice(newIndex, 0, layer);
        updateLayersList();
        render();
        scheduleAutoSave();
    }

    // ===== Layers List UI =====
    function updateLayersList() {
        // Check if there are layers
        if (state.layers.length === 0) {
            layersList.innerHTML = `
                <div class="empty-layers">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                        <circle cx="8.5" cy="8.5" r="1.5"/>
                        <polyline points="21 15 16 10 5 21"/>
                    </svg>
                    <p>Arraste imagens aqui<br>ou clique em <strong>+</strong></p>
                </div>
            `;
            return;
        }

        layersList.innerHTML = '';
        
        // Render from top to bottom (reverse order)
        for (let i = state.layers.length - 1; i >= 0; i--) {
            const layer = state.layers[i];
            const item = document.createElement('div');
            item.className = 'layer-item' + (layer.id === state.selectedLayerId ? ' selected' : '');
            item.dataset.layerId = layer.id;
            item.draggable = true;

            // Create thumbnail
            const thumbCanvas = document.createElement('canvas');
            thumbCanvas.width = 36;
            thumbCanvas.height = 36;
            const thumbCtx = thumbCanvas.getContext('2d');
            
            const scale = Math.min(36 / layer.originalWidth, 36 / layer.originalHeight);
            const tw = layer.originalWidth * scale;
            const th = layer.originalHeight * scale;
            thumbCtx.drawImage(layer.image, (36 - tw) / 2, (36 - th) / 2, tw, th);

            item.innerHTML = `
                <div class="layer-thumb"></div>
                <div class="layer-info">
                    <div class="layer-name">${escapeHtml(layer.name)}</div>
                    <div class="layer-dims">${layer.originalWidth} × ${layer.originalHeight}</div>
                </div>
                <div class="layer-actions">
                    <button class="layer-action-btn toggle-vis ${layer.visible ? '' : 'hidden-layer'}" data-layer-id="${layer.id}" title="${layer.visible ? 'Ocultar' : 'Mostrar'}">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            ${layer.visible
                                ? '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>'
                                : '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>'
                            }
                        </svg>
                    </button>
                </div>
            `;

            item.querySelector('.layer-thumb').appendChild(thumbCanvas);

            // Click to select
            item.addEventListener('click', (e) => {
                if (e.target.closest('.layer-action-btn')) return;
                selectLayer(layer.id);
            });

            // Toggle visibility
            item.querySelector('.toggle-vis').addEventListener('click', (e) => {
                e.stopPropagation();
                layer.visible = !layer.visible;
                updateLayersList();
                render();
                scheduleAutoSave();
            });

            // Drag and drop for reordering
            item.addEventListener('dragstart', (e) => {
                item.classList.add('dragging');
                e.dataTransfer.setData('text/plain', layer.id);
                e.dataTransfer.effectAllowed = 'move';
            });
            item.addEventListener('dragend', () => {
                item.classList.remove('dragging');
            });
            item.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
            });
            item.addEventListener('drop', (e) => {
                e.preventDefault();
                const fromId = parseInt(e.dataTransfer.getData('text/plain'));
                const toId = layer.id;
                if (fromId === toId) return;
                
                const fromIndex = state.layers.findIndex(l => l.id === fromId);
                const toIndex = state.layers.findIndex(l => l.id === toId);
                
                const [moved] = state.layers.splice(fromIndex, 1);
                state.layers.splice(toIndex, 0, moved);
                updateLayersList();
                render();
                scheduleAutoSave();
            });

            layersList.appendChild(item);
        }
    }

    // ===== Properties Panel =====
    function updatePropertiesPanel() {
        const layer = getSelectedLayer();
        
        if (!layer) {
            propsContent.classList.add('hidden');
            noSelection.style.display = '';
            return;
        }

        propsContent.classList.remove('hidden');
        noSelection.style.display = 'none';

        propX.value = Math.round(layer.x);
        propY.value = Math.round(layer.y);
        propWidth.value = Math.round(layer.width);
        propHeight.value = Math.round(layer.height);
        propRotation.value = Math.round(layer.rotation);
        propRotationSlider.value = Math.round(layer.rotation);
        propOpacity.value = Math.round(layer.opacity);
        propOpacitySlider.value = Math.round(layer.opacity);
    }

    // ===== Properties Event Handlers =====
    function onPropChange(prop, value) {
        const layer = getSelectedLayer();
        if (!layer) return;

        value = parseFloat(value);
        if (isNaN(value)) return;

        switch (prop) {
            case 'x':
                layer.x = value;
                break;
            case 'y':
                layer.y = value;
                break;
            case 'width':
                if (state.lockRatio) {
                    const ratio = layer.height / layer.width;
                    layer.width = Math.max(1, value);
                    layer.height = Math.round(layer.width * ratio);
                    propHeight.value = Math.round(layer.height);
                } else {
                    layer.width = Math.max(1, value);
                }
                break;
            case 'height':
                if (state.lockRatio) {
                    const ratio = layer.width / layer.height;
                    layer.height = Math.max(1, value);
                    layer.width = Math.round(layer.height * ratio);
                    propWidth.value = Math.round(layer.width);
                } else {
                    layer.height = Math.max(1, value);
                }
                break;
            case 'rotation':
                layer.rotation = value;
                propRotationSlider.value = value;
                propRotation.value = Math.round(value);
                break;
            case 'opacity':
                layer.opacity = Math.max(0, Math.min(100, value));
                propOpacitySlider.value = layer.opacity;
                propOpacity.value = Math.round(layer.opacity);
                break;
        }

        render();
        scheduleAutoSave();
    }

    // Wire up property inputs
    propX.addEventListener('input', () => onPropChange('x', propX.value));
    propY.addEventListener('input', () => onPropChange('y', propY.value));
    propWidth.addEventListener('input', () => onPropChange('width', propWidth.value));
    propHeight.addEventListener('input', () => onPropChange('height', propHeight.value));
    propRotation.addEventListener('input', () => onPropChange('rotation', propRotation.value));
    propRotationSlider.addEventListener('input', () => onPropChange('rotation', propRotationSlider.value));
    propOpacity.addEventListener('input', () => onPropChange('opacity', propOpacity.value));
    propOpacitySlider.addEventListener('input', () => onPropChange('opacity', propOpacitySlider.value));

    // Lock ratio toggle
    document.getElementById('prop-lock-ratio').addEventListener('click', function () {
        state.lockRatio = !state.lockRatio;
        this.classList.toggle('active', state.lockRatio);
    });

    // Rotation presets
    document.querySelectorAll('.rot-preset').forEach(btn => {
        btn.addEventListener('click', () => {
            onPropChange('rotation', btn.dataset.rot);
        });
    });

    // ===== Mouse Interaction on Canvas =====
    function getCanvasCoords(e) {
        const rect = canvas.getBoundingClientRect();
        const scaleX = state.canvasWidth / rect.width;
        const scaleY = state.canvasHeight / rect.height;
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    }

    function hitTest(x, y) {
        // Test from top layer down
        for (let i = state.layers.length - 1; i >= 0; i--) {
            const layer = state.layers[i];
            if (!layer.visible) continue;

            // Transform point to layer's local space
            const cx = layer.x + layer.width / 2;
            const cy = layer.y + layer.height / 2;
            const angle = -(layer.rotation * Math.PI) / 180;
            
            const dx = x - cx;
            const dy = y - cy;
            const localX = dx * Math.cos(angle) - dy * Math.sin(angle) + layer.width / 2;
            const localY = dx * Math.sin(angle) + dy * Math.cos(angle) + layer.height / 2;

            if (localX >= 0 && localX <= layer.width && localY >= 0 && localY <= layer.height) {
                return layer;
            }
        }
        return null;
    }

    // ===== Canvas Edge Resize Detection =====
    function getCanvasEdge(e) {
        const containerRect = canvasContainer.getBoundingClientRect();
        const threshold = 8; // pixels from edge to trigger resize
        const x = e.clientX;
        const y = e.clientY;
        const left = containerRect.left;
        const right = containerRect.right;
        const top = containerRect.top;
        const bottom = containerRect.bottom;

        const nearRight = Math.abs(x - right) < threshold;
        const nearBottom = Math.abs(y - bottom) < threshold;
        const nearLeft = Math.abs(x - left) < threshold;
        const nearTop = Math.abs(y - top) < threshold;

        // Only allow right / bottom / bottom-right for intuitive resize
        if (nearRight && nearBottom) return 'br';
        if (nearRight && y > top && y < bottom) return 'r';
        if (nearBottom && x > left && x < right) return 'b';

        return null;
    }

    // ===== Canvas Area Mouse Events (edge resize + pan) =====
    canvasArea.addEventListener('mousemove', (e) => {
        if (state.isDragging || state.isResizing || state.isRotating || state.isPanning || state.isCanvasResizing) return;
        
        const edge = getCanvasEdge(e);
        if (edge === 'br') canvasArea.style.cursor = 'nwse-resize';
        else if (edge === 'r') canvasArea.style.cursor = 'ew-resize';
        else if (edge === 'b') canvasArea.style.cursor = 'ns-resize';
        else canvasArea.style.cursor = '';
    });

    canvasArea.addEventListener('mousedown', (e) => {
        // Check if clicking on canvas edge for resize
        const edge = getCanvasEdge(e);
        if (edge && e.button === 0) {
            e.preventDefault();
            e.stopPropagation();
            state.isCanvasResizing = true;
            state.canvasResizeEdge = edge;
            state.dragStart = { x: e.clientX, y: e.clientY };
            state.layerStartState = {
                width: state.canvasWidth,
                height: state.canvasHeight
            };
            return;
        }
    });

    // ===== Canvas Mouse Events =====
    canvas.addEventListener('mousedown', (e) => {
        if (e.button === 1) {
            // Middle click - pan
            state.isPanning = true;
            state.dragStart = { x: e.clientX - state.panX, y: e.clientY - state.panY };
            document.body.classList.add('canvas-dragging');
            e.preventDefault();
            return;
        }

        if (e.button !== 0) return;

        const coords = getCanvasCoords(e);
        const hitLayer = hitTest(coords.x, coords.y);

        if (hitLayer) {
            selectLayer(hitLayer.id);
            state.isDragging = true;
            state.dragStart = {
                x: coords.x - hitLayer.x,
                y: coords.y - hitLayer.y
            };
            state.layerStartState = { ...hitLayer };
        } else {
            selectLayer(null);
            // Start panning with left click on empty area
            state.isPanning = true;
            state.dragStart = { x: e.clientX - state.panX, y: e.clientY - state.panY };
            document.body.classList.add('canvas-dragging');
        }
    });

    document.addEventListener('mousemove', (e) => {
        // Canvas edge resize
        if (state.isCanvasResizing) {
            const dx = (e.clientX - state.dragStart.x) / state.zoom;
            const dy = (e.clientY - state.dragStart.y) / state.zoom;
            const startState = state.layerStartState;
            const edge = state.canvasResizeEdge;

            let newW = startState.width;
            let newH = startState.height;

            if (edge === 'r' || edge === 'br') newW = Math.max(50, Math.round(startState.width + dx));
            if (edge === 'b' || edge === 'br') newH = Math.max(50, Math.round(startState.height + dy));

            state.canvasWidth = newW;
            state.canvasHeight = newH;
            canvasWidthInput.value = newW;
            canvasHeightInput.value = newH;
            canvas.width = newW;
            canvas.height = newH;
            canvasContainer.style.width = newW + 'px';
            canvasContainer.style.height = newH + 'px';
            updateExportInfo();
            render();
            return;
        }

        if (state.isPanning) {
            state.panX = e.clientX - state.dragStart.x;
            state.panY = e.clientY - state.dragStart.y;
            applyZoom();
            return;
        }

        if (state.isDragging) {
            const coords = getCanvasCoords(e);
            const layer = getSelectedLayer();
            if (!layer) return;

            layer.x = coords.x - state.dragStart.x;
            layer.y = coords.y - state.dragStart.y;

            // Snapping to center
            const cx = layer.x + layer.width / 2;
            const cy = layer.y + layer.height / 2;
            const canvasCx = state.canvasWidth / 2;
            const canvasCy = state.canvasHeight / 2;
            const snapThreshold = 8 / state.zoom;

            if (Math.abs(cx - canvasCx) < snapThreshold) {
                layer.x = canvasCx - layer.width / 2;
            }
            if (Math.abs(cy - canvasCy) < snapThreshold) {
                layer.y = canvasCy - layer.height / 2;
            }
            // Snap edges
            if (Math.abs(layer.x) < snapThreshold) layer.x = 0;
            if (Math.abs(layer.y) < snapThreshold) layer.y = 0;
            if (Math.abs(layer.x + layer.width - state.canvasWidth) < snapThreshold) layer.x = state.canvasWidth - layer.width;
            if (Math.abs(layer.y + layer.height - state.canvasHeight) < snapThreshold) layer.y = state.canvasHeight - layer.height;

            updatePropertiesPanel();
            render();
            return;
        }

        if (state.isResizing) {
            handleResize(e);
            return;
        }

        if (state.isRotating) {
            handleRotation(e);
            return;
        }
    });

    document.addEventListener('mouseup', () => {
        if (state.isCanvasResizing) {
            state.isCanvasResizing = false;
            state.canvasResizeEdge = null;
            state.layerStartState = null;
            scheduleAutoSave();
        }
        if (state.isDragging) {
            scheduleAutoSave();
        }
        if (state.isResizing) {
            scheduleAutoSave();
        }
        if (state.isRotating) {
            scheduleAutoSave();
        }
        state.isDragging = false;
        state.isResizing = false;
        state.isRotating = false;
        state.isPanning = false;
        state.layerStartState = null;
        document.body.classList.remove('canvas-dragging');
    });

    // ===== Resize Handling =====
    function onResizeStart(e) {
        e.stopPropagation();
        e.preventDefault();
        
        const layer = getSelectedLayer();
        if (!layer) return;

        state.isResizing = true;
        state.resizeHandle = e.target.dataset.handle;
        state.layerStartState = { ...layer };
        state.dragStart = { x: e.clientX, y: e.clientY };
    }

    function handleResize(e) {
        const layer = getSelectedLayer();
        if (!layer || !state.layerStartState) return;

        const start = state.layerStartState;
        const dx = (e.clientX - state.dragStart.x) / state.zoom;
        const dy = (e.clientY - state.dragStart.y) / state.zoom;
        const handle = state.resizeHandle;

        // Account for rotation when calculating delta
        const angle = -(start.rotation * Math.PI) / 180;
        const rdx = dx * Math.cos(angle) - dy * Math.sin(angle);
        const rdy = dx * Math.sin(angle) + dy * Math.cos(angle);

        let newX = start.x;
        let newY = start.y;
        let newW = start.width;
        let newH = start.height;

        if (handle.includes('r')) {
            newW = Math.max(20, start.width + rdx);
        }
        if (handle.includes('l')) {
            newW = Math.max(20, start.width - rdx);
            newX = start.x + (start.width - newW);
        }
        if (handle.includes('b')) {
            newH = Math.max(20, start.height + rdy);
        }
        if (handle.includes('t')) {
            newH = Math.max(20, start.height - rdy);
            newY = start.y + (start.height - newH);
        }

        // Maintain aspect ratio if locked
        if (state.lockRatio && (handle === 'tl' || handle === 'tr' || handle === 'bl' || handle === 'br')) {
            const ratio = start.aspectRatio;
            if (Math.abs(rdx) > Math.abs(rdy)) {
                newH = newW / ratio;
                if (handle.includes('t')) {
                    newY = start.y + start.height - newH;
                }
            } else {
                newW = newH * ratio;
                if (handle.includes('l')) {
                    newX = start.x + start.width - newW;
                }
            }
        }

        layer.x = newX;
        layer.y = newY;
        layer.width = Math.max(20, newW);
        layer.height = Math.max(20, newH);

        updatePropertiesPanel();
        render();
    }

    // ===== Rotation Handling =====
    function onRotateStart(e) {
        e.stopPropagation();
        e.preventDefault();
        
        const layer = getSelectedLayer();
        if (!layer) return;

        state.isRotating = true;
        state.layerStartState = { ...layer };
        
        const rect = canvas.getBoundingClientRect();
        const cx = rect.left + ((layer.x + layer.width / 2) / state.canvasWidth) * rect.width;
        const cy = rect.top + ((layer.y + layer.height / 2) / state.canvasHeight) * rect.height;
        
        state.rotateCenter = { x: cx, y: cy };
        state.rotateStartAngle = Math.atan2(e.clientY - cy, e.clientX - cx) * (180 / Math.PI);
    }

    function handleRotation(e) {
        const layer = getSelectedLayer();
        if (!layer || !state.layerStartState) return;

        const center = state.rotateCenter;
        const currentAngle = Math.atan2(e.clientY - center.y, e.clientX - center.x) * (180 / Math.PI);
        let delta = currentAngle - state.rotateStartAngle;

        // Snap to 15 degree increments when holding shift
        if (e.shiftKey) {
            delta = Math.round(delta / 15) * 15;
        }

        layer.rotation = state.layerStartState.rotation + delta;

        // Normalize to -360 to 360
        while (layer.rotation > 360) layer.rotation -= 360;
        while (layer.rotation < -360) layer.rotation += 360;

        updatePropertiesPanel();
        render();
    }

    // ===== Zoom =====
    canvasArea.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.05 : 0.05;
        state.zoom = Math.max(0.1, Math.min(5, state.zoom + delta));
        applyZoom();
    }, { passive: false });

    document.getElementById('zoom-in').addEventListener('click', () => {
        state.zoom = Math.min(5, state.zoom + 0.1);
        applyZoom();
    });

    document.getElementById('zoom-out').addEventListener('click', () => {
        state.zoom = Math.max(0.1, state.zoom - 0.1);
        applyZoom();
    });

    document.getElementById('zoom-fit').addEventListener('click', fitCanvasToView);

    // ===== File Input & Drag-Drop =====
    document.getElementById('btn-add-image').addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
        fileInput.value = '';
    });

    // Drag and drop on entire app
    let dragCounter = 0;
    
    document.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        if (e.dataTransfer.types.includes('Files')) {
            dropOverlay.classList.remove('hidden');
        }
    });

    document.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter === 0) {
            dropOverlay.classList.add('hidden');
        }
    });

    document.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
    });

    document.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        dropOverlay.classList.add('hidden');
        
        if (e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files);
        }
    });

    function handleFiles(files) {
        for (const file of files) {
            if (!file.type.startsWith('image/')) continue;
            
            const reader = new FileReader();
            reader.onload = (e) => {
                const dataUrl = e.target.result;
                const img = new Image();
                img.onload = () => {
                    const name = file.name.replace(/\.[^/.]+$/, '');
                    addLayer(img, name, dataUrl);
                };
                img.src = dataUrl;
            };
            reader.readAsDataURL(file);
        }
    }

    // ===== Load image as dataURL via fetch (avoids tainted canvas) =====
    function loadImageAsDataUrl(url) {
        return fetch(url)
            .then(response => {
                if (!response.ok) throw new Error('Failed to load: ' + url);
                return response.blob();
            })
            .then(blob => {
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
            })
            .then(dataUrl => {
                return new Promise((resolve, reject) => {
                    const img = new Image();
                    img.onload = () => resolve({ image: img, dataUrl: dataUrl });
                    img.onerror = reject;
                    img.src = dataUrl;
                });
            });
    }

    // ===== Preset Buttons =====
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            const w = parseInt(this.dataset.width);
            const h = parseInt(this.dataset.height);
            setCanvasSize(w, h);
        });
    });

    document.getElementById('apply-size').addEventListener('click', () => {
        document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
        setCanvasSize(
            parseInt(canvasWidthInput.value) || 1080,
            parseInt(canvasHeightInput.value) || 1080
        );
    });

    // ===== Quick Action Buttons =====
    document.getElementById('btn-add-frame').addEventListener('click', () => {
        // Load the frame image via fetch to avoid tainted canvas
        const frameUrl = '../00%20Quadro%20Explorarlocais_upscayl_5x_high-fidelity-4x.png';
        
        loadImageAsDataUrl(frameUrl)
            .then(({ image, dataUrl }) => {
                const layer = addLayer(image, 'Quadro Explorar Locais', dataUrl);
                // Fit frame to canvas
                layer.x = 0;
                layer.y = 0;
                layer.width = state.canvasWidth;
                layer.height = state.canvasHeight;
                updatePropertiesPanel();
                render();
                scheduleAutoSave();
            })
            .catch(() => {
                // Fallback: let user pick the file manually
                alert('Não foi possível carregar o quadro automaticamente.\nPor favor, arraste o arquivo "00 Quadro Explorarlocais..." diretamente para o editor.');
            });
    });

    document.getElementById('btn-fit-to-canvas').addEventListener('click', () => {
        const layer = getSelectedLayer();
        if (!layer) return;
        layer.x = 0;
        layer.y = 0;
        layer.width = state.canvasWidth;
        layer.height = state.canvasHeight;
        updatePropertiesPanel();
        render();
        scheduleAutoSave();
    });

    document.getElementById('btn-center').addEventListener('click', () => {
        const layer = getSelectedLayer();
        if (!layer) return;
        layer.x = (state.canvasWidth - layer.width) / 2;
        layer.y = (state.canvasHeight - layer.height) / 2;
        updatePropertiesPanel();
        render();
        scheduleAutoSave();
    });

    document.getElementById('btn-delete-layer').addEventListener('click', () => {
        if (state.selectedLayerId) {
            removeLayer(state.selectedLayerId);
        }
    });

    // ===== Layer Order Buttons =====
    document.getElementById('btn-bring-front').addEventListener('click', () => {
        if (state.selectedLayerId) moveLayerOrder(state.selectedLayerId, 'top');
    });
    document.getElementById('btn-bring-up').addEventListener('click', () => {
        if (state.selectedLayerId) moveLayerOrder(state.selectedLayerId, 'up');
    });
    document.getElementById('btn-send-down').addEventListener('click', () => {
        if (state.selectedLayerId) moveLayerOrder(state.selectedLayerId, 'down');
    });
    document.getElementById('btn-send-back').addEventListener('click', () => {
        if (state.selectedLayerId) moveLayerOrder(state.selectedLayerId, 'bottom');
    });

    // ===== Flip Buttons =====
    document.getElementById('btn-flip-h').addEventListener('click', () => {
        const layer = getSelectedLayer();
        if (!layer) return;
        layer.flipH = !layer.flipH;
        render();
        scheduleAutoSave();
    });
    document.getElementById('btn-flip-v').addEventListener('click', () => {
        const layer = getSelectedLayer();
        if (!layer) return;
        layer.flipV = !layer.flipV;
        render();
        scheduleAutoSave();
    });

    // ===== Export =====
    document.getElementById('btn-export').addEventListener('click', exportImage);

    // ===== Save / New Project Buttons =====
    document.getElementById('btn-save-project').addEventListener('click', saveProject);
    document.getElementById('btn-new-project').addEventListener('click', () => {
        if (state.layers.length > 0 && !confirm('Tem certeza que deseja iniciar um novo projeto? O projeto atual será descartado.')) {
            return;
        }
        clearProject();
    });

    document.getElementById('export-format').addEventListener('change', function () {
        const qualityGroup = document.getElementById('quality-group');
        qualityGroup.style.display = this.value === 'png' ? 'none' : '';
        updateExportInfo();
    });

    document.getElementById('export-quality-slider').addEventListener('input', function () {
        document.getElementById('export-quality').value = this.value;
        updateExportInfo();
    });
    document.getElementById('export-quality').addEventListener('input', function () {
        document.getElementById('export-quality-slider').value = this.value;
        updateExportInfo();
    });
    document.getElementById('export-scale').addEventListener('change', updateExportInfo);

    function updateExportInfo() {
        const format = document.getElementById('export-format').value;
        const scale = parseInt(document.getElementById('export-scale').value);
        const w = state.canvasWidth * scale;
        const h = state.canvasHeight * scale;
        
        document.getElementById('export-info').innerHTML = `
            <strong>Saída:</strong> ${w} × ${h}px<br>
            <strong>Formato:</strong> ${format.toUpperCase()}<br>
            <strong>Escala:</strong> ${scale}x
        `;
    }

    function exportImage() {
        const modal = document.getElementById('export-modal');
        const progressFill = document.getElementById('export-progress-fill');
        const statusText = document.getElementById('export-status');

        modal.classList.remove('hidden');
        progressFill.style.width = '0%';
        statusText.textContent = 'Preparando exportação...';

        const format = document.getElementById('export-format').value;
        const quality = parseInt(document.getElementById('export-quality').value) / 100;
        const scale = parseInt(document.getElementById('export-scale').value);

        // Create export canvas — uses clean dataURL images to avoid taint
        const exportCanvas = document.createElement('canvas');
        exportCanvas.width = state.canvasWidth * scale;
        exportCanvas.height = state.canvasHeight * scale;
        const exportCtx = exportCanvas.getContext('2d');

        // Enable high-quality rendering
        exportCtx.imageSmoothingEnabled = true;
        exportCtx.imageSmoothingQuality = 'high';

        requestAnimationFrame(() => {
            progressFill.style.width = '30%';
            statusText.textContent = 'Renderizando camadas...';

            setTimeout(() => {
                // Scale context
                exportCtx.scale(scale, scale);

                // White background
                exportCtx.fillStyle = '#ffffff';
                exportCtx.fillRect(0, 0, state.canvasWidth, state.canvasHeight);

                // Draw all visible layers using their stored dataURL images
                for (const layer of state.layers) {
                    if (!layer.visible) continue;

                    exportCtx.save();
                    exportCtx.globalAlpha = layer.opacity / 100;

                    const cx = layer.x + layer.width / 2;
                    const cy = layer.y + layer.height / 2;
                    exportCtx.translate(cx, cy);
                    exportCtx.rotate((layer.rotation * Math.PI) / 180);
                    exportCtx.scale(layer.flipH ? -1 : 1, layer.flipV ? -1 : 1);

                    exportCtx.drawImage(
                        layer.image,
                        -layer.width / 2,
                        -layer.height / 2,
                        layer.width,
                        layer.height
                    );

                    exportCtx.restore();
                }

                progressFill.style.width = '70%';
                statusText.textContent = 'Codificando imagem...';

                setTimeout(() => {
                    let mimeType = 'image/png';
                    let ext = 'png';
                    if (format === 'jpeg') { mimeType = 'image/jpeg'; ext = 'jpg'; }
                    if (format === 'webp') { mimeType = 'image/webp'; ext = 'webp'; }

                    try {
                        exportCanvas.toBlob((blob) => {
                            if (!blob) {
                                statusText.textContent = 'Erro ao exportar! Tente novamente.';
                                setTimeout(() => modal.classList.add('hidden'), 2000);
                                return;
                            }
                            progressFill.style.width = '100%';
                            statusText.textContent = 'Download iniciado!';

                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `explorar_locais_${state.canvasWidth}x${state.canvasHeight}_${Date.now()}.${ext}`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(url);

                            setTimeout(() => {
                                modal.classList.add('hidden');
                            }, 1000);
                        }, mimeType, format === 'png' ? undefined : quality);
                    } catch (err) {
                        console.error('Export error:', err);
                        statusText.textContent = 'Erro: ' + err.message;
                        setTimeout(() => modal.classList.add('hidden'), 3000);
                    }
                }, 100);
            }, 100);
        });
    }

    // ===== SAVE / RESTORE PROJECT =====
    function serializeProject() {
        const data = {
            version: 2,
            canvasWidth: state.canvasWidth,
            canvasHeight: state.canvasHeight,
            idCounter: state.idCounter,
            selectedLayerId: state.selectedLayerId,
            layers: state.layers.map(l => ({
                id: l.id,
                name: l.name,
                dataUrl: l.dataUrl,
                x: l.x,
                y: l.y,
                width: l.width,
                height: l.height,
                rotation: l.rotation,
                opacity: l.opacity,
                visible: l.visible,
                flipH: l.flipH,
                flipV: l.flipV,
                originalWidth: l.originalWidth,
                originalHeight: l.originalHeight,
            })),
        };
        return data;
    }

    function saveProject() {
        try {
            const data = serializeProject();
            const json = JSON.stringify(data);
            localStorage.setItem(SAVE_KEY, json);
            showSaveIndicator('Projeto salvo!');
        } catch (e) {
            console.warn('Falha ao salvar projeto:', e);
            // If localStorage is full, try clearing old data
            if (e.name === 'QuotaExceededError') {
                showSaveIndicator('⚠️ Projeto muito grande para salvar automaticamente');
            }
        }
    }

    function scheduleAutoSave() {
        clearTimeout(state.autoSaveTimer);
        state.autoSaveTimer = setTimeout(saveProject, AUTOSAVE_DELAY);
    }

    function loadProject() {
        try {
            const json = localStorage.getItem(SAVE_KEY);
            if (!json) return false;

            const data = JSON.parse(json);
            if (!data || !data.layers || data.layers.length === 0) return false;

            // Show restore prompt
            return data;
        } catch (e) {
            console.warn('Falha ao carregar projeto:', e);
            return false;
        }
    }

    function restoreProject(data) {
        state.canvasWidth = data.canvasWidth || 1080;
        state.canvasHeight = data.canvasHeight || 1080;
        state.idCounter = data.idCounter || 0;
        state.isFirstImage = false;
        canvasWidthInput.value = state.canvasWidth;
        canvasHeightInput.value = state.canvasHeight;
        canvas.width = state.canvasWidth;
        canvas.height = state.canvasHeight;
        canvasContainer.style.width = state.canvasWidth + 'px';
        canvasContainer.style.height = state.canvasHeight + 'px';

        // Load layers sequentially
        let loaded = 0;
        const total = data.layers.length;
        state.layers = [];

        if (total === 0) {
            updateLayersList();
            updatePropertiesPanel();
            updateExportInfo();
            fitCanvasToView();
            render();
            return;
        }

        data.layers.forEach(layerData => {
            const img = new Image();
            img.onload = () => {
                const layer = {
                    id: layerData.id,
                    name: layerData.name,
                    image: img,
                    dataUrl: layerData.dataUrl,
                    x: layerData.x,
                    y: layerData.y,
                    width: layerData.width,
                    height: layerData.height,
                    rotation: layerData.rotation || 0,
                    opacity: layerData.opacity !== undefined ? layerData.opacity : 100,
                    visible: layerData.visible !== undefined ? layerData.visible : true,
                    flipH: !!layerData.flipH,
                    flipV: !!layerData.flipV,
                    originalWidth: layerData.originalWidth || img.naturalWidth,
                    originalHeight: layerData.originalHeight || img.naturalHeight,
                    aspectRatio: (layerData.originalWidth || img.naturalWidth) / (layerData.originalHeight || img.naturalHeight),
                };
                state.layers.push(layer);
                loaded++;

                if (loaded === total) {
                    // Sort by original order (by id)
                    state.layers.sort((a, b) => {
                        const aIdx = data.layers.findIndex(d => d.id === a.id);
                        const bIdx = data.layers.findIndex(d => d.id === b.id);
                        return aIdx - bIdx;
                    });
                    state.selectedLayerId = data.selectedLayerId || null;
                    updateLayersList();
                    updatePropertiesPanel();
                    updateExportInfo();
                    fitCanvasToView();
                    render();
                    showSaveIndicator('Projeto restaurado!');
                }
            };
            img.onerror = () => {
                loaded++;
                console.warn('Falha ao carregar camada:', layerData.name);
                if (loaded === total) {
                    state.layers.sort((a, b) => {
                        const aIdx = data.layers.findIndex(d => d.id === a.id);
                        const bIdx = data.layers.findIndex(d => d.id === b.id);
                        return aIdx - bIdx;
                    });
                    updateLayersList();
                    updatePropertiesPanel();
                    updateExportInfo();
                    fitCanvasToView();
                    render();
                }
            };
            img.src = layerData.dataUrl;
        });
    }

    function clearProject() {
        localStorage.removeItem(SAVE_KEY);
        state.layers = [];
        state.selectedLayerId = null;
        state.idCounter = 0;
        state.isFirstImage = true;
        setCanvasSize(1080, 1080);
        document.getElementById('preset-instagram').classList.add('active');
        updateLayersList();
        updatePropertiesPanel();
        render();
    }

    // Save indicator toast
    function showSaveIndicator(msg) {
        let indicator = document.getElementById('save-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'save-indicator';
            indicator.style.cssText = `
                position: fixed;
                bottom: 60px;
                right: 20px;
                background: rgba(108, 92, 231, 0.9);
                color: #fff;
                padding: 8px 16px;
                border-radius: 8px;
                font-family: var(--font);
                font-size: 12px;
                font-weight: 600;
                z-index: 9999;
                opacity: 0;
                transform: translateY(10px);
                transition: opacity 0.3s, transform 0.3s;
                pointer-events: none;
                backdrop-filter: blur(8px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            `;
            document.body.appendChild(indicator);
        }
        indicator.textContent = msg;
        indicator.style.opacity = '1';
        indicator.style.transform = 'translateY(0)';

        clearTimeout(indicator._hideTimer);
        indicator._hideTimer = setTimeout(() => {
            indicator.style.opacity = '0';
            indicator.style.transform = 'translateY(10px)';
        }, 2000);
    }

    // ===== Keyboard Shortcuts =====
    document.addEventListener('keydown', (e) => {
        const layer = getSelectedLayer();
        
        // Don't handle if typing in input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

        const step = e.shiftKey ? 10 : 1;

        switch (e.key) {
            case 'Delete':
            case 'Backspace':
                if (layer) {
                    e.preventDefault();
                    removeLayer(layer.id);
                }
                break;
            case 'ArrowUp':
                if (layer) { e.preventDefault(); layer.y -= step; updatePropertiesPanel(); render(); scheduleAutoSave(); }
                break;
            case 'ArrowDown':
                if (layer) { e.preventDefault(); layer.y += step; updatePropertiesPanel(); render(); scheduleAutoSave(); }
                break;
            case 'ArrowLeft':
                if (layer) { e.preventDefault(); layer.x -= step; updatePropertiesPanel(); render(); scheduleAutoSave(); }
                break;
            case 'ArrowRight':
                if (layer) { e.preventDefault(); layer.x += step; updatePropertiesPanel(); render(); scheduleAutoSave(); }
                break;
            case 'Escape':
                selectLayer(null);
                break;
        }

        // Ctrl shortcuts
        if (e.ctrlKey || e.metaKey) {
            switch (e.key) {
                case 'e':
                    e.preventDefault();
                    exportImage();
                    break;
                case 's':
                    e.preventDefault();
                    saveProject();
                    break;
                case '=':
                case '+':
                    e.preventDefault();
                    state.zoom = Math.min(5, state.zoom + 0.1);
                    applyZoom();
                    break;
                case '-':
                    e.preventDefault();
                    state.zoom = Math.max(0.1, state.zoom - 0.1);
                    applyZoom();
                    break;
                case '0':
                    e.preventDefault();
                    fitCanvasToView();
                    break;
            }
        }
    });

    // ===== Utility =====
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ===== Window Resize =====
    window.addEventListener('resize', () => {
        clearTimeout(window._resizeTimer);
        window._resizeTimer = setTimeout(fitCanvasToView, 150);
    });

    // ===== Warn before leaving =====
    window.addEventListener('beforeunload', (e) => {
        if (state.layers.length > 0) {
            saveProject(); // Force save before leaving
        }
    });

    // ===== Initialize =====
    function init() {
        document.getElementById('quality-group').style.display = 'none';

        // Try to restore saved project
        const savedData = loadProject();
        if (savedData) {
            // Create restore banner
            const banner = document.createElement('div');
            banner.id = 'restore-banner';
            banner.style.cssText = `
                position: fixed;
                top: 60px;
                left: 50%;
                transform: translateX(-50%);
                background: linear-gradient(135deg, #1a1a27 0%, #222234 100%);
                border: 1px solid #6c5ce7;
                border-radius: 12px;
                padding: 16px 24px;
                display: flex;
                align-items: center;
                gap: 16px;
                z-index: 999;
                box-shadow: 0 8px 32px rgba(108, 92, 231, 0.3);
                font-family: 'Inter', sans-serif;
                animation: fadeIn 0.3s ease;
            `;
            banner.innerHTML = `
                <div style="flex:1">
                    <div style="font-size:14px;font-weight:700;color:#e8e8f0;margin-bottom:4px">
                        📂 Projeto anterior encontrado
                    </div>
                    <div style="font-size:12px;color:#9898b0">
                        ${savedData.layers.length} camada(s) • ${savedData.canvasWidth}×${savedData.canvasHeight}px
                    </div>
                </div>
                <button id="btn-restore-yes" style="
                    padding:8px 20px;background:#6c5ce7;border:none;border-radius:8px;
                    color:#fff;font-weight:700;font-size:13px;cursor:pointer;font-family:inherit;
                ">Restaurar</button>
                <button id="btn-restore-no" style="
                    padding:8px 20px;background:transparent;border:1px solid #2a2a3e;border-radius:8px;
                    color:#9898b0;font-weight:600;font-size:13px;cursor:pointer;font-family:inherit;
                ">Novo projeto</button>
            `;
            document.body.appendChild(banner);

            document.getElementById('btn-restore-yes').addEventListener('click', () => {
                banner.remove();
                restoreProject(savedData);
            });
            document.getElementById('btn-restore-no').addEventListener('click', () => {
                banner.remove();
                clearProject();
            });

            // Still init blank canvas while waiting
            document.getElementById('preset-instagram').classList.add('active');
            initCanvas();
        } else {
            document.getElementById('preset-instagram').classList.add('active');
            initCanvas();
        }
    }

    init();

})();
