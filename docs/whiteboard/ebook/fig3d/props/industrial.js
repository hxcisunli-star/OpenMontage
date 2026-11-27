// Workshop props (fig3d/props): a robot arm, a belt conveyor with workpieces, a machining cell, a panel PC on a pedestal, an
// operator console, a network cabinet with an isolation lever, a stack light, a media-scan kiosk, a glass partition, file cards with
// small padlocks, a shield badge, an opened PC tower and a backup disk. First made for the 3D case book 《摆渡的幽灵》
// (projects/ghost-ferry-livebook-cn); course-neutral. Generic shapes: no maker's name, no logo. Every mesh carries a material slot.
// All wording on screens is a parameter (the callers pass words from their page data).
import * as T from 'three';
import { slab, cyl, lathe, torus, ball, pipe, screen, led, extrude, rrectShape, canvasTex, group, at, tag, TAU } from './kit.js';

const FONT = '"Noto Sans CJK SC","Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif';

// ---------------------------------------------------------------- screen pictures
// a calm machine screen: a title bar, a few gauges and bars, a status word
export function runScreen({ title = '', word = '', tone = '#2f9e64', seed = 1 } = {}) {
  return canvasTex(512, 320, (g, w, h) => {
    g.fillStyle = '#10202b'; g.fillRect(0, 0, w, h);
    g.fillStyle = '#1d3a4d'; g.fillRect(0, 0, w, h * 0.16);
    g.fillStyle = '#e8f1f6'; g.font = `${Math.round(h * 0.09)}px ${FONT}`; g.textBaseline = 'middle'; g.fillText(title, w * 0.04, h * 0.085);
    for (let i = 0; i < 3; i++) {
      const cx = w * (0.17 + i * 0.22), cy = h * 0.48, r = h * 0.15, a = Math.PI * (0.9 + ((seed * 7 + i * 5) % 9) / 10);
      g.strokeStyle = '#35566b'; g.lineWidth = 9; g.beginPath(); g.arc(cx, cy, r, Math.PI * 0.75, Math.PI * 2.25); g.stroke();
      g.strokeStyle = tone; g.beginPath(); g.arc(cx, cy, r, Math.PI * 0.75, a + Math.PI * 0.3); g.stroke();
    }
    for (let i = 0; i < 5; i++) { g.fillStyle = '#35566b'; g.fillRect(w * 0.72, h * (0.26 + i * 0.1), w * 0.23, h * 0.05); g.fillStyle = tone; g.fillRect(w * 0.72, h * (0.26 + i * 0.1), w * 0.23 * (0.35 + ((seed * 3 + i * 4) % 6) / 10), h * 0.05); }
    g.fillStyle = tone; g.fillRect(0, h * 0.8, w, h * 0.2);
    g.fillStyle = '#ffffff'; g.font = `bold ${Math.round(h * 0.11)}px ${FONT}`; g.fillText(word, w * 0.04, h * 0.905);
  });
}
// a locked screen: a red field, a drawn padlock and one word (no ransom text, no instructions)
export function lockScreen({ word = '', sub = '' } = {}) {
  return canvasTex(512, 320, (g, w, h) => {
    g.fillStyle = '#7d1414'; g.fillRect(0, 0, w, h);
    g.fillStyle = '#a81c1c'; for (let y = 0; y < h; y += 16) g.fillRect(0, y, w, 6);
    const cx = w * 0.25, cy = h * 0.52;
    g.strokeStyle = '#ffe9c9'; g.lineWidth = 16; g.beginPath(); g.arc(cx, cy - h * 0.1, h * 0.14, Math.PI, 0); g.stroke();
    g.fillStyle = '#ffe9c9'; g.fillRect(cx - h * 0.2, cy - h * 0.1, h * 0.4, h * 0.32);
    g.fillStyle = '#7d1414'; g.beginPath(); g.arc(cx, cy + h * 0.03, h * 0.04, 0, TAU); g.fill(); g.fillRect(cx - h * 0.015, cy + h * 0.03, h * 0.03, h * 0.1);
    g.fillStyle = '#ffffff'; g.textBaseline = 'middle';
    g.font = `bold ${Math.round(h * 0.15)}px ${FONT}`; g.fillText(word, w * 0.47, h * 0.42);
    g.font = `${Math.round(h * 0.085)}px ${FONT}`; g.fillText(sub, w * 0.47, h * 0.62);
  });
}
// a scanner screen: a tray picture with a tick or a cross and one word
export function scanScreen({ word = '', state = 'idle' } = {}) {
  const tone = state === 'stop' ? '#c0392b' : state === 'ok' ? '#2f9e64' : '#2c5d86';
  return canvasTex(384, 256, (g, w, h) => {
    g.fillStyle = '#0f1b26'; g.fillRect(0, 0, w, h);
    g.strokeStyle = tone; g.lineWidth = 12; g.beginPath(); g.arc(w * 0.26, h * 0.5, h * 0.27, 0, TAU); g.stroke();
    g.lineCap = 'round'; g.beginPath();
    if (state === 'stop') { g.moveTo(w * 0.19, h * 0.36); g.lineTo(w * 0.33, h * 0.64); g.moveTo(w * 0.33, h * 0.36); g.lineTo(w * 0.19, h * 0.64); }
    else if (state === 'ok') { g.moveTo(w * 0.18, h * 0.5); g.lineTo(w * 0.24, h * 0.61); g.lineTo(w * 0.35, h * 0.38); }
    else { g.moveTo(w * 0.26, h * 0.34); g.lineTo(w * 0.26, h * 0.56); g.moveTo(w * 0.26, h * 0.66); g.lineTo(w * 0.26, h * 0.67); }
    g.stroke();
    g.fillStyle = '#ffffff'; g.font = `bold ${Math.round(h * 0.15)}px ${FONT}`; g.textBaseline = 'middle'; g.fillText(word, w * 0.5, h * 0.5);
  });
}

