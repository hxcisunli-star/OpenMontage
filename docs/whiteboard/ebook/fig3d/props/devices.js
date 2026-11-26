// Computers and plant equipment: a laptop, an operator workstation, a USB stick, a PLC rack, a drive (frequency converter) cabinet.
// Every one is built from rounded, bevelled parts with the details that make it recognisable without a label.
import * as T from 'three';
import { slab, cyl, torus, ball, pipe, screen, led, lathe, extrude, rrectShape, group, at, tag, canvasTex, TAU } from './kit.js';
import { engScreen, scadaScreen, vfdDisplay, moduleFace } from './screens.js';

// ---------------------------------------------------------------- laptop
// open: lid angle from closed (0) to wide open (~1.9 rad). tex: the picture on its screen.
export function laptop({ tex = engScreen(), open = 1.85, w = 0.36, d = 0.25, shell = 'plasticDark' } = {}) {
  const g = new T.Group();
  g.name = 'laptop';
  const baseH = 0.022;
  const base = slab(w, d, baseH, shell === 'plasticDark' ? 'plastic' : shell, { r: 0.018, bevel: 0.006 });
  base.rotation.x = -Math.PI / 2;
  base.position.y = baseH / 2;
  g.add(base);
  // keyboard well and keys (instanced rounded caps)
  const well = slab(w * 0.86, d * 0.44, 0.004, 'rubber', { r: 0.006, bevel: 0.001 });
  well.rotation.x = -Math.PI / 2; well.position.set(0, baseH + 0.0005, -d * 0.12);
  g.add(well);
  const capGeo = new T.ExtrudeGeometry(rrectShape(0.0165, 0.0165, 0.003), { depth: 0.002, bevelEnabled: true, bevelThickness: 0.0012, bevelSize: 0.0012, bevelSegments: 2, curveSegments: 4 });
  const rows = 5, cols = 14, keys = new T.InstancedMesh(capGeo, undefined, rows * cols + 1);
  const m4 = new T.Matrix4(), q = new T.Quaternion().setFromEuler(new T.Euler(-Math.PI / 2, 0, 0)), s1 = new T.Vector3(1, 1, 1);
  let n = 0;
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const x = -w * 0.4 + (c + (r % 2) * 0.3) * (w * 0.8 / (cols - 0.5)), z = -d * 0.3 + r * (d * 0.36 / (rows - 1));
    if (r === rows - 1 && c > 3 && c < 10) { if (c === 4) { m4.compose(new T.Vector3(0, baseH + 0.002, z), q, new T.Vector3(7, 1, 1)); keys.setMatrixAt(n++, m4); } continue; }
    m4.compose(new T.Vector3(x, baseH + 0.002, z), q, s1); keys.setMatrixAt(n++, m4);
  }
  keys.count = n;
  tag(keys, 'plasticLight', { noEdges: true, noOutline: true });
  g.add(keys);
  // trackpad and a status light
  const pad = slab(w * 0.3, d * 0.2, 0.002, 'plastic', { r: 0.008, bevel: 0.0008 });
  pad.rotation.x = -Math.PI / 2; pad.position.set(0, baseH + 0.0005, d * 0.3);
  g.add(pad);
  g.add(at(led(0.0025, '#3cf2a0'), w * 0.42, baseH + 0.001, d * 0.42));
  // side ports
  for (let i = 0; i < 2; i++) g.add(at(slab(0.004, 0.006, 0.014, 'rubber', { r: 0.001, bevel: 0.0005 }), w / 2 + 0.0005, baseH * 0.5, -0.02 + i * 0.03, 0, Math.PI / 2));
  // hinge and lid with bezel and screen
  const hinge = new T.Group();
  hinge.position.set(0, baseH, -d / 2 + 0.008);
  hinge.add(at(cyl(0.008, 0.008, w * 0.7, 'metal', { seg: 16 }), 0, 0, 0, 0, 0, Math.PI / 2));
  const lid = new T.Group();
  const lidD = d * 0.98;
  const back = slab(w, lidD, 0.012, shell === 'plasticDark' ? 'plastic' : shell, { r: 0.018, bevel: 0.005 });
  back.position.set(0, lidD / 2, 0.006);
  lid.add(back);
  const bezel = slab(w * 0.97, lidD * 0.95, 0.002, 'rubber', { r: 0.012, bevel: 0.0008 });
  bezel.position.set(0, lidD / 2, 0.0125);
  lid.add(bezel);
  const scr = screen(w * 0.9, lidD * 0.84, tex);
  scr.position.set(0, lidD / 2 + 0.004, 0.0137);
  scr.name = 'screen';
  lid.add(scr);
  lid.add(at(ball(0.0018, 'rubber'), 0, lidD * 0.965, 0.0137));          // camera dot
  // the lid stands up at open = π/2 and leans back beyond that
  lid.rotation.x = -(open - Math.PI / 2);
  hinge.add(lid);
  g.add(hinge);
  g.userData.screen = scr;
  g.userData.lid = lid;
  return g;
}

