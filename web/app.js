/**
 * 河海课表 PWA
 *
 * 数据流：GitHub Actions 抓取教务系统 → 口令加密成 data/schedule.enc.json
 * → 本页拉取 → 用 WebCrypto 解密 → 存 localStorage → 离线可用。
 */

// 网页版从同目录读数据；打包成 Android App 时优先从 GitHub 拉最新，失败则用包内自带的那份
const BUNDLED_DATA_URL = 'data/schedule.enc.json';
const REMOTE_DATA_URL = 'https://boccaccio-0.github.io/hhu-schedule/data/schedule.enc.json';
const IS_ANDROID_APP = location.hostname === 'appassets.androidplatform.net';
const KEY_PASS = 'hhu.pass';
const KEY_DATA = 'hhu.data';
const KEY_META = 'hhu.meta';
const KEY_START = 'hhu.startOverride';
const KEY_CHECKED = 'hhu.checkedAt';
const KEY_CHECKED_OK = 'hhu.checkedOk';

const WEEKDAY_SHORT = ['一', '二', '三', '四', '五', '六', '日'];
const PALETTE = 8;
const DAY_MS = 86400000;

const state = { schedule: null, meta: null, week: 1, pass: '' };

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------------ 工具 */

function b64ToBytes(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function hashString(text) {
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) | 0;
  return Math.abs(hash);
}

function colorClass(name) {
  return 'c' + (hashString(name) % PALETTE);
}

function toast(message) {
  const el = $('toast');
  if (!message) { el.hidden = true; return; }
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 2400);
}

/* ------------------------------------------------------------------ 解密 */

async function decryptEnvelope(envelope, passphrase) {
  const encoder = new TextEncoder();
  const salt = b64ToBytes(envelope.salt);
  const iv = b64ToBytes(envelope.iv);
  const ciphertext = b64ToBytes(envelope.ct);
  const baseKey = await crypto.subtle.importKey('raw', encoder.encode(passphrase), 'PBKDF2', false, ['deriveKey']);
  const key = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: envelope.iter || 200000, hash: 'SHA-256' },
    baseKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['decrypt'],
  );
  const plaintext = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ciphertext);
  return JSON.parse(new TextDecoder().decode(plaintext));
}

/**
 * 数据源顺序：
 * - 网页版：只有同目录一份；
 * - App 版：解锁时先用包内数据（秒开），后台刷新时优先拉 GitHub 上的最新数据。
 */
function dataSources(preferRemote = true) {
  if (!IS_ANDROID_APP) return [BUNDLED_DATA_URL];
  return preferRemote ? [REMOTE_DATA_URL, BUNDLED_DATA_URL] : [BUNDLED_DATA_URL, REMOTE_DATA_URL];
}

/** 记录"最后一次成功从网上取到数据"的时间，用于区分「没变化」和「没同步成功」。 */
function markChecked(ok) {
  if (ok) localStorage.setItem(KEY_CHECKED, new Date().toISOString());
  localStorage.setItem(KEY_CHECKED_OK, ok ? '1' : '0');
}

async function fetchEnvelope(preferRemote = true) {
  let lastError = null;
  let triedNetwork = false;
  for (const url of dataSources(preferRemote)) {
    // 网页版那份同源文件就是线上数据；App 版只有 GitHub 那个地址算联网
    const isNetworkSource = !IS_ANDROID_APP || url === REMOTE_DATA_URL;
    if (isNetworkSource) triedNetwork = true;
    try {
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) {
        const error = new Error(response.status === 404 ? '服务器上还没有课表数据' : `拉取数据失败：HTTP ${response.status}`);
        error.code = response.status;
        throw error;
      }
      const envelope = await response.json();
      if (isNetworkSource) markChecked(true);
      return envelope;
    } catch (error) {
      lastError = error;  // 联网失败时自动退回下一数据源（App 内即包内自带数据）
    }
  }
  if (triedNetwork) markChecked(false);  // 联网没成功，记录状态但保留上次成功时间
  throw lastError || new Error('无法获取课表数据');
}

/* ------------------------------------------------------------------ 周次 */

