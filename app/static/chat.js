export function initChat({ app }) {
  const messages = document.querySelector('#messages');
  const form = document.querySelector('#chat-form');
  const input = document.querySelector('#message');
  const welcome = document.querySelector('#chat-welcome');
  const suggestions = document.querySelector('#chat-suggestions');
  const micBtn = document.querySelector('#mic-btn');
  const recOverlay = document.querySelector('#rec-overlay');
  const recTime = document.querySelector('#rec-time');
  const recHint = document.querySelector('#rec-hint');
  const sessionId =
    localStorage.joannaSession || (localStorage.joannaSession = crypto.randomUUID());

  // Mostra app/static/joanna.jpeg como rosto da Joanna se o arquivo existir.
  const avatar = document.querySelector('.joanna-avatar');
  fetch('/static/joanna.jpeg', { method: 'HEAD' })
    .then((r) => {
      if (!r.ok || !avatar) return;
      avatar.classList.add('has-img');
      avatar.querySelector('img').src = '/static/joanna.jpeg';
    })
    .catch(() => {});

  // Alterna entre o botão de microfone (campo vazio) e o de enviar (com texto).
  function syncMode() {
    form.dataset.mode = input.value.trim() ? 'text' : 'voice';
  }
  input.addEventListener('input', syncMode);
  syncMode();

  function addMessage(kind, text, audioUrl) {
    if (welcome) welcome.hidden = true;
    const el = document.createElement('div');
    el.className = kind;
    const p = document.createElement('p');
    p.className = 'msg-text';
    p.textContent = text;
    el.append(p);
    if (audioUrl) el.append(buildAudioControl(audioUrl));
    messages.append(el);
    el.scrollIntoView({ block: 'end' });
    return el;
  }

  function buildAudioControl(url) {
    const audio = new Audio(url);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'replay-btn';
    btn.textContent = '▶ Ouvir';
    btn.addEventListener('click', () => {
      if (audio.paused) audio.play();
      else audio.pause();
    });
    audio.addEventListener('play', () => (btn.textContent = '❚❚ Pausar'));
    audio.addEventListener('pause', () => (btn.textContent = '▶ Ouvir'));
    audio.addEventListener('ended', () => (btn.textContent = '▶ Ouvir'));
    audio.play().catch(() => {}); // autoplay; ignora bloqueio do navegador
    return btn;
  }

  function showTyping() {
    if (welcome) welcome.hidden = true;
    const el = document.createElement('div');
    el.className = 'assistant typing';
    el.setAttribute('aria-label', 'Joanna está pensando');
    el.innerHTML = '<span></span><span></span><span></span>';
    messages.append(el);
    el.scrollIntoView({ block: 'end' });
    return el;
  }

  async function send(message) {
    if (!message) return;
    addMessage('user', message);
    input.value = '';
    syncMode();
    input.disabled = true;
    const typing = showTyping();
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: sessionId }),
      });
      const data = await response.json();
      addMessage('assistant', data.reply || data.detail || 'Ocorreu um erro.');
    } catch {
      addMessage('assistant', 'Não foi possível falar com o servidor.');
    } finally {
      typing.remove();
      input.disabled = false;
      input.focus();
    }
  }

  async function sendAudio(blob, filename) {
    const placeholder = addMessage('user voice-pending', '🎤 Áudio enviado');
    const typing = showTyping();
    micBtn.disabled = true;
    try {
      const body = new FormData();
      body.append('session_id', sessionId);
      body.append('audio', blob, filename);
      const response = await fetch('/api/voice', { method: 'POST', body });
      const data = await response.json();
      if (!response.ok) {
        placeholder.querySelector('.msg-text').textContent = '🎤 Áudio';
        addMessage('assistant', data.detail || 'Não consegui processar o áudio.');
        return;
      }
      placeholder.querySelector('.msg-text').textContent = data.transcript;
      const audioUrl = data.audio ? `data:audio/mp3;base64,${data.audio}` : null;
      addMessage('assistant', data.reply, audioUrl);
    } catch {
      addMessage('assistant', 'Não foi possível falar com o servidor.');
    } finally {
      typing.remove();
      micBtn.disabled = false;
    }
  }

  /* ---------- Gravação estilo WhatsApp: segurar para gravar ---------- */
  const recorder = createRecorder(sendAudio, {
    onStart: () => {
      recOverlay.hidden = false;
      form.classList.add('recording');
    },
    onTick: (secs) => {
      recTime.textContent = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
    },
    onCancelState: (willCancel) => {
      form.classList.toggle('will-cancel', willCancel);
      recHint.textContent = willCancel ? 'Solte para cancelar' : '← arraste para cancelar';
    },
    onStop: () => {
      recOverlay.hidden = true;
      form.classList.remove('recording', 'will-cancel');
      recHint.textContent = '← arraste para cancelar';
    },
    onError: (msg) => {
      recOverlay.hidden = true;
      form.classList.remove('recording', 'will-cancel');
      addMessage('assistant', msg);
    },
  });

  micBtn.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    try {
      micBtn.setPointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
    recorder.start(e.clientX, e.clientY);
  });
  micBtn.addEventListener('pointermove', (e) => recorder.move(e.clientX, e.clientY));
  micBtn.addEventListener('pointerup', () => recorder.stop());
  micBtn.addEventListener('pointercancel', () => recorder.stop());

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    send(input.value.trim());
  });

  suggestions?.addEventListener('click', (event) => {
    const btn = event.target.closest('button[data-prompt]');
    if (btn) send(btn.dataset.prompt);
  });

  app.onConnChange.push((connected) => {
    input.placeholder = connected
      ? 'Ex.: O que eu tenho amanhã?'
      : 'Conecte o Google Calendar para conversar…';
    micBtn.disabled = !connected;
  });
}

