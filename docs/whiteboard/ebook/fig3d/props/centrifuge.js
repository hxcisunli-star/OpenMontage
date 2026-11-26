// A gas centrifuge in the shape of the IR-1 family as described in public reports (tall, slender casing; a metal rotor
// spinning inside; its own motor at the bottom; gas pipes at the top). Proportions are schematic (示意), not an engineering drawing.
import * as T from 'three';
import { lathe, cyl, torus, slab, pipe, group, at, tag, TAU } from './kit.js';

const H = 1.82;          // casing top (metres, schematic)

// cut: open the front quarter of the casing to show the rotor. rotor: angle of the rotor (radians), for the spin.
// lod 1: a lighter version for machines seen from far away (fewer segments; no bolts, valves or rotor rings; the same outline)
export function centrifuge({ cut = false, rotor = 0, valves = true, tilt = 0, glowRotor = false, lod = 0 } = {}) {
  const g = new T.Group();
  const sg = (n) => (lod ? Math.max(10, Math.round(n / 3)) : n);
  if (lod) valves = false;
  g.name = 'centrifuge';
  // foot plate on the floor
  g.add(lathe([[0, 0], [0.17, 0], [0.18, 0.012], [0.17, 0.028], [0.1, 0.034], [0.09, 0.05], [0, 0.05]], 'paintDark'));
  // motor housing with cooling fins (the drive sits under each centrifuge)
  const fins = [[0, 0.05], [0.112, 0.05]];
  for (let y = 0.06; y < 0.21; y += lod ? 0.05 : 0.022) fins.push([0.112, y], [0.124, y + 0.004], [0.124, y + 0.012], [0.112, y + 0.016]);
  fins.push([0.112, 0.225], [0.1, 0.235], [0, 0.235]);
  g.add(lathe(fins, 'paintDark', { seg: sg(48) }));
  // power lead to the motor
  g.add(pipe([[0.12, 0.12, 0], [0.22, 0.1, 0], [0.26, 0.02, 0.04], [0.4, 0.012, 0.06]], 0.012, 'cable', lod ? { bend: 0.05, seg: 8, radial: 5 } : { bend: 0.05 }));

  // casing: bottom flange, long tube, a clamp ring at mid height, top flange
  const casing = [[0.0, 0.235], [0.115, 0.235], [0.115, 0.27], [0.092, 0.275], [0.09, 0.29], [0.09, 0.98], [0.1, 0.985], [0.1, 1.035], [0.09, 1.04],
    [0.09, H - 0.06], [0.112, H - 0.055], [0.112, H - 0.015], [0.08, H - 0.01], [0.0, H - 0.01]];
  const phiStart = Math.PI / 4, phiLength = cut ? TAU * 0.75 : TAU;        // the open quarter faces +z (the camera)
  const shell = lathe(casing, 'paint', { seg: sg(96), phiStart, phiLength });
  shell.name = 'casing';
  g.add(shell);
  if (cut) {
    // inside of the shell, and the cut faces in the cut-away colour
    g.add(lathe([[0.083, 0.29], [0.083, H - 0.06]], 'paintLight', { seg: sg(64), phiStart, phiLength, extra: { cut: true, noEdges: true } }));
    for (const phi of [phiStart, phiStart + phiLength]) {
      const face = new T.Mesh(new T.PlaneGeometry(0.008, H - 0.35));
      tag(face, 'cutFace', { noOutline: true });
      face.position.set(Math.sin(phi) * 0.0865, (0.29 + H - 0.06) / 2, Math.cos(phi) * 0.0865);
      face.rotation.y = phi + Math.PI / 2;
      face.userData.cut = true;
      g.add(face);
    }
  }

  // bolts round the bottom and top flanges (instanced little hex heads)
  const boltGeo = new T.CylinderGeometry(0.0075, 0.0075, 0.012, 6);
  for (const [y, r] of lod ? [] : [[0.268, 0.104], [H - 0.012, 0.101]]) {
    const n = 12, bolts = new T.InstancedMesh(boltGeo, undefined, n), m4 = new T.Matrix4();
    for (let i = 0; i < n; i++) { const a = i / n * TAU + 0.13; m4.makeTranslation(Math.sin(a) * r, y, Math.cos(a) * r); bolts.setMatrixAt(i, m4); }
    tag(bolts, 'metal', { noEdges: true, noOutline: true });
    g.add(bolts);
  }
  if (!cut && !lod) {
    const plate = slab(0.07, 0.045, 0.004, 'plasticLight', { r: 0.004, bevel: 0.001 });
    plate.position.set(0, 0.72, 0.091); g.add(plate);
    for (let i = 0; i < 3; i++) { const l = slab(0.05 - i * 0.01, 0.004, 0.001, 'paintDark', { r: 0.001, bevel: 0.0003 }); l.userData.noOutline = true; l.position.set(-0.008 + i * 0.004, 0.73 - i * 0.01, 0.0935); g.add(l); }
    const port = group(at(cyl(0.012, 0.012, 0.05, 'metal', { seg: 16 }), 0.105, 0.4, 0, 0, 0, Math.PI / 2), at(cyl(0.02, 0.02, 0.008, 'metal', { seg: 20 }), 0.13, 0.4, 0, 0, 0, Math.PI / 2));
    g.add(port);
  }

  // rotor: a long thin metal tube with end caps and bellows rings, on a bearing pin at the bottom and a magnet ring at the top
  const rot = new T.Group();
  rot.name = 'rotor';
  const rp = [[0, 0.31], [0.062, 0.31], [0.066, 0.32], [0.066, H - 0.13], [0.062, H - 0.12], [0, H - 0.12]];
  rot.add(lathe(rp, glowRotor ? 'hot' : 'alu', { seg: sg(48) }));
  for (const y of lod ? [] : [0.66, 1.0, 1.34]) rot.add(at(torus(0.067, 0.006, 'metal', { seg: 48, tube: 8 }), 0, y, 0, Math.PI / 2));
  // two marks on the rotor so its turning can be seen
  for (const a of [0, Math.PI]) {
    const m = tag(new T.Mesh(new T.BoxGeometry(0.012, H - 0.5, 0.004)), 'paintDark', { noEdges: true });
    m.position.set(Math.sin(a) * 0.067, (0.32 + H - 0.13) / 2, Math.cos(a) * 0.067);
    m.rotation.y = a;
    rot.add(m);
  }
  rot.rotation.y = rotor;
  g.add(rot);
  g.add(at(cyl(0.006, 0.018, 0.06, 'metal', { seg: 16 }), 0, 0.27, 0));                 // bearing pin
  if (!lod) g.add(at(torus(0.05, 0.008, 'copper', { seg: 40, tube: 8 }), 0, H - 0.09, 0, Math.PI / 2)); // top magnet ring

  // top: a small manifold with three gas lines (feed, product, tails) going up to the cascade headers, each with a valve
  const top = new T.Group();
  top.position.y = H;
  top.add(at(lathe([[0, 0], [0.07, 0], [0.075, 0.01], [0.06, 0.06], [0, 0.065]], 'metal', { seg: 36 }), 0, -0.01, 0));
  const lines = [[-0.035, 0.0], [0.0, 0.035], [0.035, 0.0]];
  const valveBodies = [];
  lines.forEach(([x, z], i) => {
    top.add(pipe([[x * 0.6, 0.05, z * 0.6], [x, 0.14, z], [x, 0.34 + i * 0.05, z]], 0.011, 'pipe', lod ? { bend: 0.05, seg: 8, radial: 5 } : { bend: 0.05 }));
    if (valves) {
      const vy = 0.2 + i * 0.02;
      const body = at(cyl(0.02, 0.02, 0.04, 'paintDark', { seg: 20 }), x, vy, z);
      valveBodies.push(body);
      top.add(body);
      top.add(at(cyl(0.005, 0.005, 0.04, 'metal', { seg: 8 }), x, vy + 0.03, z));
      top.add(at(torus(0.02, 0.004, 'stamp', { seg: 24, tube: 6 }), x, vy + 0.05, z, Math.PI / 2));
      for (let k = 0; k < 3; k++) { const sp = cyl(0.0018, 0.0018, 0.038, 'stamp', { seg: 6 }); sp.position.set(x, vy + 0.05, z); sp.rotation.set(Math.PI / 2, 0, k * Math.PI / 3); sp.rotateX(Math.PI / 2); top.add(sp); }
    }
  });
  g.add(top);
  g.rotation.z = tilt;
  g.userData.rotor = rot;
  g.userData.valves = valveBodies;
  g.userData.height = H + 0.4;
  return g;
}

