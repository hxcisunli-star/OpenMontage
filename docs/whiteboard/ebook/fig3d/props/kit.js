// Geometry helpers for the props (fig3d/props). First made for the Stuxnet 3D book (projects/stuxnet-livebook-cn); course-neutral. Every mesh carries a material *slot* name (userData.slot), not a material:
// looks.js turns slots into materials, so the same model can be drawn in any look (and, in stage 2, follow the page theme).
import * as T from 'three';

export const TAU = Math.PI * 2;

export function tag(mesh, slot, extra = {}) {
  mesh.userData.slot = slot;
  Object.assign(mesh.userData, extra);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

// a solid of revolution from a profile [[r, y], ...] (bottom to top); phiLength < 2π leaves a cut-away opening
export function lathe(profile, slot, { seg = 56, phiStart = 0, phiLength = TAU, extra } = {}) {
  const g = new T.LatheGeometry(profile.map(([r, y]) => new T.Vector2(Math.max(r, 1e-4), y)), seg, phiStart, phiLength);
  const cut = phiLength < TAU - 1e-3;
  return tag(new T.Mesh(g), slot, { cut, ...(extra || {}) });
}

// a rounded rectangle in the XY plane, centred
export function rrectShape(w, h, r) {
  r = Math.min(r, w / 2 - 1e-4, h / 2 - 1e-4);
  const s = new T.Shape(), x = -w / 2, y = -h / 2;
  s.moveTo(x + r, y);
  s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
  s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
  return s;
}

// a rounded, bevelled slab: w (x) × h (y) × d (z), centred. Used for casings, panels, keys - never left as a bare box.
export function slab(w, h, d, slot, { r = 0.04, bevel = 0.012, curve = 6, holes = [] } = {}) {
  const b = Math.min(bevel, d / 2 - 1e-4, r * 0.9);
  const shape = rrectShape(w - 2 * b, h - 2 * b, Math.max(1e-3, r - b));
  for (const hl of holes) shape.holes.push(hl);
  const g = new T.ExtrudeGeometry(shape, { depth: Math.max(1e-4, d - 2 * b), bevelEnabled: b > 0, bevelThickness: b, bevelSize: b, bevelSegments: 3, curveSegments: curve });
  g.translate(0, 0, -(d - 2 * b) / 2);
  g.computeVertexNormals();
  return tag(new T.Mesh(g), slot);
}

// an extruded outline (Shape) along z, centred in depth
export function extrude(shape, depth, slot, { bevel = 0.006, curve = 10 } = {}) {
  const g = new T.ExtrudeGeometry(shape, { depth: Math.max(1e-4, depth - 2 * bevel), bevelEnabled: bevel > 0, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 2, curveSegments: curve });
  g.translate(0, 0, -(depth - 2 * bevel) / 2);
  return tag(new T.Mesh(g), slot);
}

export function cyl(rTop, rBot, h, slot, { seg = 40, open = false, phiStart = 0, phiLength = TAU } = {}) {
  return tag(new T.Mesh(new T.CylinderGeometry(rTop, rBot, h, seg, 1, open, phiStart, phiLength)), slot);
}
export function torus(R, r, slot, { seg = 48, tube = 12, arc = TAU } = {}) {
  return tag(new T.Mesh(new T.TorusGeometry(R, r, tube, seg, arc)), slot);
}
export function ball(r, slot, { w = 24, h = 16 } = {}) {
  return tag(new T.Mesh(new T.SphereGeometry(r, w, h)), slot);
}

// a pipe or cable through points with rounded bends (straight runs stay straight)
export function pipePath(points, bend = 0.15) {
  const P = points.map((p) => new T.Vector3(...p));
  const path = new T.CurvePath();
  let cur = P[0].clone();
  for (let i = 1; i < P.length; i++) {
    const a = P[i - 1], b = P[i], c = P[i + 1];
    if (!c) { path.add(new T.LineCurve3(cur, b.clone())); break; }
    const ab = b.clone().sub(a), bc = c.clone().sub(b);
    const k = Math.min(bend, ab.length() / 2, bc.length() / 2);
    const p1 = b.clone().sub(ab.normalize().multiplyScalar(k)), p2 = b.clone().add(bc.normalize().multiplyScalar(k));
    path.add(new T.LineCurve3(cur, p1));
    path.add(new T.QuadraticBezierCurve3(p1, b.clone(), p2));
    cur = p2;
  }
  return path;
}
export function pipe(points, r, slot, { bend = 0.15, seg, radial = 14, smooth = false } = {}) {
  const curve = smooth ? new T.CatmullRomCurve3(points.map((p) => new T.Vector3(...p)), false, 'centripetal') : pipePath(points, bend);
  const len = curve.getLength();
  const g = new T.TubeGeometry(curve, seg || Math.max(24, Math.round(len * 40)), r, radial, false);
  const m = tag(new T.Mesh(g), slot);
  m.userData.curve = curve;
  return m;
}

// a canvas texture drawn by fn(ctx, w, h); colour space sRGB
export function canvasTex(w, h, fn) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  fn(c.getContext('2d'), w, h);
  const t = new T.CanvasTexture(c);
  t.colorSpace = T.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}
// a screen surface (emissive picture) facing +z
export function screen(w, h, tex, { slot = 'screen' } = {}) {
  const m = tag(new T.Mesh(new T.PlaneGeometry(w, h)), slot, { map: tex });
  m.castShadow = false;
  return m;
}
export function led(r, color, { on = true } = {}) {
  const m = ball(r, 'led', { w: 12, h: 8 });
  m.userData.color = color;
  m.userData.on = on;
  m.castShadow = false;
  return m;
}

export function group(...kids) {
  const g = new T.Group();
  for (const k of kids) if (k) g.add(k);
  return g;
}
export function at(obj, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0) {
  obj.position.set(x, y, z);
  obj.rotation.set(rx, ry, rz);
  return obj;
}

// seeded random, so every render of a shot is the same picture
export function rng(seed = 1) {
  let s = seed >>> 0;
  return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// fade a mesh out towards the bottom: a per-vertex alpha from a0 (at y0) to a1 (at y1), in the mesh's own coordinates.
// looks.js turns on vertex colours for meshes marked fade, so the see-through figure dissolves into the floor.
export function fadeY(mesh, y0, y1, a0, a1) {
  const pos = mesh.geometry.attributes.position, n = pos.count, col = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    const t = Math.min(1, Math.max(0, (pos.getY(i) - y0) / (y1 - y0)));
    const k = t * t * (3 - 2 * t);
    col[i * 4] = col[i * 4 + 1] = col[i * 4 + 2] = 1;
    col[i * 4 + 3] = a0 + (a1 - a0) * k;
  }
  mesh.geometry.setAttribute('color', new T.BufferAttribute(col, 4));
  mesh.userData.fade = true;
  return mesh;
}
