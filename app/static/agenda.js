// Tela de agenda: calendário (mês / semana / dia) + filtros + criação/edição.
// Premissa do MVP: usuário e eventos no mesmo fuso configurado (America/Sao_Paulo).

const HOUR_PX = 48;
const WEEKDAYS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
const pad = (n) => String(n).padStart(2, '0');

export function initAgenda({ app }) {
  const $ = (sel) => document.querySelector(sel);
  const grid = $('#ag-grid');
  const statusBox = $('#ag-status');
  const periodLabel = $('#ag-period');
  const countLabel = $('#f-count');

  const filters = {
    text: $('#f-text'), attendee: $('#f-attendee'),
    from: $('#f-from'), to: $('#f-to'),
    start: $('#f-start'), end: $('#f-end'),
    allday: $('#f-allday'), people: $('#f-people'), hide: $('#f-hide'),
  };

  const dialog = $('#event-dialog');
  const form = $('#event-form');
  const fields = {
    title: $('#e-title'), start: $('#e-start'), end: $('#e-end'),
    location: $('#e-location'), attendees: $('#e-attendees'), description: $('#e-description'),
  };
  const formTitle = $('#event-form-title');
  const deleteBtn = $('#e-delete');
  const saveBtn = $('#e-save');
  const formError = $('#e-error');

  const state = { view: 'month', anchor: noon(new Date()), events: [], loaded: false, editing: null };

  // ---------- helpers de fuso ----------
  function noon(d) { const x = new Date(d); x.setHours(12, 0, 0, 0); return x; }

  function tzOffset(date) {
    const part = new Intl.DateTimeFormat('en-US', { timeZone: app.timezone, timeZoneName: 'longOffset' })
      .formatToParts(date).find((p) => p.type === 'timeZoneName').value;
    const m = part.match(/GMT([+-])(\d{1,2})(?::(\d{2}))?/);
    if (!m) return '+00:00';
    return `${m[1]}${pad(+m[2])}:${m[3] || '00'}`;
  }

  function tzParts(date) {
    const f = new Intl.DateTimeFormat('en-CA', {
      timeZone: app.timezone, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'short',
    });
    const p = Object.fromEntries(f.formatToParts(date).map((x) => [x.type, x.value]));
    const hour = parseInt(p.hour, 10) % 24;
    const wd = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 }[p.weekday];
    return {
      key: `${p.year}-${p.month}-${p.day}`, weekday: wd,
      hour, minute: +p.minute, minutes: hour * 60 + +p.minute,
    };
  }

  const dayKeyOf = (ev) => (ev.all_day ? ev.start.slice(0, 10) : tzParts(new Date(ev.start)).key);
  const startMinutesOf = (ev) => (ev.all_day ? 0 : tzParts(new Date(ev.start)).minutes);
  function durationMinutes(ev) {
    if (ev.all_day || !ev.end) return 60;
    return Math.max(15, (new Date(ev.end) - new Date(ev.start)) / 60000);
  }

  function dayStartISO(date) {
    const y = date.getFullYear(), m = date.getMonth() + 1, d = date.getDate();
    const off = tzOffset(new Date(y, m - 1, d, 12));
    return `${y}-${pad(m)}-${pad(d)}T00:00:00${off}`;
  }
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const dateKey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

  // ---------- janela de busca ----------
  function windowRange() {
    if (rangeActive()) {
      return { start: `${filters.start.value}T00:00:00${tzOffset(new Date())}`,
               end: `${filters.end.value}T23:59:59${tzOffset(new Date())}` };
    }
    const a = state.anchor;
    if (state.view === 'day') {
      return { start: dayStartISO(a), end: dayStartISO(addDays(a, 1)) };
    }
    if (state.view === 'week') {
      const s = addDays(a, -a.getDay());
      return { start: dayStartISO(s), end: dayStartISO(addDays(s, 7)) };
    }
    const first = new Date(a.getFullYear(), a.getMonth(), 1);
    const gridStart = addDays(first, -first.getDay());
    return { start: dayStartISO(gridStart), end: dayStartISO(addDays(gridStart, 42)) };
  }

  const rangeActive = () => Boolean(filters.start.value && filters.end.value);

  // ---------- carregar ----------
  let loadSeq = 0;
  async function load() {
    const seq = ++loadSeq;
    if (!app.connected) {
      state.events = [];
      showStatus('Conecte o Google Calendar para ver sua agenda.');
      grid.innerHTML = '';
      countLabel.textContent = '';
      return;
    }
    const { start, end } = windowRange();
    showStatus('Carregando…');
    try {
      const url = `/api/events?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
      const res = await fetch(url);
      const data = await res.json();
      if (seq !== loadSeq) return; // resposta obsoleta: navegação mais recente em andamento
      if (!res.ok) throw new Error(data.detail || 'Falha ao carregar.');
      state.events = data.events || [];
      state.loaded = true;
      hideStatus();
    } catch (err) {
      if (seq !== loadSeq) return;
      showStatus(err.message || 'Não foi possível carregar a agenda.');
      state.events = [];
    }
    paint();
  }

  function showStatus(msg) { statusBox.textContent = msg; statusBox.hidden = false; }
  function hideStatus() { statusBox.hidden = true; }

  // ---------- filtros ----------
  function matches(ev) {
    const text = filters.text.value.trim().toLowerCase();
    if (text) {
      const hay = `${ev.title} ${ev.description || ''} ${ev.location || ''}`.toLowerCase();
      if (!hay.includes(text)) return false;
    }
    const who = filters.attendee.value.trim().toLowerCase();
    if (who) {
      const hit = (ev.attendees || []).some(
        (a) => (a.email || '').toLowerCase().includes(who) || (a.name || '').toLowerCase().includes(who),
      );
      if (!hit) return false;
    }
    if (filters.allday.checked && !ev.all_day) return false;
    if (filters.people.checked && !(ev.attendees || []).length) return false;
    const from = filters.from.value, to = filters.to.value;
    if (from || to) {
      if (ev.all_day) return false;
      const mins = startMinutesOf(ev);
      if (from && mins < toMinutes(from)) return false;
      if (to && mins > toMinutes(to)) return false;
    }
    return true;
  }
  const toMinutes = (hhmm) => { const [h, m] = hhmm.split(':').map(Number); return h * 60 + m; };

  // ---------- pintar ----------
  function paint() {
    const anyFilter =
      filters.text.value || filters.attendee.value || filters.from.value || filters.to.value ||
      filters.allday.checked || filters.people.checked;
    const flagged = state.events.map((ev) => ({ ev, ok: matches(ev) }));
    const visible = filters.hide.checked ? flagged.filter((x) => x.ok) : flagged;
    const okCount = flagged.filter((x) => x.ok).length;
    countLabel.textContent = anyFilter || rangeActive()
      ? `${okCount} de ${state.events.length} compromissos`
      : `${state.events.length} compromissos`;

    periodLabel.textContent = periodText();
    grid.className = 'calendar-grid';
    grid.innerHTML = '';
    if (rangeActive()) return renderList(visible);
    if (state.view === 'month') return renderMonth(visible);
    return renderTimeGrid(visible, state.view === 'week' ? 7 : 1);
  }

  function periodText() {
    const a = state.anchor;
    if (rangeActive()) return `${fmt(filters.start.value)} – ${fmt(filters.end.value)}`;
    if (state.view === 'day')
      return cap(a.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' }));
    if (state.view === 'week') {
      const s = addDays(a, -a.getDay()), e = addDays(s, 6);
      return `${s.getDate()} – ${e.getDate()} de ${cap(e.toLocaleDateString('pt-BR', { month: 'long' }))} ${e.getFullYear()}`;
    }
    return cap(a.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' }));
  }
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const fmt = (iso) => iso.split('-').reverse().join('/');

  function chip(entry, opts = {}) {
    const { ev, ok } = entry;
    const node = document.createElement('button');
    node.type = 'button';
    node.className = `chip${ok ? '' : ' dim'}${ev.all_day ? ' all-day' : ''}`;
    const time = ev.all_day ? 'Dia inteiro' : hhmm(ev.start);
    node.innerHTML = opts.withTime === false
      ? `<span class="chip-title">${escapeHtml(ev.title)}</span>`
      : `<span class="chip-time">${time}</span><span class="chip-title">${escapeHtml(ev.title)}</span>`;
    node.addEventListener('click', (e) => { e.stopPropagation(); openEvent(ev); });
    return node;
  }
  const hhmm = (iso) => { const p = tzParts(new Date(iso)); return `${pad(p.hour)}:${pad(p.minute)}`; };

  function renderMonth(entries) {
    const a = state.anchor;
    const first = new Date(a.getFullYear(), a.getMonth(), 1);
    const gridStart = addDays(first, -first.getDay());
    const byDay = groupByDay(entries);
    const todayKey = tzParts(new Date()).key;

    const head = document.createElement('div');
    head.className = 'month-head';
    WEEKDAYS.forEach((w) => { const c = document.createElement('span'); c.textContent = w; head.append(c); });
    grid.append(head);

    const body = document.createElement('div');
    body.className = 'month-body';
    for (let i = 0; i < 42; i++) {
      const day = addDays(gridStart, i);
      const key = dateKey(day);
      const cell = document.createElement('div');
      cell.className = 'day-cell';
      if (day.getMonth() !== a.getMonth()) cell.classList.add('outside');
      if (key === todayKey) cell.classList.add('today');
      cell.innerHTML = `<span class="day-num">${day.getDate()}</span>`;
      const list = byDay.get(key) || [];
      list.slice(0, 3).forEach((entry) => cell.append(chip(entry)));
      if (list.length > 3) {
        const more = document.createElement('span');
        more.className = 'more';
        more.textContent = `+${list.length - 3} mais`;
        more.addEventListener('click', (e) => { e.stopPropagation(); state.view = 'day'; state.anchor = noon(day); syncViewButtons(); load(); });
        cell.append(more);
      }
      cell.addEventListener('click', () => openNew(`${key}T09:00`, `${key}T10:00`));
      body.append(cell);
    }
    grid.append(body);
  }

  function renderTimeGrid(entries, days) {
    const a = state.anchor;
    const startDay = days === 7 ? addDays(a, -a.getDay()) : new Date(a);
    const cols = Array.from({ length: days }, (_, i) => addDays(startDay, i));
    const byDay = groupByDay(entries);
    const todayKey = tzParts(new Date()).key;

    const wrap = document.createElement('div');
    wrap.className = days === 1 ? 'time-grid time-grid--day' : 'time-grid';
    wrap.style.setProperty('--days', days);

    wrap.append(el('div', 'tg-corner'));
    cols.forEach((d) => {
      const h = el('div', 'tg-dayhead');
      if (dateKey(d) === todayKey) h.classList.add('today');
      h.innerHTML = `<span>${WEEKDAYS[d.getDay()]}</span><strong>${d.getDate()}</strong>`;
      wrap.append(h);
    });

    wrap.append(el('div', 'tg-allday-label', 'Dia inteiro'));
    cols.forEach((d) => {
      const cell = el('div', 'tg-allday');
      (byDay.get(dateKey(d)) || []).filter((x) => x.ev.all_day).forEach((entry) => cell.append(chip(entry, { withTime: false })));
      wrap.append(cell);
    });

    const scroller = el('div', 'tg-scroll');
    const hours = el('div', 'tg-hours');
    for (let h = 0; h < 24; h++) hours.append(el('span', 'tg-hour', `${pad(h)}:00`));
    scroller.append(hours);

    cols.forEach((d) => {
      const col = el('div', 'tg-col');
      col.style.height = `${24 * HOUR_PX}px`;
      for (let h = 1; h < 24; h++) { const line = el('div', 'tg-line'); line.style.top = `${h * HOUR_PX}px`; col.append(line); }
      (byDay.get(dateKey(d)) || []).filter((x) => !x.ev.all_day).forEach((entry) => {
        const { ev, ok } = entry;
        const top = (startMinutesOf(ev) / 60) * HOUR_PX;
        const h = Math.max(22, (durationMinutes(ev) / 60) * HOUR_PX);
        const box = el('button', `event-box${ok ? '' : ' dim'}`);
        box.type = 'button';
        box.style.top = `${top}px`;
        box.style.height = `${h}px`;
        box.innerHTML = `<strong>${escapeHtml(ev.title)}</strong><span>${hhmm(ev.start)}${ev.end ? '–' + hhmm(ev.end) : ''}</span>`;
        box.addEventListener('click', (e) => { e.stopPropagation(); openEvent(ev); });
        col.append(box);
      });
      col.addEventListener('click', (e) => {
        const y = e.offsetY;
        let mins = Math.round((y / HOUR_PX) * 60 / 30) * 30;
        mins = Math.max(0, Math.min(23 * 60 + 30, mins));
        const k = dateKey(d);
        const sh = pad(Math.floor(mins / 60)), sm = pad(mins % 60);
        const eh = pad(Math.floor((mins + 60) / 60) % 24), em = pad((mins + 60) % 60);
        openNew(`${k}T${sh}:${sm}`, `${k}T${eh}:${em}`);
      });
      scroller.append(col);
    });

    wrap.append(scroller);
    grid.append(wrap);
    requestAnimationFrame(() => { scroller.scrollTop = 7 * HOUR_PX; });
  }

  function renderList(entries) {
    const byDay = groupByDay(entries);
    const keys = [...byDay.keys()].sort();
    if (!keys.length) { grid.append(el('p', 'empty-list', 'Nenhum compromisso no intervalo com os filtros atuais.')); return; }
    const list = el('div', 'agenda-list');
    keys.forEach((key) => {
      const group = el('div', 'agenda-day');
      const [y, m, d] = key.split('-').map(Number);
      const label = new Date(y, m - 1, d).toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' });
      group.append(el('h3', 'agenda-day-label', cap(label)));
      byDay.get(key).forEach((entry) => {
        const { ev, ok } = entry;
        const row = el('button', `agenda-row${ok ? '' : ' dim'}`);
        row.type = 'button';
        row.innerHTML =
          `<span class="agenda-time">${ev.all_day ? 'Dia inteiro' : hhmm(ev.start)}</span>` +
          `<span class="agenda-info"><strong>${escapeHtml(ev.title)}</strong>` +
          `${ev.location ? `<em>${escapeHtml(ev.location)}</em>` : ''}` +
          `${(ev.attendees || []).length ? `<em>${ev.attendees.length} participante(s)</em>` : ''}</span>`;
        row.addEventListener('click', () => openEvent(ev));
        group.append(row);
      });
      list.append(group);
    });
    grid.append(list);
  }

  function groupByDay(entries) {
    const map = new Map();
    entries.slice().sort((a, b) => (a.ev.start < b.ev.start ? -1 : 1)).forEach((entry) => {
      const k = dayKeyOf(entry.ev);
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(entry);
    });
    return map;
  }

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }
  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ---------- modal ----------
  function openNew(startLocal, endLocal) {
    state.editing = null;
    formTitle.textContent = 'Novo compromisso';
    deleteBtn.hidden = true;
    form.reset();
    fields.start.value = startLocal;
    fields.end.value = endLocal;
    showDialog();
  }

  function openEvent(ev) {
    state.editing = ev;
    formTitle.textContent = 'Editar compromisso';
    deleteBtn.hidden = false;
    fields.title.value = ev.title || '';
    fields.start.value = ev.all_day ? `${ev.start.slice(0, 10)}T00:00` : toLocalInput(ev.start);
    fields.end.value = ev.end ? (ev.all_day ? `${ev.end.slice(0, 10)}T00:00` : toLocalInput(ev.end)) : '';
    fields.location.value = ev.location || '';
    fields.attendees.value = (ev.attendees || []).map((a) => a.email).join(', ');
    fields.description.value = ev.description || '';
    showDialog();
  }

  function toLocalInput(iso) {
    const p = tzParts(new Date(iso));
    return `${p.key}T${pad(p.hour)}:${pad(p.minute)}`;
  }
  function localInputToISO(value) {
    const off = tzOffset(new Date(value));
    return `${value}:00${off}`;
  }

  function showDialog() {
    formError.hidden = true;
    dialog.hidden = false;
    setTimeout(() => fields.title.focus(), 0);
  }
  function closeDialog() { dialog.hidden = true; }

  dialog.addEventListener('click', (e) => { if (e.target.dataset.close !== undefined) closeDialog(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !dialog.hidden) closeDialog(); });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (fields.end.value <= fields.start.value) return showFormError('O fim deve ser depois do início.');
    const attendees = fields.attendees.value.split(',').map((s) => s.trim()).filter(Boolean);
    const payload = {
      title: fields.title.value.trim(),
      start: localInputToISO(fields.start.value),
      end: localInputToISO(fields.end.value),
      description: fields.description.value.trim() || null,
      location: fields.location.value.trim() || null,
      attendees,
    };
    saveBtn.disabled = true;
    try {
      const editing = state.editing;
      const res = await fetch(editing ? `/api/events/${encodeURIComponent(editing.id)}` : '/api/events', {
        method: editing ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || 'Falha ao salvar.'); }
      closeDialog();
      await load();
    } catch (err) {
      showFormError(err.message);
    } finally {
      saveBtn.disabled = false;
    }
  });

  deleteBtn.addEventListener('click', async () => {
    const ev = state.editing;
    if (!ev || !confirm(`Excluir "${ev.title}"? Essa ação não pode ser desfeita.`)) return;
    deleteBtn.disabled = true;
    try {
      const res = await fetch(`/api/events/${encodeURIComponent(ev.id)}`, { method: 'DELETE' });
      if (!res.ok && res.status !== 204) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || 'Falha ao excluir.'); }
      closeDialog();
      await load();
    } catch (err) {
      showFormError(err.message);
    } finally {
      deleteBtn.disabled = false;
    }
  });

  function showFormError(msg) { formError.textContent = msg; formError.hidden = false; }

  // ---------- controles ----------
  function syncViewButtons() {
    document.querySelectorAll('.view-switch button').forEach((b) => b.classList.toggle('active', b.dataset.view === state.view));
  }
  document.querySelectorAll('.view-switch button').forEach((b) => {
    b.addEventListener('click', () => { state.view = b.dataset.view; syncViewButtons(); load(); });
  });
  $('#ag-prev').addEventListener('click', () => { shiftAnchor(-1); load(); });
  $('#ag-next').addEventListener('click', () => { shiftAnchor(1); load(); });
  $('#ag-today').addEventListener('click', () => { state.anchor = noon(new Date()); load(); });
  $('#ag-new').addEventListener('click', () => {
    const k = tzParts(new Date()).key;
    openNew(`${k}T09:00`, `${k}T10:00`);
  });
  $('#ag-clear').addEventListener('click', () => {
    Object.values(filters).forEach((f) => { if (f.type === 'checkbox') f.checked = false; else f.value = ''; });
    filters.hide.checked = true;
    load();
  });
  $('#filters-toggle').addEventListener('click', () => {
    $('#filters').classList.toggle('filters--open');
  });

  function shiftAnchor(dir) {
    const a = state.anchor;
    if (state.view === 'day') a.setDate(a.getDate() + dir);
    else if (state.view === 'week') a.setDate(a.getDate() + dir * 7);
    else a.setMonth(a.getMonth() + dir);
    state.anchor = noon(a);
  }

  const debounce = (fn, ms = 250) => { let t; return () => { clearTimeout(t); t = setTimeout(fn, ms); }; };
  ['text', 'attendee'].forEach((k) => filters[k].addEventListener('input', debounce(paint)));
  ['from', 'to'].forEach((k) => filters[k].addEventListener('change', paint));
  ['allday', 'people', 'hide'].forEach((k) => filters[k].addEventListener('change', paint));
  ['start', 'end'].forEach((k) => filters[k].addEventListener('change', load));

  app.onConnChange.push((connected) => { if (connected && document.querySelector('#view-agenda').hidden === false) load(); });

  syncViewButtons();

  return {
    activate() {
      if (!state.loaded) load();
      else paint();
    },
  };
}
