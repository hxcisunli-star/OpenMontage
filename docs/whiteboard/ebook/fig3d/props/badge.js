// A certificate (a code-signing certificate, an ID) drawn as a stamped pass on a lanyard. The face is generic (no real company name or logo):
// the page's DOM text names the companies.
import * as T from 'three';
import { slab, torus, pipe, screen, extrude, cyl, at, tag } from './kit.js';
import { passFace } from './screens.js';

function starShape(R, r, n = 5) {
  const s = new T.Shape();
  for (let i = 0; i < n * 2; i++) {
    const a = Math.PI / 2 + i * Math.PI / n, rr = i % 2 ? r : R;
    const x = Math.cos(a) * rr, y = Math.sin(a) * rr;
    if (i) s.lineTo(x, y); else s.moveTo(x, y);
  }
  s.closePath();
  return s;
}

export function pass({ who = '甲', revoked = false, tone = '#1D4F8F', strap = true, strapLen = 0.22, face = {} } = {}) {
  const g = new T.Group();
  g.name = 'pass';
  const W = 0.096, H = 0.06;
  const card = slab(W, H, 0.0016, 'paper', { r: 0.005, bevel: 0.0005 });
  g.add(card);
  const faceMesh = screen(W * 0.97, H * 0.95, passFace({ who, revoked, tone, ...face }));
  faceMesh.userData.slot = 'screen';
  faceMesh.position.z = 0.0009;
  g.add(faceMesh);
  // the red stamp: a raised ring with a star, pressed over the corner of the card
  const ring = new T.Shape(); ring.absarc(0, 0, 0.012, 0, Math.PI * 2, false);
  const hole = new T.Path(); hole.absarc(0, 0, 0.0095, 0, Math.PI * 2, true); ring.holes.push(hole);
  const stampG = new T.Group();
  stampG.add(extrude(ring, 0.0008, 'stamp', { bevel: 0.0002 }));
  stampG.add(extrude(starShape(0.007, 0.003), 0.0008, 'stamp', { bevel: 0.0002 }));
  stampG.position.set(W * 0.32, -H * 0.18, 0.0016);
  stampG.rotation.z = -0.3;
  g.add(stampG);
  // clip, slot and strap
  g.add(at(slab(0.012, 0.0028, 0.0018, 'rubber', { r: 0.0012, bevel: 0.0004 }), 0, H * 0.445, 0.0005));
  g.add(at(torus(0.004, 0.0009, 'metal', { seg: 20, tube: 6 }), 0, H / 2 + 0.004, 0));
  g.add(at(cyl(0.0035, 0.0035, 0.01, 'metal', { seg: 12 }), 0, H / 2 + 0.011, 0));
  if (strap) {
    const s = pipe([[0, H / 2 + 0.016, 0], [-0.02, H / 2 + strapLen * 0.6, -0.01], [0, H / 2 + strapLen, -0.02]], 0.0025, 'cableBlue', { smooth: true, radial: 8 });
    s.scale.z = 0.5;
    g.add(s);
  }
  g.userData.stamp = stampG;
  g.userData.face = faceMesh;
  return g;
}
