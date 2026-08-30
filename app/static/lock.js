/* Trava de acesso: teclado numérico. Toda recarga da página começa travada;
   ao acertar o PIN, o servidor devolve um cookie de sessão e o app é carregado. */
const PIN_LENGTH = 6;

const overlay = document.querySelector('#lock-screen');
const dots = [...overlay.querySelectorAll('.pin-dot')];
const errorEl = document.querySelector('#lock-error');
const keys = document.querySelector('#lock-keys');

let entry = '';
let busy = false;

function render() {
  dots.forEach((dot, i) => dot.classList.toggle('filled', i < entry.length));
}

function unlock() {
  overlay.remove();
  document.body.classList.remove('locked');
  import('/static/app.js');
}

async function submit() {
  busy = true;
  overlay.classList.add('checking');
  try {
    const res = await fetch('/auth/unlock', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: entry }),
    });
    if (!res.ok) throw new Error('nope');
    overlay.classList.add('ok');
    setTimeout(unlock, 220);
  } catch {
    overlay.classList.remove('checking');
    overlay.classList.add('shake');
    errorEl.textContent = 'Código incorreto. Tente de novo.';
    entry = '';
    render();
    busy = false;
    setTimeout(() => overlay.classList.remove('shake'), 450);
  }
}

function press(key) {
  if (busy) return;
  errorEl.textContent = '';
  if (key === 'del') {
    entry = entry.slice(0, -1);
    render();
    return;
  }
  if (entry.length >= PIN_LENGTH) return;
  entry += key;
  render();
  if (entry.length === PIN_LENGTH) submit();
}

keys.addEventListener('click', (event) => {
  const btn = event.target.closest('button[data-key]');
  if (btn) press(btn.dataset.key);
});

window.addEventListener('keydown', (event) => {
  if (event.key >= '0' && event.key <= '9') press(event.key);
  else if (event.key === 'Backspace') press('del');
});

render();