// ---------------------------------------------------------------- stack light: a pole with red, amber and green lenses
export function stackLight({ h = 0.5, on = true } = {}) {
  const g = new T.Group();
  g.name = 'stacklight';
  g.add(at(cyl(0.012, 0.012, h - 0.18, 'metal', { seg: 14 }), 0, (h - 0.18) / 2, 0));
  g.add(at(lathe([[0, 0], [0.03, 0], [0.032, 0.008], [0.014, 0.016], [0, 0.016]], 'plastic', { seg: 20 }), 0, 0, 0));
  const lens = {};
  ['green', 'amber', 'red'].forEach((k, i) => {
    const m = tag(new T.Mesh(new T.CylinderGeometry(0.03, 0.03, 0.05, 24)), 'led', { color: { green: '#35d07f', amber: '#ffb52e', red: '#ff3b30' }[k], on });
    m.castShadow = false;
    m.position.set(0, h - 0.18 + 0.027 + i * 0.054, 0);
    g.add(m);
    lens[k] = m;
    g.add(at(cyl(0.031, 0.031, 0.004, 'plastic', { seg: 24 }), 0, h - 0.18 + 0.054 + i * 0.054, 0));
  });
  g.add(at(lathe([[0, 0], [0.031, 0], [0.026, 0.012], [0, 0.016]], 'plastic', { seg: 24 }), 0, h - 0.016, 0));
  g.userData.lens = lens;
  return g;
}

// ---------------------------------------------------------------- a six-axis style robot arm on a plinth, with a two-finger gripper
// userData.joints: { turret (turns about y), shoulder, elbow, wrist (turn about z) }
export function robotArm({ tone = 'warn' } = {}) {
  const g = new T.Group();
  g.name = 'robot';
  g.add(at(slab(0.5, 0.06, 0.5, 'paintDark', { r: 0.03, bevel: 0.01 }), 0, 0.03, 0));
  g.add(lathe([[0, 0.06], [0.17, 0.06], [0.17, 0.1], [0.14, 0.14], [0.13, 0.2], [0, 0.2]], 'paintDark', { seg: 36 }));
  const turret = new T.Group();
  turret.position.y = 0.2;
  turret.add(lathe([[0, 0], [0.125, 0], [0.13, 0.03], [0.11, 0.1], [0.09, 0.13], [0, 0.13]], tone, { seg: 36 }));
  for (const s of [-1, 1]) turret.add(at(slab(0.03, 0.2, 0.14, tone, { r: 0.03, bevel: 0.008 }), s * 0.085, 0.2, 0));
  g.add(turret);
  const joint = (r, w) => { const j = cyl(r, r, w, 'paintDark', { seg: 28 }); j.rotation.x = Math.PI / 2; return j; };
  const shoulder = new T.Group();
  shoulder.position.set(0, 0.24, 0);
  shoulder.add(at(joint(0.065, 0.2), 0, 0, 0));
  shoulder.add(at(slab(0.1, 0.46, 0.09, tone, { r: 0.045, bevel: 0.012 }), 0, 0.2, 0));
  shoulder.add(at(slab(0.035, 0.3, 0.1, 'paintDark', { r: 0.015, bevel: 0.006 }), 0, 0.2, 0));
  turret.add(shoulder);
  const elbow = new T.Group();
  elbow.position.set(0, 0.4, 0);
  elbow.add(at(joint(0.055, 0.17), 0, 0, 0));
  elbow.add(at(slab(0.4, 0.085, 0.08, tone, { r: 0.04, bevel: 0.012 }), 0.17, 0, 0));
  elbow.add(at(pipe([[0.0, 0.05, 0.03], [0.14, 0.075, 0.035], [0.3, 0.05, 0.03]], 0.008, 'cable', { smooth: true, radial: 8 }), 0, 0, 0));
  shoulder.add(elbow);
  const wrist = new T.Group();
  wrist.position.set(0.36, 0, 0);
  wrist.add(at(joint(0.042, 0.12), 0, 0, 0));
  const hand = cyl(0.03, 0.035, 0.1, 'metal', { seg: 24 });
  hand.rotation.z = Math.PI / 2; hand.position.x = 0.07;
  wrist.add(hand);
  wrist.add(at(slab(0.02, 0.09, 0.11, 'paintDark', { r: 0.008, bevel: 0.004 }), 0.125, 0, 0));
  const fingers = [];
  for (const s of [-1, 1]) {
    const f = group(at(slab(0.07, 0.016, 0.03, 'metal', { r: 0.006, bevel: 0.003 }), 0.035, 0, 0), at(slab(0.016, 0.03, 0.03, 'rubber', { r: 0.004, bevel: 0.002 }), 0.066, -s * 0.008, 0));
    f.position.set(0.135, s * 0.03, 0);
    wrist.add(f);
    fingers.push(f);
  }
  elbow.add(wrist);
  g.userData.joints = { turret, shoulder, elbow, wrist, fingers };
  // a pose: reaching forward and down a little
  shoulder.rotation.z = -0.35; elbow.rotation.z = -0.55; wrist.rotation.z = -0.4;
  return g;
}

