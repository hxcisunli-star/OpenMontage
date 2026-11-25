// The stage of one 3D figure: renderer, camera with a limited orbit, lights, picking, labels.
// It renders on demand (a frame only when something changed or a tween runs) and not at all while the figure is off screen.
import {
  WebGLRenderer, Scene, PerspectiveCamera, HemisphereLight, DirectionalLight, Vector3, Vector2, Raycaster, Group, Plane,
} from 'three';
import { Animator } from './anim.js';
import { readTheme, onThemeChange, color } from './theme.js';
import { Labels } from './labels.js';

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

export class Stage {
  constructor(host, opts = {}) {
    this.host = host;
    this.opts = opts;
    this.canvas = document.createElement('canvas');
    this.canvas.className = 'f3-canvas';
    this.canvas.setAttribute('aria-hidden', 'true');
    host.appendChild(this.canvas);
    this.renderer = new WebGLRenderer({ canvas: this.canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.scene = new Scene();
    this.root = new Group();
    this.scene.add(this.root);
    this.camera = new PerspectiveCamera(opts.fov || 28, 1.6, 0.1, 400);
    this.hemi = new HemisphereLight(0xffffff, 0x808080, 2.2);
    this.sun = new DirectionalLight(0xffffff, 1.5);
    this.sun.position.set(-6, 12, 8);
    this.scene.add(this.hemi, this.sun);
    const home = { yaw: opts.yaw ?? 0.55, pitch: opts.pitch ?? 0.6, radius: opts.radius ?? 16, target: (opts.target || [0, 1, 0]).slice() };
    this.home = home;
    this.view = { yaw: home.yaw, pitch: home.pitch, radius: home.radius, target: new Vector3(...home.target) };
    this.limits = { yaw: opts.yawRange ?? 0.7, pitchMin: opts.pitchMin ?? 0.18, pitchMax: opts.pitchMax ?? 1.25, zoomMin: 0.6, zoomMax: 1.5 };
    this.anim = new Animator();
    this.labels = new Labels(host);
    this.theme = readTheme();
    this.themed = new Set();          // materials coloured from a theme variable: material.userData.colorKey
    this.pickables = [];
    this.visible = true;
    this.frames = 0;
    this.frameTimes = [];
    this._raf = 0;
    this._frame = this._frame.bind(this);
    this._unTheme = onThemeChange(() => this.applyTheme());
    this._ro = new ResizeObserver(() => this.resize());
    this._ro.observe(host);
    this._io = new IntersectionObserver((es) => {
      const v = es.some((e) => e.isIntersecting);
      if (v && !this.visible && this._pausedAt) this.anim.shift(performance.now() - this._pausedAt);
      if (!v) this._pausedAt = performance.now();
      this.visible = v;
      if (v) this.invalidate();
    });
    this._io.observe(host);
    this._bindPointer();
    this.tip = document.createElement('div');
    this.tip.className = 'f3-tip';
    this.tip.hidden = true;
    host.appendChild(this.tip);
    this.resize();
  }

  // ---- theme
  themedMaterial(mat, key) {
    mat.userData.colorKey = key;
    mat.color.copy(color(this.theme[key]));
    this.themed.add(mat);
    return mat;
  }
  applyTheme() {
    this.theme = readTheme();
    for (const m of this.themed) m.color.copy(color(this.theme[m.userData.colorKey]));
    this.hemi.groundColor.copy(color(this.theme.dark ? '#30343c' : '#9a958a'));
    this.hemi.intensity = this.theme.dark ? 1.7 : 2.2;
    if (this.onTheme) this.onTheme(this.theme);
    this.invalidate();
  }

  // ---- camera
  updateCamera() {
    const v = this.view;
    const r = v.radius;
    this.camera.position.set(
      v.target.x + r * Math.cos(v.pitch) * Math.sin(v.yaw),
      v.target.y + r * Math.sin(v.pitch),
      v.target.z + r * Math.cos(v.pitch) * Math.cos(v.yaw));
    this.camera.lookAt(v.target);
  }
  zoom(f) {
    this.view.radius = clamp(this.view.radius * f, this.home.radius * this.limits.zoomMin, this.home.radius * this.limits.zoomMax);
    this.invalidate();
  }
  resetView() {
    const h = this.home, v = this.view, from = { yaw: v.yaw, pitch: v.pitch, radius: v.radius };
    this.anim.tween({ ms: 450, step: (k) => {
      v.yaw = from.yaw + (h.yaw - from.yaw) * k; v.pitch = from.pitch + (h.pitch - from.pitch) * k; v.radius = from.radius + (h.radius - from.radius) * k;
    } });
    this.invalidate();
  }
  // move the camera to a new framing (and make it the one 回正 returns to); a step of a scene can look at what it is about
  frame(p, ms = 650) {
    const v = this.view, from = { yaw: v.yaw, pitch: v.pitch, radius: v.radius, t: v.target.toArray() };
    Object.assign(this.home, p);
    const to = { yaw: p.yaw ?? from.yaw, pitch: p.pitch ?? from.pitch, radius: p.radius ?? from.radius, t: p.target || from.t };
    this.anim.tween({ ms, step: (k) => {
      v.yaw = from.yaw + (to.yaw - from.yaw) * k; v.pitch = from.pitch + (to.pitch - from.pitch) * k; v.radius = from.radius + (to.radius - from.radius) * k;
      v.target.set(...from.t.map((x, i) => x + (to.t[i] - x) * k));
    } });
    this.invalidate();
  }
  setHome(p) {
    Object.assign(this.home, p);
    if (p.target) this.view.target.set(...p.target);
    if (p.radius !== undefined) this.view.radius = p.radius;
    this.invalidate();
  }

  resize() {
    const w = Math.max(1, this.host.clientWidth), h = Math.max(1, this.host.clientHeight);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.invalidate();
  }

  // ---- loop
  invalidate() {
    if (!this._raf && !this.disposed) this._raf = requestAnimationFrame(this._frame);
  }
  _frame(now) {
    this._raf = 0;
    if (!this.visible || this.disposed) return;
    this.anim.tick(now);
    this.renderNow();
    if (this.anim.busy) {
      if (this._last) this.frameTimes.push(now - this._last);
      if (this.frameTimes.length > 600) this.frameTimes.shift();
      this._last = now;
      this.invalidate();
    } else {
      this._last = 0;
    }
  }
  renderNow() {
    this.updateCamera();
    this.renderer.render(this.scene, this.camera);
    this.labels.update(this.camera, this.host.clientWidth, this.host.clientHeight);
    this.frames++;
  }
  // test hook: draw and read the pixels in the same task (a later read of the default drawing buffer returns blank)
  probePixels() {
    this.renderNow();
    const gl = this.renderer.getContext();
    const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
    const px = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
    // drawn: pixels with any colour; varied: pixels that differ from the most common colour (the desk), so a bare desk is not counted as a figure
    let drawn = 0, sampled = 0;
    const bins = new Map();
    for (let i = 0; i < px.length; i += 4 * 7) {
      sampled++;
      if (px[i + 3] === 0) continue;
      drawn++;
      const k = (px[i] >> 4) << 8 | (px[i + 1] >> 4) << 4 | (px[i + 2] >> 4);
      bins.set(k, (bins.get(k) || 0) + 1);
    }
    const counts = [...bins.values()].sort((a, b) => b - a);
    return { w, h, sampled, drawn, varied: drawn - (counts[0] || 0), colors: counts.filter((c) => c >= sampled * 0.002).length };
  }
  fps() {
    const t = this.frameTimes.filter((x) => x > 0 && x < 1000);
    if (t.length < 5) return null;
    const avg = t.reduce((a, b) => a + b, 0) / t.length;
    return Math.round(1000 / avg);
  }

  // ---- pointer: drag to turn (inside limits), hover for a tip, click, drag along a constraint
  _bindPointer() {
    const c = this.canvas, ray = new Raycaster(), ndc = new Vector2();
    let drag = null;
    const pick = (e) => {
      const r = c.getBoundingClientRect();
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, this.camera);
      const hit = ray.intersectObjects(this.pickables.filter((o) => o.visible !== false), false)[0];
      return hit ? hit.object : null;
    };
    c.addEventListener('pointerdown', (e) => {
      const wrap = this.host.closest && this.host.closest('.f3-wrap');
      if (wrap) wrap.focus({ preventScroll: true });          // so ←/→ step the figure after a click on the picture
      const o = pick(e);
      if (o && o.userData.drag) {
        const d = o.userData.drag;
        drag = { kind: 'constraint', obj: o, d, plane: new Plane(new Vector3(0, 1, 0), -(d.y ?? 0)) };
      } else {
        drag = { kind: 'orbit', x: e.clientX, y: e.clientY, yaw: this.view.yaw, pitch: this.view.pitch, moved: false, obj: o };
      }
      c.setPointerCapture(e.pointerId);
    });
    c.addEventListener('pointermove', (e) => {
      if (drag && drag.kind === 'orbit') {
        const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
        this.view.yaw = clamp(drag.yaw - dx * 0.006, this.home.yaw - this.limits.yaw, this.home.yaw + this.limits.yaw);
        this.view.pitch = clamp(drag.pitch + dy * 0.005, this.limits.pitchMin, this.limits.pitchMax);
        this.tip.hidden = true;
        this.invalidate();
        return;
      }
      if (drag && drag.kind === 'constraint') {
        const r = c.getBoundingClientRect();
        ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
        ray.setFromCamera(ndc, this.camera);
        const p = new Vector3();
        if (ray.ray.intersectPlane(drag.plane, p)) {
          const d = drag.d, v = clamp(d.axis === 'z' ? p.z : p.x, d.min, d.max);
          d.onDrag(v);
          this.invalidate();
        }
        return;
      }
      const o = pick(e);
      c.style.cursor = o && (o.userData.onClick || o.userData.drag) ? 'pointer' : (o ? 'help' : 'grab');
      if (o && o.userData.tip) {
        const r = this.host.getBoundingClientRect();
        this.tip.textContent = typeof o.userData.tip === 'function' ? o.userData.tip() : o.userData.tip;
        this.tip.hidden = false;
        this.tip.style.transform = `translate(${Math.round(e.clientX - r.left + 14)}px, ${Math.round(e.clientY - r.top + 14)}px)`;
      } else {
        this.tip.hidden = true;
      }
    });
    const end = (e) => {
      if (drag && drag.kind === 'orbit' && !drag.moved && drag.obj && drag.obj.userData.onClick) drag.obj.userData.onClick();
      if (drag && drag.kind === 'constraint' && drag.d.onEnd) drag.d.onEnd();
      drag = null;
      try { c.releasePointerCapture(e.pointerId); } catch (err) { /* already released */ }
    };
    c.addEventListener('pointerup', end);
    c.addEventListener('pointercancel', end);
    c.addEventListener('pointerleave', () => { this.tip.hidden = true; });
  }

  // free the GPU side of everything under obj (geometries, materials; the shared shadow texture stays)
  disposeTree(obj) {
    obj.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      const mats = o.material ? [].concat(o.material) : [];
      for (const m of mats) { this.themed.delete(m); m.dispose(); }
    });
  }
  // empty a group and free what was in it (scenes rebuild their objects on every choice)
  clearGroup(g) {
    for (const o of [...g.children]) { g.remove(o); this.disposeTree(o); }
    this.invalidate();
  }
  clear() {
    this.anim.cancelAll();
    for (const o of [...this.root.children]) this.root.remove(o);
    this.pickables.length = 0;
    this.labels.clear();
    this.invalidate();
  }
  dispose() {
    this.disposed = true;
    this.anim.cancelAll();
    this._unTheme();
    this._ro.disconnect();
    this._io.disconnect();
    this.disposeTree(this.scene);
    this.labels.clear();
    this.renderer.dispose();
    this.renderer.forceContextLoss();          // a closed full-screen figure gives its WebGL context back
  }
}
