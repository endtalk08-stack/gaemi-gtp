(() => {
  const openButton = document.getElementById('sketchPadMenuItem');
  const chatArea = document.getElementById('chatArea');

  if (!openButton || !chatArea) return;

  const createSketchPad = () => {
    const existing = document.getElementById('gaemiSketchPadCard');
    if (existing) {
      existing.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      return;
    }

    const message = document.createElement('section');
    message.className = 'sketch-pad-message';
    message.dataset.chatToolMessage = 'sketch-pad';
    message.setAttribute('aria-label', '스케치');
    message.innerHTML = `
      <div id="gaemiSketchPadCard" class="sketch-pad-card">
        <div class="sketch-pad-head">
          <div>
            <h2 class="sketch-pad-title">스케치</h2>
            <p class="sketch-pad-subtitle">손가락이나 마우스로 바로 그릴 수 있어요.</p>
          </div>
          <button type="button" class="chat-tool-close" data-chat-tool-close aria-label="스케치 닫기" title="닫기">
            <i data-lucide="x" aria-hidden="true"></i>
          </button>
        </div>

        <div class="sketch-pad-toolbar" role="toolbar" aria-label="스케치 도구">
          <div class="sketch-pad-tool-group">
            <button type="button" class="sketch-pad-tool is-active" data-sketch-tool="pen" aria-pressed="true" title="펜">
              <i data-lucide="pencil" aria-hidden="true"></i>
              <span>펜</span>
            </button>
            <button type="button" class="sketch-pad-tool" data-sketch-tool="eraser" aria-pressed="false" title="지우개">
              <i data-lucide="eraser" aria-hidden="true"></i>
              <span>지우개</span>
            </button>
          </div>

          <div class="sketch-pad-colors" aria-label="펜 색상">
            <button type="button" class="sketch-pad-color is-active" data-sketch-color="#111827" style="--sketch-color:#111827" aria-label="검정" aria-pressed="true"></button>
            <button type="button" class="sketch-pad-color" data-sketch-color="#ef4444" style="--sketch-color:#ef4444" aria-label="빨강" aria-pressed="false"></button>
            <button type="button" class="sketch-pad-color" data-sketch-color="#3b82f6" style="--sketch-color:#3b82f6" aria-label="파랑" aria-pressed="false"></button>
            <button type="button" class="sketch-pad-color" data-sketch-color="#22c55e" style="--sketch-color:#22c55e" aria-label="초록" aria-pressed="false"></button>
            <button type="button" class="sketch-pad-color" data-sketch-color="#f59e0b" style="--sketch-color:#f59e0b" aria-label="주황" aria-pressed="false"></button>
          </div>

          <label class="sketch-pad-size">
            <span>굵기</span>
            <input type="range" min="2" max="18" step="1" value="5" aria-label="펜 굵기">
          </label>

          <div class="sketch-pad-tool-group sketch-pad-tool-group--history">
            <button type="button" class="sketch-pad-icon" data-sketch-action="undo" title="실행 취소" aria-label="실행 취소">
              <i data-lucide="undo-2" aria-hidden="true"></i>
            </button>
            <button type="button" class="sketch-pad-icon" data-sketch-action="redo" title="다시 실행" aria-label="다시 실행">
              <i data-lucide="redo-2" aria-hidden="true"></i>
            </button>
          </div>
        </div>

        <div class="sketch-pad-canvas-wrap">
          <canvas class="sketch-pad-canvas" aria-label="스케치 캔버스"></canvas>
        </div>

        <div class="sketch-pad-actions">
          <button type="button" class="sketch-pad-button sketch-pad-button--quiet" data-sketch-action="clear">전체 삭제</button>
          <button type="button" class="sketch-pad-button sketch-pad-button--primary" data-sketch-action="save">
            <i data-lucide="download" aria-hidden="true"></i>
            <span>이미지 저장</span>
          </button>
        </div>
      </div>
    `;

    chatArea.appendChild(message);
    if (window.lucide) window.lucide.createIcons();

    const canvas = message.querySelector('.sketch-pad-canvas');
    const wrap = message.querySelector('.sketch-pad-canvas-wrap');
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    const sizeInput = message.querySelector('.sketch-pad-size input');

    let drawing = false;
    let tool = 'pen';
    let color = '#111827';
    let lineWidth = Number(sizeInput.value);
    let lastPoint = null;
    let undoStack = [];
    let redoStack = [];
    let cssWidth = 0;
    let cssHeight = 0;

    const getDpr = () => Math.max(1, Math.min(window.devicePixelRatio || 1, 2));

    const setupContext = () => {
      const dpr = getDpr();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
    };

    const fillBackground = () => {
      ctx.save();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.restore();
      setupContext();
    };

    const snapshot = () => {
      try {
        return ctx.getImageData(0, 0, canvas.width, canvas.height);
      } catch (_) {
        return null;
      }
    };

    const pushHistory = () => {
      const image = snapshot();
      if (!image) return;
      undoStack.push(image);
      if (undoStack.length > 30) undoStack.shift();
      redoStack = [];
    };

    const restore = (image) => {
      if (!image || image.width !== canvas.width || image.height !== canvas.height) return;
      ctx.save();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.putImageData(image, 0, 0);
      ctx.restore();
      setupContext();
    };

    const resizeCanvas = (preserve = true) => {
      const previous = preserve && canvas.width && canvas.height ? document.createElement('canvas') : null;
      if (previous) {
        previous.width = canvas.width;
        previous.height = canvas.height;
        previous.getContext('2d').drawImage(canvas, 0, 0);
      }

      cssWidth = Math.max(280, Math.floor(wrap.clientWidth));
      cssHeight = Math.max(260, Math.min(430, Math.round(cssWidth * 0.62)));
      const dpr = getDpr();

      canvas.width = Math.round(cssWidth * dpr);
      canvas.height = Math.round(cssHeight * dpr);
      canvas.style.width = `${cssWidth}px`;
      canvas.style.height = `${cssHeight}px`;
      setupContext();

      if (previous) {
        ctx.save();
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.drawImage(previous, 0, 0, previous.width, previous.height, 0, 0, canvas.width, canvas.height);
        ctx.restore();
        setupContext();
      } else {
        fillBackground();
        pushHistory();
      }
    };

    const pointFromEvent = (event) => {
      const rect = canvas.getBoundingClientRect();
      return {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top
      };
    };

    const beginStroke = (event) => {
      if (event.pointerType === 'mouse' && event.button !== 0) return;
      drawing = true;
      lastPoint = pointFromEvent(event);
      canvas.setPointerCapture?.(event.pointerId);
      event.preventDefault();
    };

    const drawStroke = (event) => {
      if (!drawing || !lastPoint) return;
      const point = pointFromEvent(event);

      ctx.save();
      ctx.globalCompositeOperation = tool === 'eraser' ? 'destination-out' : 'source-over';
      ctx.strokeStyle = color;
      ctx.lineWidth = tool === 'eraser' ? Math.max(lineWidth * 2.4, 12) : lineWidth;
      ctx.beginPath();
      ctx.moveTo(lastPoint.x, lastPoint.y);
      ctx.lineTo(point.x, point.y);
      ctx.stroke();

      if (tool === 'eraser') {
        ctx.globalCompositeOperation = 'destination-over';
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, cssWidth, cssHeight);
      }

      ctx.restore();
      lastPoint = point;
      event.preventDefault();
    };

    const endStroke = (event) => {
      if (!drawing) return;
      drawing = false;
      lastPoint = null;
      canvas.releasePointerCapture?.(event.pointerId);
      pushHistory();
      event.preventDefault();
    };

    const selectTool = (nextTool) => {
      tool = nextTool;
      message.querySelectorAll('[data-sketch-tool]').forEach((button) => {
        const active = button.dataset.sketchTool === tool;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-pressed', String(active));
      });
      canvas.classList.toggle('is-erasing', tool === 'eraser');
    };

    const selectColor = (nextColor) => {
      color = nextColor;
      selectTool('pen');
      message.querySelectorAll('[data-sketch-color]').forEach((button) => {
        const active = button.dataset.sketchColor === color;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-pressed', String(active));
      });
    };

    const undo = () => {
      if (undoStack.length <= 1) return;
      const current = undoStack.pop();
      if (current) redoStack.push(current);
      restore(undoStack[undoStack.length - 1]);
    };

    const redo = () => {
      const next = redoStack.pop();
      if (!next) return;
      undoStack.push(next);
      restore(next);
    };

    const clearCanvas = () => {
      fillBackground();
      pushHistory();
    };

    const saveImage = () => {
      const link = document.createElement('a');
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
      link.download = `gaemiGTP-sketch-${stamp}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    };

    canvas.addEventListener('pointerdown', beginStroke);
    canvas.addEventListener('pointermove', drawStroke);
    canvas.addEventListener('pointerup', endStroke);
    canvas.addEventListener('pointercancel', endStroke);
    canvas.addEventListener('contextmenu', (event) => event.preventDefault());

    sizeInput.addEventListener('input', () => {
      lineWidth = Number(sizeInput.value);
    });

    message.addEventListener('click', (event) => {
      const toolButton = event.target.closest('[data-sketch-tool]');
      if (toolButton) {
        selectTool(toolButton.dataset.sketchTool);
        return;
      }

      const colorButton = event.target.closest('[data-sketch-color]');
      if (colorButton) {
        selectColor(colorButton.dataset.sketchColor);
        return;
      }

      const actionButton = event.target.closest('[data-sketch-action]');
      if (!actionButton) return;

      const action = actionButton.dataset.sketchAction;
      if (action === 'undo') undo();
      else if (action === 'redo') redo();
      else if (action === 'clear') clearCanvas();
      else if (action === 'save') saveImage();
    });

    const resizeObserver = new ResizeObserver(() => {
      if (!wrap.clientWidth || Math.abs(wrap.clientWidth - cssWidth) < 2) return;
      const before = snapshot();
      resizeCanvas(true);
      undoStack = [];
      redoStack = [];
      const after = snapshot();
      if (after) undoStack.push(after);
      if (!before) return;
    });
    resizeObserver.observe(wrap);

    const cleanupObserver = new MutationObserver(() => {
      if (message.isConnected) return;
      resizeObserver.disconnect();
      cleanupObserver.disconnect();
    });
    cleanupObserver.observe(chatArea, { childList: true });

    resizeCanvas(false);
    message.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  openButton.addEventListener('click', () => {
    window.GaemiGTPChatTools?.closeMenu();
    createSketchPad();
  });

  window.openSketchPadInChat = createSketchPad;
})();
