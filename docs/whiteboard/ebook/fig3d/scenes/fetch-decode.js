// 取指·译码·执行 (demo, computer organisation): a toy machine with memory, PC, IR, a control unit, registers and an ALU on one bus.
// Step through a three-instruction program; every step lights the path the data takes and says what changed. A teaching model: 示意.
import { ease } from '../core/anim.js';

export default {
  name: 'fetch-decode',
  camera: { yaw: 0.24, pitch: 0.88, radius: 26, target: [-0.4, 0.4, 0.9], fov: 30, viewHeight: 520 },
  create(ctx) {
    const { stage, parts, ui, panel, data, readout } = ctx;
    stage.root.add(parts.floor(26, 16, 1));
    const world = new stage.root.constructor();
    stage.root.add(world);
    const prog = data.program;          // [{addr, text, op, a, b}] plus data words
    const box = (x, z, w, d, fill, name) => {
      const b = parts.block({ w, h: 0.5, d, fill });
      b.position.set(x, 0.25, z);
      world.add(b);
      const lab = stage.labels.add(b, name, { offset: [0, 0.55, 0] });
      parts.pickable(b, { tip: name });
      return { b, lab };
    };
    // memory: one cell per word, front row
    const mem = data.memory.map((m, i) => {
      const c = box(-7 + i * 2.5, 3.4, 2.1, 1.1, 'surface', '');
      c.lab.set(`${m.addr}：${m.text}`);
      c.lab.el.classList.add('f3-l-count');
      c.lab.offset = [0, 0.55, i % 2 ? 0.95 : -0.2];          // alternate rows, so neighbouring cells do not cover each other
      return c;
    });
    stage.labels.add([-8.4, 0.2, 3.4], '内存', { align: 'right', cls: 'f3-l-strong' });
    const pc = box(-5.2, -1.2, 2.2, 1.2, 'l4-system', 'PC');
    const ir = box(-2.2, -1.2, 3.0, 1.2, 'l4-system', 'IR');
    const cu = box(1.4, -1.6, 2.4, 1.6, 'model', '控制器');
    const r1 = box(4.6, -2.2, 1.6, 1.0, 'user', 'R1');
    const r2 = box(4.6, -0.8, 1.6, 1.0, 'user', 'R2');
    const alu = box(7.4, -1.5, 1.8, 1.8, 'model', 'ALU');
    const bus = parts.wire([[-8.2, 0.08, 1.4], [8.6, 0.08, 1.4]], { key: 'fg-2', dots: 8, dotKey: 'accent', dotSize: 0.13 });
    world.add(bus);
    for (const [x, z] of [[-5.2, -0.6], [-2.2, -0.6], [1.4, -0.8], [4.6, -0.3], [7.4, -0.6], ...data.memory.map((m, i) => [-7 + i * 2.5, 2.85])]) world.add(parts.wire([[x, 0.08, z], [x, 0.08, 1.4]], { key: 'line-strong' }));          // every part hangs on the bus
    stage.labels.add([8.9, 0.2, 1.4], '总线', { align: 'left', cls: 'f3-l-muted' });
    const parts_ = { pc, ir, cu, r1, r2, alu };
    const STEPS = ['开始'].concat(data.steps.map((s) => s.title));
    let step = 0, flowPhase = 0;
    panel.appendChild(ui.h('p', 'f3-hint f3-legend', '一台玩具计算机：内存、程序计数器 PC、指令寄存器 IR、控制器、寄存器 R1 R2、算术逻辑单元 ALU，都挂在一条总线上。一步一步看一条指令怎么被取出来、读懂、做完。'));
    const ch = ui.changed(panel);
    let play = 0, replaying = false;          // a replay stops when the reader steps by hand, resets or starts another replay
    const st = ui.stepper(ctx.below, { steps: () => STEPS, onGo: (i) => { if (!replaying) play++; go(i, true); }, onReplay: async () => {
      const me = ++play;
      for (let i = 0; i < STEPS.length; i++) { replaying = true; st.go(i); replaying = false; await stage.anim.wait(ctx.reduced ? 0 : 1500); if (me !== play) return; }
    } });
    ctx.setCaption(data.rid);

    function stateAt(i) {          // the machine state after step i (computed from the program; the data says what each step does)
      return i === 0 ? data.start : data.steps[i - 1].after;
    }
    function lightAll(on) {
      for (const k in parts_) parts_[k].b.setFill(k === 'pc' || k === 'ir' ? 'l4-system' : (k === 'r1' || k === 'r2') ? 'user' : 'model');
      mem.forEach((m) => m.b.setFill('surface'));
      for (const k of on) { if (k.startsWith('mem')) mem[+k.slice(3)].b.setFill('hl'); else parts_[k].b.setFill('hl'); }
    }
    async function go(i, animate) {
      step = i;
      const s = stateAt(i);
      pc.lab.set(`PC ＝ ${s.pc}`);
      ir.lab.set(`IR：${s.ir || '（空）'}`);
      r1.lab.set(`R1 ＝ ${s.r1}`);
      r2.lab.set(`R2 ＝ ${s.r2}`);
      mem.forEach((m, k) => m.lab.set(`${data.memory[k].addr}：${s.mem[k]}`));
      const info = i === 0 ? null : data.steps[i - 1];
      lightAll(info ? info.lit : []);
      readout.set([{ k: 'PC', v: s.pc, tag: '示意' }, { k: 'IR', v: s.ir || '—', tag: '示意' }, { k: 'R1', v: s.r1, tag: '示意' }, { k: 'R2', v: s.r2, tag: '示意' }]);
      ch.set(info ? info.changed : '程序放在内存里，PC 指着第一条指令。按 → 开始。');
      if (animate && info && info.bus) {
        await stage.anim.tween({ ms: ctx.reduced ? 0 : 900, curve: ease.inOut, step: (k) => { flowPhase = (flowPhase + 0.02) % 1; bus.setFlow(flowPhase); } });
      }
      stage.invalidate();
    }
    go(0, false);
    return {
      reset() { play++; st.go(0); stage.resetView(); },
      step(d) { st.go(step + d); },
      go: (i) => st.go(i),
      state: () => ({ step, steps: STEPS.length, machine: stateAt(step), dropping: stage.anim.busy }),
      items: () => [{ rid: data.rid, kind: 'machine' }],
    };
  },
};
