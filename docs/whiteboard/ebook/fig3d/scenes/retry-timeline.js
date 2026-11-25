// 重试时间轴 (retry timeline): our script and the service on two rails; every send flies across and an answer comes back; the wait before the next
// send is a gap on the time axis, as long as the record's seconds. Step through it with ←/→. Data: fig3d_build.retry_timeline (sequence records).
import { ease } from '../core/anim.js';

const S = 1.0;          // one second of waiting = one unit along the axis (the record gives the seconds)
const W = 1.3;          // the width one request takes on the axis: a sketch (the record does not say how long a request took)
const ZS = 1.9, ZV = -1.9;

export default {
  name: 'retry-timeline',
  camera: { yaw: 0.16, pitch: 0.82, radius: 17, target: [0, 0, 0], fov: 30 },
  create(ctx) {
    const { stage, parts, ui, panel, data, readout } = ctx;
    const pol = data.policy;
    let sc = data.scenarios[0], step = 0, items = [], guessKey = null, toks = [];
    const world = new stage.root.constructor();
    stage.root.add(parts.floor(40, 16, 1));
    stage.root.add(world);

    const ctrl = ui.h('div', 'f3-controls');
    panel.appendChild(ui.h('p', 'f3-hint f3-legend', '前面（米色）一条是我们的脚本，后面（浅青）一条是对方。每发一次，一张请求飞过去、一张回信飞回来；回信之后的灰色空档是等待，长短按记录里的秒数画。'));
    panel.appendChild(ctrl);
    let pick = null;
    if (data.scenarios.length > 1) {
      pick = ui.choices(ctrl, { label: '场景（本机模拟）', value: sc.rid, options: data.scenarios.map((x) => ({ key: x.rid, text: x.title, sub: x.code })), onChange: (k) => { sc = data.scenarios.find((x) => x.rid === k); restart(); } });
    }
    if (pol) {
      ctrl.appendChild(ui.h('p', 'f3-hint', `我们脚本自己的规矩：最多发 ${pol.max_sends} 次；重发前等 ${pol.waits.join('、')} 秒；单次最多等 ${pol.max_single} 秒；总时间预算 ${pol.budget} 秒。`));
    }
    const g = ui.guess(panel);
    const ch = ui.changed(panel);
    const st = ui.stepper(ctx.below, { steps: () => labels(), onGo: (i) => go(i, true), onReplay: () => replay() });

    function labels() {
      let n = 0;
      return ['开始'].concat(sc.steps.map((x) => (x.kind === 'send' ? `第 ${++n} 次发送` : x.label)), ['结果']);
    }
    // x position where each step starts, and the total length
    function layout() {
      let x = 0;
      const at = sc.steps.map((s) => { const here = x; x += W + (s.kind === 'send' ? s.wait * S : 0); return here; });
      return { at, len: Math.max(x, 5) };          // a short scenario still gets a readable stretch of axis
    }

    function rails(len) {
      const L = len + 2.4;
      for (const [z, fill, name] of [[ZS, 'user', '我们的脚本'], [ZV, 'model', '对方（本机假服务）']]) {
        const r = parts.block({ w: L, h: 0.12, d: 1.1, fill, outline: 0.02 });
        r.position.set(L / 2 - 1.6, 0.06, z);
        world.add(r);
        stage.labels.add([-1.9, 0.2, z], name, { cls: 'f3-l-strong', align: 'right' });
      }
      const ax = parts.axis(len + 0.4, S);
      ax.position.set(0, 0.01, ZS + 0.9);
      world.add(ax);
      stage.labels.add([0, 0.05, ZS + 1.45], '时间 →（每格 1 秒）', { cls: 'f3-l-muted', align: 'left' });
      toks = [];
      if (pol) {          // the send allowance: one token per allowed send, used ones grey out
        for (let k = 0; k < pol.max_sends; k++) {
          const t = parts.cylinder(0.22, 0.12, 'surface');
          t.position.set(-0.9 - (pol.max_sends - 1 - k) * 0.55, 0.12, ZS + 0.95);
          toks.push(t);
          world.add(t);
          if (k === 0) stage.labels.add(t, `发送名额（最多 ${pol.max_sends} 次，发一次灰一个）`, { offset: [0, 0.2, 0.75], cls: 'f3-l-muted', align: 'left' });
          parts.pickable(t, { tip: `发送名额 ${k + 1} / ${pol.max_sends}（规矩：最多发 ${pol.max_sends} 次）` });
        }
      }
    }

    function placeStep(i, x, animate) {
      const s = sc.steps[i];
      const sendNo = sc.steps.slice(0, i + 1).filter((t) => t.kind === 'send').length;
      const isQ = s.kind === 'query';
      const req = parts.block({ w: 0.55, h: 0.22, d: 0.4, fill: isQ ? 'surface' : 'user' });
      const noReply = !isQ && !s.status;          // the record says no reply came back: no reply card, no return path (Codex review F13)
      const back = parts.block({ w: 0.55, h: 0.22, d: 0.4, fill: s.status && s.status.startsWith('2') ? 'model' : (s.status ? 'note-bg' : 'surface') });
      const path = parts.wire([[x + 0.15, 0.35, ZS], [x + 0.35, 1.1, 0], [x + 0.55, 0.35, ZV]], { key: 'fg-2' });
      const pathB = parts.wire([[x + 0.75, 0.35, ZV], [x + 0.95, 1.1, 0], [x + 1.15, 0.35, ZS]], { key: 'fg-2' });
      world.add(path, req);
      if (!noReply) world.add(pathB, back);
      parts.pickable(req, { tip: isQ ? `${s.label}（不是再发一次）` : `${s.label}：第 ${sendNo} 次发送` });
      const ans = isQ ? s.text : (s.status ? `状态码 ${s.status}` : '没有状态（没收到回信）');
      if (!noReply) parts.pickable(back, { tip: isQ ? s.text : `状态码 ${s.status}（记录里写作“${s.status_text}”）` });
      items.push({ rid: sc.rid, step: i, kind: s.kind, status: s.status, wait: s.wait || 0 });
      const lab = noReply ? stage.labels.add([x + 0.35, 1.35, 0], '没收到回信（没有状态）', { cls: 'f3-l-muted' })
        : stage.labels.add(back, ans, { cls: s.status && s.status.startsWith('2') ? 'f3-l-strong' : 'f3-l-count', offset: [0, 0.6, isQ ? -0.9 : 0] });
      let waitBar = null, waitLab = null;
      if (!isQ && s.wait > 0) {
        waitBar = parts.block({ w: s.wait * S, h: 0.06, d: 0.5, fill: 'line-strong', outline: 0.015 });
        waitBar.position.set(x + W + (s.wait * S) / 2, 0.16, ZS);
        world.add(waitBar);
        parts.pickable(waitBar, { tip: `等 ${s.wait} 秒再发（按记录）` });
        waitLab = stage.labels.add(waitBar, `等 ${s.wait} 秒`, { offset: [0, 0.35, 0.55] });
      }
      const c1 = path.userData.curve, c2 = pathB.userData.curve;
      const place = (t) => {
        const a = Math.min(1, t * 2), b = Math.max(0, t * 2 - 1);
        req.position.copy(c1.getPointAt(a));
        back.visible = t > 0.5 && !noReply;
        back.position.copy(c2.getPointAt(b));
        path.visible = true;
        pathB.visible = t > 0.5;
        lab.show(t >= 1);
        if (waitBar) { waitBar.visible = t >= 1; waitLab.show(t >= 1); }
      };
      if (!animate) { place(1); return Promise.resolve(); }
      place(0);
      return stage.anim.tween({ ms: 1300, curve: ease.inOut, step: place });
    }

    function tokens(used) {          // a used allowance token turns grey and sinks a little
      toks.forEach((t, k) => { stage.themedMaterial(t.userData.mesh.material, k < used ? 'line-strong' : 'surface'); t.position.y = k < used ? 0.07 : 0.12; });
      stage.invalidate();
    }

    function setRead(i) {
      const done = sc.steps.slice(0, Math.max(0, i));
      const sends = done.filter((x) => x.kind === 'send').length;
      const over = i > sc.steps.length;          // waits already over: those before the step on show (the wait after it is still ahead), all of them at the result
      const waited = (over ? done : done.slice(0, -1)).filter((x) => x.kind === 'send').reduce((a, x) => a + x.wait, 0);
      const last = i >= sc.steps.length + 1;
      const tag = (data.caps[sc.rid] || {}).tag || '示意';
      const rows = [
        { k: '发了', v: `${sends} 次` + (pol ? ` / 最多 ${pol.max_sends}` : ''), tag },
        { k: '已经等了', v: `${waited} 秒`, tag },
        { k: '结果', v: last ? sc.total.result : '…', tag },
      ];
      if (sc.total.orders !== null) rows.push({ k: '订单', v: last ? `${sc.total.orders} 张` : '…', tag });
      readout.set(rows);
      tokens(sends);
    }

    function describe(i) {
      if (i === 0) return '';
      if (i > sc.steps.length) return `结果：${sc.total.result}（发 ${sc.total.sends} 次，共等 ${sc.total.wait} 秒${sc.total.queries !== null ? `，查 ${sc.total.queries} 次，订单 ${sc.total.orders} 张` : ''}）。${sc.remark || ''}`;
      const s = sc.steps[i - 1];
      if (s.kind === 'query') return `${s.label}：${s.text}。`;
      const k = sc.steps.slice(0, i).filter((t) => t.kind === 'send').length;
      const got = s.status ? `对方回 ${s.status}` : '没收到回信（没有状态）';
      const next = s.wait > 0 ? `，等 ${s.wait} 秒再往下走` : (i === sc.steps.length ? '，不再等' : '');
      return `第 ${k} 次发送：${got}${next}。`;
    }

    let seq = 0;
    async function go(i, animate) {
      const token = ++seq;
      step = i;
      stage.clearGroup(world);
      stage.pickables.length = 0;
      stage.labels.clear();
      items = [];
      const { at, len } = layout();
      stage.setHome({ radius: Math.max(14, len * 1.05 + 9), target: [len / 2 - 0.8, 0, 0.2] });
      rails(len);
      const upto = Math.min(i, sc.steps.length);
      for (let k = 0; k < upto; k++) {
        const anim = animate && k === upto - 1 && i <= sc.steps.length;
        if (anim) setRead(k);
        await placeStep(k, at[k], anim);
        if (token !== seq) return;
      }
      setRead(i);
      ch.set(describe(i));
      if (i > sc.steps.length && guessKey === sc.rid) g.reveal(`记录：发了 ${sc.total.sends} 次（本机模拟）。猜的和记录并排放在这里，不判对错。`);
      if (i > sc.steps.length) guessKey = null;
      stage.invalidate();
    }

    async function replay() {
      for (let i = 0; i <= sc.steps.length + 1; i++) {
        const t = seq;
        st.go(i);
        await stage.anim.wait(ctx.reduced ? 0 : 1500);
        if (seq !== t + 1) return;
      }
    }

    function restart() {
      st.redraw();
      ctx.setCaption(data.policy ? [sc.rid, data.policy.rid] : sc.rid);
      guessKey = sc.rid;
      g.ask(`先猜：这一回我们一共会发几次？`, ['1 次', '2 次', '3 次', '4 次']).then(() => {});
      go(0, false);
    }
    restart();
    return {
      reset() { sc = data.scenarios[0]; if (pick) pick.set(sc.rid); restart(); stage.resetView(); },
      step(d) { st.go(step + d); },
      go: (i) => st.go(i),
      select(rid) { sc = data.scenarios.find((x) => x.rid === rid); if (pick) pick.set(rid); restart(); },
      state: () => ({ rid: sc.rid, step, steps: sc.steps.length + 2, sends: items.filter((x) => x.kind === 'send').length, waited: items.reduce((a, x) => a + (x.kind === 'send' ? x.wait : 0), 0), total: sc.total, dropping: stage.anim.busy }),
      items: () => items.slice(),
      options: () => data.scenarios.map((x) => x.rid),
    };
  },
};