// ---------------------------------------------------------------- operator workstation: tower, monitor on a stand, keyboard, mouse
export function workstation({ tex = scadaScreen(), monitors = 1 } = {}) {
  const g = new T.Group();
  g.name = 'workstation';
  // monitor(s)
  for (let i = 0; i < monitors; i++) {
    const mon = new T.Group();
    const W = 0.6, H = 0.36;
    const shellM = slab(W, H, 0.035, 'plastic', { r: 0.015, bevel: 0.006 });
    mon.add(shellM);
    const sc = screen(W * 0.94, H * 0.89, tex);
    sc.position.set(0, 0.006, 0.0182);
    mon.add(sc);
    mon.add(at(slab(0.12, 0.06, 0.03, 'plastic', { r: 0.01, bevel: 0.004 }), 0, -0.02, -0.03));
    mon.add(at(cyl(0.018, 0.022, 0.2, 'metal', { seg: 20 }), 0, -0.27, -0.05));
    mon.add(at(lathe([[0, 0], [0.12, 0], [0.13, 0.006], [0.11, 0.016], [0, 0.018]], 'plastic', { seg: 36 }), 0, -0.375, -0.05));
    mon.position.set((i - (monitors - 1) / 2) * 0.64, 0.375, 0);
    if (monitors > 1) mon.rotation.y = (i - (monitors - 1) / 2) * -0.25;
    g.add(mon);
    if (i === 0) g.userData.screen = sc;
  }
  // keyboard: a low wedge with keys as a texture-free instanced grid
  const kb = new T.Group();
  const plate = slab(0.44, 0.15, 0.018, 'plastic', { r: 0.01, bevel: 0.004 });
  plate.rotation.x = -Math.PI / 2 + 0.06;
  kb.add(plate);
  const keyGeo = new T.ExtrudeGeometry(rrectShape(0.022, 0.022, 0.004), { depth: 0.004, bevelEnabled: true, bevelThickness: 0.0015, bevelSize: 0.0015, bevelSegments: 2, curveSegments: 4 });
  const keys = new T.InstancedMesh(keyGeo, undefined, 6 * 16);
  const m4 = new T.Matrix4(), q = new T.Quaternion().setFromEuler(new T.Euler(-Math.PI / 2 + 0.06, 0, 0));
  let n = 0;
  for (let r = 0; r < 5; r++) for (let c = 0; c < 15; c++) { m4.compose(new T.Vector3(-0.195 + c * 0.0275 + (r % 2) * 0.006, 0.012 + r * 0.0016, -0.052 + r * 0.026), q, new T.Vector3(1, 1, 1)); keys.setMatrixAt(n++, m4); }
  keys.count = n;
  tag(keys, 'plasticLight', { noEdges: true, noOutline: true });
  kb.add(keys);
  kb.position.set(0, 0.01, 0.32);
  g.add(kb);
  // mouse: a lathe-like rounded shell, squashed
  const mouse = lathe([[0, 0], [0.028, 0.0], [0.03, 0.01], [0.022, 0.024], [0, 0.03]], 'plastic', { seg: 28 });
  mouse.scale.set(1, 1, 1.6);
  mouse.position.set(0.3, 0, 0.33);
  g.add(mouse);
  // tower on the floor beside the desk (the desk itself is part of the scene)
  const tower = new T.Group();
  tower.add(at(slab(0.2, 0.44, 0.45, 'plastic', { r: 0.02, bevel: 0.008 }), 0, 0.22, 0, 0, Math.PI / 2));
  const front = slab(0.18, 0.4, 0.01, 'plasticLight', { r: 0.012, bevel: 0.003 });
  front.position.set(0, 0.22, 0.226);
  tower.add(front);
  for (let i = 0; i < 6; i++) tower.add(at(slab(0.14, 0.008, 0.004, 'rubber', { r: 0.002, bevel: 0.001 }), 0, 0.1 + i * 0.022, 0.232));
  tower.add(at(cyl(0.012, 0.012, 0.006, 'metal', { seg: 20 }), 0, 0.38, 0.232, Math.PI / 2));
  tower.add(at(led(0.004, '#3cf2a0'), 0.05, 0.38, 0.233));
  for (let i = 0; i < 2; i++) tower.add(at(slab(0.016, 0.007, 0.006, 'rubber', { r: 0.001, bevel: 0.0005 }), -0.04 + i * 0.03, 0.34, 0.232));
  tower.position.set(0.55, -0.74, 0.05);
  g.add(tower);
  return g;
}

