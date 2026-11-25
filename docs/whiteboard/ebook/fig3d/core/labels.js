// Chinese labels are DOM text laid over the canvas: sharp at any size, selectable, and read by screen readers (the canvas itself is aria-hidden).
import { Vector3 } from 'three';

export class Labels {
  constructor(host) {
    this.layer = document.createElement('div');
    this.layer.className = 'f3-labels';
    host.appendChild(this.layer);
    this.items = new Set();
    this._v = new Vector3();
  }
  // anchor: an Object3D (its world position, plus offset) or a fixed [x, y, z]
  add(anchor, text, opts = {}) {
    const el = document.createElement('div');
    el.className = 'f3-label' + (opts.cls ? ' ' + opts.cls : '');
    el.textContent = text;
    this.layer.appendChild(el);
    const item = {
      el, anchor, offset: opts.offset || [0, 0, 0], align: opts.align || 'center', shown: true,
      set: (t) => { el.textContent = t; },
      show: (v) => { item.shown = v; el.hidden = !v; },
      remove: () => { el.remove(); this.items.delete(item); },
    };
    this.items.add(item);
    return item;
  }
  update(camera, w, h) {
    const v = this._v;
    for (const it of this.items) {
      if (!it.shown) continue;
      if (Array.isArray(it.anchor)) v.set(...it.anchor);
      else { it.anchor.updateWorldMatrix(true, false); v.setFromMatrixPosition(it.anchor.matrixWorld); }
      v.x += it.offset[0]; v.y += it.offset[1]; v.z += it.offset[2];
      v.project(camera);
      const behind = v.z > 1;
      const x = (v.x * 0.5 + 0.5) * w, y = (-v.y * 0.5 + 0.5) * h;
      const tx = it.align === 'left' ? '0%' : it.align === 'right' ? '-100%' : '-50%';
      it.el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(${tx}, -50%)`;
      it.el.style.visibility = behind ? 'hidden' : '';
    }
  }
  clear() {
    for (const it of [...this.items]) it.remove();
  }
}
