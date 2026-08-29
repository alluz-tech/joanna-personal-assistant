import { initChat } from '/static/chat.js';
import { initAgenda } from '/static/agenda.js';

const ROUTES = ['conversa', 'agenda'];
const views = {
  conversa: document.querySelector('#view-conversa'),
  agenda: document.querySelector('#view-agenda'),
};
const navLinks = document.querySelectorAll('[data-route]');
const connectLink = document.querySelector('#connect');
const connLabel = document.querySelector('#conn-label');
const connDot = document.querySelector('#conn-dot');

export const app = {
  timezone: 'America/Sao_Paulo',
  connected: false,
  onConnChange: [],
};

/* ---------- Tema claro/escuro ---------- */
const THEME_KEY = 'joannaTheme';
const themeToggle = document.querySelector('#theme-toggle');

function storedTheme() {
  try { return localStorage.getItem(THEME_KEY); } catch { return null; }
}
function applyTheme(theme) {
  if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
}
applyTheme(storedTheme());

themeToggle.addEventListener('click', () => {
  const active = document.documentElement.dataset.theme
    || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const next = active === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  try { localStorage.setItem(THEME_KEY, next); } catch { /* ignore */ }
});

/* ---------- Roteamento (SPA) ---------- */
function currentRoute() {
  const route = location.hash.replace(/^#\/?/, '');
  return ROUTES.includes(route) ? route : 'conversa';
}

function render() {
  const route = currentRoute();
  for (const [name, el] of Object.entries(views)) el.hidden = name !== route;
  navLinks.forEach((link) => link.classList.toggle('active', link.dataset.route === route));
  if (route === 'agenda') agenda.activate();
}

async function refreshConnection() {
  try {
    const data = await fetch('/api/config').then((r) => r.json());
    app.timezone = data.timezone || app.timezone;
    app.connected = Boolean(data.connected);
  } catch {
    app.connected = false;
  }
  connLabel.textContent = app.connected ? 'Conectado' : 'Desconectado';
  connDot.classList.toggle('off', !app.connected);
  connectLink.hidden = app.connected;
  app.onConnChange.forEach((fn) => fn(app.connected));
}

initChat({ app });
const agenda = initAgenda({ app });

window.addEventListener('hashchange', render);
refreshConnection().then(render);
