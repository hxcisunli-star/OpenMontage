// 词元积木 (token blocks): the receipt of one request laid out as blocks - the fixed wrapper every request carries, and the content.
// The total is measured (the receipt); how it splits is worked out from the chapter's premise that one letter "a" is one token.
import { ease } from '../core/anim.js';

const B = 0.62, GAP = 0.14, PER_ROW = 7;

export default {
  name: 'token-blocks',
  camera: { yaw: 0.45, pitch: 0.78, radius: 15, target: [0, 0.2, 0.3], fov: 30 },
  create(ctx) {
    const { stage, parts, ui, panel, data, readout } = ctx;
    stage.root.add(parts.floor(24, 14, 1));
    const world = new stage.root.constructor();
    stage.root.add(world);
    let m = data.models[0], it = m.items.find((x) => x.text !== data.unit_text) || m.items[0], items = [], seq = 0, last = null;
    const seen = new Set();
    panel.appendChild(ui.h('p', 'f3-hint f3-legend', '小票上的一个数，摆成一块块积木：灰的是每次请求都带的“包装”，彩色的是你发的内容。'));
    const ctrl = ui.h('div', 'f3-controls');
    panel.appendChild(ctrl);
    const texts = [...new Set(data.models.flatMap((x) => x.items.map((y) => y.text)))];
    const cText = ui.choices(ctrl, { label: '发出去的话', value: it.text, options: texts.map((t) => ({ key: t, text: `“${t}”` })), onChange: (k) => { it = m.items.find((x) => x.text === k); build(true); } });
    const cModel = data.models.length > 1 && ui.choices(ctrl, { label: '模型', value: m.model, options: data.models.map((x) => ({ key: x.model, text: x.mlabel, sub: x.mname })), onChange: (k) => { const t = it.text; m = data.models.find((x) => x.model === k); it = m.items.find((x) => x.text === t); build(true); } });
    const g = ui.guess(panel);
    const ch = ui.changed(panel);

    async function build(animate) {
      const token = ++seq;
      stage.clearGroup(world);
      stage.pickables.length = 0;
      stage.labels.clear();
      items = [];
      ctx.setCaption(it.rid);          // the receipt being shown (Antigravity review: two identical caption lines read as a repeat)
      const total = it.tokens, rows = Math.ceil(total / PER_ROW);
      const plateW = PER_ROW * (B + GAP) + 0.6, plateD = rows * (B + GAP) + 1.0;
      const plate = parts.paper({ w: plateW, d: plateD, h: 0.05, fill: 'surface' });
      plate.position.set(0, 0.025, 0);
      world.add(plate);
      parts.pickable(plate, { tip: `小票：prompt_tokens = ${total}（${it.runs} 遍都是 ${total}）` });
      stage.labels.add([0, 0.1, plateD / 2 + 0.95], `小票：prompt_tokens ＝ ${total}`, { cls: 'f3-l-strong' });
      stage.setHome({ radius: Math.max(13, plateW * 1.45 + 4), target: [0, 0.2, 0.2] });
      readout.set([{ k: '小票上的数', v: '？', tag: '实测' }, { k: '包装', v: '？', tag: '示意' }, { k: '内容', v: '？', tag: '示意' }]);
      if (last && last.m === m.model && last.t !== it.text) ch.set(`“${last.t}” → “${it.text}”：小票上的数 ${last.n} → ${total}；包装 ${it.wrapper} 块没变，变的只有内容那 ${it.content} 块`);
      else if (last && last.m !== m.model) ch.set(`换一个模型：包装从 ${last.w} 块变成 ${it.wrapper} 块（各家给每次请求加的不一样多）`);
      else ch.set('');
      last = { m: m.model, t: it.text, n: total, w: it.wrapper };
      stage.invalidate();
      const key = m.model + '|' + it.text;
      if (!seen.has(key)) {
        await g.ask(`先猜：发“${it.text}”（${it.chars} 个字符），小票上写几个词元？`, ['1 个', '2 个', '5 个', '13 个']);
        if (token !== seq) return;
        seen.add(key);
        g.reveal(`小票上是 ${total}（${m.mlabel}，${it.runs} 遍都一样）。猜的和量的并排放在这里，不判对错。`);
      } else g.hide();
      for (let k = 0; k < total; k++) {
        if (token !== seq) return;
        const isWrap = k < it.wrapper;
        const b = parts.block({ w: B, h: B * 0.7, d: B, fill: isWrap ? 'line-strong' : 'model' });
        const r = Math.floor(k / PER_ROW), c = k % PER_ROW;
        const to = [-(PER_ROW - 1) * (B + GAP) / 2 + c * (B + GAP), 0.05 + B * 0.35, -(rows - 1) * (B + GAP) / 2 + r * (B + GAP)];
        b.position.set(to[0], to[1] + 4, to[2]);
        world.add(b);
        parts.pickable(b, { tip: isWrap ? `包装第 ${k + 1} 块（推算：每次请求都带）` : `内容：“${it.text}”（推算：总数减包装）` });
        items.push({ rid: it.rid, kind: isWrap ? 'wrapper' : 'content', index: k });
        if (!isWrap) stage.labels.add(b, `“${it.text}”`, { offset: [0, 0.95, 0], cls: 'f3-l-strong' });
        stage.anim.tween({ from: to[1] + 4, to: to[1], ms: 380, curve: ease.land, step: (v) => { b.position.y = v; } });
        stage.invalidate();
        readout.set([{ k: '小票上的数', v: String(k + 1 < total ? k + 1 + '…' : total), tag: '实测' }, { k: '包装', v: `${Math.min(k + 1, it.wrapper)} 块`, tag: '示意' }, { k: '内容', v: `${Math.max(0, k + 1 - it.wrapper)} 块`, tag: '示意' }]);
        await stage.anim.wait(animate && !ctx.reduced ? 110 : 0);
      }
      stage.labels.add([-(PER_ROW - 1) * (B + GAP) / 2 - 0.7, 0.3, -(rows - 1) * (B + GAP) / 2], `包装 ${it.wrapper} 块`, { align: 'right', cls: 'f3-l-muted' });
    }
    build(false);
    return {
      reset() { seen.clear(); last = null; m = data.models[0]; it = m.items.find((x) => x.text !== data.unit_text) || m.items[0]; cText.set(it.text); if (cModel) cModel.set(m.model); build(false); stage.resetView(); },
      select(model, text) { m = data.models.find((x) => x.model === model) || m; it = m.items.find((x) => x.text === text) || it; cText.set(it.text); if (cModel) cModel.set(m.model); return build(true); },
      state: () => ({ rid: it.rid, total: it.tokens, blocks: items.length, wrapper: it.wrapper, content: it.content, dropping: stage.anim.busy }),
      items: () => items.slice(),
      options: () => data.models.flatMap((x) => x.items.map((y) => [x.model, y.text])),
    };
  },
};
