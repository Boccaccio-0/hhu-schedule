// 来源：考研四科每日时间计划.xlsx / 每日作息；时间以当天零点后的分钟数保存。
export const KEY_PLAN = 'hhu.studyPlan';
export const SUBJECTS = ['高等代数', '数学分析', '英语一', '政治'];
export const CATEGORIES = [...SUBJECTS, '生活', '休息'];
export const PLAN_NOTES = ['高代按10天章节表推进。', '星号内容不学。', '学习时段含复习与订正。'];
export const PLAN_START_DATE = '2026-11-17';

const DEFAULT_ROWS = [
  [420, 450, '生活', '起床、洗漱、早餐'],
  [450, 495, '英语一', '复习词汇、长难句'],
  [495, 510, '休息', '起身活动、喝水'],
  [510, 600, '数学分析', '学习定义、定理与证明，完成对应例题'],
  [600, 615, '休息', '短休'],
  [615, 705, '高等代数', '按10天章节表学习新内容'],
  [705, 735, '政治', '知识点回顾、选择题'],
  [735, 780, '休息', '午饭、走动'],
  [780, 810, '休息', '午休'],
  [810, 900, '高等代数', '梳理证明、独立重做例题'],
  [900, 915, '休息', '短休'],
  [915, 1005, '数学分析', '独立做基础题与典型题'],
  [1005, 1020, '休息', '短休'],
  [1020, 1095, '英语一', '阅读理解及订正；按天轮换翻译、写作等题型'],
  [1095, 1140, '休息', '晚饭、走动'],
  [1140, 1230, '高等代数', '完成当天配套习题并订正'],
  [1230, 1245, '休息', '短休'],
  [1245, 1305, '数学分析', '整理错题、复述关键证明、补当天缺口'],
  [1305, 1320, '休息', '短休'],
  [1320, 1350, '高等代数', '闭卷回忆概念、定理条件，记录未完成项'],
  [1350, 1410, '政治', '复习与背诵、分析题训练或选择题订正'],
  [1410, 1440, '生活', '洗漱、放松，24:00睡觉'],
];

export function defaultEntries() {
  return DEFAULT_ROWS.map(([start, end, category, task], index) => ({ id: `default-${index + 1}`, start, end, category, task }));
}

export function formatMinute(value) {
  return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
}

export function parseMinute(value, allowMidnight = false) {
  if (typeof value !== 'string') return null;
  const text = value.trim();
  if (allowMidnight && text === '24:00') return 1440;
  if (!/^([01]?\d|2[0-3]):[0-5]\d$/.test(text)) return null;
  const [hours, minutes] = text.split(':').map(Number);
  return hours * 60 + minutes;
}

export function validateEntry(entry) {
  if (!entry || !Number.isInteger(entry.start) || entry.start < 0 || entry.start >= 1440) return '请输入有效的开始时间（00:00–23:59）。';
  if (!Number.isInteger(entry.end) || entry.end <= 0 || entry.end > 1440) return '请输入有效的结束时间（00:01–24:00）。';
  if (entry.end <= entry.start) return '结束时间必须晚于开始时间；跨午夜的安排请拆成两个时段。';
  if (!CATEGORIES.includes(entry.category)) return '请选择安排类别。';
  if (typeof entry.task !== 'string' || !entry.task.trim()) return '请填写具体任务。';
  return '';
}

export function sortedEntries(entries) {
  return [...entries].sort((a, b) => a.start - b.start || a.end - b.end);
}

export function overlappingIds(entries) {
  const ids = new Set();
  const sorted = sortedEntries(entries);
  for (let i = 0; i < sorted.length; i += 1) {
    for (let j = i + 1; j < sorted.length && sorted[j].start < sorted[i].end; j += 1) {
      ids.add(sorted[i].id);
      ids.add(sorted[j].id);
    }
  }
  return ids;
}

export function summarize(entries) {
  const minutes = Object.fromEntries(CATEGORIES.map((category) => [category, 0]));
  for (const entry of entries) minutes[entry.category] += entry.end - entry.start;
  const study = entries.filter((entry) => SUBJECTS.includes(entry.category));
  const total = SUBJECTS.reduce((sum, subject) => sum + minutes[subject], 0);
  const span = study.length ? Math.max(...study.map((entry) => entry.end)) - Math.min(...study.map((entry) => entry.start)) : 0;
  return { minutes, total, span, shares: Object.fromEntries(SUBJECTS.map((subject) => [subject, total ? minutes[subject] / total : 0])) };
}

function validateEntries(entries) {
  if (!Array.isArray(entries)) throw new Error('时间安排格式无效');
  const ids = new Set();
  for (const entry of entries) {
    if (validateEntry(entry) || typeof entry.id !== 'string' || !entry.id || ids.has(entry.id)) throw new Error('时间安排条目无效');
    ids.add(entry.id);
  }
}

export function loadPlan(storage) {
  try {
    const raw = storage.getItem(KEY_PLAN);
    if (raw === null) return { entries: defaultEntries(), error: '' };
    const saved = JSON.parse(raw);
    if (!saved || saved.version !== 1) throw new Error('不支持的时间安排版本');
    validateEntries(saved.entries);
    return { entries: sortedEntries(saved.entries), error: '' };
  } catch {
    // 保留原缓存，只有用户明确恢复默认或清除数据后才能覆盖。
    return { entries: defaultEntries(), error: '无法读取本机时间安排。原数据未改动，下方仅预览原始安排；编辑已停用。可重试读取，或确认后恢复原始安排。' };
  }
}

export function savePlan(storage, entries) {
  validateEntries(entries);
  storage.setItem(KEY_PLAN, JSON.stringify({ version: 1, entries: sortedEntries(entries) }));
}
