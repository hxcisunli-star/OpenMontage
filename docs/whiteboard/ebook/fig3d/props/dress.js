// Dress a prop for the e-book's 3D figures: every material slot becomes a flat, theme-coloured material (book.css variables through
// stage.themedMaterial, so light and dark themes follow), with a thin ink edge line. Screens keep their pictures; lights stay lit.
// A book with its own look (e.g. projects/stuxnet-livebook-cn) dresses the same props with its own materials instead.
import { MeshLambertMaterial, MeshBasicMaterial, LineSegments, EdgesGeometry, LineBasicMaterial, DoubleSide, Color } from 'three';

// slot -> book.css variable
export const SLOT_THEME = {
  paint: 'note-bg', paintDark: 'fg-2', paintLight: 'surface', metal: 'line-strong', alu: 'line', rubber: 'fg', plastic: 'fg-2', plasticLight: 'surface',
  concrete: 'line', floor: 'note-bg', pipe: 'line-strong', copper: 'pick', paper: 'surface', stamp: 'red', cable: 'fg', cableRed: 'red', cableBlue: 'accent',
  warn: 'hl', glass: 'model', cutFace: 'pick', hot: 'red', virus: 'good', ghost: 'model', earth: 'user', rock: 'line-strong', good: 'good',
};

export function dressForBook(stage, root, { edges = true } = {}) {
  const cache = new Map();
  const ink = () => stage.themedMaterial(new LineBasicMaterial({ transparent: true, opacity: 0.7 }), 'fg');
  const meshes = [];
  root.traverse((o) => { if (o.isMesh && o.userData.slot) meshes.push(o); });
  for (const o of meshes) {
    const ud = o.userData, slot = ud.slot;
    let m;
    if (slot === 'screen') m = new MeshBasicMaterial({ map: ud.map || null });
    else if (slot === 'led') m = new MeshBasicMaterial({ color: new Color(ud.color || '#33dd66').multiplyScalar(ud.on === false ? 0.25 : 1) });
    else {
      const key = slot + '|' + (ud.color || '') + (ud.cut ? '|c' : '');
      m = cache.get(key);
      if (!m) {
        m = new MeshLambertMaterial();
        if (ud.color) m.color.set(ud.color); else stage.themedMaterial(m, SLOT_THEME[slot] || 'surface');
        if (ud.cut) m.side = DoubleSide;
        if (slot === 'glass' || slot === 'ghost') { m.transparent = true; m.opacity = 0.4; m.depthWrite = false; }
        cache.set(key, m);
      }
    }
    o.material = m;
    if (edges && !ud.noEdges && !ud.noOutline && slot !== 'screen' && slot !== 'led' && !o.isInstancedMesh) o.add(new LineSegments(new EdgesGeometry(o.geometry, 35), ink()));
  }
  stage.invalidate();
  return root;
}