/* Encapsula MediaRecorder + gesto de arrastar-para-cancelar. */
function createRecorder(onComplete, cb) {
  const CANCEL_THRESHOLD = 90; // px de arraste para a esquerda/cima
  let mediaRecorder = null;
  let stream = null;
  let chunks = [];
  let startX = 0;
  let startY = 0;
  let startedAt = 0;
  let willCancel = false;
  let timer = null;
  let abortPending = false;

  function pickMime() {
    const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'];
    return candidates.find((t) => window.MediaRecorder?.isTypeSupported?.(t)) || '';
  }

  async function start(x, y) {
    if (mediaRecorder) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      cb.onError('Seu navegador não permite gravar áudio aqui.');
      return;
    }
    abortPending = false;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      cb.onError('Preciso de permissão para usar o microfone.');
      return;
    }
    if (abortPending) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
      cb.onStop();
      return;
    }
    const mimeType = pickMime();
    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    chunks = [];
    willCancel = false;
    startX = x;
    startY = y;
    startedAt = Date.now();
    mediaRecorder.addEventListener('dataavailable', (e) => {
      if (e.data.size) chunks.push(e.data);
    });
    mediaRecorder.addEventListener('stop', () => {
      const duration = Date.now() - startedAt;
      stream.getTracks().forEach((t) => t.stop());
      const type = mediaRecorder.mimeType || 'audio/webm';
      const blob = new Blob(chunks, { type });
      mediaRecorder = null;
      stream = null;
      cb.onStop();
      if (willCancel || duration < 500 || !blob.size) return;
      const ext = type.includes('mp4') ? 'mp4' : type.includes('ogg') ? 'ogg' : 'webm';
      onComplete(blob, `audio.${ext}`);
    });
    mediaRecorder.start();
    cb.onStart();
    cb.onTick(0);
    timer = setInterval(() => cb.onTick(Math.floor((Date.now() - startedAt) / 1000)), 500);
  }

  function move(x, y) {
    if (!mediaRecorder) return;
    const next = x - startX < -CANCEL_THRESHOLD || y - startY < -CANCEL_THRESHOLD;
    if (next !== willCancel) {
      willCancel = next;
      cb.onCancelState(willCancel);
    }
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
    abortPending = true; // caso o usuário solte antes do getUserMedia resolver
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
  }

  return { start, move, stop };
}
