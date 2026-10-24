/* Reliable, browser-only Korean read-aloud; no TTS service or paid API. */
(function () {
  'use strict';
  if (window.GaemiGTPReplySpeech) return;

  const MAX_CHARS = 90; // Short enough to avoid Chrome's long-utterance cutoffs.
  const NEXT_DELAY_MS = 80;
  const HEALTH_CHECK_MS = 3000;
  const START_TIMEOUT_MS = 9000;
  let current = null;
  let sequence = 0;

  // Preserve every word and punctuation mark. Break at sentences/words where
  // possible; exceptionally long unspaced tokens are the only hard splits.
  function splitIntoChunks(input) {
    const text = String(input || '').replace(/\s+/g, ' ').trim();
    const result = [];
    let start = 0;
    while (start < text.length) {
      let end = Math.min(start + MAX_CHARS, text.length);
      if (end < text.length) {
        const part = text.slice(start, end);
        let best = -1;
        for (const marker of ['. ', '! ', '? ', '。 ', '！ ', '？ ', '… ', '; ']) {
          const found = part.lastIndexOf(marker);
          if (found >= Math.floor(MAX_CHARS * .35)) best = Math.max(best, found + marker.length);
        }
        if (best > 0) end = start + best;
        else {
          const lastSpace = part.lastIndexOf(' ');
          if (lastSpace >= Math.floor(MAX_CHARS * .35)) end = start + lastSpace + 1;
        }
      }
      const chunk = text.slice(start, end).trim();
      if (chunk) result.push(chunk);
      start = end;
      while (text[start] === ' ') start += 1;
    }
    return result;
  }

  function synth() { return window.speechSynthesis; }
  function isActive(job, utterance) {
    return current === job && (!utterance || job.utterance === utterance);
  }
  function clearTimers(job) {
    if (job.nextTimer != null) clearTimeout(job.nextTimer);
    if (job.healthTimer != null) clearInterval(job.healthTimer);
    job.nextTimer = null;
    job.healthTimer = null;
  }
  function finish(job, error) {
    if (!isActive(job)) return;
    current = null;
    clearTimers(job);
    job.utterance = null;
    if (job.button) {
      job.button.title = error ? '읽기 중단 · 다시 눌러 시작' : '소리 내어 읽기';
      job.button.setAttribute('aria-pressed', 'false');
    }
  }
  function stop() {
    const previous = current;
    current = null; // Invalidate callbacks before cancel() emits 'interrupted'.
    sequence += 1;
    if (previous) {
      clearTimers(previous);
      previous.utterance = null;
      if (previous.button) {
        previous.button.title = '소리 내어 읽기';
        previous.button.setAttribute('aria-pressed', 'false');
      }
    }
    try { if ('speechSynthesis' in window) synth().cancel(); } catch (_) { /* unsupported */ }
  }

  function schedule(job, wait, fn) {
    if (!isActive(job)) return;
    if (job.nextTimer != null) clearTimeout(job.nextTimer);
    job.nextTimer = setTimeout(() => {
      job.nextTimer = null;
      if (isActive(job)) fn();
    }, wait);
  }

  function recover(job, reason) {
    if (!isActive(job)) return;
    clearTimers(job);
    job.utterance = null; // Ignore cancel-generated callbacks.
    if (job.retries >= 1 || reason === 'not-allowed' || reason === 'language-unavailable' ||
        reason === 'voice-unavailable') {
      finish(job, true);
      return;
    }
    job.retries += 1; // Retry at most once; never skip unread text.
    try { synth().cancel(); } catch (_) { /* no-op */ }
    schedule(job, 180, () => speakChunk(job));
  }

  function speakChunk(job) {
    if (!isActive(job)) return;
    if (job.index >= job.chunks.length) {
      finish(job, false);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(job.chunks[job.index]);
    utterance.lang = 'ko-KR';
    utterance.rate = 1;
    job.utterance = utterance;
    job.issuedAt = Date.now();
    utterance.onend = () => {
      if (!isActive(job, utterance)) return;
      clearTimers(job);
      job.utterance = null;
      job.index += 1;
      job.retries = 0;
      schedule(job, NEXT_DELAY_MS, () => speakChunk(job));
    };
    utterance.onerror = event => {
      if (!isActive(job, utterance)) return;
      recover(job, event?.error || 'speech-error');
    };
    try {
      synth().speak(utterance);
    } catch (_) {
      recover(job, 'speech-error');
      return;
    }
    // Some Chrome voices stop without onend/onerror. Only retry a stalled
    // chunk when the synthesis engine itself is no longer speaking.
    job.healthTimer = setInterval(() => {
      if (!isActive(job, utterance)) return;
      if (document.visibilityState === 'hidden') return;
      try {
        if (synth().paused) {
          synth().resume();
        } else if (!synth().speaking && Date.now() - job.issuedAt > START_TIMEOUT_MS) {
          recover(job, 'stalled');
        }
      } catch (_) { recover(job, 'speech-error'); }
    }, HEALTH_CHECK_MS);
  }

  function toggle(text, button) {
    if (current && current.button === button) { stop(); return; }
    stop(); // Only one reader may speak at a time, even across reply buttons.
    if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') {
      if (button) button.title = '이 브라우저는 음성 읽기를 지원하지 않습니다';
      return;
    }
    const chunks = splitIntoChunks(text);
    if (!chunks.length) return;
    const job = {id: ++sequence, chunks, index: 0, retries: 0, utterance: null,
      button: button || null, nextTimer: null, healthTimer: null, issuedAt: 0};
    current = job;
    if (button) {
      button.title = '읽는 중 · 다시 누르면 멈춤';
      button.setAttribute('aria-pressed', 'true');
    }
    speakChunk(job);
  }

  window.addEventListener('pagehide', stop);
  window.GaemiGTPReplySpeech = Object.freeze({toggle, stop, splitIntoChunks});
}());
