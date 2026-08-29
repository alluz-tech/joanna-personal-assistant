const messages = document.querySelector('#messages');
const form = document.querySelector('#chat-form');
const input = document.querySelector('#message');
const status = document.querySelector('#status');
const connect = document.querySelector('#connect');
const sessionId = localStorage.joannaSession || (localStorage.joannaSession = crypto.randomUUID());
function addMessage(kind, text) { const el = document.createElement('p'); el.className = kind; el.textContent = text; messages.append(el); el.scrollIntoView({block:'end'}); }
async function refreshStatus() { const data = await fetch('/api/auth-status').then(r => r.json()); status.textContent = data.connected ? 'Google Calendar conectado.' : 'Google Calendar não conectado.'; connect.hidden = data.connected; }
form.addEventListener('submit', async (event) => { event.preventDefault(); const message = input.value.trim(); if (!message) return; addMessage('user', message); input.value = ''; input.disabled = true; try { const response = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message, session_id:sessionId})}); const data = await response.json(); addMessage('assistant', data.reply || data.detail || 'Ocorreu um erro.'); } catch { addMessage('assistant', 'Não foi possível falar com o servidor.'); } finally { input.disabled = false; input.focus(); }});
refreshStatus();
