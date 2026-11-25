// Parts shared by every scene, in one drawing style: paper-flat fills (from book.css variables or the answer hues), a dark outline, a soft contact shadow.
// Nothing here knows about a course: a block is a token, a run of a model, a register; a wire carries current, data or requests alike.
import {
  Group, Mesh, BoxGeometry, MeshLambertMaterial, MeshBasicMaterial, BackSide, EdgesGeometry, LineSegments, LineBasicMaterial,
  PlaneGeometry, CanvasTexture, SphereGeometry, CylinderGeometry, BufferGeometry, Line, Vector3, CatmullRomCurve3, Float32BufferAttribute,
} from 'three';
import { color } from './theme.js';

export function makeParts(stage) {
  const lineMat = () => stage.themedMaterial(new LineBasicMaterial({ transparent: true, opacity: 0.9 }), 'fg');
  const hullMat = () => stage.themedMaterial(new MeshBasicMaterial({ side: BackSide }), 'fg');
  const fillMat = (fill) => {
    const m = new MeshLambertMaterial({ flatShading: true });
    if (fill && fill.startsWith('#')) m.color.copy(color(fill));
    else stage.themedMaterial(m, fill || 'surface');
    return m;
  };
  let shadowTex = null;
  const shadowTexture = () => {
    if (shadowTex) return shadowTex;
    const c = document.createElement('canvas');
    c.width = c.height = 128;
    const g = c.getContext('2d');
    const grd = g.createRadialGradient(64, 64, 6, 64, 64, 62);
    grd.addColorStop(0, 'rgba(0,0,0,0.55)');
    grd.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = grd;
    g.fillRect(0, 0, 128, 128);
    shadowTex = new CanvasTexture(c);
    return shadowTex;
  };

  // a box with an outline: block, paper, device, chip. fill: '#RRGGBB' or a theme variable name ('user', 'model', 'note-bg' ...)
  function block({ w = 1, h = 1, d = 1, fill = 'surface', outline = 0.03, edges = true } = {}) {
    const g = new Group();
    const mesh = new Mesh(new BoxGeometry(w, h, d), fillMat(fill));
    g.add(mesh);
    if (outline > 0) {
      const hull = new Mesh(new BoxGeometry(w + 2 * outline, h + 2 * outline, d + 2 * outline), hullMat());
      g.add(hull);
    }
    if (edges) g.add(new LineSegments(new EdgesGeometry(mesh.geometry), lineMat()));
    g.userData.mesh = mesh;
    g.setFill = (f) => {
      if (f.startsWith('#')) { stage.themed.delete(mesh.material); mesh.material.color.copy(color(f)); } else stage.themedMaterial(mesh.material, f);
      stage.invalidate();
    };
    return g;
  }

  // a thin sheet lying flat: a note, a card, a page
  function paper({ w = 3, d = 2, h = 0.06, fill = 'surface' } = {}) {
    return block({ w, h, d, fill, outline: 0.025 });
  }

  function shadow(w = 1, d = 1, opacity = 0.35) {
    const m = new Mesh(new PlaneGeometry(w, d), new MeshBasicMaterial({ map: shadowTexture(), transparent: true, depthWrite: false, opacity, color: 0x000000 }));
    m.rotation.x = -Math.PI / 2;
    m.position.y = 0.005;
    m.renderOrder = -1;
    return m;
  }

  // the desk: a sheet in the figure's note colour with a faint grid
  function floor(w = 20, d = 12, step = 1) {
    const g = new Group();
    const m = new Mesh(new PlaneGeometry(w, d), stage.themedMaterial(new MeshBasicMaterial(), 'note-bg'));
    m.rotation.x = -Math.PI / 2;
    g.add(m);
    const pts = [];
    for (let x = -w / 2; x <= w / 2 + 1e-6; x += step) pts.push(x, 0.002, -d / 2, x, 0.002, d / 2);
    for (let z = -d / 2; z <= d / 2 + 1e-6; z += step) pts.push(-w / 2, 0.002, z, w / 2, 0.002, z);
    const geo = new BufferGeometry();
    geo.setAttribute('position', new Float32BufferAttribute(pts, 3));
    const lm = stage.themedMaterial(new LineBasicMaterial({ transparent: true, opacity: 0.8 }), 'line');
    g.add(new LineSegments(geo, lm));
    return g;
  }

  // a wire or pipe through points, with dots that flow along it (current, data, requests)
  function wire(points, { key = 'fg', dots = 0, dotKey = 'accent', dotSize = 0.12 } = {}) {
    const g = new Group();
    const curve = new CatmullRomCurve3(points.map((p) => new Vector3(...p)), false, 'catmullrom', 0.0001);
    const geo = new BufferGeometry().setFromPoints(curve.getPoints(Math.max(8, points.length * 12)));
    g.add(new Line(geo, stage.themedMaterial(new LineBasicMaterial(), key)));
    const flow = [];
    for (let i = 0; i < dots; i++) {
      const s = new Mesh(new SphereGeometry(dotSize, 12, 8), stage.themedMaterial(new MeshBasicMaterial(), dotKey));
      g.add(s);
      flow.push(s);
    }
    g.userData.curve = curve;
    g.setFlow = (t) => {           // t: 0..1 phase; the dots sit evenly spaced and move together
      flow.forEach((s, i) => { s.position.copy(curve.getPointAt(((t + i / Math.max(1, flow.length)) % 1 + 1) % 1)); });
    };
    g.setFlow(0);
    return g;
  }

  function dot(r = 0.15, key = 'accent') {
    return new Mesh(new SphereGeometry(r, 16, 12), stage.themedMaterial(new MeshBasicMaterial(), key));
  }

  // a ruler or time axis along x from 0 to len, ticks every `every` units
  function axis(len, every = 1, { key = 'fg-2', tick = 0.18 } = {}) {
    const pts = [0, 0, 0, len, 0, 0];
    for (let x = 0; x <= len + 1e-6; x += every) pts.push(x, 0, 0, x, 0, tick);
    const geo = new BufferGeometry();
    geo.setAttribute('position', new Float32BufferAttribute(pts, 3));
    return new LineSegments(geo, stage.themedMaterial(new LineBasicMaterial(), key));
  }

  function cylinder(r, h, fill = 'surface', { opacity = 1 } = {}) {
    const g = new Group();
    const mat = fillMat(fill);
    if (opacity < 1) { mat.transparent = true; mat.opacity = opacity; mat.depthWrite = false; }          // a glass jar: what is inside shows through
    const mesh = new Mesh(new CylinderGeometry(r, r, h, 28), mat);
    g.add(mesh);
    if (opacity >= 1) g.add(new Mesh(new CylinderGeometry(r + 0.03, r + 0.03, h + 0.06, 28), hullMat()));
    else g.add(new LineSegments(new EdgesGeometry(new CylinderGeometry(r, r, h, 28), 30), lineMat()));
    g.userData.mesh = mesh;
    return g;
  }

  // make a mesh answer to hover (tip) and click
  function pickable(obj, { tip, onClick, drag } = {}) {
    const m = obj.userData.mesh || obj;
    if (tip !== undefined) m.userData.tip = tip;
    if (onClick) m.userData.onClick = onClick;
    if (drag) m.userData.drag = drag;
    stage.pickables.push(m);
    return obj;
  }

  return { block, paper, shadow, floor, wire, dot, axis, cylinder, pickable };
}
