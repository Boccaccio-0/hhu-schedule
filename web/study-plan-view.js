import { CATEGORIES, SUBJECTS, PLAN_NOTES, PLAN_START_DATE, defaultEntries, formatMinute, parseMinute, validateEntry, sortedEntries, overlappingIds, summarize, loadPlan, savePlan } from './study-plan.js';

const $ = (id) => document.getElementById(id);
const hours = (minutes) => Number((minutes / 60).toFixed(2)).toLocaleString('zh-CN');
const node = (tag, text, className = '') => {
  const result = document.createElement(tag);
  result.textContent = text;
  result.className = className;
  return result;
};

export function createPlanView({ openSheet, closeSheets, toast }) {
  // 延迟访问 localStorage，让访问被浏览器拒绝的情况也进入 loadPlan 的错误处理。
  const storage = {
    getItem: (key) => localStorage.getItem(key),
    setItem: (key, value) => localStorage.setItem(key, value),
  };
  let plan = loadPlan(storage);
  let editingId = null;
  let initialForm = null;
  const formValue = () => JSON.stringify(['plan-start', 'plan-end', 'plan-category', 'plan-task'].map((id) => $(id).value));
  const isDirty = () => !$('sheet-plan-edit').hidden && initialForm !== null && initialForm !== formValue();

  function canClose() {
    if (isDirty() && !confirm('放弃尚未保存的时间安排修改？')) return false;
    initialForm = null;
    return true;
  }

  function render() {
    $('plan-storage-error').textContent = plan.error;
    $('plan-storage-error').hidden = !plan.error;
    $('btn-plan-retry').hidden = !plan.error;
    $('btn-plan-add').disabled = !!plan.error;
    const overlaps = overlappingIds(plan.entries);
    $('plan-overlap').hidden = !overlaps.size;
    $('plan-overlap').textContent = `${overlaps.size} 个时段存在重叠。汇总按每条安排的时长分别累计，重叠部分会重复计入。`;
    const body = $('plan-rows');
    body.replaceChildren();
    for (const entry of sortedEntries(plan.entries)) {
      const row = document.createElement('tr');
      const time = node('td', `${formatMinute(entry.start)}–${formatMinute(entry.end)}`, 'plan-time');
      if (overlaps.has(entry.id)) time.append(node('span', '时间重叠', 'plan-overlap-badge'));
      const category = node('td', '', 'plan-category');
      category.append(node('span', entry.category, `plan-tag plan-tag-${CATEGORIES.indexOf(entry.category)}`));
      const task = node('td', entry.task, 'plan-task');
      const duration = node('td', `${entry.end - entry.start} 分钟`, 'plan-duration');
      const actions = node('td', '', 'plan-actions');
      for (const [label, action] of [['编辑', () => edit(entry)], ['删除', () => remove(entry)]]) {
        const button = node('button', label, label === '删除' ? 'btn danger' : 'btn ghost');
        button.type = 'button';
        button.disabled = !!plan.error;
        button.setAttribute('aria-label', `${label} ${formatMinute(entry.start)} ${entry.category} ${entry.task}`);
        button.addEventListener('click', action);
        actions.append(button);
      }
      row.append(time, category, task, duration, actions);
      body.append(row);
    }
    $('plan-empty').hidden = plan.entries.length !== 0;
    const totals = summarize(plan.entries);
    $('plan-summary-rows').replaceChildren();
    for (const subject of SUBJECTS) {
      const row = document.createElement('tr');
      row.append(node('th', subject), node('td', `${hours(totals.minutes[subject])} 小时`), node('td', `${Number((totals.shares[subject] * 100).toFixed(1))}%`));
      row.firstChild.scope = 'row';
      $('plan-summary-rows').append(row);
    }
    $('plan-total').textContent = `${hours(totals.total)} 小时`;
    $('plan-total-share').textContent = totals.total ? '100%' : '0%';
    $('plan-span').textContent = totals.total ? `${hours(totals.span)} 小时` : '无';
    $('plan-rest').textContent = `${hours(totals.minutes['休息'])} 小时`;
    $('plan-life').textContent = `${hours(totals.minutes['生活'])} 小时`;
  }

  function persist(entries, errorTarget) {
    try {
      savePlan(storage, entries);
      plan = { entries: sortedEntries(entries), error: '' };
      $(errorTarget).hidden = true;
      $('plan-action-error').hidden = true;
      render();
      return true;
    } catch {
      $(errorTarget).textContent = '保存失败，本次修改尚未保存。请检查浏览器存储权限或空间后重试；已有安排未改变。';
      $(errorTarget).hidden = false;
      return false;
    }
  }

  function edit(entry = null) {
    if (plan.error || !openSheet('sheet-plan-edit')) return;
    editingId = entry ? entry.id : null;
    $('plan-edit-title').textContent = entry ? '编辑时间安排' : '新增时间安排';
    $('plan-start').value = entry ? formatMinute(entry.start) : '';
    $('plan-end').value = entry ? formatMinute(entry.end) : '';
    $('plan-category').value = entry ? entry.category : SUBJECTS[0];
    $('plan-task').value = entry ? entry.task : '';
    $('plan-form-error').hidden = true;
    $('plan-form-overlap').hidden = true;
    initialForm = formValue();
    $('plan-start').focus();
  }

  function readEntry() {
    return {
      id: editingId || 'draft',
      start: parseMinute($('plan-start').value),
      end: parseMinute($('plan-end').value, true),
      category: $('plan-category').value,
      task: $('plan-task').value.trim(),
    };
  }

  function updateOverlap() {
    const entry = readEntry();
    const others = plan.entries.filter((item) => item.id !== editingId);
    $('plan-form-overlap').hidden = !Number.isInteger(entry.start) || !Number.isInteger(entry.end)
      || !others.some((item) => entry.start < item.end && entry.end > item.start);
  }

  function remove(entry) {
    if (plan.error || !confirm(`删除 ${formatMinute(entry.start)}–${formatMinute(entry.end)} 的“${entry.category}”安排？`)) return;
    if (persist(plan.entries.filter((item) => item.id !== entry.id), 'plan-action-error')) toast('已删除时间安排');
  }

  $('plan-form').addEventListener('submit', (event) => {
    event.preventDefault();
    if (plan.error) return;
    const entry = readEntry();
    const error = validateEntry(entry);
    if (error) {
      $('plan-form-error').textContent = error;
      $('plan-form-error').hidden = false;
      return;
    }
    if (!editingId) {
      const bytes = crypto.getRandomValues(new Uint32Array(4));
      entry.id = Array.from(bytes, (value) => value.toString(16)).join('-');
    }
    const entries = plan.entries.filter((item) => item.id !== editingId).concat(entry);
    if (!persist(entries, 'plan-form-error')) return;
    initialForm = null;
    closeSheets();
    toast('时间安排已保存在本机');
  });
  $('plan-form').addEventListener('input', updateOverlap);
  $('btn-plan-add').addEventListener('click', () => edit());
  $('btn-plan-retry').addEventListener('click', () => { plan = loadPlan(storage); render(); });
  $('btn-plan-reset').addEventListener('click', () => {
    if (!confirm('恢复原始的 22 个时段？本机的时间安排修改将被替换，课表不受影响。')) return;
    if (persist(defaultEntries(), 'plan-action-error')) toast('已恢复原始安排');
  });
  window.addEventListener('beforeunload', (event) => {
    if (isDirty()) { event.preventDefault(); event.returnValue = ''; }
  });
  $('sheet-plan-edit').addEventListener('keydown', (event) => {
    if (event.key !== 'Tab') return;
    const focusable = [...$('sheet-plan-edit').querySelectorAll('button, input, select, textarea')].filter((element) => !element.disabled);
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  for (const category of CATEGORIES) $('plan-category').append(new Option(category, category));
  $('plan-start-date').textContent = `从 ${PLAN_START_DATE} 起执行 · 每日重复`;
  for (const text of PLAN_NOTES) $('plan-notes').append(node('li', text));
  return { render, canClose };
}
