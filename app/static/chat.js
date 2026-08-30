export function initChat({ app }) {
  const messages = document.querySelector('#messages');
  const form = document.querySelector('#chat-form');
  const input = document.querySelector('#message');
  const welcome = document.querySelector('#chat-welcome');
  const suggestions = document.querySelector('#chat-suggestions');
  const micBtn = document.querySelector('#mic-btn');
  const recOverlay = document.querySelector('#rec-overlay');
  const recTime = document.querySelector('#rec-time');
  const recCancel = document.querySelector('#rec-cancel');
  const recSend = document.querySelector('#rec-send');
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

  // Libera a reprodução automática de áudio: o primeiro gesto do usuário
  // (clique em gravar/enviar) "desbloqueia" o autoplay para as respostas faladas.
  let audioArmed = false;
  const audioPrimer = new Audio(
    'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=',
  );
  function armAudio() {
    if (audioArmed) return;
    audioArmed = true;
    audioPrimer
      .play()
      .then(() => {
        audioPrimer.pause();
        audioPrimer.currentTime = 0;
      })
      .catch(() => {});
  }

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

  /* ---------- Gravação: iniciar → enviar ou cancelar ---------- */
  const recorder = createRecorder(sendAudio, {
    onStart: () => {
      recOverlay.hidden = false;
      form.classList.add('recording');
    },
    onTick: (secs) => {
      recTime.textContent = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
    },
    onStop: () => {
      recOverlay.hidden = true;
      form.classList.remove('recording');
    },
    onError: (msg) => {
      recOverlay.hidden = true;
      form.classList.remove('recording');
      addMessage('assistant', msg);
    },
  });

  micBtn.addEventListener('click', () => {
    armAudio();
    recorder.start();
  });
  recSend.addEventListener('click', () => {
    armAudio();
    recorder.finish();
  });
  recCancel.addEventListener('click', () => recorder.cancel());

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

/* Encapsula MediaRecorder: start() começa, finish() envia, cancel() descarta. */
function createRecorder(onComplete, cb) {
  let mediaRecorder = null;
  let stream = null;
  let chunks = [];
  let startedAt = 0;
  let cancelled = false;
  let timer = null;

  function pickMime() {
    const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'];
    return candidates.find((t) => window.MediaRecorder?.isTypeSupported?.(t)) || '';
  }

  function clearTimer() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  async function start() {
    if (mediaRecorder) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      cb.onError('Seu navegador não permite gravar áudio aqui.');
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      cb.onError('Preciso de permissão para usar o microfone.');
      return;
    }
    const mimeType = pickMime();
    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    chunks = [];
    cancelled = false;
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
      clearTimer();
      cb.onStop();
      if (cancelled || duration < 500 || !blob.size) return;
      const ext = type.includes('mp4') ? 'mp4' : type.includes('ogg') ? 'ogg' : 'webm';
      onComplete(blob, `audio.${ext}`);
    });
    mediaRecorder.start();
    cb.onStart();
    cb.onTick(0);
    timer = setInterval(() => cb.onTick(Math.floor((Date.now() - startedAt) / 1000)), 500);
  }

  function finish() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
  }

  function cancel() {
    cancelled = true;
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    } else {
      clearTimer();
      cb.onStop();
    }
  }

  return { start, finish, cancel };
}
