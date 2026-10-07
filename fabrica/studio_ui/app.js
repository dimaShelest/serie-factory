/* Студія промптів (fabrica studio) — одна сторінка над JSON API (DESIGN §16).
   Vanilla ES2020, без збірки й без CDN. Помилки сервера ({"error": "…"}) показуємо дослівно.
   Порядок картки = порядок роботи людини: скопіювати промпт → прикріпити файли → зробити руками →
   записати результат (оцінка ≥ 4 → «готово») → за потреби описати, що не так, і застосувати виправлення. */
'use strict';

const API = {
  state: '/api/state',
  status: '/api/status',
  log: '/api/log',
  approve: '/api/approve',
  rewrite: '/api/rewrite',
  apply: '/api/rewrite/apply',
  lessons: '/api/lessons',
  toggle: '/api/lessons/toggle',
  media: '/media',
};
const TOOLS = ['dropshot', 'ai-studio', 'gemini', 'elevenlabs', 'replicate', 'cloudflare', 'other'];
const TOOL_UA = {
  dropshot: 'dropshot', 'ai-studio': 'AI Studio', gemini: 'Gemini', elevenlabs: 'ElevenLabs',
  replicate: 'Replicate', cloudflare: 'Cloudflare', other: 'інше',
};
// підрядок у назві поверхні → інструмент журналу (береться той, що стоїть у назві найраніше)
const TOOL_NEEDLES = [['dropshot', 'dropshot'], ['ai studio', 'ai-studio'], ['gemini', 'gemini'],
  ['elevenlabs', 'elevenlabs'], ['replicate', 'replicate'], ['cloudflare', 'cloudflare']];
const STATUS_UA = {todo: 'ще не робили', in_work: 'в роботі', done: 'готово', approved: '★ затверджено', skip: 'пропущено'};
const CLOSED = new Set(['done', 'approved', 'skip']);
const KIND_UA = {image: 'фото', video: 'відео', voice: 'голос'};
const FACE_UA = {clear: 'обличчя видно', partial: 'обличчя частково', none: 'без облич'};
const SLOT_UA = {'start frame': 'стартовий кадр', 'end frame': 'кінцевий кадр', 'last frame': 'кінцевий кадр'};
const WARN_UA = {api: 'API', lint: 'lint', data: 'дані'};
const TARGET_UA = {overlay: 'шот', prompt_en: 'prompt_en', line: 'репліка'};
const SCORE_HINT = {1: 'погано', 2: 'слабко', 3: 'майже', 4: 'добре — готово', 5: 'ідеально'};
const IMAGE = /\.(png|jpe?g|webp|gif|avif)$/i;
const VIDEO = /\.(mp4|mov|webm|m4v)$/i;
const AUDIO = /\.(mp3|wav|m4a|ogg|flac)$/i;
const NO_LOCAL = "файлу немає на цьому комп'ютері";
const OFFLINE = 'Немає зв’язку зі студією. Вона запущена? (uv run fabrica studio)';

// ---------------------------------------------------------------- чисті функції (тестуються в node)

function num(x) {
  const n = typeof x === 'number' ? x : Number(x);
  if (x === null || x === undefined || x === '' || Number.isNaN(n)) return String(x ?? '');
  return Number.isInteger(n) ? String(n) : String(Math.round(n * 100) / 100);
}

function present(v) {
  if (v === null || v === undefined || v === '') return false;
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === 'object') return Object.keys(v).length > 0;
  return true;
}

function asText(v) {
  return typeof v === 'string' ? v : JSON.stringify(v, null, 2);
}

function qs(params) {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params || {})) if (v !== null && v !== undefined && v !== '') u.set(k, String(v));
  const s = u.toString();
  return s ? '?' + s : '';
}

function mediaUrl(path) {
  return API.media + '?path=' + encodeURIComponent(String(path));
}

function basename(path) {
  return String(path).split(/[\\/]/).pop() || 'file';
}

/** Попередження: {api, lint, data} від сервера або список рядків із префіксами «API: » / «lint: ». */
function groupWarnings(w) {
  const out = {api: [], lint: [], data: []};
  if (Array.isArray(w)) {
    for (const x of w) {
      const s = String(x);
      if (s.startsWith('API: ')) out.api.push(s.slice(5));
      else if (s.startsWith('lint: ')) out.lint.push(s.slice(6));
      else out.data.push(s);
    }
  } else if (w && typeof w === 'object') {
    for (const k of Object.keys(out)) out[k] = (Array.isArray(w[k]) ? w[k] : w[k] ? [w[k]] : []).map(String);
  }
  return out;
}

/** Профіль генерації → «dropshot · 5 с · 720p». */
function profileLabel(p) {
  if (!p || typeof p !== 'object') return '';
  const surface = String(p.surface || '').trim();
  const head = surface ? surface.split(/[\s(·,]/)[0] : String(p.name || '');
  let clip = '';
  if (Array.isArray(p.clip_s) && p.clip_s.length) clip = p.clip_s.map(num).join('/') + ' с';
  else if (p.clip_min_s != null || p.clip_max_s != null) clip = `${num(p.clip_min_s ?? '?')}–${num(p.clip_max_s ?? '?')} с`;
  let res = p.resolution || '';
  if (!res && p.resolution_by_tier && typeof p.resolution_by_tier === 'object') {
    res = [...new Set(Object.values(p.resolution_by_tier))].join('/');
  }
  return [head, clip, res].filter(Boolean).join(' · ');
}

function backendLabel(b) {
  if (!b || typeof b !== 'object') return '—';
  return [b.name, b.model].filter(Boolean).join(' · ') || '—';
}

/** Кліп → чипи «кліп 1 з 2», «5 с», «у монтаж 0–3 с», «старт з кадру «…»». Чип = масив частин; {item} — посилання. */
function clipParts(extra) {
  const ex = extra || {};
  const c = ex.clip;
  const out = [];
  if (c && typeof c === 'object' && !Array.isArray(c)) {
    if (c.index != null) out.push([`кліп ${c.index}` + (c.of ? ` з ${c.of}` : '')]);
    if (c.gen_s != null) out.push([`${num(c.gen_s)} с`]);
    if (Array.isArray(c.window) && c.window.length === 2) out.push([`у монтаж ${num(c.window[0])}–${num(c.window[1])} с`]);
    else if (ex.edit_window) out.push([String(ex.edit_window)]);
    const last = String(c.start_ref || '').endsWith('.last') || c.start === 'prev_last';
    if (c.start_item) out.push([last ? 'старт з останнього кадру ' : 'старт з кадру ', {item: c.start_item}]);
    else if (c.start === 'none') out.push(['старт без кадру (лише текст)']);
    else if (c.start_ref) out.push([`старт: ${c.start_ref}`]);
  } else if (present(c)) {
    out.push([String(c)]);
  } else if (ex.edit_window) {
    out.push([String(ex.edit_window)]);
  }
  return out;
}

function slotLabel(n, i) {
  const s = String((n && n.slot) || '').trim();
  return SLOT_UA[s.toLowerCase()] || s || `Image ${i + 1}`;
}

/** Стан референсу → частини тексту; {item} — посилання на картку, яку зробити спершу. */
function slotState(n) {
  const sc = n.score != null ? ` (${n.score}/5)` : '';
  switch (n.state) {
    case 'golden': return ['★ golden' + sc];
    case 'ok': return ['✓ є' + sc];
    case 'nofile': return [n.file ? `✓ є${sc}, але ${NO_LOCAL}` : `оцінка${sc} є, але без файлу — запиши результат із файлом`];
    case 'weak': return [`лише ${n.score ?? '?'}/5 — переробити`, ...(n.item ? [': ', {item: n.item}] : [])];
    case 'clip': return ['кліп є, останнього кадру ще немає', ...(n.item ? [' — ', {item: n.item}] : [])];
    default: return n.item ? ['ще немає — спершу ', {item: n.item}] : ['ще немає — джерела в цьому списку немає'];
  }
}

/** Інструмент за замовчуванням: найраніший у назві першої поверхні (далі — провайдер маршруту). */
function defaultTool(it) {
  const m = (Array.isArray(it.manual) && it.manual[0]) || {};
  const text = `${m.surface || ''} ${String(it.route || '').split(':')[0]}`.toLowerCase();
  let best = null;
  for (const [needle, tool] of TOOL_NEEDLES) {
    const i = text.indexOf(needle);
    if (i >= 0 && (!best || i < best[0])) best = [i, tool];
  }
  if (best) return best[1];
  return it.kind === 'voice' ? 'elevenlabs' : it.kind === 'video' ? 'dropshot' : 'ai-studio';
}

/** Ручні інструкції: dropshot першим, далі — як прийшли. */
function sortManual(man) {
  const list = (Array.isArray(man) ? man : []).filter(Boolean).map(m => (typeof m === 'string' ? {text: m} : m));
  const rank = m => (/dropshot/i.test(String(m.surface || '')) ? 0 : 1);
  return list.map((m, i) => [m, i]).sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1]).map(x => x[0]);
}

