// The notebook panel under a 3D figure, the readout bar over it, and the step control. Plain DOM, text only via textContent.
const h = (tag, cls, text) => {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (text !== undefined) el.textContent = text;
  return el;
};

// a row of choices; every choice may carry a one-line preview of what it will show (Electronics 101's options with their consequence)
export function choices(parent, { label, options, value, hint, onChange }) {
  const g = h('div', 'f3-group');
  g.appendChild(h('div', 'f3-glabel', label));
  const row = h('div', 'f3-chips');
  row.setAttribute('role', 'radiogroup');
  row.setAttribute('aria-label', label);
  const hintEl = h('p', 'f3-hint');
  const btns = [];
  const select = (key, fire) => {
    for (const b of btns) {
      const on = b.dataset.key === key;
      b.setAttribute('aria-checked', on ? 'true' : 'false');
      b.classList.toggle('on', on);
      b.tabIndex = on ? 0 : -1;
    }
    const opt = options.find((o) => o.key === key);
    hintEl.textContent = (opt && opt.preview) || hint || '';
    hintEl.hidden = !hintEl.textContent;
    if (fire && onChange) onChange(key);
  };
  for (const o of options) {
    const b = h('button', 'f3-chip');
    b.type = 'button';
    b.dataset.key = o.key;
    b.setAttribute('role', 'radio');
    b.appendChild(h('span', 'f3-chip-t', o.text));
    if (o.sub) b.appendChild(h('span', 'f3-chip-s', o.sub));
    b.addEventListener('click', () => select(o.key, true));
    b.addEventListener('keydown', (e) => {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      e.preventDefault();
      e.stopPropagation();
      const i = btns.indexOf(b), j = (i + (e.key === 'ArrowRight' ? 1 : -1) + btns.length) % btns.length;
      btns[j].focus();
      select(btns[j].dataset.key, true);
    });
    btns.push(b);
    row.appendChild(b);
  }
  g.appendChild(row);
  g.appendChild(hintEl);
  parent.appendChild(g);
  select(value ?? options[0].key, false);
  // subs(fn): rewrite every option's small line, e.g. what that option would give with the other knobs as they are now (Electronics 101's preview under each option)
  const subs = (fn) => btns.forEach((b) => {
    let s = b.querySelector('.f3-chip-s');
    if (!s) { s = h('span', 'f3-chip-s'); b.appendChild(s); }
    s.textContent = fn(b.dataset.key);
  });
  return { el: g, select: (k) => select(k, true), set: (k) => select(k, false), subs, get: () => (btns.find((b) => b.classList.contains('on')) || {}).dataset?.key };
}

export function slider(parent, { label, min, max, step, value, format, onInput }) {
  const g = h('div', 'f3-group f3-slider');
  const lab = h('label', 'f3-glabel');
  const id = 'f3s-' + Math.random().toString(36).slice(2, 8);
  lab.htmlFor = id;
  lab.textContent = label;
  const out = h('output', 'f3-sval');
  const inp = document.createElement('input');
  inp.type = 'range';
  inp.id = id;
  Object.assign(inp, { min, max, step, value });
  const show = () => { out.textContent = format ? format(+inp.value) : inp.value; };
  inp.addEventListener('input', () => { show(); if (onInput) onInput(+inp.value); });
  g.append(lab, inp, out);
  parent.appendChild(g);
  show();
  return { el: g, input: inp, set: (v) => { inp.value = v; show(); if (onInput) onInput(+inp.value); }, get: () => +inp.value };
}

// numbers that change with the scene, in a bar over the canvas (Designed to Scale's metric cards)
export function readout(parent) {
  const bar = h('div', 'f3-readout');
  bar.setAttribute('aria-live', 'polite');
  parent.appendChild(bar);
  const cells = new Map();
  return {
    el: bar,
    set(items) {          // [{k: label, v: value, tag?: '实测' | '示意'}]
      const keep = new Set();
      for (const it of items) {
        let c = cells.get(it.k);
        if (!c) {
          c = h('div', 'f3-metric');
          c.append(h('span', 'f3-mk', it.k), h('b', 'f3-mv'), h('span', 'f3-mt'));
          cells.set(it.k, c);
        }
        bar.appendChild(c);
        c.children[1].textContent = String(it.v);
        c.children[2].textContent = it.tag || '';
        c.children[2].hidden = !it.tag;
        c.classList.toggle('shiyi', it.tag === '示意');
        keep.add(it.k);
      }
      for (const [k, c] of cells) if (!keep.has(k)) { c.remove(); cells.delete(k); }
    },
  };
}

