// 纸条摞 (note stack): every message of a request is a note on the desk, in the order it is sent. System notes are lavender, the user's beige,
// the assistant's model-cyan. Two stories: (a) variants - take a note out or swap it, and see what two models answered ten times each (lesson 4);
// (b) window - pin the system note aside, keep the most recent notes, tear the older ones off into the program's folder (lesson 6).
import { ease } from '../core/anim.js';

const PW = 4.6, PD = 0.95, PH = 0.06, STEP_Z = 0.82, STEP_Y = 0.07;
const ROLE_FILL = { system: 'l4-system', user: 'user', assistant: 'model' };
const CELL_FILL = { correct: 'l4-grid-correct', admit: 'l4-grid-admit', fabricated: 'l4-grid-fabricated', other: 'l4-grid-other' };
const short = (t, n = 15) => (t.length <= n ? t : t.slice(0, n - 1) + '…');

export default {
  name: 'note-stack',
  camera: { yaw: 0.5, pitch: 0.8, radius: 17, target: [0, 0.4, 0], fov: 30, viewHeight: 580 },
  create(ctx) {
    const { stage, parts, ui, panel, data, readout } = ctx;
    const world = new stage.root.constructor();
    stage.root.add(world);
    stage.root.add(parts.floor(30, 20, 1));
    let items = [];
    const papers = new Map();       // key -> {g, label}

    function paper(n) {
      const g = parts.paper({ w: PW, d: PD, h: PH, fill: ROLE_FILL[n.role] });
      parts.pickable(g, { tip: `${n.role_cn}：${n.text}` + (n.stamp ? '（这一张是我们事先写进请求的）' : '') });
      const lab = stage.labels.add(g, `${n.role_cn}${n.stamp ? '（事先写好）' : ''} · ${short(n.text)}`, { offset: [0, 0.12, 0] });
      world.add(g);
      return { g, lab };
    }
    const slot = (i, n, x = 0) => [x, 0.04 + i * STEP_Y, (i - (n - 1) / 2) * STEP_Z];          // older notes further back, newer ones nearer and on top
    const moveTo = (obj, to, ms = 520, delay = 0) => {
      const from = obj.position.toArray();
      return stage.anim.tween({ ms, delay, key: obj, curve: ease.inOut, step: (k) => obj.position.set(from[0] + (to[0] - from[0]) * k, from[1] + (to[1] - from[1]) * k + Math.sin(Math.PI * k) * 0.6, from[2] + (to[2] - from[2]) * k) });
    };

    // ---------------------------------------------------------------- (a) variants: take out / swap one note, results of ten runs per model
    if (data.mode === 'variants') {
      let cur = data.variants[0], seq = 0;
      const seen = new Set();
      panel.appendChild(ui.h('p', 'f3-hint f3-legend', '每张纸条是请求里的一条消息，从前往后摞。换一种摞法，看两个模型各问十遍怎么答。'));
      const ctrl = ui.h('div', 'f3-controls');
      panel.appendChild(ctrl);
      const pick = ui.choices(ctrl, { label: '这次请求里的纸条', value: cur.rid, options: data.variants.map((v) => ({ key: v.rid, text: v.title })), onChange: (k) => { cur = data.variants.find((v) => v.rid === k); build(true); } });
      const legend = ui.h('div', 'f3-legend-row');          // what the colours and the dot of the run blocks mean (the static grid's own legend)
      const lg = data.variants[0].results[0];
      Object.entries(lg.legend || {}).forEach(([cls, text]) => { const it = ui.h('span', 'f3-legend-item'); const sw = ui.h('i', 'f3-swatch'); sw.style.background = `var(--${CELL_FILL[cls] || 'note-bg'})`; it.append(sw, document.createTextNode(text)); legend.appendChild(it); });
      if (lg.dot_legend) { const it = ui.h('span', 'f3-legend-item'); it.append(ui.h('i', 'f3-dot-mark'), document.createTextNode(lg.dot_legend)); legend.appendChild(it); }
      panel.appendChild(legend);
      const g = ui.guess(panel);
      const ch = ui.changed(panel);
      const cells = new stage.root.constructor();
      world.add(cells);
      let prev = null, cellLabels = [];
      async function build(animate) {
        const token = ++seq;
        ctx.setCaption([cur.rid, cur.results[0].rid]);
        const keys = cur.notes.map((n, i) => n.role + '|' + n.text + '|' + cur.notes.slice(0, i).filter((m) => m.role === n.role && m.text === n.text).length);          // two identical notes stay two papers
        // notes that leave fly up and away; notes that stay slide to their new place; new notes drop in
        for (const [k, p] of [...papers]) {
          if (!keys.includes(k)) {
            papers.delete(k);
            p.lab.remove();
            const from = p.g.position.toArray();
            stage.anim.tween({ ms: animate ? 520 : 0, key: p.g, curve: ease.inOut, step: (t) => p.g.position.set(from[0] + 6 * t, from[1] + 2.5 * t, from[2]), done: () => { world.remove(p.g); stage.disposeTree(p.g); } });
          }
        }
        stage.pickables.length = 0;
        items = [];
        cur.notes.forEach((n, i) => {
          const k = keys[i];
          let p = papers.get(k);
          if (!p) { p = paper(n); papers.set(k, p); const to = slot(i, cur.notes.length); p.g.position.set(to[0] - 6, to[1] + 2.5, to[2]); }
          else parts.pickable(p.g, { tip: `${n.role_cn}：${n.text}` + (n.stamp ? '（这一张是我们事先写进请求的）' : '') });
          moveTo(p.g, slot(i, cur.notes.length), animate ? 560 : 0, animate ? 90 * i : 0);
          items.push({ rid: n.rid, kind: 'note', i: n.i, role: n.role });
        });
        if (prev && prev !== cur) {
          const a = prev.notes.length, b = cur.notes.length;
          ch.set(a > b ? `抽掉了一张：纸条从 ${a} 张变成 ${b} 张` : a < b ? `多了一张：纸条从 ${a} 张变成 ${b} 张` : `换了一张：${cur.title}`);
        } else ch.set('');
        prev = cur;
        stage.clearGroup(cells);
        cellLabels.forEach((l) => l.remove());
        cellLabels = [];
        readout.set([{ k: '这次请求里的纸条', v: cur.notes.length + ' 张', tag: '实测' }].concat(cur.results.map((r) => ({ k: r.model, v: '？', tag: '实测' }))));
        stage.invalidate();
        if (!seen.has(cur.rid)) {
          await g.ask(data.question || '先猜：照这样摞好纸条，两个模型各问十遍，会怎么答？', ['说出一个暗号', '说请求里没有', '两种都有']);
          if (token !== seq) return;
          seen.add(cur.rid);
          g.reveal('结果：' + cur.results.map((r) => `${r.model}${r.short} ${r.n}/${r.total}`).join('；') + '。猜的和量的并排放在这里，不判对错。');
        } else g.hide();
        // ten small blocks per model in front of the stack: one per run, coloured by how that run was judged
        cur.results.forEach((r, m) => {
          r.cells.forEach((c, j) => {
            const b = parts.block({ w: 0.36, h: 0.36, d: 0.36, fill: CELL_FILL[c] || 'note-bg', outline: 0.02 });
            const to = [-2.2 + j * 0.48, 0.18, (cur.notes.length / 2) * STEP_Z + 1.3 + m * 0.62];
            b.position.set(to[0], to[1] + 3, to[2]);
            cells.add(b);
            if (r.dots && r.dots[j]) {          // the record's dot mark on this run (the static grid draws the same dot; its meaning is in dot_legend)
              const d = parts.dot(0.08, 'fg');
              d.position.set(0, 0.24, 0);
              b.add(d);
            }
            parts.pickable(b, { tip: `${r.model} 第 ${j + 1} 遍：${(r.legend || {})[c] || c}` + (r.dots && r.dots[j] && r.dot_legend ? `（${r.dot_legend}）` : '') });
            items.push({ rid: r.rid, kind: 'run', model: r.model, run: j + 1, cls: c });
            stage.anim.tween({ from: to[1] + 3, to: to[1], ms: ctx.reduced ? 0 : 380, delay: ctx.reduced ? 0 : (m * 10 + j) * 45, curve: ease.land, step: (v) => { b.position.y = v; } });
          });
          cellLabels.push(stage.labels.add([-2.2 - 0.5, 0.2, (cur.notes.length / 2) * STEP_Z + 1.3 + m * 0.62], r.model, { align: 'right', cls: 'f3-l-muted' }));
        });
        readout.set([{ k: '这次请求里的纸条', v: cur.notes.length + ' 张', tag: '实测' }].concat(cur.results.map((r) => ({ k: r.model, v: `${r.short} ${r.n}/${r.total}`, tag: '实测' }))));
        stage.invalidate();
      }
      build(false);
      return {
        reset() { seen.clear(); prev = null; cur = data.variants[0]; pick.set(cur.rid); build(false); stage.resetView(); },
        select(rid) { cur = data.variants.find((v) => v.rid === rid); pick.set(rid); return build(true); },
        state: () => ({ rid: cur.rid, notes: cur.notes.length, runs: items.filter((x) => x.kind === 'run').length, dropping: stage.anim.busy }),
        items: () => items.slice(),
        options: () => data.variants.map((v) => v.rid),
      };
    }

    // ---------------------------------------------------------------- (b) window: pin the system note, keep the most recent, tear off the rest
    const notes = data.whole, cut = data.cut, n = notes.length, keep = data.keep;
    const torn = cut.filter((x) => x.state === 'torn').length;
    const STEPS = ['整摞', '钉住系统消息', `只选最近 ${keep} 条`, '更早的撕下来'];
    let step = 0, seq = 0;
    panel.appendChild(ui.h('p', 'f3-hint f3-legend', `程序手里存着整段对话；每次发请求，只把系统消息和最近 ${keep} 条装进去。用 ←/→ 一步一步看。`));
    const ch = ui.changed(panel);
    const g = ui.guess(panel);
    let play = 0, replaying = false;          // a replay stops when the reader steps by hand, resets or starts another replay
    const st = ui.stepper(ctx.below, { steps: () => STEPS, onGo: (i) => { if (!replaying) play++; go(i, true); }, onReplay: async () => {
      const me = ++play;
      for (let i = 0; i < STEPS.length; i++) { replaying = true; st.go(i); replaying = false; await stage.anim.wait(ctx.reduced ? 0 : 1400); if (me !== play) return; }
    } });
    const all = notes.map((x) => { const p = paper(x); return p; });
    // labels in one column at the right edge of the papers, so they never sit on each other (review dialogue, 2026-11-24)
    all.forEach((p, i) => { p.lab.set(`${notes[i].role_cn}${notes[i].stamp ? '（事先写好）' : ''} · ${short(notes[i].text, 13)}`); p.lab.offset = [PW / 2 + 0.25, 0.12, 0]; p.lab.align = 'left'; });
    const tornIdx = cut.map((x, i) => (x.state === 'torn' ? i : -1)).filter((i) => i >= 0);
    const olderLab = stage.labels.add([PW / 2 + 0.25, 0.2, tornIdx.reduce((a, i) => a + slot(i, n)[2], 0) / Math.max(1, tornIdx.length)], `更早的 ${torn} 张：这一次不寄（标签收起）`, { cls: 'f3-l-muted', align: 'left' });
    let fr = null;          // the window frame, redrawn around the kept notes at every step
    const FX = PW + 1.9;
    const folder = parts.block({ w: PW * 0.8, h: 0.3, d: 2.2, fill: 'note-bg' });
    folder.position.set(FX, 0.15, 0);
    world.add(folder);
    const folderLab = stage.labels.add(folder, `撕下的 ${torn} 张：${data.folder || '程序手里'}（这一次不寄）`, { offset: [0, 0.9, -1.5], cls: 'f3-l-muted' });          // above the folder, clear of the note labels
    const pin = parts.dot(0.16, 'red');
    world.add(pin);
    const pinLab = stage.labels.add(pin, '钉住：每次都寄', { offset: [0.3, 0.2, -0.6], cls: 'f3-l-strong', align: 'left' });
    const winLab = stage.labels.add([0, 0, 0], `窗口：最近 ${keep} 条`, { cls: 'f3-l-strong' });
    const zKeep = slot(n - keep, n)[2], zEnd = slot(n - 1, n)[2];
    const FRAMES = [          // what each step looks at; every paper stays in view (Antigravity review)
      { radius: 26, pitch: 1.02, yaw: 0.16, target: [2.4, 0.3, 0.3] },
      { radius: 28.5, pitch: 1.02, yaw: 0.14, target: [0.6, 0.3, 0.3] },
      { radius: 28.5, pitch: 1.0, yaw: 0.14, target: [0.6, 0.3, 0.6] },
      { radius: 25, pitch: 0.95, yaw: 0.12, target: [0.8, 0.3, (zKeep + zEnd) / 2 - 1.4] },
    ];
    stage.setHome(FRAMES[0]);

    function positions(s) {
      // where every note sits after step s
      const out = [];
      let k = 0;
      const rest = n - 1;
      notes.forEach((x, i) => {
        if (i === 0) { out.push(s >= 1 ? [-PW - 0.9, 0.04, slot(n - keep, n)[2]] : slot(0, n)); return; }          // the system note moves aside, next to where the window will be, and stays pinned
        const state = cut[i].state;
        if (s >= 3 && state === 'torn') { const t = k++; out.push([FX, 0.34 + t * 0.03, -0.25 + t * 0.06]); return; }          // a neat pile in the folder
        out.push(slot(i, n));
      });
      return out;
    }
    async function go(s, animate) {
      const token = ++seq;
      step = s;
      const pos = positions(s);
      stage.frame(FRAMES[s], animate ? 650 : 0);
      items = notes.map((x, i) => ({ rid: s >= 3 ? cut[i].rid : x.rid, kind: 'note', i, role: x.role, state: s >= 1 ? cut[i].state : 'kept' }));
      all.forEach((p, i) => {
        const inFolder = s >= 3 && cut[i].state === 'torn';
        moveTo(p.g, pos[i], animate ? 620 : 0, animate ? (i === 0 ? 0 : 25 * i) : 0);
        p.lab.show(!inFolder && !(s >= 2 && cut[i].state === 'torn'));          // once the window is chosen, only its notes keep their labels
        if (i === 0) {          // the system note: in the column while it is in the stack; aside, a short label just below it
          p.lab.offset = s >= 1 ? [0, 0.12, PD / 2 + 0.45] : [PW / 2 + 0.25, 0.12, 0];
          p.lab.align = s >= 1 ? 'center' : 'left';
          p.lab.set(s >= 1 ? `系统 · ${short(notes[0].text, 9)}` : `系统 · ${short(notes[0].text, 13)}`);
        }
        p.g.children.forEach((c, j) => { if (j > 0) c.visible = !inFolder; });          // in the pile only the paper colour shows, no outline per sheet
      });
      pin.visible = s >= 1;
      pin.position.set(pos[0][0] - PW / 2 + 0.3, pos[0][1] + 0.12, pos[0][2] - 0.25);
      pinLab.show(s >= 1);
      const keptIdx = cut.map((x, i) => (x.state === 'kept' ? i : -1)).filter((i) => i >= 0);
      const zs = keptIdx.map((i) => pos[i][2]);
      const z0 = Math.min(...zs) - PD / 2 - 0.03, z1 = Math.max(...zs) + PD / 2 + 0.2;          // the far edge sits right on the first kept note, so the strip of the note before it stays outside
      if (fr) { world.remove(fr); stage.disposeTree(fr); }
      fr = new stage.root.constructor();          // the window frame: four thin red strips (a 1-pixel line was too faint on the dark desk)
      const X0 = -PW / 2 - 0.3, X1 = PW / 2 + 0.3, T = 0.08;
      for (const [x, z, w, d] of [[0, z0, X1 - X0, T], [0, z1, X1 - X0, T], [X0, (z0 + z1) / 2, T, z1 - z0], [X1, (z0 + z1) / 2, T, z1 - z0]]) {
        const s = parts.block({ w, h: 0.02, d, fill: 'red', outline: 0, edges: false });
        s.position.set(x, 0.02, z);
        fr.add(s);
      }
      fr.visible = s >= 2;
      world.add(fr);
      winLab.anchor = [0, 0.3, z1 + 0.55];          // under the red frame, clear of the note labels
      winLab.align = 'center';
      winLab.show(s >= 2);
      olderLab.show(s === 2);
      folder.visible = s >= 3; folderLab.show(s >= 3);
      const tag = (data.caps[cut[0].rid] || {}).tag || '示意';
      readout.set([
        { k: '程序手里', v: `${n} 张`, tag },
        { k: '这次寄出', v: s >= 2 ? `${1 + keep} 张` : '…', tag },
        { k: '撕下来', v: s >= 3 ? `${torn} 张` : '…', tag },
      ]);
      ch.set(['程序手里存着的全部纸条，按先后摞着。', '系统消息单放、钉住：每次请求都带上它。', `只选最近 ${keep} 条：这一段装进这次的请求。`, `更早的 ${torn} 张撕下来放回程序手里：这一次不寄，但没有消失。`][s]);
      ctx.setCaption(s >= 1 ? cut[0].rid : notes[0].rid);
      if (s === 3 && askGuess) { g.reveal(`这一次寄出 ${1 + keep} 张：系统消息 1 张，加最近 ${keep} 条。`); askGuess = false; }
      stage.invalidate();
      if (token !== seq) return;
    }
    let askGuess = true;
    g.ask(`先猜：程序手里有 ${n} 张纸条，这一次请求会寄出几张？`, [`${n} 张`, `${keep} 张`, `${keep + 1} 张`]);
    go(0, false);
    return {
      reset() { play++; askGuess = true; g.ask(`先猜：程序手里有 ${n} 张纸条，这一次请求会寄出几张？`, [`${n} 张`, `${keep} 张`, `${keep + 1} 张`]); st.go(0); stage.resetView(); },
      step(d) { st.go(step + d); },
      go: (i) => st.go(i),
      state: () => ({ step, notes: n, keep, torn, dropping: stage.anim.busy }),
      items: () => items.slice(),
    };
  },
};