/** how → [[команда?, текст]]: абзаци через порожній рядок; абзац із відступом — команда (копіюється окремо). */
function howParts(text) {
  return String(text || '').replace(/\r\n/g, '\n').split('\n\n')
    .filter(c => c.trim()).map(c => [c.startsWith('  '), c.trim()]);
}

function tokens(s) {
  return String(s ?? '').match(/\s+|[^\s]+/g) || [];
}

/** Пословний diff (LCS) → [[op, текст]], op ∈ «=», «-», «+»; заміна кількох слів поспіль — одним блоком. */
function diffWords(a, b) {
  const A = tokens(a);
  const B = tokens(b);
  let p = 0;
  while (p < A.length && p < B.length && A[p] === B[p]) p++;
  let s = 0;
  while (s < A.length - p && s < B.length - p && A[A.length - 1 - s] === B[B.length - 1 - s]) s++;
  const x = A.slice(p, A.length - s);
  const y = B.slice(p, B.length - s);
  const n = x.length;
  const m = y.length;
  const mid = [];
  if (n * m > 2500000) {
    x.forEach(t => mid.push(['-', t]));
    y.forEach(t => mid.push(['+', t]));
  } else {
    const w = m + 1;
    const L = new Uint32Array((n + 1) * w);
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        L[i * w + j] = x[i] === y[j] ? L[(i + 1) * w + j + 1] + 1 : Math.max(L[(i + 1) * w + j], L[i * w + j + 1]);
      }
    }
    let i = 0;
    let j = 0;
    while (i < n && j < m) {
      if (x[i] === y[j]) { mid.push(['=', x[i]]); i++; j++; }
      else if (L[(i + 1) * w + j] >= L[i * w + j + 1]) { mid.push(['-', x[i]]); i++; }
      else { mid.push(['+', y[j]]); j++; }
    }
    while (i < n) mid.push(['-', x[i++]]);
    while (j < m) mid.push(['+', y[j++]]);
  }
  const ops = [...A.slice(0, p).map(t => ['=', t]), ...mid, ...A.slice(A.length - s).map(t => ['=', t])];
  const out = [];
  let del = '';
  let ins = '';
  const flush = () => {
    if (del) out.push(['-', del]);
    if (ins) out.push(['+', ins]);
    del = '';
    ins = '';
  };
  for (let k = 0; k < ops.length; k++) {
    const [op, t] = ops[k];
    if (op === '=') {
      // пробіл між двома змінами (і видалено, і додано) — частина заміни, а не чергування del/ins
      if (del && ins && /^\s+$/.test(t) && k + 1 < ops.length && ops[k + 1][0] !== '=') {
        del += t;
        ins += t;
        continue;
      }
      flush();
      if (out.length && out[out.length - 1][0] === '=') out[out.length - 1][1] += t;
      else out.push(['=', t]);
    } else if (op === '-') {
      del += t;
    } else {
      ins += t;
    }
  }
  flush();
  return out;
}

function diffStat(ops) {
  const words = t => (String(t).match(/[^\s]+/g) || []).length;
  let del = 0;
  let ins = 0;
  for (const [op, t] of ops) {
    if (op === '-') del += words(t);
    else if (op === '+') ins += words(t);
  }
  return {del, ins};
}

function fmtDate(at) {
  const d = new Date(at);
  if (!at || Number.isNaN(d.getTime())) return String(at || '');
  try {
    return d.toLocaleString('uk-UA', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'});
  } catch (e) {
    return d.toISOString().slice(0, 16).replace('T', ' ');
  }
}

function lessonIds(raw) {
  return (Array.isArray(raw) ? raw : []).map(x => (x && typeof x === 'object' ? x.id || x.rule : x)).filter(Boolean).map(String);
}

function scopeParts(scope) {
  const out = [];
  if (!scope || typeof scope !== 'object') return out;
  for (const [k, v] of Object.entries(scope)) {
    if (!present(v)) continue;
    if (Array.isArray(v)) v.forEach(t => out.push(k === 'tags' ? `#${t}` : `${k}: ${t}`));
    else out.push(`${k}: ${v}`);
  }
  return out;
}

function isOverridden(it) {
  return !!(it.overridden || (it.source && it.source.overridden) || (it.extra && it.extra.overridden));
}

function searchText(it) {
  const needs = (it.needs || []).map(n => (typeof n === 'string' ? n : `${n.ref || ''} ${n.item || ''}`));
  return [it.id, it.title, it.route, it.kind, it.template, ...needs].join(' ').toLowerCase();
}

// ---------------------------------------------------------------- стан сторінки

const S = {
  story: null,
  seq: null,
  data: null,
  items: new Map(),       // id → елемент із /api/state
  ids: '',                // порядок id — змінився → перебудувати все
  cards: new Map(),       // id → {el, item, sig}
  heads: new Map(),       // крок → {sec, head}
  step: null,             // фільтр кроку
  hideDone: false,
  query: '',
  current: null,          // картка під клавішами j / k / c
  open: new Map(),        // `${id}|${секція}` → відкрито? (переживає оновлення картки)
  form: new Map(),        // id → {tool, score, path} — незбережена форма журналу
  proposals: new Map(),   // id → пропозиція переписувача
  lessons: [],
  lessonsLoaded: false,
  topH: 0,
  lastRefresh: 0,
  offline: false,
  lastFocus: null,
};

const store = {
  get(k, d = null) {
    try {
      const v = window.localStorage.getItem('studio:' + k);
      return v === null ? d : JSON.parse(v);
    } catch (e) {
      return d;
    }
  },
  set(k, v) {
    try { window.localStorage.setItem('studio:' + k, JSON.stringify(v)); } catch (e) { /* приватне вікно */ }
  },
  del(k) {
    try { window.localStorage.removeItem('studio:' + k); } catch (e) { /* приватне вікно */ }
  },
};

// ---------------------------------------------------------------- DOM-помічники

const $ = sel => document.querySelector(sel);

function add(el, kids) {
  for (const k of [kids].flat(Infinity)) {
    if (k === null || k === undefined || k === false || k === '') continue;
    el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return el;
}

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : String(v));
  }
  return add(el, kids);
}

function partsToNodes(parts) {
  return parts.map(p => (p && typeof p === 'object' && p.item ? itemLink(p.item) : String(p)));
}

function itemLink(id) {
  if (S.items.has(id)) return h('button', {type: 'button', class: 'link', onclick: () => jump(id)}, `«${id}»`);
  return h('code', {}, `«${id}»`);
}

function ul(list) {
  return h('ul', {class: 'plain'}, (list || []).map(x => h('li', {}, typeof x === 'string' ? x : asText(x))));
}

