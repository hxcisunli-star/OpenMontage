// 答案塔 (answer tower): the same question asked n times; every run is one block, the same answer stacks into one tower.
// Fewer towers = more consistent answers. Data: build-time adapter fig3d_data.answer_tower (records of kind towers or rows).
import { ANSWER_HUES } from '../core/theme.js';
import { ease } from '../core/anim.js';

const BW = 1.0, BH = 0.42, GAP = 0.6;

export default {
  name: 'answer-tower',
  camera: { yaw: 0.38, pitch: 0.5, radius: 17, target: [0, 1.4, 0], fov: 28 },
  create(ctx) {
    const { stage, parts, ui, panel, data, readout } = ctx;
    const sets = data.sets;
    const qs = [...new Map(sets.map((s) => [s.qkey, s.q])).entries()];
    let cur = { qkey: qs[0][0], model: null, variant: null };
    const seen = new Set();          // combinations already guessed and dropped
    let items = [], dropping = false, last = null, seq = 0;

    stage.root.add(parts.floor(26, 12, 1));
    const world = new stage.root.constructor();
    stage.root.add(world);

    const ctrl = ui.h('div', 'f3-controls');
    panel.appendChild(ctrl);
    const qChoice = qs.length > 1 ? ui.choices(ctrl, { label: '问题', options: qs.map(([k, q]) => ({ key: k, text: q })), value: cur.qkey, onChange: (k) => { cur.qkey = k; cur.model = null; cur.variant = null; build(); } }) : null;
    const modelBox = ui.h('div');
    const varBox = ui.h('div');
    ctrl.append(modelBox, varBox);
    const g = ui.guess(panel);
    const ch = ui.changed(panel);
    ch.set('');
    const hint = ui.h('p', 'f3-hint f3-legend', '每块积木是一遍回答；一模一样的回答垒成同一座塔。塔越少，回答越一致。');
    panel.insertBefore(hint, ctrl);
    const answers = ui.h('ol', 'f3-answers');
    answers.hidden = true;
    answers.setAttribute('aria-label', '各种回答的原话');
    panel.insertBefore(answers, g.el);

    const setFor = () => sets.find((s) => s.qkey === cur.qkey && s.model === cur.model);
    const variantFor = (s) => s.variants.find((v) => v.key === cur.variant) || s.variants[0];

    function drawSelectors() {
      const refocus = modelBox.contains(document.activeElement) ? modelBox : varBox.contains(document.activeElement) ? varBox : null;          // arrow keys keep working after the rows are rebuilt
      const models = sets.filter((s) => s.qkey === cur.qkey);
      if (!models.some((s) => s.model === cur.model)) cur.model = models[0].model;
      modelBox.replaceChildren();
      if (models.length > 1) ui.choices(modelBox, { label: '模型', options: models.map((s) => ({ key: s.model, text: s.mlabel, sub: s.mname })), value: cur.model, onChange: (k) => { cur.model = k; cur.variant = null; build(); } });
      const s = setFor();
      if (!s.variants.some((v) => v.key === cur.variant)) cur.variant = s.variants[0].key;
      varBox.replaceChildren();
      if (s.variants.length > 1) {
        ui.choices(varBox, {
          label: s.vlabel || '档位', value: cur.variant,
          options: s.variants.map((v) => ({ key: v.key, text: v.label, preview: v.preview })),
          onChange: (k) => { cur.variant = k; build(); },
        });
      }
      if (refocus) { const on = refocus.querySelector('.f3-chip.on'); if (on) on.focus(); }
    }

    async function build(skipGuess) {
      const token = ++seq;          // a newer build (another choice, replay, reset) makes this one stop at its next step
      dropping = false;
      drawSelectors();
      const s = setFor(), v = variantFor(s);
      const key = s.rid + '|' + v.key;
      ctx.setCaption(s.rid);
      stage.anim.cancelAll();
      stage.clearGroup(world);
      stage.pickables.length = 0;
      stage.labels.clear();
      items = [];
      const k = v.groups.length;
      const width = k * BW + (k - 1) * GAP;
      stage.setHome({ radius: Math.max(15, width * 1.25 + 7), target: [0, 1.2 + Math.min(4, Math.max(...v.groups.map((x) => x.count))) * BH * 0.35, 0] });
      const x0 = -width / 2 + BW / 2;
      const heights = v.groups.map(() => 0);
      const towers = v.groups.map((grp, i) => {
        const x = x0 + i * (BW + GAP);
        const sh = parts.shadow(BW * 1.9, BW * 1.9, 0.28);
        sh.position.x = x;
        world.add(sh);
        const base = stage.labels.add([x, -0.05, BW * 0.95], grp.short || grp.text, { cls: 'f3-l-base' });
        base.show(false);          // the answer shows when its first block lands, so the labels do not give the guess away
        const top = stage.labels.add([x, grp.count * BH + 0.45, 0], '×' + grp.count, { cls: 'f3-l-count' });
        top.show(false);
        return { x, base, top };
      });
      readout.set([
        { k: '问了', v: s.n + ' 遍', tag: '实测' },
        { k: '不同的回答', v: '？', tag: '实测' },
        { k: '最高的塔', v: '？', tag: '实测' },
      ]);
      answers.replaceChildren();
      answers.hidden = true;
      if (last && last.rid === s.rid && last.vkey !== v.key) ch.set(`${last.vlabel} → ${v.label}：塔从 ${last.k} 座变成 ${k} 座`);
      else if (last && last.rid !== s.rid) ch.set(`换成「${s.q}」· ${s.mlabel}：${k} 座塔`);
      else ch.set('');
      last = { rid: s.rid, vkey: v.key, vlabel: v.label, k };
      stage.invalidate();
      if (!seen.has(key) && !skipGuess) {
        const pick = await g.ask(`先猜：同一个问题问 ${s.n} 遍，会有几种不同的回答？`, ['1 种', '2–3 种', '4–6 种', '7–10 种']);
        if (token !== seq) return;          // the reader switched while the guess was open
        seen.add(key);
        g.reveal(`实测：${k} 种（${s.n} 遍）。` + (pick ? '猜的和量的并排放在这里，不判对错。' : ''));
      } else {
        g.hide();
      }
      dropping = true;
      for (let r = 0; r < v.runs.length; r++) {
        if (token !== seq) return;
        const gi = v.runs[r], t = towers[gi], level = heights[gi]++;
        const b = parts.block({ w: BW, h: BH * 0.92, d: BW, fill: ANSWER_HUES[gi % ANSWER_HUES.length] });
        const y = level * BH + BH / 2;
        b.position.set(t.x, y + 7, 0);
        world.add(b);
        const run = r + 1;
        parts.pickable(b, { tip: v.order === 'shice' ? `第 ${run} 遍 · 第 ${gi + 1} 种回答` : `“${v.groups[gi].text}” · 这种回答共 ${v.groups[gi].count} 遍` });
        items.push({ rid: s.rid, variant: v.key, group: gi, run: v.order === 'shice' ? run : null, level });
        const done = level + 1 === v.groups[gi].count;
        stage.anim.tween({ from: y + 7, to: y, ms: 420, curve: ease.land, step: (val) => { b.position.y = val; }, done: () => { t.base.show(true); if (done) t.top.show(true); } });
        stage.invalidate();
        readout.set([
          { k: '问了', v: s.n + ' 遍', tag: '实测' },
          { k: '不同的回答', v: (new Set(v.runs.slice(0, r + 1))).size + (r + 1 < v.runs.length ? ' 种…' : ' 种'), tag: '实测' },
          { k: '最高的塔', v: Math.max(...heights) + ' 块', tag: '实测' },
        ]);
        await stage.anim.wait(ctx.reduced ? 0 : 150);
      }
      if (token === seq) {
        dropping = false;
        if (v.order === 'shiyi') {          // the answers word for word, as in the static figure (records of kind towers carry them)
          v.groups.forEach((grp, gi) => {
            const li = ui.h('li');
            const sw = ui.h('i', 'f3-swatch');
            sw.style.background = ANSWER_HUES[gi % ANSWER_HUES.length];
            li.append(sw, ui.h('b', '', `×${grp.count}`), document.createTextNode(' ' + grp.text));
            answers.appendChild(li);
          });
          answers.hidden = false;
        }
      }
    }

    build();
    return {
      reset() { seen.clear(); last = null; if (qChoice) qChoice.set(qs[0][0]); cur = { qkey: qs[0][0], model: null, variant: null }; build(); stage.resetView(); },
      replay() { build(true); },
      state() {
        const s = setFor(), v = variantFor(s);
        return { rid: s.rid, q: s.q, model: s.model, variant: v.key, towers: v.groups.length, blocks: items.length, n: s.n, dropping: !!dropping, counts: v.groups.map((x) => x.count) };
      },
      items: () => items.slice(),
      select(what, key) { cur[what] = key; if (what === 'qkey') { cur.model = null; cur.variant = null; if (qChoice) qChoice.set(key); } if (what === 'model') cur.variant = null; return build(); },
      options: () => ({ q: qs.map((x) => x[0]), models: sets.filter((s) => s.qkey === cur.qkey).map((s) => s.model), variants: setFor().variants.map((v) => v.key) }),
    };
  },
};