// ---------------------------------------------------------------- a belt conveyor on legs, with a few workpieces riding on it
// userData.items: the workpieces (move them along x between -len/2 and len/2); userData.rollers (turn them about z)
export function conveyor({ len = 1.4, w = 0.34, h = 0.5, items = 4 } = {}) {
  const g = new T.Group();
  g.name = 'conveyor';
  for (const s of [-1, 1]) {
    g.add(at(slab(len, 0.07, 0.025, 'paint', { r: 0.012, bevel: 0.005 }), 0, h - 0.02, s * (w / 2 + 0.012)));
    for (const x of [-len / 2 + 0.12, len / 2 - 0.12]) {
      g.add(at(slab(0.045, h - 0.05, 0.045, 'paintDark', { r: 0.01, bevel: 0.004 }), x, (h - 0.05) / 2, s * (w / 2 - 0.01)));
      g.add(at(slab(0.09, 0.012, 0.09, 'rubber', { r: 0.01, bevel: 0.003 }), x, 0.006, s * (w / 2 - 0.01)));
    }
  }
  for (const x of [-len / 2 + 0.12, len / 2 - 0.12]) g.add(at(slab(0.03, 0.03, w, 'paintDark', { r: 0.008, bevel: 0.003 }), x, 0.16, 0));
  const belt = slab(len - 0.04, 0.014, w - 0.01, 'rubber', { r: 0.006, bevel: 0.003 });
  belt.position.set(0, h - 0.003, 0);
  g.add(belt);
  const rollers = [];
  for (const x of [-len / 2 + 0.02, len / 2 - 0.02]) {
    const r = cyl(0.03, 0.03, w + 0.01, 'metal', { seg: 24 });
    r.rotation.x = Math.PI / 2; r.position.set(x, h - 0.02, 0);
    g.add(r); rollers.push(r);
  }
  // the drive: a motor under one end, with a guard
  g.add(at(group(at((() => { const m = cyl(0.05, 0.05, 0.16, 'paintDark', { seg: 24 }); m.rotation.x = Math.PI / 2; return m; })(), 0, 0, 0), at(slab(0.09, 0.09, 0.03, 'alu', { r: 0.02, bevel: 0.006 }), 0, 0, 0.09)), len / 2 - 0.2, h - 0.14, 0.05));
  // workpieces: small housings (a turned body with a flange and a bore)
  const list = [];
  for (let i = 0; i < items; i++) {
    const p = group(lathe([[0.012, 0], [0.05, 0], [0.05, 0.012], [0.034, 0.018], [0.034, 0.05], [0.026, 0.056], [0.012, 0.056]], 'alu', { seg: 28 }), at(cyl(0.012, 0.012, 0.05, 'paintDark', { seg: 16 }), 0, 0.028, 0));
    p.position.set(-len / 2 + 0.16 + i * ((len - 0.32) / Math.max(1, items - 1)), h + 0.005, 0);
    g.add(p); list.push(p);
  }
  g.userData.items = list; g.userData.rollers = rollers; g.userData.len = len; g.userData.top = h + 0.005;
  return g;
}

// ---------------------------------------------------------------- a machining cell: an enclosure with a window, a spindle and a table inside
// userData.spindle (turn about y), userData.door
export function machineCell({ w = 0.9, h = 0.95, d = 0.7 } = {}) {
  const g = new T.Group();
  g.name = 'cell';
  g.add(at(slab(w, 0.1, d, 'paintDark', { r: 0.02, bevel: 0.008 }), 0, 0.05, 0));
  g.add(at(slab(w, h - 0.1, 0.03, 'paintLight', { r: 0.03, bevel: 0.008 }), 0, 0.1 + (h - 0.1) / 2, -d / 2 + 0.015));
  for (const s of [-1, 1]) g.add(at(slab(0.03, h - 0.1, d, 'paintLight', { r: 0.02, bevel: 0.008 }), s * (w / 2 - 0.015), 0.1 + (h - 0.1) / 2, 0));
  g.add(at(slab(w, 0.04, d, 'paint', { r: 0.03, bevel: 0.01 }), 0, h + 0.01, 0));
  // front: a lower apron, a frame with a window (glass), a handle
  g.add(at(slab(w, 0.28, 0.03, 'paintLight', { r: 0.02, bevel: 0.008 }), 0, 0.24, d / 2 - 0.015));
  const hole = rrectShape(w * 0.62, h * 0.4, 0.03);
  const frame = slab(w * 0.74, h * 0.52, 0.03, 'paint', { r: 0.04, bevel: 0.008, holes: [hole] });
  frame.position.set(-w * 0.09, 0.38 + h * 0.26, d / 2 - 0.01);
  g.add(frame);
  const glass = tag(new T.Mesh(new T.PlaneGeometry(w * 0.62, h * 0.4)), 'glass', { color: '#cfe6f2' });
  glass.castShadow = false;
  glass.position.set(-w * 0.09, 0.38 + h * 0.26, d / 2 - 0.012);
  g.add(glass);
  g.add(at(slab(0.02, 0.16, 0.025, 'metal', { r: 0.008, bevel: 0.003 }), w * 0.2, 0.38 + h * 0.26, d / 2 + 0.012));
  g.add(at(slab(w * 0.2, h * 0.52, 0.03, 'paintLight', { r: 0.02, bevel: 0.008 }), w * 0.39, 0.38 + h * 0.26, d / 2 - 0.015));
  // inside: a table with a vice and a part, a spindle head with a tool
  g.add(at(slab(w * 0.55, 0.05, d * 0.5, 'metal', { r: 0.01, bevel: 0.004 }), -w * 0.09, 0.4, 0));
  g.add(at(slab(0.16, 0.06, 0.12, 'paintDark', { r: 0.01, bevel: 0.004 }), -w * 0.09, 0.455, 0));
  g.add(at(cyl(0.035, 0.035, 0.05, 'alu', { seg: 24 }), -w * 0.09, 0.51, 0));
  g.add(at(slab(0.2, 0.22, 0.2, 'paint', { r: 0.03, bevel: 0.01 }), -w * 0.09, h - 0.14, -0.02));
  const spindle = group(at(cyl(0.04, 0.03, 0.1, 'metal', { seg: 24 }), 0, -0.05, 0), at(cyl(0.008, 0.008, 0.09, 'alu', { seg: 12 }), 0, -0.14, 0), at(slab(0.03, 0.012, 0.012, 'paintDark', { r: 0.003, bevel: 0.002 }), 0.03, -0.03, 0));
  spindle.position.set(-w * 0.09, h - 0.25, -0.02);
  g.add(spindle);
  g.userData.spindle = spindle;
  return g;
}