/** <details> з пам'яттю відкриття: оновлення картки не згортає те, що людина розгорнула. */
function details(id, name, defOpen, summary, ...kids) {
  const key = `${id}|${name}`;
  const open = S.open.has(key) ? S.open.get(key) : defOpen;
  const d = h('details', {class: 'box', open}, summary, ...kids);
  d.addEventListener('toggle', () => S.open.set(key, d.open));
  return d;
}

function toast(msg, type = 'ok', ms) {
  const box = $('#toasts');
  if (!box) return;
  const t = h('div', {class: `toast ${type}`, role: type === 'error' ? 'alert' : 'status'},
    h('span', {class: 'toast-text'}, msg),
    h('button', {type: 'button', class: 'toast-x', 'aria-label': 'Закрити', onclick: () => t.remove()}, '×'));
  box.append(t);
  setTimeout(() => t.remove(), ms ?? (type === 'error' ? 12000 : type === 'warn' ? 9000 : 3500));
  while (box.children.length > 5) box.firstChild.remove();
}

function flash(btn, label) {
  if (!btn) return;
  if (!btn.dataset.label) btn.dataset.label = btn.textContent;
  btn.textContent = label;
  btn.classList.add('flash');
  clearTimeout(btn._flash);
  btn._flash = setTimeout(() => {
    btn.textContent = btn.dataset.label;
    btn.classList.remove('flash');
  }, 1500);
}

async function copyText(text, btn) {
  let ok = false;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      ok = true;
    }
  } catch (e) { /* нижче — запасний шлях */ }
  if (!ok) {
    const a = h('textarea', {class: 'offscreen', 'aria-hidden': 'true'});
    a.value = text;
    document.body.append(a);
    a.select();
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    a.remove();
  }
  if (btn) flash(btn, ok ? 'Скопійовано ✓' : 'Не вдалося');
  if (!ok) toast('Не вдалося скопіювати — виділи текст і натисни Cmd+C', 'error');
  return ok;
}

function copyBtn(label, text, cls = 'btn small') {
  return h('button', {type: 'button', class: cls, onclick: e => copyText(text, e.currentTarget)}, label);
}

function copyBlock(label, text) {
  return h('div', {class: 'cblock'},
    h('div', {class: 'cblock-head'}, h('span', {}, label), copyBtn('Копіювати', text)),
    h('pre', {}, text));
}

function setBusy(btn, on, label) {
  if (!btn) return;
  if (on) {
    btn.dataset.idle = btn.textContent;
    btn.disabled = true;
    btn.classList.add('busy');
    btn.setAttribute('data-pending', '1');
    if (label) btn.textContent = label;
  } else {
    btn.disabled = false;
    btn.classList.remove('busy');
    btn.removeAttribute('data-pending');
    if (btn.dataset.idle) btn.textContent = btn.dataset.idle;
  }
}

function mediaEl(path, caption) {
  const url = mediaUrl(path);
  const audio = AUDIO.test(path);
  let el;
  let media;
  if (IMAGE.test(path)) {
    media = h('img', {src: url, alt: caption || basename(path), loading: 'lazy'});
    el = h('a', {href: url, target: '_blank', rel: 'noopener', title: 'Відкрити в новій вкладці'}, media);
  } else if (VIDEO.test(path)) {
    media = el = h('video', {src: url, controls: true, preload: 'metadata', playsinline: true});
  } else if (audio) {
    media = el = h('audio', {src: url, controls: true, preload: 'none'});
  } else {
    return h('a', {href: url, target: '_blank', rel: 'noopener'}, caption || basename(path));
  }
  const fig = h('figure', {class: audio ? 'audio' : null}, el, caption ? h('figcaption', {}, caption) : null);
  media.addEventListener('error', () => {
    fig.replaceWith(h('div', {class: 'nofile'}, `${caption ? caption + ' · ' : ''}${NO_LOCAL}`));
  }, {once: true});
  return fig;
}

// ---------------------------------------------------------------- мережа

async function api(path, {method = 'GET', body, form, timeout = 30000} = {}) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeout);
  const opts = {method, signal: ctl.signal, headers: {Accept: 'application/json'}};
  if (form) {
    opts.body = form;
  } else if (body !== undefined) {
    opts.body = JSON.stringify(body);
    opts.headers['Content-Type'] = 'application/json; charset=utf-8';
  }
  let res;
  let text;
  try {
    res = await fetch(path, opts);
    text = await res.text();
  } catch (e) {
    throw new Error(e && e.name === 'AbortError' ? 'Студія не відповіла вчасно — спробуй ще раз.' : OFFLINE);
  } finally {
    clearTimeout(timer);
  }
  let data = null;
  try { data = text ? JSON.parse(text) : {}; } catch (e) { data = null; }
  if (!res.ok) throw new Error((data && data.error) || `Помилка студії (HTTP ${res.status})`);
  if (data === null) throw new Error('Студія відповіла не JSON — онови сторінку.');
  if (data && data.error) throw new Error(data.error);
  return data;
}

function fetchState() {
  return api(API.state + qs({story: S.story, seq: S.seq}));
}

