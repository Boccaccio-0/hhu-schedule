import assert from 'node:assert/strict';
import { test } from 'node:test';
import { KEY_PLAN, defaultEntries, formatMinute, parseMinute, validateEntry, sortedEntries, overlappingIds, locateEntry, summarize, loadPlan, savePlan } from '../web/study-plan.js';

const storage = () => {
  const values = new Map();
  return { values, getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
};

test('原表 22 段及四科、生活、休息、跨度汇总', () => {
  const entries = defaultEntries();
  assert.equal(entries.length, 22);
  assert.equal(entries[0].start, 420);
  assert.equal(entries.at(-1).end, 1440);
  assert.equal(entries.reduce((sum, entry) => sum + entry.end - entry.start, 0), 1020);
  assert.equal(overlappingIds(entries).size, 0);
  const totals = summarize(entries);
  assert.deepEqual(totals.minutes, { 高等代数: 300, 数学分析: 240, 英语一: 120, 政治: 90, 生活: 60, 休息: 210 });
  assert.equal(totals.total, 750);
  assert.equal(totals.span, 960);
  assert.deepEqual(totals.shares, { 高等代数: .4, 数学分析: .32, 英语一: .16, 政治: .12 });
  entries[0].task = '修改副本';
  assert.equal(defaultEntries()[0].task, '起床、洗漱、早餐');
});

test('时间边界、24:00 和非法输入', () => {
  assert.equal(parseMinute('00:00'), 0);
  assert.equal(parseMinute('7:30'), 450);
  assert.equal(parseMinute('23:59'), 1439);
  assert.equal(parseMinute('24:00', true), 1440);
  assert.equal(formatMinute(1440), '24:00');
  for (const value of ['', '24:00', '25:00', '12:60', '-1:00', '7.30', '12:2', null]) assert.equal(parseMinute(value), null);
  assert.equal(parseMinute('24:01', true), null);
  const entry = defaultEntries()[0];
  for (const patch of [{ start: null }, { start: 1440 }, { end: null }, { end: 1441 }, { end: 420 }, { end: 400 }, { start: 420.5 }, { category: '不存在' }, { task: '  ' }]) {
    assert.ok(validateEntry({ ...entry, ...patch }));
  }
  assert.equal(validateEntry({ ...entry, end: 1440 }), '');
});

test('修改、新增、删除、排序与恢复原始数据', () => {
  const store = storage();
  const entries = loadPlan(store).entries;
  entries[1].end = 480;
  entries.push({ id: 'extra', start: 0, end: 60, category: '政治', task: '复习' });
  savePlan(store, entries);
  const loaded = loadPlan(store);
  assert.equal(loaded.entries[0].id, 'extra');
  assert.equal(summarize(loaded.entries).total, 795);
  savePlan(store, loaded.entries.filter((entry) => entry.id !== 'extra'));
  assert.equal(summarize(loadPlan(store).entries).total, 735);
  savePlan(store, defaultEntries());
  assert.deepEqual(loadPlan(store).entries, defaultEntries());
});

test('重叠和包含关系会提示，相邻与间隔不冲突，排序不改变原数组', () => {
  const a = { id: 'a', start: 100, end: 300 };
  const b = { id: 'b', start: 120, end: 150 };
  const c = { id: 'c', start: 160, end: 200 };
  const d = { id: 'd', start: 300, end: 350 };
  const entries = [d, b, a, c];
  assert.deepEqual([...overlappingIds(entries)].sort(), ['a', 'b', 'c']);
  assert.equal(sortedEntries(entries)[0], a);
  assert.equal(entries[0], d);
});

test('空安排可持久化，零学习时间汇总没有 NaN', () => {
  const store = storage();
  savePlan(store, []);
  assert.deepEqual(loadPlan(store).entries, []);
  for (const entries of [[], [defaultEntries()[0]]]) {
    const totals = summarize(entries);
    assert.equal(totals.total, 0);
    assert.equal(totals.span, 0);
    assert.ok(Object.values(totals.shares).every((share) => share === 0));
  }
});

test('定位当前时段：包含开始，不包含结束，支持 24:00 与每日重新开始', () => {
  const entries = defaultEntries();
  for (const entry of entries) {
    assert.equal(locateEntry(entries, entry.start), entry);
    assert.equal(locateEntry(entries, entry.end - 1), entry);
  }
  assert.equal(locateEntry(entries, 450), entries[1]);
  assert.equal(locateEntry(entries, 1439), entries.at(-1));
  assert.equal(locateEntry(entries, 0), entries[0]);
});

test('定位空档、结束、空列表与重叠；使用排序后的自定义安排且不改变原数组', () => {
  const a = { id: 'a', start: 100, end: 200 };
  const b = { id: 'b', start: 300, end: 400 };
  const overlap = { id: 'overlap', start: 120, end: 180 };
  const entries = [b, overlap, a];
  assert.equal(locateEntry(entries, 50), a);
  assert.equal(locateEntry(entries, 150), a);
  assert.equal(locateEntry(entries, 200), b);
  assert.equal(locateEntry(entries, 400), b);
  assert.equal(locateEntry(entries, 1439), b);
  assert.equal(locateEntry([], 700), null);
  assert.equal(entries[0], b);
});

test('损坏或未知版本缓存不被覆盖，非法条目和重复 ID 被拒绝', () => {
  const store = storage();
  const entries = defaultEntries();
  for (const raw of ['{bad', 'null', JSON.stringify({ version: 2, entries }), JSON.stringify({ version: 1, entries: [entries[0], entries[0]] }), JSON.stringify({ version: 1, entries: [{ ...entries[0], end: 1 }] })]) {
    store.setItem(KEY_PLAN, raw);
    assert.ok(loadPlan(store).error);
    assert.equal(store.getItem(KEY_PLAN), raw);
  }
  assert.throws(() => savePlan(store, [{ ...entries[0], task: '' }]));
});

test('存储失败向调用方报告，不改变旧数据；课表键隔离', () => {
  const store = storage();
  store.setItem('hhu.data', '课表原数据');
  savePlan(store, defaultEntries());
  const before = store.getItem(KEY_PLAN);
  const unavailable = { getItem() { throw new Error('拒绝读取'); }, setItem() { throw new Error('空间不足'); } };
  assert.ok(loadPlan(unavailable).error);
  assert.throws(() => savePlan(unavailable, []));
  assert.equal(store.getItem(KEY_PLAN), before);
  assert.equal(store.getItem('hhu.data'), '课表原数据');
});