// ---------------------------------------------------------------- an industrial panel PC on a pedestal (the host of a work station)
// userData.screen; userData.box (the computer box under the panel, with fins and ports)
export function panelPC({ tex = runScreen(), h = 1.0 } = {}) {
  const g = new T.Group();
  g.name = 'panelpc';
  g.add(lathe([[0, 0], [0.14, 0], [0.15, 0.012], [0.12, 0.03], [0.04, 0.045], [0, 0.045]], 'paintDark', { seg: 32 }));
  g.add(at(cyl(0.028, 0.032, h - 0.3, 'metal', { seg: 20 }), 0, (h - 0.3) / 2 + 0.04, 0));
  // the computer box: a finned housing with a row of ports and two lamps
  const box = new T.Group();
  box.add(slab(0.24, 0.16, 0.09, 'alu', { r: 0.012, bevel: 0.005 }));
  for (let i = 0; i < 9; i++) box.add(at(slab(0.012, 0.15, 0.022, 'alu', { r: 0.003, bevel: 0.002 }), -0.1 + i * 0.025, 0, -0.052));
  for (let i = 0; i < 4; i++) box.add(at(slab(0.026, 0.02, 0.006, 'rubber', { r: 0.003, bevel: 0.001 }), -0.07 + i * 0.036, -0.045, 0.046));
  const lamps = [at(led(0.006, '#35d07f'), 0.085, 0.05, 0.047), at(led(0.006, '#ffb52e', { on: false }), 0.085, 0.03, 0.047)];
  lamps.forEach((l) => box.add(l));
  box.position.set(0, h * 0.42, 0.06);
  g.add(box);
  // the panel: a tilted housing with the screen, a key row and a mushroom stop button
  const head = new T.Group();
  head.add(slab(0.44, 0.31, 0.05, 'plastic', { r: 0.02, bevel: 0.008 }));
  const sc = screen(0.36, 0.225, tex);
  sc.position.set(-0.02, 0.022, 0.0256);
  head.add(sc);
  for (let i = 0; i < 6; i++) head.add(at(slab(0.04, 0.024, 0.008, 'plasticLight', { r: 0.004, bevel: 0.002 }), -0.165 + i * 0.058, -0.123, 0.027));
  head.add(at(cyl(0.02, 0.022, 0.02, 'warn', { seg: 20 }), 0.19, -0.105, 0.03, Math.PI / 2));
  head.add(at(lathe([[0, 0], [0.018, 0], [0.022, 0.006], [0.012, 0.016], [0, 0.017]], 'stamp', { seg: 20 }), 0.19, -0.105, 0.04, Math.PI / 2));
  head.add(at(slab(0.1, 0.08, 0.06, 'paintDark', { r: 0.015, bevel: 0.005 }), 0, -0.02, -0.05));
  head.position.set(0, h - 0.12, 0.02);
  head.rotation.x = -0.28;
  g.add(head);
  g.userData.screen = sc; g.userData.box = box; g.userData.head = head; g.userData.lamps = lamps;
  return g;
}

// ---------------------------------------------------------------- the operator console: a sloped desk with a wide screen, keys and a stop button
export function console3({ tex = runScreen(), w = 0.9 } = {}) {
  const g = new T.Group();
  g.name = 'console';
  g.add(at(slab(w, 0.62, 0.42, 'paint', { r: 0.03, bevel: 0.01 }), 0, 0.31, 0));
  g.add(at(slab(w + 0.02, 0.05, 0.44, 'paintDark', { r: 0.015, bevel: 0.006 }), 0, 0.025, 0));
  const desk = slab(w, 0.04, 0.36, 'paintLight', { r: 0.02, bevel: 0.008 });
  desk.position.set(0, 0.66, 0.1); desk.rotation.x = 0.22;
  g.add(desk);
  for (let r = 0; r < 2; r++) for (let c = 0; c < 8; c++) {
    const k = cyl(0.016, 0.018, 0.012, ['plasticLight', 'good', 'warn', 'plasticLight'][(r * 3 + c) % 4], { seg: 16 });
    k.position.set(-w * 0.36 + c * 0.075, 0.69 - (r ? 0.016 : 0) + 0.006, 0.07 + r * 0.075 + 0.1 - 0.06);
    k.rotation.x = 0.22;
    g.add(k);
  }
  g.add(at(lathe([[0, 0], [0.03, 0], [0.034, 0.008], [0.018, 0.024], [0, 0.026]], 'stamp', { seg: 24 }), w * 0.4, 0.655, 0.21, 0.22));
  const mon = slab(w * 0.86, 0.4, 0.04, 'plastic', { r: 0.02, bevel: 0.008 });
  mon.position.set(0, 0.93, -0.12); mon.rotation.x = -0.12;
  g.add(mon);
  const sc = screen(w * 0.8, 0.34, tex);
  sc.position.set(0, 0.93, -0.12); sc.rotation.x = -0.12; sc.translateZ(0.0206);
  g.add(sc);
  g.add(at(slab(0.14, 0.12, 0.05, 'paintDark', { r: 0.015, bevel: 0.005 }), 0, 0.72, -0.15));
  g.userData.screen = sc;
  return g;
}