// a desk: top with rounded front edge on four legs
export function desk({ w = 1.5, d = 0.75, h = 0.74, top = 'paintLight' } = {}) {
  const g = new T.Group();
  const t = slab(w, d, 0.035, top, { r: 0.02, bevel: 0.008 });
  t.rotation.x = -Math.PI / 2; t.position.y = h;
  g.add(t);
  for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) g.add(at(cyl(0.022, 0.022, h - 0.02, 'metal', { seg: 16 }), x * (w / 2 - 0.06), (h - 0.02) / 2, z * (d / 2 - 0.06)));
  g.add(at(slab(w - 0.12, 0.25, 0.012, 'paintDark', { r: 0.01, bevel: 0.003 }), 0, h - 0.16, -d / 2 + 0.06));
  return g;
}

// ---------------------------------------------------------------- USB stick
// a rounded body with a grip, a metal plug with its two windows, an activity light and a key-ring loop
export function usbStick({ on = true, body = 'plastic', capOff = true } = {}) {
  const g = new T.Group();
  g.name = 'usb';
  const L = 0.06, W = 0.02, H = 0.009;
  const b = slab(L, W, H, body, { r: 0.008, bevel: 0.0025 });
  b.rotation.x = -Math.PI / 2;
  g.add(b);
  // grip ridges
  for (let i = 0; i < 5; i++) g.add(at(slab(0.0025, W * 0.7, 0.0012, 'rubber', { r: 0.0008, bevel: 0.0003 }), -0.018 + i * 0.0045, H / 2 + 0.0004, 0, -Math.PI / 2));
  // metal plug: an open sleeve (lathe-free: a rounded tube made by extruding a rectangle with a rectangular hole)
  const sleeveShape = rrectShape(0.0122, 0.0046, 0.0006);
  const hole = rrectShape(0.0112, 0.0036, 0.0004);
  sleeveShape.holes.push(hole);
  const sleeve = extrude(sleeveShape, 0.013, 'metal', { bevel: 0.0002, curve: 4 });
  sleeve.rotation.y = Math.PI / 2;
  sleeve.position.set(L / 2 + 0.0065, 0, 0);
  g.add(sleeve);
  // the tongue inside and the two square windows on top
  g.add(at(slab(0.012, 0.0094, 0.0016, 'plasticLight', { r: 0.0004, bevel: 0.0002 }), L / 2 + 0.0065, -0.0006, 0, -Math.PI / 2));
  for (const z of [-0.0028, 0.0028]) { const win = slab(0.0026, 0.0026, 0.0006, 'rubber', { r: 0.0002, bevel: 0.0001 }); win.userData.noOutline = true; win.userData.noEdges = true; g.add(at(win, L / 2 + 0.008, 0.0023, z, -Math.PI / 2)); }
  // activity light and key-ring loop
  const l = led(0.0016, '#ffb347', { on });
  l.position.set(L * 0.28, H / 2 + 0.0002, W * 0.25);
  g.add(l);
  g.userData.led = l;
  g.userData.plug = sleeve;
  g.add(at(torus(0.0055, 0.0014, 'metal', { seg: 24, tube: 8 }), -L / 2 - 0.004, 0, 0, Math.PI / 2));
  g.scale.setScalar(1);
  return g;
}

