/* gaemiGTP voice avatar: no dependencies, no background server calls. */
(function () {
  'use strict';
  if (window.GaemiGTPVoiceAvatar) return;

  const scriptBase = (document.currentScript && document.currentScript.src) || window.location.href;
  const embedded = window.GAEMI_VOICE_EMBEDDED_ASSETS || {};
  const assets = {
    image: embedded.image || new URL('../assets/gaemi_avatar_mouthless.webp', scriptBase).href,
    sample: embedded.sample || new URL('../assets/gaemi_voice_sample.mp3', scriptBase).href
  };
  const css = `
    .gaemi-voice-dock{position:fixed;right:20px;bottom:24px;z-index:10010;width:min(305px,calc(100vw - 24px));border:1px solid rgba(255,255,255,.17);border-radius:20px;overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,.44);background:linear-gradient(165deg,#23242c,#14151b);color:#f8fafc;font:14px/1.4 system-ui,-apple-system,sans-serif;user-select:none}
    .gaemi-voice-dock[hidden]{display:none!important}
    .gaemi-voice-top{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:12px 12px 2px}
    .gaemi-voice-live{font-size:11px;letter-spacing:.12em;font-weight:800;color:#fcd34d}
    .gaemi-voice-x{border:0;border-radius:100px;background:#343740;color:#fff;width:30px;height:30px;font-size:20px;cursor:pointer}
    .gaemi-voice-art{display:block;width:100%;height:min(43vh,390px);max-height:390px;object-fit:contain;filter:drop-shadow(0 10px 20px rgba(0,0,0,.24))}
    .gaemi-voice-floor{position:absolute;bottom:62px;left:10%;right:10%;height:11px;border-radius:50%;background:rgba(0,0,0,.13);filter:blur(9px);pointer-events:none}
    .gaemi-voice-controls{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:11px 12px 12px;background:rgba(12,13,18,.58)}
    .gaemi-voice-state{font-size:12px;color:#e5e7eb;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .gaemi-voice-action{border:1px solid #51535d;border-radius:10px;background:#31343d;color:white;padding:7px 10px;white-space:nowrap;font-size:12px;cursor:pointer}
    .gaemi-voice-action:hover,.gaemi-voice-x:hover{background:#4b4e5b}
    @media(max-width:640px){.gaemi-voice-dock{right:12px;bottom:80px;width:min(240px,calc(100vw - 24px))}.gaemi-voice-art{height:min(38vh,320px)}}
  `;
  const SAMPLE_TEXT = '개미 여러분, 오늘도 돈 되는 이슈만 쏙쏙 골라왔습니다. 바로 시작하시죠.';
  const WIDTH = 1344;
  const HEIGHT = 1808;
  // Crop above the knees in the compact site overlay so the lip motion is visible.
  const CROP = {x:260,y:20,width:825,height:1110};
  let panel, canvas, ctx, stateEl, sampleButton, avatar;
  let playing = false;
  let mode = 'idle';
  let currentButton = null;
  let activeUtterance = null;
  let audioEl = null;
  let audioCtx = null;
  let analyser = null;
  let sourceNode = null;
  let fftValues = null;
  let blobUrl = null;
  let raf = 0;
  let lastTime = 0;
  let jaw = 0;
  let speechStartedAt = 0;
  let lastBoundaryAt = 0;
  let runId = 0;

  function setState(text) { if (stateEl) stateEl.textContent = text; }
  function prepareUI() {
    if (panel) return;
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
    panel = document.createElement('section');
    panel.className = 'gaemi-voice-dock';
    panel.hidden = true;
    panel.setAttribute('aria-label', '개미 캐릭터 음성 읽기');
    panel.innerHTML = '<div class="gaemi-voice-top"><span class="gaemi-voice-live">● GAEMI LIVE</span><button type="button" class="gaemi-voice-x" aria-label="음성 읽기 닫기">×</button></div><div class="gaemi-voice-floor"></div><canvas class="gaemi-voice-art" role="img" aria-label="입을 움직이며 말하는 개미 캐릭터"></canvas><div class="gaemi-voice-controls"><span class="gaemi-voice-state" aria-live="polite">준비 중</span><button class="gaemi-voice-action" type="button" data-sample>샘플 목소리</button><button class="gaemi-voice-action" type="button" data-stop>정지</button></div>';
    document.body.appendChild(panel);
    canvas = panel.querySelector('canvas');
    canvas.width = 540;
    canvas.height = 727;
    ctx = canvas.getContext('2d');
    stateEl = panel.querySelector('.gaemi-voice-state');
    sampleButton = panel.querySelector('[data-sample]');
    panel.querySelector('.gaemi-voice-x').addEventListener('click', stop);
    panel.querySelector('[data-stop]').addEventListener('click', stop);
    sampleButton.addEventListener('click', () => { playSample(); });
    avatar = new Image();
    avatar.onload = () => draw(0);
    avatar.onerror = () => setState('캐릭터 이미지를 불러올 수 없습니다');
    avatar.src = assets.image;
  }

  function draw(open) {
    if (!ctx || !avatar?.complete || !avatar.naturalWidth) return;
    const sx = canvas.width / CROP.width;
    const sy = canvas.height / CROP.height;
    ctx.save();
    ctx.setTransform(sx, 0, 0, sy, -CROP.x * sx, -CROP.y * sy);
    ctx.clearRect(CROP.x, CROP.y, CROP.width, CROP.height);
    ctx.drawImage(avatar, 0, 0, WIDTH, HEIGHT);
    const x = 659, y = 620;
    const p = Math.max(0, Math.min(1, open));
    // Draw anatomy-aware lips, not an animated rectangle. Base avatar has original mouth inpainted.
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(x - 43, y - 3);
    ctx.quadraticCurveTo(x - 20, y - 10 - p * 5, x - 1, y - 4 - p * 3);
    ctx.quadraticCurveTo(x + 19, y - 10 - p * 5, x + 43, y - 3);
    ctx.quadraticCurveTo(x + 29, y + 2 + p * 18, x, y + 3 + p * 23);
    ctx.quadraticCurveTo(x - 29, y + 2 + p * 18, x - 43, y - 3);
    ctx.closePath();
    ctx.fillStyle = '#201b1c';
    ctx.fill();
    ctx.lineWidth = 3;
    ctx.strokeStyle = '#171314';
    ctx.stroke();
    if (p > .18) {
      ctx.save();
      ctx.clip();
      // Visible teeth and tongue appear only when the jaw opens far enough.
      if (p > .42) {
        ctx.beginPath();
        ctx.ellipse(x, y - 1, 29, 6, 0, 0, Math.PI * 2);
        ctx.fillStyle = '#c7b9b7';
        ctx.fill();
      }
      ctx.beginPath();
      ctx.ellipse(x, y + 13 + p * 3, 27, 8, 0, 0, Math.PI * 2);
      ctx.fillStyle = '#785258';
      ctx.fill();
      ctx.restore();
    }
    ctx.beginPath();
    ctx.moveTo(x - 29, y + 17 + p * 13);
    ctx.quadraticCurveTo(x, y + 27 + p * 14, x + 29, y + 17 + p * 13);
    ctx.strokeStyle = '#756b69';
    ctx.lineWidth = 2.1;
    ctx.stroke();
    ctx.restore();
  }

  function animate(now) {
    if (!playing) { raf = 0; draw(0); return; }
    const dt = Math.min(0.08, Math.max(.005, (now - (lastTime || now)) / 1000));
    lastTime = now;
    let target = 0;
    if (mode === 'audio' && analyser && fftValues) {
      analyser.getByteTimeDomainData(fftValues);
      let energy = 0;
      for (let i=0;i<fftValues.length;i++) {
        const v = (fftValues[i]-128)/128;
        energy += v*v;
      }
      const rms = Math.sqrt(energy/fftValues.length);
      const normalized = Math.min(1, Math.max(0, (rms - .012) * 12));
      target = normalized < .08 ? 0 : Math.pow(normalized,.64);
    } else if (mode === 'speech') {
      // Web Speech does not expose PCM. This is an approximate syllabic animation,
      // intentionally distinct from audio-reactive MP3 lip sync.
      const sinceStart = (now - speechStartedAt) / 1000;
      const syllable = Math.abs(Math.sin(sinceStart * 17.8)) * .62 + Math.abs(Math.sin(sinceStart * 7.2)) * .27;
      const gap = (now - lastBoundaryAt) / 1000;
      target = gap < .38 ? syllable : syllable * .72;
    }
    const ease = target > jaw ? Math.min(1,dt*25) : Math.min(1,dt*17);
    jaw += (target-jaw) * ease;
    draw(jaw);
    raf = requestAnimationFrame(animate);
  }

  function begin(button, which) {
    prepareUI();
    stop(false);
    runId++;
    playing = true;
    mode = which;
    currentButton = button || null;
    if (currentButton) currentButton.title = '읽는 중 · 다시 누르면 멈춤';
    panel.hidden = false;
    lastTime = 0;
    jaw = 0;
    setState('읽는 중');
    raf = requestAnimationFrame(animate);
    return runId;
  }

  function finished(id) {
    if (runId !== id) return;
    stop();
  }

  function stop(hide = true) {
    runId++;
    playing = false;
    mode = 'idle';
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    if (audioEl) {
      audioEl.pause();
      audioEl.removeAttribute('src');
      audioEl.load();
      audioEl = null;
    }
    try { if (sourceNode) sourceNode.disconnect(); } catch (_) { /* no-op */ }
    sourceNode = null;
    analyser = null;
    fftValues = null;
    if (blobUrl) { URL.revokeObjectURL(blobUrl); blobUrl = null; }
    if (activeUtterance) {
      activeUtterance.onstart = activeUtterance.onend = activeUtterance.onerror = activeUtterance.onboundary = null;
      activeUtterance = null;
      try { window.speechSynthesis?.cancel(); } catch (_) { /* no-op */ }
    }
    if (currentButton) currentButton.title = '소리 내어 읽기';
    currentButton = null;
    if (panel) { panel.hidden = hide; if (!hide) setState('준비 중'); }
    draw(0);
  }

  async function playAudio(url, button, revokeBlob = false) {
    const id = begin(button, 'audio');
    if (revokeBlob) blobUrl = url;
    audioEl = new Audio();
    audioEl.preload = 'auto';
    audioEl.src = url;
    audioEl.addEventListener('ended', () => finished(id), {once:true});
    audioEl.addEventListener('error', () => { if (runId === id) { setState('음성을 재생할 수 없습니다'); setTimeout(()=>finished(id),1400); } }, {once:true});
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        audioCtx = audioCtx || new AudioContextClass();
        if (audioCtx.state === 'suspended') await audioCtx.resume();
        if (id !== runId) return;
        const node = audioCtx.createMediaElementSource(audioEl);
        sourceNode = node;
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 1024;
        fftValues = new Uint8Array(analyser.fftSize);
        node.connect(analyser);
        analyser.connect(audioCtx.destination);
      }
      await audioEl.play();
    } catch (err) {
      if (runId === id) {
        setState('재생 실패: 다시 눌러 주세요');
        setTimeout(()=>finished(id),1600);
      }
    }
  }

  function playSample() { return playAudio(assets.sample, null, false); }

  function selectKoreanMaleVoice() {
    const voices = window.speechSynthesis.getVoices();
    const korean = voices.filter(v => /^ko([-_]|$)/i.test(v.lang));
    const score = v => /injoon|hyunsu|male|seonu|woojin|guy|chang|jun|준|현수|인준/i.test(v.name) ? 10 : 0;
    return korean.sort((a,b)=>score(b)-score(a))[0] || null;
  }

  function playBrowserSpeech(text, button) {
    if (!('speechSynthesis' in window)) { prepareUI(); setState('브라우저 음성이 지원되지 않습니다'); return; }
    const id = begin(button, 'speech');
    const utterance = new SpeechSynthesisUtterance(text);
    activeUtterance = utterance;
    utterance.lang = 'ko-KR';
    utterance.rate = 1;
    const koreanVoice = selectKoreanMaleVoice();
    if (koreanVoice) utterance.voice = koreanVoice;
    utterance.onstart = () => {
      if (runId !== id) return;
      speechStartedAt = performance.now();
      lastBoundaryAt = speechStartedAt;
      setState('본문 읽는 중 · 브라우저 음성');
    };
    utterance.onboundary = () => { lastBoundaryAt = performance.now(); };
    utterance.onend = () => finished(id);
    utterance.onerror = () => finished(id);
    try { window.speechSynthesis.speak(utterance); }
    catch (_) { finished(id); }
  }

  async function toggle(text, button) {
    if (playing) { stop(); return; }
    const clean = String(text || '').replace(/\s+/g,' ').trim();
    if (!clean) return;
    if (clean === SAMPLE_TEXT) return playSample();
    // Optional first-party voice-cloning endpoint; do not send voice assets to third parties.
    // POST {text} -> audio/mpeg (raw) or JSON {audio_url}. Configure only after backend is deployed.
    if (typeof window.GAEMI_VOICE_TTS_ENDPOINT === 'string' && window.GAEMI_VOICE_TTS_ENDPOINT) {
      const id = begin(button,'audio');
      setState('목소리 생성 중');
      try {
        const response = await fetch(window.GAEMI_VOICE_TTS_ENDPOINT, {
          method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({text:clean})
        });
        if (!response.ok) throw new Error('tts_http_' + response.status);
        if (runId !== id) return;
        if (response.headers.get('content-type')?.includes('application/json')) {
          const result = await response.json();
          if (!result.audio_url || !String(result.audio_url).startsWith('/')) throw new Error('invalid_voice_url');
          return playAudio(result.audio_url,button);
        }
        const blob = await response.blob();
        if (!blob.type.startsWith('audio/') || !blob.size) throw new Error('invalid_voice_audio');
        const url = URL.createObjectURL(blob);
        return playAudio(url,button,true);
      } catch (error) {
        if (runId === id) { stop(false); playBrowserSpeech(clean,button); }
      }
      return;
    }
    playBrowserSpeech(clean,button);
  }

  window.addEventListener('beforeunload',() => stop());
  window.GaemiGTPVoiceAvatar = Object.freeze({toggle,playSample,stop});
}());