// ---------------------------------------------------------------- a network cabinet: a waist-high open rack with a switch, patch cables
// and a big isolation lever on its roof. userData.lever (a pivot: rotation.x = up (about -0.5) .. down (about 1.0), swinging towards +z), userData.ports (lamps)
export function netCabinet({ ports = 8 } = {}) {
  const g = new T.Group();
  g.name = 'netcab';
  const W = 0.62, H = 0.8, D = 0.42;
  g.add(at(slab(W + 0.04, 0.05, D + 0.04, 'paintDark', { r: 0.015, bevel: 0.006 }), 0, 0.025, 0));
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) g.add(at(slab(0.035, H, 0.035, 'paintDark', { r: 0.008, bevel: 0.004 }), sx * (W / 2 - 0.018), H / 2 + 0.04, sz * (D / 2 - 0.018)));
  g.add(at(slab(W, 0.03, D, 'paintDark', { r: 0.012, bevel: 0.005 }), 0, H + 0.04, 0));
  g.add(at(slab(W - 0.04, H - 0.06, 0.012, 'paint', { r: 0.01, bevel: 0.003 }), 0, H / 2 + 0.04, -D / 2 + 0.03));
  // the switch: a flat unit with a row of ports and a lamp over each
  const sw = new T.Group();
  sw.add(slab(W - 0.08, 0.075, D - 0.1, 'plastic', { r: 0.008, bevel: 0.004 }));
  const lamps = [];
  for (let i = 0; i < ports; i++) {
    const x = -(W - 0.2) / 2 + i * ((W - 0.2) / (ports - 1));
    sw.add(at(slab(0.03, 0.026, 0.008, 'rubber', { r: 0.003, bevel: 0.001 }), x, -0.012, (D - 0.1) / 2 + 0.002));
    const l = led(0.0055, '#35d07f');
    l.position.set(x, 0.022, (D - 0.1) / 2 + 0.003);
    sw.add(l); lamps.push(l);
  }
  sw.position.set(0, H * 0.72, 0.02);
  g.add(sw);
  // a patch panel and a shelf unit below, for the look of a real rack
  g.add(at(slab(W - 0.08, 0.05, D - 0.14, 'alu', { r: 0.006, bevel: 0.003 }), 0, H * 0.52, 0));
  for (let i = 0; i < 12; i++) g.add(at(cyl(0.008, 0.008, 0.01, 'rubber', { seg: 10 }), -(W - 0.2) / 2 + i * ((W - 0.2) / 11), H * 0.52, (D - 0.14) / 2 + 0.004, Math.PI / 2));
  g.add(at(slab(W - 0.08, 0.16, D - 0.12, 'paint', { r: 0.01, bevel: 0.004 }), 0, H * 0.24, 0));
  for (let i = 0; i < 5; i++) g.add(at(slab(W - 0.2, 0.01, 0.006, 'rubber', { r: 0.002, bevel: 0.001 }), 0, H * 0.18 + i * 0.026, (D - 0.12) / 2 + 0.002));
  // the isolation lever stands on the roof: a base with two cheeks, a pivot, a long arm and a red ball grip (it swings towards +z)
  const lx = W / 2 - 0.15, ly = H + 0.055;
  g.add(at(slab(0.24, 0.05, 0.2, 'alu', { r: 0.015, bevel: 0.006 }), lx, ly + 0.025, 0.02));
  for (const sx of [-1, 1]) g.add(at(slab(0.022, 0.13, 0.14, 'paintDark', { r: 0.02, bevel: 0.006 }), lx + sx * 0.07, ly + 0.11, 0.02));
  for (const sz of [-1, 1]) g.add(at(slab(0.09, 0.03, 0.035, 'copper', { r: 0.006, bevel: 0.003 }), lx, ly + 0.065, 0.02 + sz * 0.075));
  const lever = new T.Group();
  lever.position.set(lx, ly + 0.12, 0.02);
  const pin = cyl(0.02, 0.02, 0.17, 'metal', { seg: 20 });
  pin.rotation.z = Math.PI / 2;
  lever.add(pin);
  lever.add(at(slab(0.04, 0.4, 0.04, 'metal', { r: 0.012, bevel: 0.005 }), 0, 0.2, 0));
  lever.add(at(lathe([[0, 0], [0.03, 0], [0.034, 0.012], [0.024, 0.03], [0, 0.03]], 'paintDark', { seg: 20 }), 0, 0.38, 0));
  lever.add(at(ball(0.058, 'stamp', { w: 24, h: 18 }), 0, 0.455, 0));
  g.add(lever);
  g.userData.lever = lever; g.userData.ports = lamps; g.userData.sw = sw; g.userData.size = { W, H, D };
  return g;
}