// "这一步变了什么" (Designed to Scale's WHAT CHANGED)
export function changed(parent) {
  const box = h('div', 'f3-changed');
  box.setAttribute('aria-live', 'polite');
  box.append(h('b', 'f3-changed-k', '这一步变了什么'), h('span', 'f3-changed-v'));
  parent.appendChild(box);
  return { el: box, set: (t) => { box.children[1].textContent = t; box.hidden = !t; } };
}

// guess first (optional, never marked right or wrong), then see the measurement side by side with the guess
export function guess(parent) {
  const box = h('div', 'f3-guess');
  box.hidden = true;
  parent.appendChild(box);
  let pending = null;
  return {
    el: box,
    ask(question, options) {
      if (pending) { const p = pending; pending = null; p(null); }          // an older question that was never answered
      box.replaceChildren();
      box.hidden = false;
      box.classList.remove('done');
      box.appendChild(h('p', 'f3-guess-q', question));
      const row = h('div', 'f3-guess-o');
      return new Promise((resolve) => {
        pending = resolve;
        const pick = (v) => { pending = null; box.classList.add('done'); row.replaceChildren(); box.appendChild(h('p', 'f3-guess-a', v === null ? '没猜，直接看。' : '你猜：' + v)); resolve(v); };
        for (const o of options) {
          const b = h('button', 'f3-chip', o);
          b.type = 'button';
          b.addEventListener('click', () => pick(o));
          row.appendChild(b);
        }
        const skip = h('button', 'f3-link', '跳过，直接看');
        skip.type = 'button';
        skip.addEventListener('click', () => pick(null));
        row.appendChild(skip);
        box.appendChild(row);
      });
    },
    reveal(text) {
      if (pending) { const p = pending; pending = null; box.classList.add('done'); box.querySelector('.f3-guess-o')?.replaceChildren(); box.appendChild(h('p', 'f3-guess-a', '没猜，直接看。')); p(null); }          // shown before the reader answered: close the question first
      const r = h('p', 'f3-guess-r', text);
      box.appendChild(r);
    },
    hide() { if (pending) { const p = pending; pending = null; p(null); } box.hidden = true; box.replaceChildren(); },
  };
}

// ← step dots → and replay (Designed to Scale's step bar)
export function stepper(parent, { steps, onGo, onReplay }) {
  const bar = h('div', 'f3-steps');
  bar.setAttribute('role', 'group');
  bar.setAttribute('aria-label', '分步');
  const prev = h('button', 'f3-step-nav', '←');
  prev.type = 'button';
  prev.setAttribute('aria-label', '上一步');
  const next = h('button', 'f3-step-nav', '→');
  next.type = 'button';
  next.setAttribute('aria-label', '下一步');
  const dots = h('div', 'f3-step-dots');
  const replay = h('button', 'f3-step-replay', '重放');
  replay.type = 'button';
  let cur = 0, list = [];
  const draw = () => {
    dots.replaceChildren();
    list = steps().map((s, i) => {
      const b = h('button', 'f3-dot');
      b.type = 'button';
      b.append(h('span', 'f3-dot-n', String(i + 1)), h('span', 'f3-dot-t', s));
      b.setAttribute('aria-label', `第 ${i + 1} 步：${s}`);
      b.addEventListener('click', () => go(i));
      dots.appendChild(b);
      return b;
    });
    mark();
  };
  const mark = () => {
    list.forEach((b, i) => { b.classList.toggle('on', i === cur); b.classList.toggle('past', i < cur); if (i === cur) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current'); });
    prev.disabled = cur <= 0;
    next.disabled = cur >= list.length - 1;
  };
  const go = (i) => { cur = Math.max(0, Math.min(list.length - 1, i)); mark(); onGo(cur); };
  prev.addEventListener('click', () => go(cur - 1));
  next.addEventListener('click', () => go(cur + 1));
  replay.addEventListener('click', () => { if (onReplay) onReplay(); else go(0); });
  bar.append(prev, dots, next, replay);
  parent.appendChild(bar);
  draw();
  return { el: bar, go, redraw: () => { cur = 0; draw(); }, get current() { return cur; }, prev: () => go(cur - 1), next: () => go(cur + 1) };
}

export function button(parent, text, fn, cls = 'f3-btn') {
  const b = h('button', cls, text);
  b.type = 'button';
  b.addEventListener('click', fn);
  parent.appendChild(b);
  return b;
}

export { h };