// ---------------------------------------------------------------- PLC rack
// a mounting rail with modules side by side: power supply, CPU (with mode lights and a key switch), communication modules (with bus
// connectors and cables), input/output modules (with terminal blocks and wires). Generic: no maker's name or logo.
export function plcRack({ modules = ['PS', 'CPU', 'CP', 'CP', 'IO', 'IO', 'IO'], lights = 'run', glowModule = -1, cables = true } = {}) {
  const g = new T.Group();
  g.name = 'plc';
  const MH = 0.125, MD = 0.12;
  const widths = { PS: 0.05, CPU: 0.04, CP: 0.04, IO: 0.04 };
  const total = modules.reduce((s, m) => s + widths[m] + 0.002, 0);
  // rail and back plate
  g.add(at(slab(total + 0.08, 0.16, 0.012, 'paintDark', { r: 0.006, bevel: 0.002 }), 0, 0, -MD / 2 - 0.006));
  g.add(at(slab(total + 0.06, 0.035, 0.008, 'metal', { r: 0.003, bevel: 0.0015 }), 0, -0.02, -MD / 2 + 0.002));
  let x = -total / 2;
  const names = { PS: '电源', CPU: '控制器', CP: '通信', IO: '输入输出' };
  const leds = [];
  modules.forEach((m, i) => {
    const w = widths[m];
    const mod = new T.Group();
    const body = slab(w, MH, MD, i === glowModule ? 'hot' : 'paintLight', { r: 0.004, bevel: 0.0015 });
    mod.add(body);
    // front cover with a hinged flap line and a label strip
    const face = screen(w * 0.5, MH * 0.62, moduleFace(names[m]));
    face.userData.slot = 'paper';
    face.position.set(-w * 0.18, -0.01, MD / 2 + 0.0008);
    mod.add(face);
    mod.add(at(slab(w * 0.86, 0.004, 0.003, 'paintDark', { r: 0.001, bevel: 0.0005 }), 0, MH * 0.36, MD / 2 + 0.001));
    // lights column
    const n = m === 'IO' ? 8 : m === 'CPU' ? 5 : 3;
    for (let k = 0; k < n; k++) {
      let color = '#33dd66', on = true;
      if (m === 'CPU') color = ['#33dd66', '#e9b923', '#e8473a', '#33dd66', '#e9b923'][k];
      if (m === 'CPU') on = lights === 'run' ? (k === 0 || k === 3) : lights === 'fault' ? k === 2 : true;
      if (m === 'IO') on = (k * 7 + i) % 3 !== 0;
      if (m === 'CP') color = '#33dd66';
      const l = led(0.0022, color, { on });
      l.position.set(w * 0.3, MH * 0.3 - k * (m === 'IO' ? 0.011 : 0.014), MD / 2 + 0.002);
      mod.add(l);
      leds.push(l);
    }
    if (m === 'CPU') {
      // key switch and a memory card slot
      mod.add(at(cyl(0.007, 0.007, 0.004, 'metal', { seg: 20 }), 0, -MH * 0.32, MD / 2 + 0.002, Math.PI / 2));
      mod.add(at(slab(0.0025, 0.009, 0.002, 'paintDark', { r: 0.0005, bevel: 0.0003 }), 0, -MH * 0.32, MD / 2 + 0.0045));
      mod.add(at(slab(w * 0.6, 0.004, 0.003, 'rubber', { r: 0.001, bevel: 0.0004 }), 0, -MH * 0.44, MD / 2 + 0.001));
    }
    if (m === 'CP' && cables) {
      // a bus plug (D-shaped) with a violet cable going down
      mod.add(at(slab(0.018, 0.03, 0.016, 'plastic', { r: 0.003, bevel: 0.0015 }), 0, -MH * 0.2, MD / 2 + 0.008));
      mod.add(pipe([[0, -MH * 0.2 - 0.015, MD / 2 + 0.012], [0, -MH * 0.5 - 0.02, MD / 2 + 0.02], [0.01 * (i % 2 ? 1 : -1), -0.25, MD / 2 + 0.05]], 0.0045, 'cableBlue', { bend: 0.03 }));
    }
    if (m === 'IO' && cables) {
      for (let k = 0; k < 6; k++) {
        const y = MH * 0.18 - k * 0.016;
        mod.add(at(slab(0.008, 0.008, 0.006, 'metal', { r: 0.001, bevel: 0.0005 }), -w * 0.1, y, MD / 2 + 0.003));
        mod.add(pipe([[-w * 0.1, y, MD / 2 + 0.006], [-w * 0.1, y - 0.004, MD / 2 + 0.02], [-w * 0.12 + k * 0.0012, -0.2, MD / 2 + 0.03]], 0.0017, k % 2 ? 'cableRed' : 'cableBlue', { bend: 0.02, radial: 6 }));
      }
    }
    mod.position.x = x + w / 2;
    x += w + 0.002;
    g.add(mod);
  });
  g.userData.leds = leds;
  g.userData.width = total;
  return g;
}