// ---------------------------------------------------------------- a media-scan kiosk: a column with a sloped screen and a tray with a socket
// userData.screen, userData.slot (where a stick plugs in, in the kiosk's own coordinates)
export function scanKiosk({ tex = scanScreen() } = {}) {
  const g = new T.Group();
  g.name = 'kiosk';
  g.add(at(slab(0.46, 0.04, 0.4, 'paintDark', { r: 0.03, bevel: 0.01 }), 0, 0.02, 0));
  g.add(at(slab(0.3, 0.84, 0.2, 'paintLight', { r: 0.04, bevel: 0.012 }), 0, 0.46, -0.03));
  g.add(at(slab(0.24, 0.5, 0.012, 'accent', { r: 0.02, bevel: 0.004 }), 0, 0.42, 0.073));
  const head = new T.Group();
  head.add(slab(0.4, 0.3, 0.06, 'plastic', { r: 0.025, bevel: 0.01 }));
  const sc = screen(0.33, 0.22, tex);
  sc.position.set(0, 0.012, 0.0306);
  head.add(sc);
  head.position.set(0, 1.0, 0.03); head.rotation.x = -0.45;
  g.add(head);
  // the tray: a shelf with a socket and a ring of light
  g.add(at(slab(0.3, 0.03, 0.16, 'alu', { r: 0.015, bevel: 0.006 }), 0, 0.78, 0.13));
  const ring = torus(0.035, 0.006, 'led', { seg: 28, tube: 8 });
  ring.userData.color = '#4aa3ff'; ring.userData.on = true; ring.castShadow = false;
  ring.rotation.x = Math.PI / 2; ring.position.set(0, 0.797, 0.14);
  g.add(ring);
  g.add(at(slab(0.03, 0.012, 0.014, 'rubber', { r: 0.003, bevel: 0.001 }), 0, 0.797, 0.14));
  g.userData.screen = sc; g.userData.ring = ring; g.userData.slot = new T.Vector3(0, 0.81, 0.14);
  return g;
}

// ---------------------------------------------------------------- a glass partition with posts, a top rail and a doorway
// spans x in [-len/2, len/2]; door = [x0, x1] leaves a gap; userData.panels (the glass), userData.strips (the lit edge strips)
export function glassWall({ len = 4, h = 1.25, door = null, color = '#9fd3ff' } = {}) {
  const g = new T.Group();
  g.name = 'wall';
  const runs = door ? [[-len / 2, door[0]], [door[1], len / 2]] : [[-len / 2, len / 2]];
  const panels = [], strips = [];
  for (const [a, b] of runs) {
    const n = Math.max(1, Math.round((b - a) / 0.9));
    for (let i = 0; i <= n; i++) {
      const x = a + (b - a) * i / n;
      g.add(at(slab(0.05, h, 0.05, 'alu', { r: 0.012, bevel: 0.005 }), x, h / 2, 0));
      g.add(at(slab(0.1, 0.02, 0.1, 'paintDark', { r: 0.01, bevel: 0.004 }), x, 0.01, 0));
    }
    g.add(at(slab(b - a, 0.04, 0.05, 'alu', { r: 0.012, bevel: 0.005 }), (a + b) / 2, h + 0.02, 0));
    g.add(at(slab(b - a, 0.05, 0.04, 'alu', { r: 0.012, bevel: 0.005 }), (a + b) / 2, 0.05, 0));
    const pane = tag(new T.Mesh(new T.BoxGeometry(b - a - 0.05, h - 0.1, 0.012)), 'glass', { color });
    pane.castShadow = false;
    pane.position.set((a + b) / 2, h / 2 + 0.03, 0);
    g.add(pane); panels.push(pane);
    const strip = tag(new T.Mesh(new T.BoxGeometry(b - a - 0.06, 0.016, 0.02)), 'led', { color, on: true });
    strip.castShadow = false;
    strip.position.set((a + b) / 2, h - 0.02, 0);
    g.add(strip); strips.push(strip);
  }
  if (door) {          // door posts a little taller, with a lintel sign plate
    for (const x of door) g.add(at(slab(0.07, h + 0.25, 0.07, 'paintDark', { r: 0.015, bevel: 0.006 }), x, (h + 0.25) / 2, 0));
    g.add(at(slab(door[1] - door[0] + 0.07, 0.12, 0.05, 'paintDark', { r: 0.015, bevel: 0.006 }), (door[0] + door[1]) / 2, h + 0.19, 0));
  }
  g.userData.panels = panels; g.userData.strips = strips;
  return g;
}

// ---------------------------------------------------------------- a file card: a sheet with a folded corner, a colour band and lines
// userData.sheet (recolour it), userData.lock (a small padlock, hidden until the file is locked)
export function fileCard({ tone = '#2c5d86', w = 0.12, h = 0.16 } = {}) {
  const g = new T.Group();
  g.name = 'file';
  const s = new T.Shape(), c = 0.03;
  s.moveTo(-w / 2, -h / 2); s.lineTo(w / 2, -h / 2); s.lineTo(w / 2, h / 2 - c); s.lineTo(w / 2 - c, h / 2); s.lineTo(-w / 2, h / 2); s.closePath();
  const sheet = extrude(s, 0.006, 'paper', { bevel: 0.001, curve: 2 });
  g.add(sheet);
  const fold = new T.Shape(); fold.moveTo(w / 2 - c, h / 2); fold.lineTo(w / 2, h / 2 - c); fold.lineTo(w / 2 - c, h / 2 - c); fold.closePath();
  g.add(at(extrude(fold, 0.002, 'line', { bevel: 0.0005, curve: 2 }), 0, 0, 0.004));
  const band = slab(w * 0.8, h * 0.16, 0.002, 'accent', { r: 0.004, bevel: 0.0008 });
  band.userData.color = tone;
  band.position.set(-w * 0.04, h * 0.26, 0.004);
  g.add(band);
  for (let i = 0; i < 4; i++) g.add(at(slab(w * (i === 3 ? 0.5 : 0.76), h * 0.035, 0.0012, 'line', { r: 0.002, bevel: 0.0004 }), i === 3 ? -w * 0.13 : 0, h * (0.08 - i * 0.1), 0.0036));
  const lock = miniLock();
  lock.scale.setScalar(h * 2.2);
  lock.position.set(0, -h * 0.12, 0.012);
  lock.visible = false;
  g.add(lock);
  g.userData.sheet = sheet; g.userData.band = band; g.userData.lock = lock;
  return g;
}

