// RC 充电 (demo, electronics): a battery charges a capacitor through a resistor. Pick R and C, close the switch, watch the capacitor fill and its
// voltage curve rise; τ = R × C. Everything is computed from the real formula V_C(t) = V (1 − e^(−t/τ)) and marked 示意 (no measurement).
import { ease } from '../core/anim.js';

const SVGNS = 'http://www.w3.org/2000/svg';          // the SVG namespace name (an identifier, never fetched); the only URL-like string allowed in our fig3d code
const fmtT = (s) => (s < 1 ? `${Math.round(s * 1000)} 毫秒` : `${s.toFixed(2)} 秒`);

export default {
  name: 'rc-charge',
  camera: { yaw: 0.6, pitch: 0.75, radius: 15, target: [0, 0.4, 0], fov: 30 },
  create(ctx) {
    const { stage, parts, ui, panel, data, readout } = ctx;
    const V = data.volts, Rs = data.r_options, Cs = data.c_options, T = data.window_s;
    let R = Rs[1], C = Cs[1], vc = 0, t = 0, running = null, ghost = null, guessed = false;
    const tau = () => (R.ohm * C.farad);
    stage.root.add(parts.floor(20, 14, 1));
    // the board and the parts
    const board = parts.block({ w: 9, h: 0.3, d: 5, fill: 'surface' });
    board.position.set(0, 0.15, 0);
    stage.root.add(board);
    const batt = parts.cylinder(0.55, 1.4, 'l4-system');
    batt.position.set(-3.2, 1.0, 0);
    stage.root.add(batt);
    stage.labels.add(batt, `电池 ${V} 伏`, { offset: [0, 1.05, 0], cls: 'f3-l-strong' });
    const res = parts.block({ w: 1.6, h: 0.36, d: 0.36, fill: 'user' });
    res.position.set(0, 0.5, -1.6);
    stage.root.add(res);
    const resLab = stage.labels.add(res, '', { offset: [0, 0.55, 0] });
    const capShell = parts.cylinder(0.6, 1.5, 'note-bg', { opacity: 0.35 });
    capShell.position.set(3.2, 1.05, 0);
    stage.root.add(capShell);
    const fill = parts.cylinder(0.5, 1.4, 'accent');
    fill.children[1].visible = false;
    fill.position.set(3.2, 0.35, 0);
    stage.root.add(fill);
    const capLab = stage.labels.add(capShell, '', { offset: [0, 1.15, 0] });
    const sw = parts.block({ w: 1.0, h: 0.3, d: 0.6, fill: 'note-bg' });
    sw.position.set(0, 0.45, 1.6);
    stage.root.add(sw);
    const swLab = stage.labels.add(sw, '开关：断开（点它合上）', { offset: [0, 0.5, 0.2] });
    parts.pickable(sw, { tip: '点一下：合上开关，开始充电', onClick: () => start() });
    const loop = parts.wire([[-3.2, 0.35, -0.4], [-3.2, 0.35, -1.6], [-0.8, 0.35, -1.6], [0.8, 0.35, -1.6], [3.2, 0.35, -1.6], [3.2, 0.35, -0.6], [3.2, 0.35, 1.6], [0.5, 0.35, 1.6], [-0.5, 0.35, 1.6], [-3.2, 0.35, 1.6], [-3.2, 0.35, 0.4]], { dots: 14, dotKey: 'accent', dotSize: 0.1 });
    stage.root.add(loop);
    let phase = 0;

    // the controls: options with a one-line preview of what they will do (τ for that choice)
    panel.appendChild(ui.h('p', 'f3-hint f3-legend', '电池经过电阻给电容充电。电阻越大、电容越大，充得越慢；时间常数 τ ＝ R × C 是充到约 63% 所用的时间。'));
    const ctrl = ui.h('div', 'f3-controls');
    panel.appendChild(ctrl);
    const prev = (r, c) => `这一档：τ ＝ ${r.text} × ${c.text} ＝ ${fmtT(r.ohm * c.farad)}`;
    const oR = Rs.map((r) => ({ key: r.key, text: r.text })), oC = Cs.map((c) => ({ key: c.key, text: c.text }));          // one preview line for both knobs, under them (the same line twice read as a repeat)
    const cR = ui.choices(ctrl, { label: '电阻 R', value: R.key, options: oR, onChange: (k) => { R = Rs.find((x) => x.key === k); changed(); } });
    const cC = ui.choices(ctrl, { label: '电容 C', value: C.key, options: oC, onChange: (k) => { C = Cs.find((x) => x.key === k); changed(); } });
    ui.button(ctrl, '合上开关，开始充电', () => start(), 'f3-btn');
    const tauLine = ui.h('p', 'f3-hint');
    panel.appendChild(tauLine);
    // the curve panel (DOM SVG): this run, the previous run as a shadow, and the 63% line
    const curve = document.createElementNS(SVGNS, 'svg');
    curve.setAttribute('viewBox', '0 0 320 150');
    curve.setAttribute('class', 'f3-curve');
    curve.setAttribute('role', 'img');
    const mk = (tag, attrs) => { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); curve.appendChild(e); return e; };
    mk('line', { x1: 34, y1: 128, x2: 312, y2: 128, class: 'ax' });
    mk('line', { x1: 34, y1: 10, x2: 34, y2: 128, class: 'ax' });
    const th = mk('line', { x1: 34, x2: 312, class: 'thr' });
    const thT = mk('text', { x: 38, class: 'thr-t' });
    const yT = mk('text', { x: 4, y: 16, class: 'lab' });
    yT.textContent = `${V} 伏`;
    const xT = mk('text', { x: 312, y: 144, class: 'lab', 'text-anchor': 'end' });
    xT.textContent = `${T} 秒`;
    const ghostP = mk('polyline', { class: 'ghost', points: '' });
    const lineP = mk('polyline', { class: 'now', points: '' });
    const tauM = mk('line', { class: 'tau', y1: 10, y2: 128 });
    const curveBox = ui.h('div', 'f3-curvebox');
    curveBox.appendChild(ui.h('div', 'f3-glabel', '电容两端的电压（按公式算，示意）'));
    curveBox.appendChild(curve);
    panel.appendChild(curveBox);
    const g = ui.guess(panel);
    const ch = ui.changed(panel);
    const X = (s) => 34 + (s / T) * 278, Y = (v) => 128 - (v / V) * 118;
    const yThr = Y(V * (1 - Math.exp(-1)));
    th.setAttribute('y1', yThr); th.setAttribute('y2', yThr);
    thT.setAttribute('y', yThr - 4);
    thT.textContent = '约 63%：用时就是 τ';
    const pts = (tt) => { const out = []; for (let k = 0; k <= 80; k++) { const s = (tt * k) / 80; out.push(`${X(s).toFixed(1)},${Y(V * (1 - Math.exp(-s / tau()))).toFixed(1)}`); } return out.join(' '); };

    function show() {
      const tv = tau();
      resLab.set(`电阻 ${R.text}`);
      capLab.set(`电容 ${C.text} · ${vc.toFixed(2)} 伏`);
      fill.scale.y = Math.max(0.02, vc / V);
      fill.position.y = 0.35 + 0.7 * fill.scale.y;
      const tx = Math.min(X(tv), 312);
      tauM.setAttribute('x1', tx); tauM.setAttribute('x2', tx);
      tauM.style.display = tv <= T ? '' : 'none';
      curve.setAttribute('aria-label', `电容电压曲线：τ ＝ ${fmtT(tv)}，现在 ${vc.toFixed(2)} 伏`);
      readout.set([
        { k: 'τ ＝ R × C', v: fmtT(tv), tag: '示意' },
        { k: '此刻电压', v: `${vc.toFixed(2)} 伏`, tag: '示意' },
        { k: '电流', v: `${((V - vc) / R.ohm * 1000).toFixed(2)} 毫安`, tag: '示意' },
      ]);
      stage.invalidate();
    }
    function changed() {
      op++;
      ch.set(`换了一档：τ ＝ ${R.text} × ${C.text} ＝ ${fmtT(tau())}。合上开关看看。`);
      stop(false);
      if (lineP.getAttribute('points')) ghostP.setAttribute('points', lineP.getAttribute('points'));          // the last curve stays as a shadow to compare with
      vc = 0; t = 0; lineP.setAttribute('points', '');
      show();
      refreshPreviews();
      scrub(read.s, false);          // the cursor reads the new curve at the same second
    }
    function refreshPreviews() {
      tauLine.textContent = prev(R, C) + '（一个 τ 后约到 63%，五个 τ 后几乎充满）';
      cR.set(R.key); cC.set(C.key);
      cR.subs((k) => 'τ＝' + fmtT(Rs.find((x) => x.key === k).ohm * C.farad));          // what each option would give with the other knob as it is
      cC.subs((k) => 'τ＝' + fmtT(R.ohm * Cs.find((x) => x.key === k).farad));
    }
    // read the curve at any second: a slider (keyboard, screen readers) and a cursor on the board you drag along its rail (both the same control)
    const rail = parts.block({ w: 6, h: 0.06, d: 0.18, fill: 'line-strong', outline: 0 });
    rail.position.set(0, 0.33, 2.25);
    stage.root.add(rail);
    const cursor = parts.block({ w: 0.36, h: 0.36, d: 0.36, fill: 'accent' });
    cursor.position.set(-3, 0.5, 2.25);
    stage.root.add(cursor);
    const curLab = stage.labels.add(cursor, '', { offset: [0, 0.5, 0.3] });
    const marker = mk('line', { class: 'cur', y1: 10, y2: 128 });
    const scrubber = ui.slider(panel, { label: '看第几秒', min: 0, max: T, step: 0.1, value: 0, format: (v) => `${v.toFixed(1)} 秒`, onInput: (v) => scrub(v, true) });
    function scrub(s, fromSlider) {
      const v = V * (1 - Math.exp(-s / tau()));
      cursor.position.x = -3 + 6 * (s / T);
      curLab.set(`第 ${s.toFixed(1)} 秒：${v.toFixed(2)} 伏`);
      marker.setAttribute('x1', X(s)); marker.setAttribute('x2', X(s));
      if (!fromSlider) scrubber.input.value = s.toFixed(1);
      scrubber.el.querySelector('output').textContent = `${s.toFixed(1)} 秒`;
      read = { s, v };
      stage.invalidate();
    }
    let read = { s: 0, v: 0 };
    parts.pickable(cursor, { tip: '沿轨道拖动，看第几秒的电压', drag: { axis: 'x', min: -3, max: 3, y: 0.5, onDrag: (x) => scrub(((x + 3) / 6) * T, false) } });
    function stop(keepGhost) {
      if (running) { running.cancel = true; running = null; }
      if (keepGhost) ghostP.setAttribute('points', lineP.getAttribute('points'));
      swLab.set('开关：断开（点它合上）');
      sw.setFill('note-bg');
    }
    let op = 0;
    async function start() {
      const ticket = ++op;
      if (!guessed) {
        guessed = true;
        const pick = await g.ask('先猜：把电阻换大一档，电容充到一样满，会更快、更慢，还是一样？', ['更快', '更慢', '一样']);
        if (ticket !== op) return;          // the reader reset or changed a knob while the question was open
        g.reveal(`按公式：电阻大，τ 就大，充得更慢。现在这一档 τ ＝ ${fmtT(tau())}。${pick ? '猜的和算的并排放在这里，不判对错。' : ''}`);
      }
      if (lineP.getAttribute('points')) ghostP.setAttribute('points', lineP.getAttribute('points'));
      stop(false);
      const me = running = { cancel: false };
      swLab.set('开关：合上（在充电）');
      sw.setFill('good');
      vc = 0; t = 0;
      const ms = ctx.reduced ? 0 : 4000;          // the T-second window plays in four seconds (time is sped up or slowed down: 示意)
      await stage.anim.tween({ ms, curve: ease.linear, step: (k) => {
        if (me.cancel) return;
        t = k * T; vc = V * (1 - Math.exp(-t / tau()));
        phase = (phase + 0.004 + 0.05 * (V - vc) / V) % 1;
        loop.setFlow(phase);
        scrub(t, false);          // the cursor rides along with the charge, so the picture shows one moment; drag it back afterwards to read earlier seconds
        lineP.setAttribute('points', pts(t));
        show();
      } });
      if (me.cancel) return;
      running = null;
      swLab.set(vc >= V * 0.99 ? '开关：合上（已几乎充满，电流接近 0）' : '开关：合上（还在充电）');
      ch.set(`${T} 秒后电容到 ${vc.toFixed(2)} 伏（${(vc / V * 100).toFixed(0)}%）。虚线是上一次的曲线，可以比一比。`);
    }
    show();
    refreshPreviews();
    ctx.setCaption(data.rid);
    ch.set('');
    return {
      reset() { op++; scrub(0, false); stop(false); ghostP.setAttribute('points', ''); R = Rs[1]; C = Cs[1]; cR.set(R.key); cC.set(C.key); vc = 0; t = 0; lineP.setAttribute('points', ''); guessed = false; g.hide(); ch.set(''); refreshPreviews(); show(); stage.resetView(); },
      choose(r, c) { if (r) { R = Rs.find((x) => x.key === r); cR.set(r); } if (c) { C = Cs.find((x) => x.key === c); cC.set(c); } changed(); },
      start: () => { guessed = true; return start(); },
      state: () => ({ R: R.key, C: C.key, tau: tau(), vc, t, dropping: !!running, expected: V * (1 - Math.exp(-t / tau())), cursor: read }),
      items: () => [{ rid: data.rid, kind: 'circuit' }],
    };
  },
};
