// Turns the static figures of a .fig3d block into a 3D figure when the reader's browser can show one.
// Without script, without WebGL, or with "reduce motion", the static figures stay exactly as they are (the fallback is the page itself).
// Wide screens get the 3D figure in place of the static ones (with a button back to them); narrow screens keep the static
// figures and get a button that opens the 3D figure full screen.
import { Stage } from './stage.js';
import { makeParts } from './parts.js';
import * as ui from './ui.js';

const NARROW = 760;

function detectEnv() {
  let webgl = false;
  try {
    const c = document.createElement('canvas');
    webgl = !!(c.getContext('webgl2') || c.getContext('webgl'));
  } catch (e) { webgl = false; }
  const mq = (q) => !!(window.matchMedia && window.matchMedia(q).matches);
  return { webgl, reduced: mq('(prefers-reduced-motion: reduce)'), narrow: window.innerWidth < NARROW };
}

export function boot(defs) {
  const reg = new Map(defs.map((d) => [d.name, d]));
  const hook = { instances: [], env: null, blocks: [] };
  window.__EBOOK_FIG3D__ = hook;
  const run = () => {
    hook.env = detectEnv();
    document.querySelectorAll('.fig3d[data-scene]').forEach((el) => setup(el, reg, hook));
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
}

function setup(el, reg, hook) {
  const env = hook.env;
  const def = reg.get(el.dataset.scene);
  const block = { el, scene: el.dataset.scene, state: 'static', open: null };
  hook.blocks.push(block);
  const setState = (s) => { block.state = s; el.dataset.fig3dState = s; };
  if (!def) { setState('static-unknown-scene'); return; }
  if (!env.webgl) { setState('static-no-webgl'); return; }
  let data;
  try { data = JSON.parse(el.querySelector('script.fig3d-data').textContent); } catch (e) { setState('static-bad-data'); return; }
  const head = el.querySelector('.fig3d-head');
  const stat = el.querySelector('.fig3d-static');
  head.hidden = false;
  const tools = ui.h('span', 'fig3d-tools');
  head.appendChild(tools);
  let inst = null;

  const mount = (where) => {
    const wrap = ui.h('div', 'f3-wrap');
    wrap.tabIndex = -1;          // focusable from script (a click on the canvas focuses it), so the arrow keys reach the figure
    const view = ui.h('div', 'f3-view');
    if (def.camera && def.camera.viewHeight) view.style.setProperty('--f3-max', def.camera.viewHeight + 'px');          // a scene that needs a taller stage
    wrap.appendChild(view);
    const zoom = ui.h('div', 'f3-zoom');
    ui.button(zoom, '＋', () => inst.stage.zoom(0.85), 'f3-zbtn').setAttribute('aria-label', '放大');
    ui.button(zoom, '－', () => inst.stage.zoom(1.18), 'f3-zbtn').setAttribute('aria-label', '缩小');
    ui.button(zoom, '⟲', () => inst.stage.resetView(), 'f3-zbtn').setAttribute('aria-label', '回正');
    view.appendChild(zoom);
    const stage = new Stage(view, def.camera || {});
    if (env.reduced) stage.anim.instant = true;
    const read = ui.readout(view);
    const below = ui.h('div', 'f3-below');
    wrap.appendChild(below);
    const panel = ui.h('div', 'f3-panel');
    const cap = ui.h('div', 'f3-cap');
    wrap.append(panel, cap);
    const ctx = {
      stage, parts: makeParts(stage), ui, panel, below, readout: read, data, reduced: env.reduced, where,
      setCaption(rids) {
        cap.replaceChildren();
        for (const rid of [].concat(rids)) {
          const c = data.caps && data.caps[rid];
          if (!c) continue;
          const line = ui.h('span', 'f3-cap-line');
          line.append(ui.h('span', 'tag ' + (c.tag === '实测' ? 'tag-shice' : c.tag === '示意' ? 'tag-shiyi' : 'tag-source'), c.tag), document.createTextNode(' ' + c.cap));
          cap.appendChild(line);
        }
        for (const rid of [].concat(rids)) if (data.afters && data.afters[rid]) cap.appendChild(ui.h('span', 'f3-cap-line f3-cap-after', data.afters[rid]));          // the static figure's own caveat sentence
        if (data.note) cap.appendChild(ui.h('span', 'f3-cap-line f3-cap-note', data.note));
      },
    };
    const api = def.create(ctx);
    const foot = ui.h('div', 'f3-foot');
    ui.button(foot, '重来', () => api.reset(), 'f3-btn f3-reset');
    panel.appendChild(foot);
    wrap.addEventListener('keydown', (e) => {
      if (e.target.closest && e.target.closest('.f3-chips')) return;
      if ((e.key === 'ArrowRight' || e.key === 'ArrowLeft') && api.step) { e.preventDefault(); api.step(e.key === 'ArrowRight' ? 1 : -1); }
    });
    inst = { scene: def.name, where, el, wrap, stage, api, state: () => api.state() };
    hook.instances.push(inst);
    block.open = inst;
    stage.invalidate();
    return inst;
  };

  if (!env.narrow && !env.reduced) {
    const back = ui.button(tools, '看原图', () => {
      const showStatic = stat.hidden;
      stat.hidden = !showStatic;
      if (inst) inst.wrap.hidden = showStatic;
      back.textContent = showStatic ? '看立体图' : '看原图';
      setState(showStatic ? 'inline-static' : 'inline');
      if (inst && !showStatic) inst.stage.invalidate();
    }, 'fig3d-btn');
    back.hidden = true;          // only once the 3D figure is there is there anything to switch back from
    setState('pending');
    const io = new IntersectionObserver((es) => {
      if (!es.some((e) => e.isIntersecting) || inst) return;
      io.disconnect();
      const i = mount('inline');
      el.insertBefore(i.wrap, stat);
      stat.hidden = true;
      back.hidden = false;
      setState('inline');
    }, { rootMargin: '300px 0px' });
    io.observe(el);
    return;
  }

  // narrow screen or reduced motion: the static figures stay; a button opens the 3D figure over the page
  setState('static-button');
  const open = ui.button(tools, env.reduced ? '打开立体图（动作已减到最少）' : '打开立体图', () => openOverlay(), 'fig3d-btn fig3d-open');
  const openOverlay = () => {
    const ov = ui.h('div', 'f3-overlay');
    ov.setAttribute('role', 'dialog');
    ov.setAttribute('aria-modal', 'true');
    ov.setAttribute('aria-label', '立体图：' + (data.title || ''));
    const bar = ui.h('div', 'f3-ov-bar');
    bar.append(ui.h('span', 'tag tag-3d', '立体图'), ui.h('span', 'f3-ov-title', data.title || ''));
    const close = ui.button(bar, '关闭', () => shut(), 'fig3d-btn f3-close');
    ov.appendChild(bar);
    const inerted = [...document.body.children].filter((x) => !x.inert);
    inerted.forEach((x) => { x.inert = true; });          // the page behind the dialog takes no focus and is not read
    document.body.appendChild(ov);
    document.documentElement.classList.add('f3-locked');
    const i = mount('overlay');
    ov.appendChild(i.wrap);
    setState('overlay');
    const onKey = (e) => {
      if (e.key === 'Escape') { shut(); return; }
      if (e.key !== 'Tab') return;          // keep the keyboard inside the dialog
      const f = [...ov.querySelectorAll('button:not([disabled]), input, [tabindex]:not([tabindex="-1"])')].filter((x) => x.offsetParent !== null);
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    };
    document.addEventListener('keydown', onKey);
    close.focus();
    function shut() {
      document.removeEventListener('keydown', onKey);
      i.stage.dispose();
      ov.remove();
      inerted.forEach((x) => { x.inert = false; });
      document.documentElement.classList.remove('f3-locked');
      hook.instances.splice(hook.instances.indexOf(i), 1);
      inst = null;
      block.open = null;
      setState('static-button');
      open.focus();
    }
  };
}