function scheduleStart() {
  const override = localStorage.getItem(KEY_START);
  const iso = override || (state.schedule && state.schedule.startDate);
  if (!iso) return null;
  const date = new Date(`${iso}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function totalWeeks() {
  return (state.schedule && state.schedule.totalWeeks) || 20;
}

function currentWeek() {
  const start = scheduleStart();
  if (!start) return 1;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.floor((today - start) / DAY_MS);
  const week = Math.floor(days / 7) + 1;
  return Math.min(Math.max(week, 1), totalWeeks());
}

function weekDates(week) {
  const start = scheduleStart();
  if (!start) return null;
  return {
    monday: new Date(start.getTime() + (week - 1) * 7 * DAY_MS),
    sunday: new Date(start.getTime() + (week - 1) * 7 * DAY_MS + 6 * DAY_MS),
  };
}

function formatRange(range) {
  if (!range) return '';
  return `${range.monday.getMonth() + 1}月${range.monday.getDate()}日 - ${range.sunday.getMonth() + 1}月${range.sunday.getDate()}日`;
}

function todayColumn() {
  const start = scheduleStart();
  if (!start) return 0;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.floor((today - start) / DAY_MS);
  if (days < 0) return 0;
  if (Math.floor(days / 7) + 1 !== state.week) return 0;
  return (days % 7) + 1;
}

function isActive(course, week) {
  const spans = course.weeks || [];
  if (!spans.length) return true;
  for (const [from, to] of spans) {
    if (week < from || week > to) continue;
    if (course.parity === '单' && week % 2 === 0) continue;
    if (course.parity === '双' && week % 2 === 1) continue;
    return true;
  }
  return false;
}

/* ------------------------------------------------------------------ 渲染 */

function render() {
  $('gate').hidden = true;
  $('topbar').hidden = false;
  $('timetable-view').hidden = false;
  renderHeader();
  renderGrid();
  renderOther();
  renderFooter();
}

function renderHeader() {
  const total = totalWeeks();
  $('week-title').textContent = `第 ${state.week} 周`;
  $('week-dates').textContent = formatRange(weekDates(state.week)) || '起始日期未知';
  $('btn-prev').disabled = state.week <= 1;
  $('btn-next').disabled = state.week >= total;
}

function renderGrid() {
  const schedule = state.schedule;
  const grid = $('grid');
  grid.innerHTML = '';
  const highlight = todayColumn();
  const rowCount = schedule.periods.length;
  grid.style.gridTemplateRows = `auto repeat(${rowCount}, minmax(92px, auto))`;

  grid.append(el('div', 'day-head'));
  for (let day = 1; day <= 7; day += 1) {
    const head = el('div', 'day-head', WEEKDAY_SHORT[day - 1]);
    if (day === highlight) head.classList.add('today');
    grid.append(head);
  }

  // 背景格：决定每行高度与今日底色，课程块会盖在它们上面
  for (const period of schedule.periods) {
    const label = el('div', 'period-label');
    const sections = period.sections || [];
    const span = sections.length ? `${sections[0]}-${sections[sections.length - 1]}节` : period.name;
    label.append(el('b', '', span));
    if (period.time) label.append(el('span', '', period.time.slice(0, 5)));
    label.style.gridRow = String(period.index + 1);
    label.style.gridColumn = '1';
    grid.append(label);

    for (let day = 1; day <= 7; day += 1) {
      const cell = el('div', 'cell');
      if (day === highlight) cell.classList.add('today');
      cell.style.gridRow = String(period.index + 1);
      cell.style.gridColumn = String(day + 1);
      grid.append(cell);
    }
  }

  // 课程块：同一天里时间重叠的归成一簇，再决定并排还是堆叠
  for (let day = 1; day <= 7; day += 1) {
    for (const cluster of clusterInstances(buildDayInstances(day))) {
      grid.append(clusterEl(cluster, day));
    }
  }
}

/** 把同一天、同一门课、同一批周次、连续或重叠小节的记录合并成一节课。 */
function buildDayInstances(day) {
  const byKey = new Map();
  for (const course of state.schedule.courses) {
    if (course.day !== day) continue;
    const key = [course.name, course.room, (course.weeks || []).map((w) => w.join('-')).join(','), course.parity || ''].join('|');
    let inst = byKey.get(key);
    if (!inst) {
      inst = {
        key, name: course.name, room: course.room, teacher: course.teacher, note: course.note,
        weeks: course.weeks || [], parity: course.parity || null, sections: new Set(), rows: new Set(),
      };
      byKey.set(key, inst);
    }
    (course.sections || []).forEach((s) => inst.sections.add(s));
    inst.rows.add(course.bigPeriod);
  }
  return [...byKey.values()]
    .map((inst) => {
      const sections = [...inst.sections].sort((a, b) => a - b);
      const rows = [...inst.rows].sort((a, b) => a - b);
      return { ...inst, sections, firstRow: rows[0], lastRow: rows[rows.length - 1] };
    })
    .sort((a, b) => a.firstRow - b.firstRow || a.sections[0] - b.sections[0]);
}

/** 时间上互相重叠的课程归为一簇（用于并排或堆叠渲染）。 */
function clusterInstances(list) {
  const clusters = [];
  for (const inst of [...list].sort((a, b) => a.firstRow - b.firstRow || a.lastRow - b.lastRow)) {
    const hit = clusters.find((c) => c.lastRow >= inst.firstRow);
    if (hit) {
      hit.items.push(inst);
      hit.lastRow = Math.max(hit.lastRow, inst.lastRow);
    } else {
      clusters.push({ items: [inst], firstRow: inst.firstRow, lastRow: inst.lastRow });
    }
  }
  return clusters;
}

function weeksShort(course) {
  if (!course.weeks || !course.weeks.length) return '';
  const text = course.weeks.map(([a, b]) => (a === b ? String(a) : `${a}-${b}`)).join('、');
  return `${text}周${course.parity ? ` ${course.parity}` : ''}`;
}

function sectionsText(inst) {
  return inst.sections && inst.sections.length ? `第 ${inst.sections.join('-')} 节` : '';
}

function timeRangeOf(inst) {
  const periods = state.schedule.periods;
  const first = periods.find((p) => (p.sections || []).includes(inst.sections[0]));
  const last = periods.find((p) => (p.sections || []).includes(inst.sections[inst.sections.length - 1]));
  if (!first || !last) return '';
  return `${first.time.split('-')[0]}-${last.time.split('-')[1]}`;
}

/** 本周要上的课：一个时段一块，跨大节的课合并成一块。 */
function blockEl(inst, day, { conflict = false, otherWeeks = [], ghost = false } = {}) {
  const node = document.createElement('button');
  node.type = 'button';
  node.className = `block ${ghost ? 'ghost' : colorClass(inst.name)}`;
  node.style.gridColumn = String(day + 1);
  node.style.gridRow = `${inst.firstRow + 1} / ${inst.lastRow + 2}`;
  node.append(el('span', 'name', inst.name));
  if (inst.room) node.append(el('span', 'room', inst.room));
  node.append(el('span', 'weeks', weeksShort(inst)));
  if (conflict && !ghost) node.append(el('span', 'conflict', '⚠ 时间冲突'));
  if (!ghost && otherWeeks.length) {
    node.append(el('span', 'other', `其他周：${otherWeeks.map(weeksShort).join('、')}`));
  }
  node.addEventListener('click', () => openDetail(day, inst.firstRow, inst.key));
  return node;
}

/**
 * 渲染一个时段簇：
 * - 本周要上的课排在上面（冲突时上下堆叠并标注），每块都占满整列宽度；
 * - 本周不上的安排灰显，并标出各自周次；
 * - 同一门课在别的周次的安排，直接写在它的块里。
 */
function clusterEl(cluster, day) {
  const active = cluster.items.filter((inst) => isActive(inst, state.week));
  const inactive = cluster.items.filter((inst) => !isActive(inst, state.week));
  const box = el('div', 'stack');
  box.style.gridColumn = String(day + 1);
  box.style.gridRow = `${cluster.firstRow + 1} / ${cluster.lastRow + 2}`;
  const list = active.length ? active : inactive;
  const limit = active.length ? 2 : 3;
  const shown = list.slice(0, limit);
  shown.forEach((inst) => {
    box.append(blockEl(inst, day, {
      ghost: !active.length,
      conflict: active.length > 1,
      // 只把「同一门课在别的周次」的安排写进它自己的块里，避免串课
      otherWeeks: active.length ? inactive.filter((o) => o.name === inst.name) : [],
    }));
  });
  const hidden = list.length - shown.length;
  if (hidden > 0) box.append(el('span', 'more', `+${hidden} 门其他周`));
  if (active.length) {
    const foreign = inactive.filter((o) => !active.some((a) => a.name === o.name));
    if (foreign.length) {
      box.append(el('span', 'more', `其他周还有：${foreign.map((o) => `${o.name} ${weeksShort(o)}`).join('、')}`));
    }
  }
  return box;
}

function renderOther() {
  const list = (state.schedule.otherCourses || []).filter((c) => c.name);
  const box = $('other-courses');
  box.innerHTML = '';
  if (!list.length) { box.hidden = true; return; }
  box.hidden = false;
  box.append(el('h2', '', '本学期无固定时间的课程'));
  const ul = document.createElement('ul');
  for (const course of list) {
    const parts = [course.name];
    if (course.teacher) parts.push(course.teacher);
    if (course.kind) parts.push(course.kind);
    ul.append(el('li', '', parts.join(' · ')));
  }
  box.append(ul);
}

function renderFooter() {
  const meta = state.meta;
  const term = state.schedule.termName || state.schedule.term || '';
  const checked = localStorage.getItem(KEY_CHECKED);
  const checkOk = localStorage.getItem(KEY_CHECKED_OK);
  const parts = [term];
  if (meta && meta.updated) parts.push(`课表更新于 ${formatTime(meta.updated)}`);
  if (checked) {
    parts.push(`${formatTime(checked)} 已同步${checkOk === '1' ? '' : '（联网失败，用本机数据）'}`);
  } else if (IS_ANDROID_APP) {
    parts.push('当前用包内数据');
  }
  if (IS_ANDROID_APP) parts.push('App 版');
  $('footer-note').textContent = parts.filter(Boolean).join(' · ');
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatTime(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function weeksText(course) {
  if (!course.weeks || !course.weeks.length) return '未标明周次';
  const text = course.weeks.map(([from, to]) => (from === to ? String(from) : `${from}-${to}`)).join('、');
  return `第 ${text} 周${course.parity ? `（${course.parity}周）` : ''}`;
}

/* ------------------------------------------------------------------ 弹层 */

function openSheet(id) {
  for (const sheet of document.querySelectorAll('.sheet')) sheet.hidden = sheet.id !== id;
  $('backdrop').hidden = false;
}

function closeSheets() {
  for (const sheet of document.querySelectorAll('.sheet')) sheet.hidden = true;
  $('backdrop').hidden = true;
}

function openDetail(day, bigPeriod, key) {
  const period = state.schedule.periods.find((p) => p.index === bigPeriod);
  $('detail-title').textContent = `星期${WEEKDAY_SHORT[day - 1]} · ${period ? period.name : ''}`;

  const body = $('detail-body');
  body.innerHTML = '';

  const clusters = clusterInstances(buildDayInstances(day));
  const cluster = clusters.find((c) => bigPeriod >= c.firstRow && bigPeriod <= c.lastRow);
  if (!cluster) {
    body.append(el('div', 'note', '这一格没有课程。'));
    openSheet('sheet-detail');
    return;
  }

  // 只显示点中的那一条安排；同时段的其他安排收进折叠区，需要时再展开
  const current = cluster.items.find((i) => i.key === key) || cluster.items[0];
  const others = cluster.items.filter((i) => i !== current);
  const activeCount = cluster.items.filter((inst) => isActive(inst, state.week)).length;
  if (activeCount > 1 && isActive(current, state.week)) {
    body.append(el('div', 'warn', `⚠ 本周这个时段有 ${activeCount} 门课重叠，请以教务系统为准`));
  }
  body.append(courseDetailEl(current));

  if (others.length) {
    const fold = document.createElement('details');
    fold.className = 'fold';
    fold.append(el('summary', '', `同一时段另有 ${others.length} 条安排`));
    const list = el('ul', 'slots');
    for (const inst of others) {
      const item = el('li', '');
      const link = document.createElement('button');
      link.type = 'button';
      link.className = 'linkish';
      link.textContent = `${inst.name} · ${sectionsText(inst)} · ${weeksShort(inst)} · ${inst.room}`;
      link.addEventListener('click', () => openDetail(day, inst.firstRow, inst.key));
      item.append(link);
      list.append(item);
    }
    fold.append(list);
    body.append(fold);
  }
  openSheet('sheet-detail');
}

/** 单条课程安排的详情（教师/教室/节次/周次/备注）+ 可展开的全学期安排。 */
function courseDetailEl(inst) {
  const isOn = isActive(inst, state.week);
  const box = el('div', 'course-detail');
  const name = el('span', `name ${colorClass(inst.name)}`, inst.name);
  if (!isOn) name.style.opacity = '.55';
  box.append(name);
  box.append(el('span', `badge${isOn ? ' on' : ''}`, isOn ? '本周上' : '本周不上'));

  const dl = document.createElement('dl');
  const add = (label, value) => {
    if (!value) return;
    dl.append(el('dt', '', label), el('dd', '', value));
  };
  add('教师', inst.teacher);
  add('教室', inst.room);
  add('节次', [sectionsText(inst), timeRangeOf(inst)].filter(Boolean).join(' · '));
  add('周次', weeksText(inst));
  add('备注', inst.note);
  box.append(dl);

  // 同一门课在不同周次可能换时段，需要时展开对照
  const slots = courseSlots(inst.name);
  if (slots.length > 1) {
    const fold = document.createElement('details');
    fold.className = 'fold';
    fold.append(el('summary', '', `《${inst.name}》全学期安排（${slots.length} 处）`));
    const list = el('ul', 'slots');
    for (const slot of slots) {
      list.append(el('li', '', `${WEEKDAY_SHORT[slot.day - 1]} ${slot.sectionsText} · ${slot.weeksText} · ${slot.room}`));
    }
    fold.append(list);
    box.append(fold);
  }
  return box;
}

/** 某门课在整学期的所有时段（含周次与教室），用于详情页对照。 */
function courseSlots(name) {
  const slots = [];
  for (let day = 1; day <= 7; day += 1) {
    for (const inst of buildDayInstances(day)) {
      if (inst.name !== name) continue;
      slots.push({ day, sectionsText: sectionsText(inst), weeksText: weeksText(inst), room: inst.room });
    }
  }
  return slots.sort((a, b) => a.day - b.day || a.sectionsText.localeCompare(b.sectionsText));
}

function openWeekPicker() {
  const picker = $('week-picker');
  picker.innerHTML = '';
  const current = currentWeek();
  for (let week = 1; week <= totalWeeks(); week += 1) {
    const button = el('button', '', `第 ${week} 周`);
    if (week === current) button.classList.add('current');
    if (week === state.week) button.classList.add('selected');
    button.addEventListener('click', () => {
      state.week = week;
      closeSheets();
      render();
    });
    picker.append(button);
  }
  openSheet('sheet-weeks');
}

function openSettings() {
  const schedule = state.schedule;
  $('set-term').textContent = schedule.termName || schedule.term || '-';
  $('set-updated').textContent = state.meta && state.meta.updated ? formatTime(state.meta.updated) : '-';
  const checked = localStorage.getItem(KEY_CHECKED);
  const checkOk = localStorage.getItem(KEY_CHECKED_OK);
  $('set-checked').textContent = checked
    ? `${formatTime(checked)}${checkOk === '1' ? '' : '（上次联网失败，当前用本机缓存）'}`
    : '本次打开尚未联网成功';
  const start = scheduleStart();
  const auto = schedule.startDate || '未知';
  $('set-start').textContent = start
    ? `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}${localStorage.getItem(KEY_START) ? '（手动校正）' : ''}`
    : '未知';
  $('set-build').textContent = `校历第 1 周：${auto} · 共 ${totalWeeks()} 周`;
  openSheet('sheet-settings');
}

/* ------------------------------------------------------------------ 同步 */

function persist(schedule, meta) {
  localStorage.setItem(KEY_DATA, JSON.stringify(schedule));
  localStorage.setItem(KEY_META, JSON.stringify(meta));
}

/** 用已取到的密文数据解锁并落盘。 */
async function applyEnvelope(envelope, passphrase, { initial = false } = {}) {
  const schedule = await decryptEnvelope(envelope, passphrase);
  state.pass = passphrase;
  state.schedule = schedule;
  state.meta = { updated: envelope.updated, payloadHash: envelope.payloadHash };
  localStorage.setItem(KEY_PASS, passphrase);
  persist(schedule, state.meta);
  if (initial) state.week = currentWeek();
  render();
}

/** 首次解锁：App 版先用包内数据，保证秒开。 */
async function unlock(passphrase, options = {}) {
  return applyEnvelope(await fetchEnvelope(false), passphrase, options);
}

async function refresh({ silent = false } = {}) {
  if (!state.pass) return;
  if (!navigator.onLine) {
    if (!silent) toast('当前没有网络，显示的是本机缓存');
    return;
  }
  try {
    const envelope = await fetchEnvelope(true);  // 刷新时优先取远端最新
    if (state.schedule && state.meta && envelope.payloadHash === state.meta.payloadHash) {
      state.meta = { ...state.meta, updated: envelope.updated };
      localStorage.setItem(KEY_META, JSON.stringify(state.meta));
      render();
    } else {
      await applyEnvelope(envelope, state.pass);  // 用刚取到的那份，别再退回包内旧数据
    }
    if (!silent) toast('课表已是最新');
  } catch (error) {
    if (silent) return;
    toast(state.schedule ? `同步失败，继续使用本机缓存（${error.message}）` : `同步失败：${error.message}`);
  }
}

/* ------------------------------------------------------------------ 启动 */

function showGate(message = '') {
  $('gate').hidden = false;
  $('topbar').hidden = true;
  $('timetable-view').hidden = true;
  $('gate-hint').textContent = message;
  const meta = localStorage.getItem(KEY_META);
  if (meta) {
    try {
      $('gate-status').textContent = `本机缓存数据：${formatTime(JSON.parse(meta).updated)}`;
    } catch { /* 忽略损坏缓存 */ }
  }
}

function bind() {
  $('gate-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const input = $('gate-input');
    const button = $('gate-submit');
    const passphrase = input.value;
    if (!passphrase) return;
    button.disabled = true;
    button.textContent = '解锁中…';
    $('gate-hint').textContent = '';
    try {
      await unlock(passphrase, { initial: true });
      input.value = '';
      if (IS_ANDROID_APP) refresh({ silent: true });  // App 版：解锁后后台拉一次最新数据
    } catch (error) {
      const hint = error.code === 404
        ? '服务器上还没有课表数据：请先在 GitHub 仓库运行一次「同步课表数据」workflow。'
        : (error.name === 'OperationError' ? '口令不对，或数据文件已损坏。' : `解锁失败：${error.message}`);
      $('gate-hint').textContent = hint;
    } finally {
      button.disabled = false;
      button.textContent = '解锁';
    }
  });

  $('btn-prev').addEventListener('click', () => {
    state.week = Math.max(1, state.week - 1);
    render();
  });
  $('btn-next').addEventListener('click', () => {
    state.week = Math.min(totalWeeks(), state.week + 1);
    render();
  });
  $('btn-week').addEventListener('click', openWeekPicker);
  $('btn-settings').addEventListener('click', openSettings);
  $('backdrop').addEventListener('click', closeSheets);
  for (const button of document.querySelectorAll('[data-close]')) button.addEventListener('click', closeSheets);

  $('btn-refresh').addEventListener('click', () => refresh());
  $('btn-change-pass').addEventListener('click', () => {
    closeSheets();
    localStorage.removeItem(KEY_PASS);
    state.pass = '';
    showGate('请输入当前生效的同步口令。');
  });
  $('btn-clear').addEventListener('click', () => {
    if (!confirm('清除本机缓存的课表与口令？下次打开需要重新解锁。')) return;
    for (const key of [KEY_PASS, KEY_DATA, KEY_META, KEY_START]) localStorage.removeItem(key);
    location.reload();
  });

  const shiftStart = (days) => {
    const start = scheduleStart();
    if (!start) return;
    const next = new Date(start.getTime() + days * DAY_MS);
    localStorage.setItem(KEY_START, `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}-${String(next.getDate()).padStart(2, '0')}`);
    state.week = currentWeek();
    render();
    openSettings();
  };
  $('btn-start-back').addEventListener('click', () => shiftStart(-7));
  $('btn-start-fwd').addEventListener('click', () => shiftStart(7));
  $('btn-start-reset').addEventListener('click', () => {
    localStorage.removeItem(KEY_START);
    state.week = currentWeek();
    render();
    openSettings();
  });
}

async function init() {
  bind();
  if ('serviceWorker' in navigator && !IS_ANDROID_APP) {
    navigator.serviceWorker.register('sw.js').catch(() => { /* 离线能力不可用不影响使用 */ });
  }
  if (IS_ANDROID_APP) $('install-hint').hidden = true;

  const cached = localStorage.getItem(KEY_DATA);
  if (cached) {
    try {
      state.schedule = JSON.parse(cached);
      state.meta = JSON.parse(localStorage.getItem(KEY_META) || 'null');
      state.pass = localStorage.getItem(KEY_PASS) || '';
      state.week = currentWeek();
      render();
      if (state.pass) refresh({ silent: true });
      return;
    } catch {
      localStorage.removeItem(KEY_DATA);
    }
  }
  showGate();
}

init();
