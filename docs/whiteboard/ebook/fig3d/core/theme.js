// Colours of the 3D figures come from book.css variables, so the figures follow the light and dark themes like every other figure.
import { Color } from 'three';

const NAMES = ['bg', 'surface', 'note-bg', 'fg', 'fg-2', 'muted', 'faint', 'line', 'line-strong', 'accent', 'red', 'hl', 'user', 'model', 'model-line',
  'model-bar', 'sticky', 'good', 'bad', 'pick', 'l4-system', 'l4-grid-correct', 'l4-grid-admit', 'l4-grid-fabricated', 'l4-grid-other'];

// the ten pale hues of the lesson-3 "rows" figures (blocks.py ROW_COLORS): one hue per distinct answer, the same in the flat figure and in the 3D one
export const ANSWER_HUES = ['#FFF3A8', '#CDEBFA', '#FAD3D9', '#D4F0D2', '#E3CA9B', '#E6D5F7', '#E2EDB0', '#BFEBDD', '#D9DEE5', '#F1C0E8'];

export function readTheme(el) {
  const cs = getComputedStyle(el || document.documentElement);
  const t = {};
  for (const n of NAMES) {
    const v = cs.getPropertyValue('--' + n).trim();
    t[n] = v || '#888888';
  }
  t.dark = isDark();
  return t;
}

export function isDark() {
  const html = document.documentElement;
  const set = html.getAttribute('data-theme');
  if (set === 'dark') return true;
  if (set === 'light') return false;
  return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
}

export function color(v) {
  const c = new Color();
  try { c.set(v); } catch (e) { c.set('#888888'); }
  return c;
}

// call fn when the reader switches the theme (the ◐ button sets data-theme) or the system scheme changes
export function onThemeChange(fn) {
  const obs = new MutationObserver(() => fn());
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  const mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  if (mq && mq.addEventListener) mq.addEventListener('change', fn);
  return () => { obs.disconnect(); if (mq && mq.removeEventListener) mq.removeEventListener('change', fn); };
}