async function refresh(forceId) {
  try {
    applyState(await fetchState(), false, forceId);
    S.offline = false;
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function quietRefresh() {
  if (!S.data || Date.now() - S.lastRefresh < 3000) return;
  try {
    applyState(await fetchState(), false);
    S.offline = false;
  } catch (e) {
    if (!S.offline) toast(e.message, 'error');
    S.offline = true;
  }
}

async function loadLessons(quiet) {
  try {
    const d = await api(API.lessons + qs({story: S.story}));
    S.lessons = Array.isArray(d.lessons) ? d.lessons : [];
    S.lessonsLoaded = true;
  } catch (e) {
    if (!quiet) toast(e.message, 'error');
    return false;
  }
  updateLessonsBtn();
  if (!$('#lessons-panel').hidden) renderLessons();
  return true;
}

// ---------------------------------------------------------------- дії

async function setStatus(it, status, btn) {
  setBusy(btn, true);
  try {
    await api(API.status, {method: 'POST', body: {story: S.story, item: it.id, status}});
    toast(`${it.id}: ${STATUS_UA[status] || status}`);
    await refresh(it.id);
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    setBusy(btn, false);
  }
}

async function approve(it, btn) {
  if (!window.confirm(`Затвердити «${it.id}» як golden?\nАвтоматика братиме саме найкращий записаний результат.`)) return;
  setBusy(btn, true, 'Затверджую…');
  try {
    const d = await api(API.approve, {method: 'POST', body: {story: S.story, item: it.id}});
    toast(d.message || `«${it.id}» затверджено ★`);
    await refresh(it.id);
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    setBusy(btn, false);
  }
}

function formState(id) {
  if (!S.form.has(id)) S.form.set(id, {});
  return S.form.get(id);
}

async function submitLog(it, f, btn) {
  const fs = formState(it.id);
  if (!fs.score) {
    toast('Постав оцінку 1–5', 'error');
    return;
  }
  const file = f.upload.files && f.upload.files[0];
  const path = f.path.value.trim().replace(/^["']+|["']+$/g, '');
  const fields = {story: S.story, item: it.id, tool: f.tool.value, score: fs.score, notes: f.notes.value.trim()};
  let opts;
  if (file) {
    const fd = new FormData();
    for (const [k, v] of Object.entries(fields)) fd.append(k, String(v));
    fd.append('upload', file, file.name);
    opts = {method: 'POST', form: fd, timeout: 600000};
  } else {
    opts = {method: 'POST', body: {...fields, file: path || null}, timeout: 120000};
  }
  setBusy(btn, true, file ? 'Завантажую…' : 'Записую…');
  try {
    const d = await api(API.log, opts);
    const en = d.entry || {};
    toast(`Записано: ${it.id} · ${en.score ?? fs.score}/5` + (en.id != null ? ` (#${en.id})` : '')
      + ((en.score ?? fs.score) >= 4 ? ' → готово ✓' : ''));
    for (const w of d.warnings || []) toast(String(w), 'warn');
    S.form.delete(it.id);
    store.del('notes:' + it.id);
    f.upload.value = '';
    await refresh(it.id);
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    setBusy(btn, false);
  }
}

async function askRewrite(it, ta, btn, out) {
  const feedback = ta.value.trim();
  if (!feedback) {
    toast('Спершу опиши, що вийшло не так', 'error');
    ta.focus();
    return;
  }
  setBusy(btn, true, 'Думаю… (до хвилини)');
  try {
    const d = await api(API.rewrite, {method: 'POST', body: {story: S.story, item: it.id, feedback}, timeout: 300000});
    if (!d.proposal) throw new Error('Студія не повернула пропозицію — спробуй ще раз.');
    S.proposals.set(it.id, d.proposal);
    if (out.isConnected) {
      out.replaceChildren(proposalView(it, d.proposal));
      out.scrollIntoView({block: 'nearest'});
    } else {
      replaceCard(S.items.get(it.id) || it);
    }
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    setBusy(btn, false);
  }
}

async function applyProposal(it, p, opts, btn) {
  const body = {story: S.story, proposal: p.id, save_lesson: !!opts.save};
  if (opts.save && opts.rule) body.rule = opts.rule;
  setBusy(btn, true, 'Застосовую…');
  try {
    const d = await api(API.apply, {method: 'POST', body, timeout: 120000});
    S.proposals.delete(it.id);
    store.del('fb:' + it.id);
    S.open.set(`${it.id}|rewrite`, false);
    toast('Промпт оновлено ✓' + (body.save_lesson ? ' · урок збережено' : ''));
    if (d.item && d.item.id) {
      S.items.set(d.item.id, d.item);
      replaceCard(d.item);
    }
    await refresh(it.id);
    if (body.save_lesson) loadLessons(true);
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    setBusy(btn, false);
  }
}

async function toggleLesson(l, sw, el) {
  sw.disabled = true;
  try {
    await api(API.toggle, {method: 'POST', body: {story: S.story, id: l.id, active: sw.checked}});
    l.active = sw.checked;
    el.classList.toggle('off', !sw.checked);
    toast(`Урок ${l.id}: ${sw.checked ? 'увімкнено' : 'вимкнено'}`);
    updateLessonsBtn();
    refresh();
  } catch (e) {
    sw.checked = !sw.checked;
    toast(e.message, 'error');
  } finally {
    sw.disabled = false;
  }
}

// ---------------------------------------------------------------- картка

function sig(it) {
  return JSON.stringify(it);
}

function cardHead(it, st) {
  const ex = it.extra || {};
  const badges = [];
  if (it.step) badges.push(h('span', {class: 'badge'}, `крок ${it.step}`));
  badges.push(h('span', {class: 'badge'}, KIND_UA[it.kind] || it.kind || '—'));
  if (it.route) badges.push(h('span', {class: 'badge route', title: 'маршрут: провайдер і модель'}, it.route));
  if (ex.face === 'clear' && String(it.route || '').startsWith('cloudflare:')) {
    badges.push(h('span', {class: 'badge face', title: 'обличчя в кадрі: dropshot може відхилити — запасний шлях Cloudflare'},
      'обличчя → Cloudflare'));
  } else if (ex.face) {
    badges.push(h('span', {class: 'badge'}, FACE_UA[ex.face] || `обличчя: ${ex.face}`));
  }
  if (it.template) badges.push(h('span', {class: 'badge', title: 'шаблон'}, it.template));
  if (it.golden) badges.push(h('span', {class: 'badge golden'}, '★ golden'));
  const ls = lessonIds(ex.lessons);
  if (ls.length) badges.push(h('span', {class: 'badge lessons', title: ls.join(', ')}, `враховано уроків: ${ls.length}`));
  if (isOverridden(it)) badges.push(h('span', {class: 'badge override'}, 'змінено через студію'));
  const apiWarn = groupWarnings(it.warnings).api.length;
  if (apiWarn) badges.push(h('span', {class: 'badge bad'}, `⚠ API: ${apiWarn}`));
  if (it.prompt_sha) badges.push(h('span', {class: 'badge', title: 'версія промпту'}, `промпт ${String(it.prompt_sha).slice(0, 8)}`));
  const pills = [h('span', {class: 'pill next-flag'}, '← далі'), h('span', {class: `pill ${st}`}, STATUS_UA[st] || st)];
  if (it.stale) pills.unshift(h('span', {class: 'pill stale', title: 'статус ставили для старої версії промпту'}, 'промпт змінився'));
  return h('header', {},
    h('div', {class: 'title-row'},
      h('h3', {}, h('code', {class: 'iid'}, it.id), it.title || ''),
      h('div', {class: 'chips', style: 'margin:0'}, pills)),
    h('div', {class: 'badges'}, badges));
}

function statusRow(it, st) {
  const mk = (status, label) => h('button', {
    type: 'button', class: `btn st-${status}`, 'aria-pressed': String(st === status),
    title: st === status ? 'Натисни ще раз, щоб скинути' : null,
    onclick: e => setStatus(it, st === status ? 'todo' : status, e.currentTarget),
  }, label);
  return h('div', {class: 'status-row', role: 'group', 'aria-label': 'Статус'},
    mk('in_work', 'В роботі'), mk('done', 'Готово ✓'), mk('skip', 'Пропустити'),
    h('button', {type: 'button', class: 'btn gold', 'aria-pressed': String(st === 'approved'),
      onclick: e => approve(it, e.currentTarget)}, '★ Затвердити golden'));
}

function promptBlock(it) {
  const prompt = String(it.prompt || '');
  return h('div', {class: 'section'},
    h('div', {class: 'prompt-head'},
      h('button', {type: 'button', class: 'btn primary big', onclick: e => copyText(prompt, e.currentTarget)}, 'Копіювати промпт'),
      h('span', {class: 'hint'}, `${prompt.length} символів · клавіша c`)),
    h('pre', {class: 'prompt'}, prompt || '— промпт порожній —'));
}

function clipBlock(it) {
  const chips = clipParts(it.extra);
  if (!chips.length) return null;
  return h('div', {class: 'chips'}, chips.map(parts => h('span', {class: 'chip on'}, partsToNodes(parts))));
}

function stateBlock(title, v) {
  if (!present(v)) return null;
  return h('div', {class: 'section state'}, h('h4', {}, title), ul(Array.isArray(v) ? v : [v]));
}

function slotEl(n, i) {
  const state = n.state || 'missing';
  const file = n.file && (state === 'ok' || state === 'golden' || state === 'weak' || state === 'clip');
  return h('li', {class: `slot s-${state}`},
    h('div', {class: 'slot-head'}, h('b', {}, slotLabel(n, i)), ' = ', h('code', {}, n.ref || '?')),
    file ? mediaEl(n.file, '') : null,
    h('div', {class: 'slot-state'}, partsToNodes(slotState(n))),
    n.file ? h('div', {class: 'slot-file'},
      'файл: ', h('code', {}, n.file),
      file ? h('a', {class: 'btn small', href: mediaUrl(n.file), download: basename(n.file)}, '⤓ Зберегти') : null,
      copyBtn('Шлях', n.file)) : null);
}

function needsBlock(it) {
  const needs = (it.needs || []).map(n => (typeof n === 'string' ? {ref: n, state: 'missing'} : n)).filter(Boolean);
  if (!needs.length) return null;
  const missing = needs.filter(n => n.state !== 'ok' && n.state !== 'golden').length;
  return h('div', {class: 'section'},
    h('h4', {}, 'Що прикріпити' + (missing ? ` · бракує ${missing}` : ' · усе є ✓')),
    h('ol', {class: 'slots'}, needs.map(slotEl)));
}

function manualOne(it, m, j) {
  const head = [m.surface, m.title].filter(Boolean).join(' — ') || 'Інструкція';
  const body = [];
  if (m.url) body.push(h('p', {class: 'url'}, h('a', {href: m.url, target: '_blank', rel: 'noopener'}, m.url)));
  for (const [cmd, chunk] of howParts(m.how)) body.push(cmd ? copyBlock('Команда', chunk) : h('p', {class: 'how'}, chunk));
  if (present(m.text)) body.push(copyBlock('Текст', asText(m.text)));
  if (present(m.endpoint)) body.push(copyBlock('Endpoint', asText(m.endpoint)));
  if (present(m.cmd)) body.push(copyBlock('Команда', asText(m.cmd)));
  if (present(m.body)) body.push(copyBlock('Тіло запиту (JSON)', asText(m.body)));
  if (present(m.json)) body.push(copyBlock('JSON', asText(m.json)));
  for (const [cmd, chunk] of howParts(typeof m.note === 'string' ? m.note : m.note ? asText(m.note) : '')) {
    body.push(cmd ? copyBlock('Команда', chunk) : h('p', {class: 'note'}, chunk));
  }
  if (!body.length) body.push(h('p', {class: 'hint'}, 'Деталей немає.'));
  return details(it.id, `manual${j}`, j === 0, h('summary', {}, head), body);
}

function manualBlock(it) {
  const man = sortManual(it.manual);
  if (!man.length) return null;
  return h('div', {class: 'section'}, h('h4', {}, 'Як зробити руками'), man.map((m, j) => manualOne(it, m, j)));
}

function payloadBlock(it) {
  if (!present(it.payload)) return null;
  const text = asText(it.payload);
  const copy = h('button', {type: 'button', class: 'btn small', onclick: e => {
    e.preventDefault();
    e.stopPropagation();
    copyText(text, e.currentTarget);
  }}, 'Копіювати JSON');
  return h('div', {class: 'section'}, details(it.id, 'payload', false,
    h('summary', {class: 'bar-sum'}, h('span', {class: 'grow'}, 'Payload — тіло запиту до API (JSON)'), copy),
    h('pre', {}, text)));
}

function previewBlock(it) {
  const p = it.extra && it.extra.preview_es;
  return present(p) ? h('div', {class: 'section'}, copyBlock("Текст прев'ю голосу (іспанською)", asText(p))) : null;
}

function successBlock(it) {
  const s = it.extra && it.extra.success;
  if (!present(s)) return null;
  return h('div', {class: 'section success'}, h('h4', {}, 'Успіх, якщо'), ul(Array.isArray(s) ? s : [s]));
}

function warningsBlock(it) {
  const w = groupWarnings(it.warnings);
  const total = w.api.length + w.lint.length + w.data.length;
  if (!total) return null;
  const sum = Object.keys(w).filter(k => w[k].length).map(k => h('span', {class: `wsum ${k} has`}, `${WARN_UA[k]} ${w[k].length}`));
  const groups = Object.keys(w).filter(k => w[k].length)
    .map(k => h('div', {class: `wgroup ${k}`}, h('h5', {}, `${WARN_UA[k]} (${w[k].length})`), ul(w[k])));
  return h('div', {class: 'section'},
    details(it.id, 'warnings', false, h('summary', {}, `⚠ Попередження (${total})`, ...sum), groups));
}

function lessonsBlock(it) {
  const ids = lessonIds(it.extra && it.extra.lessons);
  if (!ids.length) return null;
  const rules = new Map(S.lessons.map(l => [String(l.id), l.rule]));
  return h('div', {class: 'section'}, details(it.id, 'lessons', false,
    h('summary', {}, `Уроки в промпті (${ids.length})`),
    ul(ids.map(id => (rules.get(id) ? `${id}: ${rules.get(id)}` : id)))));
}

function resultEl(r) {
  const sc = Number(r.score);
  const old = r.current === false;
  return h('div', {class: 'result' + (old ? ' old' : '')},
    r.file ? mediaEl(r.file, '') : h('div', {class: 'nofile'}, 'без файлу'),
    r.last_frame ? h('div', {style: 'margin-top:6px'}, mediaEl(r.last_frame, 'останній кадр')) : null,
    h('div', {class: 'meta'},
      h('span', {class: `score-badge s${sc}`}, `${r.score ?? '?'}/5`), ' ',
      h('b', {}, TOOL_UA[r.tool] || r.tool || ''),
      ` · #${r.id ?? '?'}`, r.at ? ` · ${fmtDate(r.at)}` : '', old ? ' · стара версія промпту' : ''),
    r.notes ? h('div', {class: 'notes'}, r.notes) : null);
}

function resultsBlock(it) {
  const rs = (Array.isArray(it.results) ? it.results : []).slice().sort((a, b) => (b.id ?? 0) - (a.id ?? 0));
  if (!rs.length) return null;
  const rest = rs.slice(6);
  return h('div', {class: 'section'},
    h('h4', {}, `Результати (${rs.length})`),
    h('div', {class: 'results'}, rs.slice(0, 6).map(resultEl)),
    rest.length ? details(it.id, 'more-results', false, h('summary', {}, `Ще ${rest.length}`),
      h('div', {class: 'results'}, rest.map(resultEl))) : null);
}

function logBlock(it) {
  const fs = formState(it.id);
  const tool = fs.tool || store.get('tool:' + it.kind) || defaultTool(it);
  const toolSel = h('select', {name: 'tool'}, TOOLS.map(t => h('option', {value: t}, TOOL_UA[t])));
  toolSel.value = TOOLS.includes(tool) ? tool : 'other';
  toolSel.addEventListener('change', () => {
    formState(it.id).tool = toolSel.value;
    store.set('tool:' + it.kind, toolSel.value);
  });
  const hint = h('span', {class: 'hint'}, fs.score ? SCORE_HINT[fs.score] : '≥ 4 — елемент стає «готово»');
  const scoreBtns = [1, 2, 3, 4, 5].map(n => h('button', {
    type: 'button', class: 'score-btn' + (n <= 2 ? ' lo' : n >= 4 ? ' hi' : ''), 'aria-pressed': String(fs.score === n),
    title: SCORE_HINT[n], 'aria-label': `Оцінка ${n} — ${SCORE_HINT[n]}`,
    onclick: () => {
      formState(it.id).score = n;
      scoreBtns.forEach((b, i) => b.setAttribute('aria-pressed', String(i + 1 === n)));
      hint.textContent = SCORE_HINT[n];
    },
  }, String(n)));
  const notes = h('textarea', {name: 'notes', placeholder: 'Що вийшло, що не так (необов’язково)'});
  notes.value = store.get('notes:' + it.id, '') || '';
  notes.addEventListener('input', () => store.set('notes:' + it.id, notes.value));
  const upload = h('input', {type: 'file', name: 'upload', accept: 'image/*,video/*,audio/*'});
  const path = h('input', {type: 'text', name: 'path', placeholder: 'або шлях до файлу: ~/Downloads/result.mp4',
    autocomplete: 'off', spellcheck: 'false'});
  path.value = fs.path || '';
  path.addEventListener('input', () => { formState(it.id).path = path.value; });
  const drop = h('div', {class: 'drop'},
    h('span', {class: 'field-label'}, 'Файл результату — перетягни сюди або вибери'), upload,
    h('span', {class: 'or'}, '— або —'), path);
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', e => {
    e.preventDefault();
    e.stopPropagation();
    drop.classList.remove('over');
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
      upload.files = e.dataTransfer.files;
      toast(`Файл: ${e.dataTransfer.files[0].name}`);
    }
  });
  const submit = h('button', {type: 'submit', class: 'btn primary big'}, 'Записати результат');
  const form = h('form', {class: 'log', novalidate: true},
    h('div', {class: 'row'},
      h('label', {}, h('span', {class: 'field-label'}, 'Інструмент'), toolSel),
      h('div', {class: 'grow'}, h('span', {class: 'field-label'}, 'Оцінка'),
        h('div', {class: 'scores', role: 'group', 'aria-label': 'Оцінка 1–5'}, scoreBtns), hint)),
    h('label', {}, h('span', {class: 'field-label'}, 'Нотатки'), notes),
    drop,
    h('div', {class: 'actions'}, submit));
  form.addEventListener('submit', e => {
    e.preventDefault();
    submitLog(it, form.elements, submit);
  });
  return h('div', {class: 'section'}, details(it.id, 'log', it.status === 'in_work' || !!fs.score,
    h('summary', {}, '＋ Записати результат'), form));
}

function changeView(c) {
  const where = [TARGET_UA[c.target] || c.target, c.key].filter(Boolean).join(' ');
  const head = h('div', {class: 'field'}, `${where ? where + ' · ' : ''}${c.field || ''}`);
  if (typeof c.old === 'string' && typeof c.new === 'string') {
    return h('div', {class: 'change'}, head, h('span', {class: 'hint'}, 'було → стало'), diffPre(diffWords(c.old, c.new)));
  }
  return h('div', {class: 'change'}, head, h('div', {class: 'two'},
    h('div', {}, h('span', {class: 'hint'}, 'було'), h('pre', {class: 'old'}, c.old == null ? '—' : asText(c.old))),
    h('div', {}, h('span', {class: 'hint'}, 'стало'), h('pre', {class: 'new'}, c.new == null ? '—' : asText(c.new)))));
}

function diffPre(ops) {
  return h('pre', {class: 'diff'}, ops.map(([op, t]) => (op === '=' ? t : h(op === '-' ? 'del' : 'ins', {}, t))));
}

function proposalView(it, p) {
  const changes = Array.isArray(p.changes) ? p.changes : [];
  const lesson = p.lesson && typeof p.lesson === 'object' ? p.lesson : null;
  const box = h('div', {class: 'proposal'},
    h('h5', {}, `Пропозиція${p.id ? ' ' + p.id : ''}${p.backend ? ' · ' + p.backend : ''}`));
  if (!changes.length) box.append(h('p', {class: 'hint'}, 'Модель не запропонувала змін у полях.'));
  changes.forEach(c => box.append(changeView(c)));
  if (p.prompt_old != null || p.prompt_new != null) {
    const ops = diffWords(p.prompt_old, p.prompt_new);
    const st = diffStat(ops);
    box.append(h('div', {},
      h('div', {class: 'cblock-head'},
        h('span', {}, `Промпт: було → стало · −${st.del} / +${st.ins} слів`),
        copyBtn('Копіювати новий', String(p.prompt_new || ''))),
      diffPre(ops)));
  }
  if (present(p.warnings_new)) {
    box.append(h('div', {class: 'wgroup lint'}, h('h5', {}, `Попередження нового промпту (${p.warnings_new.length})`),
      ul(p.warnings_new)));
  }
  let ruleTa = null;
  let save = null;
  if (lesson) {
    ruleTa = h('textarea', {'aria-label': 'Правило уроку'});
    ruleTa.value = lesson.rule || '';
    save = h('input', {type: 'checkbox', checked: true});
    box.append(h('div', {class: 'lesson-box'},
      h('h5', {}, 'Урок'),
      lesson.problem ? h('p', {class: 'hint', style: 'margin:0'}, `Проблема: ${lesson.problem}`) : null,
      h('label', {}, h('span', {class: 'field-label'}, 'Правило (англійською, одне речення — можна виправити)'), ruleTa),
      scopeParts(lesson.scope).length ? h('div', {class: 'chips', style: 'margin:0'},
        scopeParts(lesson.scope).map(s => h('span', {class: 'chip'}, s))) : null,
      h('label', {class: 'toggle'}, save, "Запам'ятати урок")));
  }
  const applyBtn = h('button', {type: 'button', class: 'btn primary big'}, 'Застосувати');
  const sync = () => { applyBtn.disabled = !changes.length && !(save && save.checked); };
  if (save) save.addEventListener('change', sync);
  sync();
  applyBtn.addEventListener('click', () => applyProposal(it, p,
    {save: !!(save && save.checked), rule: ruleTa ? ruleTa.value.trim() : ''}, applyBtn));
  const reject = h('button', {type: 'button', class: 'btn', onclick: () => {
    S.proposals.delete(it.id);
    box.remove();
  }}, 'Відхилити');
  box.append(h('div', {class: 'actions'}, applyBtn, reject));
  return box;
}

function rewriteBlock(it) {
  const p = S.proposals.get(it.id);
  const be = (S.data && S.data.rewrite_backend) || {};
  const ta = h('textarea', {placeholder: 'Напр.: «ліхтарик світить у камеру, а має — на стелю; хлопець дивиться в об’єктив»'});
  ta.value = store.get('fb:' + it.id, '') || '';
  ta.addEventListener('input', () => store.set('fb:' + it.id, ta.value));
  const out = h('div', {}, p ? proposalView(it, p) : null);
  const go = h('button', {type: 'button', class: 'btn primary'}, 'Запропонувати зміни');
  go.addEventListener('click', () => askRewrite(it, ta, go, out));
  const src = it.source && present(it.source.fields)
    ? details(it.id, 'source', false,
      h('summary', {}, `Поля, які можна змінити (${[it.source.kind, it.source.key].filter(Boolean).join(' ')})`),
      h('pre', {}, asText(it.source.fields)))
    : null;
  return h('div', {class: 'section'}, details(it.id, 'rewrite', !!p, h('summary', {}, '✎ Редагувати промпт'),
    h('div', {class: 'rewrite'},
      h('label', {}, h('span', {class: 'field-label'}, 'Опиши, що вийшло не так (можна українською)'), ta),
      be.ok === false ? h('p', {class: 'backend-warn'}, `Переписувач недоступний: ${be.note || backendLabel(be)}`) : null,
      h('div', {class: 'actions'}, go, h('span', {class: 'hint'}, `модель: ${backendLabel(be)}`)),
      src, out)));
}

function card(it) {
  const st = it.status || 'todo';
  const ex = it.extra || {};
  const el = h('article', {class: `card st-${st}`, id: 'card-' + it.id, 'data-id': it.id, tabindex: '-1',
    'aria-label': `${it.id} — ${it.title || ''}`});
  el.addEventListener('pointerdown', () => { if (S.current !== it.id) setCurrent(it.id, false); });
  return add(el, [
    cardHead(it, st),
    statusRow(it, st),
    promptBlock(it),
    clipBlock(it),
    stateBlock('Стан із попереднього шоту — має бути в кадрі', ex.state_in),
    needsBlock(it),
    manualBlock(it),
    payloadBlock(it),
    previewBlock(it),
    successBlock(it),
    stateBlock('Стан на кінці шоту → наступний шот', ex.state_out),
    warningsBlock(it),
    lessonsBlock(it),
    resultsBlock(it),
    logBlock(it),
    rewriteBlock(it),
  ]);
}

/** Картка зайнята: людина в полі вводу, вибрала файл або чекає відповіді — тихе оновлення її не чіпає. */
function isBusy(el) {
  const a = document.activeElement;
  if (a && el.contains(a) && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) return true;
  if (el.querySelector('[data-pending], .proposal')) return true;
  return [...el.querySelectorAll('input[type="file"]')].some(f => f.files && f.files.length);
}

function replaceCard(it) {
  const c = S.cards.get(it.id);
  const el = card(it);
  if (c) c.el.replaceWith(el);
  S.cards.set(it.id, {el, item: it, sig: sig(it)});
  markCurrent();
  applyFilters();
}

// ---------------------------------------------------------------- сторінка

function stepInfo(n) {
  const s = (S.data.steps || []).find(x => (x.n ?? x.step) === n);
  return s || {title: n ? `Крок ${n}` : 'Без кроку', todo: ''};
}

function groupBySteps(items) {
  const g = new Map();
  for (const it of items) {
    const n = Number(it.step) || 0;
    if (!g.has(n)) g.set(n, []);
    g.get(n).push(it);
  }
  return new Map([...g.entries()].sort((a, b) => (a[0] === 0) - (b[0] === 0) || a[0] - b[0]));
}

function stepHead(n, list) {
  const s = stepInfo(n);
  const closed = list.filter(i => CLOSED.has(i.status)).length;
  return h('div', {class: 'step-head'},
    h('h2', {}, n ? `Крок ${n} · ${s.title || ''}` : s.title || 'Без кроку'),
    s.todo ? h('p', {}, s.todo) : null,
    s.tool ? h('p', {}, h('b', {}, 'Чим: '), s.tool) : null,
    h('p', {class: 'count'}, `готово ${closed} з ${list.length}`));
}

function renderTop() {
  const d = S.data;
  const items = d.items || [];
  $('#story').textContent = d.story || '';
  document.title = `${d.story || 'Студія'} · студія промптів`;
  const seqs = Array.isArray(d.sequences) ? d.sequences.slice() : [];
  if (d.seq && !seqs.some(s => s.name === d.seq)) seqs.unshift({name: d.seq, title: d.seq});
  const sel = $('#seq');
  sel.replaceChildren(...seqs.map(s => h('option', {value: s.name}, s.title || s.name)));
  sel.value = d.seq || '';
  const pc = $('#profile-chip');
  const pl = profileLabel(d.profile);
  pc.hidden = !pl;
  pc.textContent = pl;
  pc.title = d.profile ? ['профіль генерації: ' + (d.profile.name || ''), d.profile.surface, d.profile.note].filter(Boolean).join(' · ') : '';
  const bc = $('#backend-chip');
  const b = d.rewrite_backend;
  bc.hidden = !b;
  if (b) {
    const bad = b.ok === false;
    bc.className = 'chip ' + (bad ? 'bad' : 'ok');
    bc.textContent = `✎ ${backendLabel(b)} ${bad ? '✗' : '✓'}`;
    bc.title = bad ? `Переписувач недоступний: ${b.note || ''}` : b.note || 'Переписувач промптів готовий';
  }
  const pr = d.progress || {};
  const done = pr.done ?? items.filter(i => CLOSED.has(i.status)).length;
  const total = pr.total ?? items.length;
  $('#progress-fill').style.width = total ? `${Math.min(100, Math.round((100 * done) / total))}%` : '0%';
  $('#progress-text').textContent = `${done} / ${total}`;
  const pb = $('#progress');
  pb.setAttribute('aria-valuemax', String(total));
  pb.setAttribute('aria-valuenow', String(done));
  const nl = $('#next-line');
  const nx = pr.next ? S.items.get(pr.next) : null;
  if (pr.next) {
    nl.replaceChildren('Далі: ', nx && nx.step ? `крок ${nx.step} · ` : '', itemLink(pr.next), nx && nx.title ? ` — ${nx.title}` : '');
  } else {
    nl.replaceChildren(items.length ? 'Усе в цій послідовності зроблено ✓' : '');
  }
  $('#next-btn').disabled = !pr.next;
}

function renderSteps() {
  const items = S.data.items || [];
  const counts = new Map();
  for (const it of items) {
    const n = Number(it.step) || 0;
    const c = counts.get(n) || {total: 0, closed: 0};
    c.total++;
    if (CLOSED.has(it.status)) c.closed++;
    counts.set(n, c);
  }
  const steps = (S.data.steps || []).map(s => ({n: s.n ?? s.step, title: s.title, todo: s.todo}));
  for (const n of counts.keys()) if (!steps.some(s => s.n === n)) steps.push({n, title: n ? `Крок ${n}` : 'Без кроку'});
  steps.sort((a, b) => (a.n === 0) - (b.n === 0) || a.n - b.n);
  const btn = (n, mark, label, c, title) => {
    const complete = c.total > 0 && c.closed === c.total;
    return h('button', {
      type: 'button', title: title || null, disabled: !c.total && n !== null,
      class: 'step-btn' + (S.step === n ? ' on' : '') + (complete ? ' complete' : '') + (c.total ? '' : ' empty'),
      'aria-pressed': String(S.step === n), onclick: () => setStep(S.step === n ? null : n),
    }, h('span', {class: 'step-n'}, complete ? '✓' : mark), h('span', {}, label), h('span', {class: 'step-c'}, `${c.closed} / ${c.total}`));
  };
  const all = {total: items.length, closed: items.filter(i => CLOSED.has(i.status)).length};
  $('#step-list').replaceChildren(btn(null, '≡', 'Усі кроки', all, ''),
    ...steps.map(s => btn(s.n, String(s.n || '·'), s.title || `Крок ${s.n}`, counts.get(s.n) || {total: 0, closed: 0}, s.todo)));
}

function renderMain() {
  const main = $('#main');
  S.cards.clear();
  S.heads.clear();
  const items = S.data.items || [];
  if (!items.length) {
    main.replaceChildren(h('p', {class: 'empty-note'}, 'У цій послідовності немає елементів.'));
    return;
  }
  const secs = [];
  for (const [n, list] of groupBySteps(items)) {
    const head = stepHead(n, list);
    const cards = list.map(it => {
      const el = card(it);
      S.cards.set(it.id, {el, item: it, sig: sig(it)});
      return el;
    });
    const sec = h('section', {class: 'step-sec', 'data-step': String(n)}, head, ...cards);
    S.heads.set(n, {sec, head});
    secs.push(sec);
  }
  secs.push(h('p', {class: 'empty-note', id: 'filtered-empty', hidden: true}, 'За цим фільтром нічого немає.'));
  main.replaceChildren(...secs);
  if (S.current && !S.cards.has(S.current)) S.current = null;
  markCurrent();
}

function updateMain(forceId) {
  for (const [n, list] of groupBySteps(S.data.items || [])) {
    const g = S.heads.get(n);
    if (!g) continue;
    const head = stepHead(n, list);
    g.head.replaceWith(head);
    g.head = head;
  }
  for (const it of S.data.items || []) {
    const c = S.cards.get(it.id);
    if (!c) continue;
    if (c.sig === sig(it)) {
      c.item = it;
    } else if (it.id === forceId || !isBusy(c.el)) {
      replaceCard(it);
    } else {
      c.item = it;                 // зайнята — оновимо наступного разу (sig лишається старим)
    }
  }
}

function applyState(d, rebuild, forceId) {
  S.data = d;
  S.story = d.story || S.story;
  S.seq = d.seq || S.seq;
  S.items = new Map((d.items || []).map(it => [it.id, it]));
  S.lastRefresh = Date.now();
  if (S.step !== null && !(d.items || []).some(it => (Number(it.step) || 0) === S.step)) S.step = null;
  syncUrl();
  const ids = (d.items || []).map(it => it.id).join('\n');
  renderTop();
  renderSteps();
  if (rebuild || ids !== S.ids) {
    S.ids = ids;
    renderMain();
  } else {
    updateMain(forceId);
  }
  markNext();
  applyFilters();
}

function syncUrl() {
  try {
    const url = location.pathname + qs({story: S.story, seq: S.seq});
    if (url !== location.pathname + location.search) history.replaceState(null, '', url);
  } catch (e) { /* не критично */ }
}

function applyFilters() {
  const q = S.query.trim().toLowerCase();
  let shown = 0;
  for (const c of S.cards.values()) {
    const it = c.item;
    const ok = (S.step === null || (Number(it.step) || 0) === S.step)
      && (!S.hideDone || !CLOSED.has(it.status))
      && (!q || searchText(it).includes(q));
    c.el.hidden = !ok;
    if (ok) shown++;
  }
  for (const g of S.heads.values()) g.sec.hidden = !g.sec.querySelector('article.card:not([hidden])');
  const e = document.getElementById('filtered-empty');
  if (e) e.hidden = shown > 0 || !S.cards.size;
}

function markCurrent() {
  for (const c of S.cards.values()) c.el.classList.toggle('current', c.item.id === S.current);
}

function markNext() {
  const next = S.data && S.data.progress && S.data.progress.next;
  for (const c of S.cards.values()) c.el.classList.toggle('is-next', c.item.id === next);
}

function setStep(n) {
  S.step = n;
  store.set('step', n);
  renderSteps();
  applyFilters();
  window.scrollTo({top: 0});
}

function resetFilters() {
  S.step = null;
  S.hideDone = false;
  S.query = '';
  $('#search').value = '';
  $('#hide-done').checked = false;
  store.set('step', null);
  store.set('hideDone', false);
  renderSteps();
  applyFilters();
}

function setCurrent(id, scroll) {
  S.current = id;
  markCurrent();
  const c = S.cards.get(id);
  if (c && scroll) {
    c.el.scrollIntoView({block: 'start'});
    c.el.focus({preventScroll: true});
  }
}

function jump(id) {
  const c = S.cards.get(id);
  if (!c) {
    toast(`«${id}» немає в цій послідовності`, 'warn');
    return;
  }
  if (c.el.hidden) resetFilters();
  setCurrent(id, true);
  c.el.classList.remove('pulse');
  void c.el.offsetWidth;
  c.el.classList.add('pulse');
}

function goNext() {
  const next = S.data && S.data.progress && S.data.progress.next;
  if (next) jump(next);
  else toast('Усе в цій послідовності зроблено ✓');
}

function visibleCards() {
  return [...document.querySelectorAll('#main article.card:not([hidden])')];
}

function nearestCard(cards) {
  const i = cards.findIndex(c => c.getBoundingClientRect().bottom > S.topH + 40);
  return i < 0 ? cards.length - 1 : i;
}

function move(d) {
  const cards = visibleCards();
  if (!cards.length) return;
  let i = cards.findIndex(c => c.dataset.id === S.current);
  i = i < 0 ? nearestCard(cards) : Math.min(cards.length - 1, Math.max(0, i + d));
  setCurrent(cards[i].dataset.id, true);
}

function copyCurrent() {
  const cards = visibleCards();
  let id = S.current;
  if (!id || !S.cards.has(id) || S.cards.get(id).el.hidden) {
    if (!cards.length) return;
    id = cards[nearestCard(cards)].dataset.id;
    setCurrent(id, false);
  }
  const it = S.cards.get(id).item;
  copyText(String(it.prompt || '')).then(ok => { if (ok) toast(`Промпт «${id}» скопійовано`); });
}

function updateLessonsBtn() {
  const btn = $('#lessons-btn');
  const active = S.lessons.filter(l => l.active !== false).length;
  btn.textContent = S.lessons.length ? `Уроки · ${active}/${S.lessons.length}` : 'Уроки';
}

function lessonEl(l) {
  const sw = h('input', {type: 'checkbox', role: 'switch', checked: l.active !== false, 'aria-label': `Урок ${l.id} активний`});
  const el = h('div', {class: 'lesson' + (l.active === false ? ' off' : '')},
    h('div', {class: 'lesson-top'}, h('b', {}, l.id || '?'), h('label', {class: 'toggle'}, sw, 'активний')),
    h('div', {class: 'rule'}, l.rule || ''),
    l.problem ? h('div', {class: 'problem'}, `Проблема: ${l.problem}`) : null,
    h('div', {class: 'meta'},
      l.item ? h('span', {class: 'chip'}, l.item) : null,
      scopeParts(l.scope).map(s => h('span', {class: 'chip'}, s)),
      l.at ? h('span', {class: 'chip'}, fmtDate(l.at)) : null));
  sw.addEventListener('change', () => toggleLesson(l, sw, el));
  return el;
}

function renderLessons() {
  const body = $('#lessons-body');
  if (!S.lessonsLoaded) {
    body.replaceChildren(h('p', {class: 'loading'}, 'Завантажую…'));
    return;
  }
  if (!S.lessons.length) {
    body.replaceChildren(h('p', {class: 'empty-note'},
      "Уроків ще немає. Урок з'являється, коли ти виправляєш промпт через «Редагувати промпт» і лишаєш галочку «Запам'ятати урок»."));
    return;
  }
  body.replaceChildren(
    h('p', {class: 'hint'}, 'Активні уроки дописуються в промпти, яких стосуються. Вимкни урок, якщо він заважає.'),
    ...S.lessons.map(lessonEl));
}

function openLessons() {
  S.lastFocus = document.activeElement;
  $('#backdrop').hidden = false;
  $('#lessons-panel').hidden = false;
  renderLessons();
  $('#lessons-close').focus();
  loadLessons(false);
}

function closeLessons() {
  $('#backdrop').hidden = true;
  $('#lessons-panel').hidden = true;
  if (S.lastFocus && S.lastFocus.focus) S.lastFocus.focus({preventScroll: true});
}

function trackTop() {
  const top = $('#top');
  const set = () => {
    const sticky = getComputedStyle(top).position === 'sticky';
    S.topH = sticky ? top.offsetHeight : 0;
    document.documentElement.style.setProperty('--top-h', `${S.topH}px`);
  };
  set();
  if ('ResizeObserver' in window) new ResizeObserver(set).observe(top);
  window.addEventListener('resize', set);
}

function onKey(e) {
  if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
  if (!$('#lessons-panel').hidden) {
    if (e.key === 'Escape') closeLessons();
    return;
  }
  const t = e.target;
  if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) {
    if (e.key === 'Escape') t.blur();
    return;
  }
  if (e.key === 'j') move(1);
  else if (e.key === 'k') move(-1);
  else if (e.key === 'c') copyCurrent();
  else if (e.key === 'n') goNext();
  else return;
  e.preventDefault();
}