// a control cabinet that holds the PLC rack (a steel box with an open door)
export function cabinet({ w = 0.6, h = 1.0, d = 0.3, doorOpen = 1.9, slot = 'paintLight' } = {}) {
  const g = new T.Group();
  const back = slab(w, h, 0.02, slot, { r: 0.01, bevel: 0.004 });
  back.position.set(0, h / 2, -d / 2);
  g.add(back);
  for (const sx of [-1, 1]) g.add(at(slab(0.02, h, d, slot, { r: 0.006, bevel: 0.003 }), sx * (w / 2 - 0.01), h / 2, 0));
  g.add(at(slab(w, 0.02, d, slot, { r: 0.006, bevel: 0.003 }), 0, h - 0.01, 0));
  g.add(at(slab(w, 0.02, d, slot, { r: 0.006, bevel: 0.003 }), 0, 0.01, 0));
  const door = new T.Group();
  door.position.set(-w / 2, h / 2, d / 2);
  const panel = slab(w, h, 0.02, slot, { r: 0.01, bevel: 0.004 });
  panel.position.set(w / 2, 0, 0.01);
  door.add(panel);
  door.add(at(slab(0.02, 0.1, 0.02, 'paintDark', { r: 0.005, bevel: 0.002 }), w - 0.05, 0, 0.03));
  door.rotation.y = -doorOpen;
  g.add(door);
  return g;
}