// a small padlock (about 0.2 wide at scale 1): a body with a keyhole and a shackle
export function miniLock({ slot = 'hot' } = {}) {
  const g = new T.Group();
  g.name = 'lock';
  g.add(at(slab(0.2, 0.16, 0.07, slot, { r: 0.03, bevel: 0.012 }), 0, 0.08, 0));
  const arc = torus(0.062, 0.018, 'alu', { seg: 28, tube: 10, arc: Math.PI });
  arc.position.y = 0.2;
  g.add(arc);
  for (const sx of [-1, 1]) g.add(at(cyl(0.018, 0.018, 0.05, 'alu', { seg: 14 }), sx * 0.062, 0.178, 0));
  g.add(at(cyl(0.018, 0.018, 0.012, 'rubber', { seg: 16 }), 0, 0.095, 0.036, Math.PI / 2));
  g.add(at(slab(0.014, 0.04, 0.012, 'rubber', { r: 0.004, bevel: 0.002 }), 0, 0.07, 0.036));
  return g;
}

// a shield badge with a tick (about 0.2 tall at scale 1)
export function shield({ slot = 'good' } = {}) {
  const g = new T.Group();
  g.name = 'shield';
  const s = new T.Shape();
  s.moveTo(0, 0.11); s.quadraticCurveTo(0.05, 0.1, 0.09, 0.075); s.lineTo(0.09, 0.0); s.quadraticCurveTo(0.085, -0.075, 0, -0.11); s.quadraticCurveTo(-0.085, -0.075, -0.09, 0.0); s.lineTo(-0.09, 0.075); s.quadraticCurveTo(-0.05, 0.1, 0, 0.11);
  g.add(extrude(s, 0.03, slot, { bevel: 0.006, curve: 10 }));
  const tick = pipe([[-0.04, 0.0, 0.02], [-0.012, -0.035, 0.02], [0.045, 0.04, 0.02]], 0.01, 'plasticLight', { bend: 0.01, radial: 8 });
  g.add(tick);
  return g;
}