function bindStatic() {
  trackTop();
  S.step = store.get('step', null);
  S.hideDone = !!store.get('hideDone', false);
  $('#hide-done').checked = S.hideDone;
  $('#seq').addEventListener('change', async e => {
    const prev = S.seq;
    S.seq = e.target.value;
    S.current = null;
    S.proposals.clear();
    try {
      applyState(await fetchState(), true);
      window.scrollTo({top: 0});
    } catch (err) {
      S.seq = prev;
      e.target.value = prev || '';
      toast(err.message, 'error');
    }
  });
  $('#next-btn').addEventListener('click', goNext);
  $('#lessons-btn').addEventListener('click', openLessons);
  $('#lessons-close').addEventListener('click', closeLessons);
  $('#backdrop').addEventListener('click', closeLessons);
  $('#search').addEventListener('input', e => {
    S.query = e.target.value;
    applyFilters();
  });
  $('#hide-done').addEventListener('change', e => {
    S.hideDone = e.target.checked;
    store.set('hideDone', S.hideDone);
    applyFilters();
  });
  document.addEventListener('keydown', onKey);
  // файл, кинутий повз зону завантаження, не повинен відкриватися замість студії
  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', e => e.preventDefault());
  document.addEventListener('visibilitychange', () => { if (!document.hidden) quietRefresh(); });
  window.addEventListener('focus', quietRefresh);
}

function fatal(e) {
  $('#main').replaceChildren(h('div', {class: 'fatal', role: 'alert'},
    h('p', {}, h('b', {}, 'Не вдалося завантажити студію.')),
    h('p', {}, e.message),
    h('button', {type: 'button', class: 'btn primary', onclick: boot}, 'Спробувати ще раз')));
}

async function boot() {
  $('#main').replaceChildren(h('p', {class: 'loading'}, 'Завантажую…'));
  let d;
  try {
    d = await fetchState();
  } catch (e) {
    fatal(e);
    return;
  }
  S.story = d.story || S.story;
  await loadLessons(true);
  applyState(d, true);
  updateLessonsBtn();
}

function init() {
  const p = new URLSearchParams(location.search);
  S.story = p.get('story');
  S.seq = p.get('seq');
  bindStatic();
  boot();
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    API, TOOLS, num, present, asText, qs, mediaUrl, basename, groupWarnings, profileLabel, backendLabel, clipParts,
    slotLabel, slotState, defaultTool, sortManual, howParts, tokens, diffWords, diffStat, lessonIds, scopeParts,
    searchText,
  };
} else if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
}
