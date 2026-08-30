export function initChat({ app }) {
  const messages = document.querySelector('#messages');
  const form = document.querySelector('#chat-form');
  const input = document.querySelector('#message');
  const welcome = document.querySelector('#chat-welcome');
  const suggestions = document.querySelector('#chat-suggestions');
  const sessionId =
    localStorage.joannaSession || (localStorage.joannaSession = crypto.randomUUID());

  function addMessage(kind, text) {
    if (welcome) welcome.hidden = true;
    const el = document.createElement('p');
    el.className = kind;
    el.textContent = text;
    messages.append(el);
    el.scrollIntoView({ block: 'end' });
  }

  async function send(message) {
    if (!message) return;
    addMessage('user', message);
    input.value = '';
    input.disabled = true;
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
      input.disabled = false;
      input.focus();
    }
  }

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
  });
}