// ---------------------------------------------------------------- an opened PC tower (side panel off): the frame, a fan, a board, a power unit,
// a drive cage with drawers, front ports. userData.drawers (groups to put file cards in), userData.port (front socket position),
// userData.side (the removed side panel, lying next to it), userData.net (the network socket at the back)
export function openTower({ w = 0.44, h = 0.9, d = 0.9, drawers = 4 } = {}) {
  const g = new T.Group();
  g.name = 'tower';
  // frame: floor, roof, back, front, far side (the near side is open)
  g.add(at(slab(w, 0.03, d, 'paintDark', { r: 0.012, bevel: 0.005 }), 0, 0.015, 0));
  g.add(at(slab(w, 0.03, d, 'paintDark', { r: 0.012, bevel: 0.005 }), 0, h - 0.015, 0));
  g.add(at(slab(w, h, 0.025, 'paintDark', { r: 0.012, bevel: 0.005 }), 0, h / 2, -d / 2 + 0.012));
  g.add(at(slab(0.025, h, d, 'paintDark', { r: 0.012, bevel: 0.005 }), -w / 2 + 0.012, h / 2, 0));
  const front = slab(w + 0.02, h + 0.02, 0.04, 'plastic', { r: 0.03, bevel: 0.012 });
  front.position.set(0, h / 2, d / 2 + 0.02);
  g.add(front);
  for (let i = 0; i < 7; i++) g.add(at(slab(w * 0.6, 0.012, 0.006, 'rubber', { r: 0.003, bevel: 0.001 }), 0, 0.12 + i * 0.03, d / 2 + 0.042));
  g.add(at(cyl(0.024, 0.024, 0.01, 'metal', { seg: 24 }), 0.1, h - 0.1, d / 2 + 0.043, Math.PI / 2));
  const power = led(0.008, '#35d07f');
  power.position.set(-0.02, h - 0.1, d / 2 + 0.044);
  g.add(power);
  const ports = [];
  for (let i = 0; i < 2; i++) { const p = slab(0.034, 0.014, 0.01, 'rubber', { r: 0.003, bevel: 0.001 }); p.position.set(-0.11, h - 0.2 - i * 0.04, d / 2 + 0.042); g.add(p); ports.push(p); }
  // inside: the board on the far side, a cooler with a fan, memory sticks, a power unit, cables
  g.add(at(slab(0.012, h * 0.6, d * 0.62, 'good', { r: 0.01, bevel: 0.003 }), -w / 2 + 0.035, h * 0.56, -0.08));
  const fanHub = new T.Group();
  fanHub.add(at(cyl(0.11, 0.11, 0.05, 'alu', { seg: 32 }), 0, 0, 0, 0, 0, Math.PI / 2));
  const blades = new T.Group();
  for (let i = 0; i < 7; i++) { const b = slab(0.012, 0.085, 0.04, 'rubber', { r: 0.008, bevel: 0.003 }); b.position.set(0.03, Math.cos(i * TAU / 7) * 0.055, Math.sin(i * TAU / 7) * 0.055); b.rotation.x = i * TAU / 7; b.rotation.y = 0.5; blades.add(b); }
  blades.add(at(cyl(0.028, 0.028, 0.014, 'plastic', { seg: 20 }), 0.032, 0, 0, 0, 0, Math.PI / 2));
  fanHub.add(blades);
  fanHub.position.set(-w / 2 + 0.075, h * 0.62, -0.1);
  g.add(fanHub);
  for (let i = 0; i < 4; i++) g.add(at(slab(0.06, 0.16, 0.012, 'accent', { r: 0.004, bevel: 0.002 }), -w / 2 + 0.07, h * 0.6, 0.1 + i * 0.03));
  g.add(at(slab(w * 0.8, 0.16, 0.24, 'alu', { r: 0.012, bevel: 0.005 }), -0.02, 0.115, -d / 2 + 0.15));
  g.add(pipe([[-0.05, 0.2, -d / 2 + 0.2], [-0.12, 0.34, -0.1], [-w / 2 + 0.06, 0.42, 0.0]], 0.012, 'cable', { smooth: true, radial: 8 }));
  g.add(pipe([[0.0, 0.2, -d / 2 + 0.22], [0.0, 0.3, 0.05], [0.02, 0.36, 0.2]], 0.01, 'cableRed', { smooth: true, radial: 8 }));
  // the drive cage at the front: open drawers, one above the other
  const cage = new T.Group(), slots = [];
  const cw = w * 0.74, cd = d * 0.4, ch = h * 0.66;
  // the cage is closed towards the board side only; on the open side two slim posts hold the drawers, so what lies in them shows
  cage.add(at(slab(0.012, ch, cd, 'alu', { r: 0.004, bevel: 0.002 }), -cw / 2, ch / 2, 0));
  for (const sz of [-1, 1]) cage.add(at(slab(0.014, ch, 0.014, 'alu', { r: 0.003, bevel: 0.002 }), cw / 2, ch / 2, sz * (cd / 2 - 0.007)));
  for (let i = 0; i < drawers; i++) {
    const y = 0.03 + i * (ch / drawers);
    const dr = new T.Group();
    dr.add(at(slab(cw - 0.02, 0.014, cd - 0.02, 'paintLight', { r: 0.006, bevel: 0.003 }), 0, 0, 0));
    dr.add(at(slab(cw - 0.02, 0.05, 0.012, 'paintLight', { r: 0.006, bevel: 0.003 }), 0, 0.025, cd / 2 - 0.016));
    dr.add(at(slab(0.07, 0.014, 0.014, 'metal', { r: 0.004, bevel: 0.002 }), 0, 0.03, cd / 2 - 0.004));
    dr.position.set(0, y, 0);
    cage.add(dr); slots.push(dr);
  }
  cage.position.set(0.03, 0.06, d / 2 - cd / 2 - 0.03);
  g.add(cage);
  // the removed side panel leans against the back
  const side = slab(d - 0.04, h - 0.04, 0.012, 'plastic', { r: 0.02, bevel: 0.004 });
  g.userData.side = side;
  g.userData.drawers = slots; g.userData.drawerSize = { w: cw - 0.02, d: cd - 0.02, h: ch / drawers };
  g.userData.port = ports[0]; g.userData.fan = blades; g.userData.power = power;
  g.userData.net = new T.Vector3(0.08, h * 0.3, -d / 2);
  g.userData.size = { w, h, d };
  return g;
}

// an external backup disk with a coiled cable lying beside it (not plugged in)
export function backupDisk() {
  const g = new T.Group();
  g.name = 'backup';
  g.add(at(slab(0.16, 0.035, 0.22, 'alu', { r: 0.02, bevel: 0.008 }), 0, 0.02, 0));
  g.add(at(slab(0.1, 0.004, 0.14, 'plastic', { r: 0.01, bevel: 0.001 }), 0, 0.039, 0));
  const lamp = led(0.005, '#35d07f', { on: false });
  lamp.position.set(0.055, 0.02, 0.111);
  g.add(lamp);
  const coil = [];
  for (let k = 0; k <= 60; k++) { const a = k * 0.42, r = 0.035 + k * 0.0006; coil.push([0.17 + Math.cos(a) * r, 0.008 + k * 0.00025, Math.sin(a) * r]); }
  g.add(pipe(coil, 0.005, 'cable', { smooth: true, radial: 6, seg: 120 }));
  g.add(at(slab(0.024, 0.012, 0.03, 'plasticLight', { r: 0.003, bevel: 0.001 }), 0.17 + 0.07, 0.025, 0.02));
  g.userData.lamp = lamp;
  return g;
}

// a floor cable between two points (a flat run on the floor with a soft curve), for the star of network cables in a workshop
export function floorCable(a, b, { slot = 'cableBlue', r = 0.012, lift = 0.012, bow = 0.0 } = {}) {
  const mid = [(a[0] + b[0]) / 2 + (b[2] - a[2]) * bow, lift, (a[2] + b[2]) / 2 - (b[0] - a[0]) * bow];
  const m = pipe([[a[0], lift, a[2]], mid, [b[0], lift, b[2]]], r, slot, { smooth: true, radial: 8 });
  m.receiveShadow = true;
  return m;
}