// ---------------------------------------------------------------- drive cabinet (frequency converter)
// a tall steel cabinet: louvred vents, a display window showing the output frequency, a small keypad, a warning sign, cable glands
export function vfdCabinet({ hz = '1064', color = '#ff5a3c', w = 0.5, h = 1.4, d = 0.4, warn = true } = {}) {
  const g = new T.Group();
  g.name = 'vfd';
  g.add(at(slab(w, h, d, 'paint', { r: 0.02, bevel: 0.008 }), 0, h / 2 + 0.06, 0));
  g.add(at(slab(w + 0.02, 0.06, d + 0.02, 'paintDark', { r: 0.01, bevel: 0.004 }), 0, 0.03, 0));            // plinth
  g.add(at(slab(w * 0.94, h * 0.97, 0.006, 'paintLight', { r: 0.016, bevel: 0.002 }), 0, h / 2 + 0.06, d / 2 + 0.002)); // door
  // louvres
  for (let i = 0; i < 7; i++) {
    const y = 0.2 + i * 0.035;
    const lv = slab(w * 0.6, 0.012, 0.02, 'paintDark', { r: 0.004, bevel: 0.002 });
    lv.position.set(0, y, d / 2 + 0.01);
    lv.rotation.x = -0.5;
    g.add(lv);
  }
  // display window and keypad
  const disp = screen(w * 0.56, w * 0.22, vfdDisplay(hz, 'Hz', { color }));
  disp.position.set(0, h * 0.78, d / 2 + 0.0105);
  g.add(disp);
  g.add(at(slab(w * 0.64, w * 0.3, 0.012, 'plastic', { r: 0.01, bevel: 0.003 }), 0, h * 0.78, d / 2 + 0.002));
  for (let i = 0; i < 4; i++) g.add(at(cyl(0.012, 0.012, 0.008, i === 3 ? 'stamp' : 'plasticLight', { seg: 16 }), -0.075 + i * 0.05, h * 0.66, d / 2 + 0.008, Math.PI / 2));
  // door handle and lock
  g.add(at(slab(0.025, 0.12, 0.02, 'metal', { r: 0.008, bevel: 0.003 }), w * 0.38, h * 0.52, d / 2 + 0.015));
  // warning triangle (generic high-voltage mark)
  if (warn) {
    const tri = new T.Shape(); tri.moveTo(0, 0.05); tri.lineTo(0.045, -0.03); tri.lineTo(-0.045, -0.03); tri.closePath();
    const sign = extrude(tri, 0.004, 'warn', { bevel: 0.001 });
    sign.position.set(0, h * 0.45, d / 2 + 0.006);
    g.add(sign);
    const bolt = new T.Shape(); bolt.moveTo(0.006, 0.03); bolt.lineTo(-0.008, -0.002); bolt.lineTo(0.002, -0.002); bolt.lineTo(-0.006, -0.024); bolt.lineTo(0.01, 0.004); bolt.lineTo(0.0, 0.004); bolt.closePath();
    const bm = extrude(bolt, 0.002, 'rubber', { bevel: 0.0005 });
    bm.position.set(0, h * 0.45, d / 2 + 0.0095);
    g.add(bm);
  }
  // cables out of the top
  for (let i = 0; i < 3; i++) g.add(pipe([[-0.12 + i * 0.12, h + 0.06, 0], [-0.12 + i * 0.12, h + 0.3, 0], [-0.12 + i * 0.12, h + 0.36, -0.2]], 0.018, 'cable', { bend: 0.08 }));
  g.userData.display = disp;
  return g;
}

// a small desktop computer: monitor on a stand with a coloured screen (one per ~1000 infected hosts on page 1)
const tint = new Map();
function tintTex(color) {
  if (!tint.has(color)) tint.set(color, canvasTex(64, 40, (g, w, h) => { g.fillStyle = color; g.fillRect(0, 0, w, h); g.fillStyle = 'rgba(255,255,255,0.35)'; g.fillRect(4, 4, w * 0.5, 5); g.fillRect(4, 12, w * 0.7, 4); g.fillRect(4, 19, w * 0.4, 4); }));
  return tint.get(color);
}
export function miniPC({ color = '#8a94a3', lit = false } = {}) {
  const g = new T.Group();
  const mon = slab(0.1, 0.066, 0.01, 'plastic', { r: 0.006, bevel: 0.002 });
  mon.position.y = 0.075;
  g.add(mon);
  const sc = screen(0.092, 0.056, tintTex(lit ? color : '#5b6573'));
  sc.position.set(0, 0.076, 0.0052);
  g.add(sc);
  g.add(at(cyl(0.006, 0.008, 0.04, 'metal', { seg: 10 }), 0, 0.025, -0.002));
  g.add(at(lathe([[0, 0], [0.03, 0], [0.032, 0.003], [0.026, 0.007], [0, 0.008]], 'plastic', { seg: 20 }), 0, 0, -0.002));
  g.add(at(slab(0.09, 0.03, 0.006, 'plasticLight', { r: 0.004, bevel: 0.0015 }), 0, 0.004, 0.045, -Math.PI / 2 + 0.08));
  g.userData.screen = sc;
  return g;
}