// one stretch of a cascade: rows of centrifuges on a floor, with header pipes along each row (number of machines simplified)
export function cascade({ rows = 4, cols = 10, dx = 0.5, dz = 0.62, cutAt = null, rotor = 0, hot = [], lod = 0 } = {}) {
  const g = new T.Group();
  g.name = 'cascade';
  const x0 = -((cols - 1) * dx) / 2, z0 = -((rows - 1) * dz) / 2;
  const machines = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const isCut = cutAt && cutAt[0] === r && cutAt[1] === c;
      const isHot = hot.some(([a, b]) => a === r && b === c);
      const m = centrifuge({ cut: isCut, rotor: rotor + (r * 7 + c) * 0.37, valves: true, glowRotor: isHot, lod });
      m.position.set(x0 + c * dx, 0, z0 + r * dz);
      m.userData.rc = [r, c];
      g.add(m);
      machines.push(m);
    }
    // header pipes over the row: three lines (feed, product, tails)
    for (let i = 0; i < 3; i++) {
      const z = z0 + r * dz + [-0.035, 0.035, 0.0][i];
      const x1 = x0 - 0.3, x2 = x0 + (cols - 1) * dx + 0.3, y = H + 0.34 + i * 0.05;
      g.add(pipe([[x1, y, z], [x2, y, z]], 0.016, 'pipe', lod ? { radial: 6, seg: 2 } : { radial: 16 }));
      for (let xx = x1 + 0.4; xx < x2 - 0.2; xx += 0.9) g.add(at(cyl(0.024, 0.024, 0.016, 'metal', { seg: 18 }), xx, y, z, 0, 0, Math.PI / 2));
    }
    // a walkway grating beside the row
    const walk = slab((cols - 1) * dx + 0.9, 0.03, 0.18, 'paintDark', { r: 0.01, bevel: 0.004 });
    walk.position.set(0, 0.015, z0 + r * dz + dz / 2);
    walk.rotation.x = 0;
    g.add(walk);
  }
  // supports for the headers at both ends of each row
  for (let r = 0; r < rows; r++) {
    for (const x of [x0 - 0.3, x0 + (cols - 1) * dx + 0.3]) {
      g.add(at(cyl(0.025, 0.03, H + 0.5, 'paintDark', { seg: 16 }), x, (H + 0.5) / 2, z0 + r * dz));
    }
  }
  g.userData.machines = machines;
  return g;
}
