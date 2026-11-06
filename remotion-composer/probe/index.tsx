/**
 * LayoutProbe — measures the REAL layout of a whiteboard lesson (docs/whiteboard_layout_check.py drives it).
 *
 * It is the unchanged `Explainer` plus an invisible <Probe/> that, on the frames listed in `props.probe.frames`, waits for the fonts, reads the DOM
 * boxes of everything drawn and prints one `@@LAYOUT {json}` console line.  Nothing here touches src/, so published renders and the chunk cache
 * fingerprint (hashed: src/, package files, fonts) are unaffected; this folder is neither hashed nor uploaded to the remote render machine.
 *
 * All coordinates are CSS px in the 1920x1080 viewport.
 */
import React, { useEffect } from "react";
import { CalculateMetadataFunction, Composition, continueRender, delayRender, registerRoot, useCurrentFrame } from "remotion";
import { Explainer } from "../src/Explainer";
import type { ExplainerProps } from "../src/Explainer";

type ProbeProps = ExplainerProps & { probe?: { frames: number[]; dump?: boolean } };
type Box = [number, number, number, number]; // x0, y0, x1, y1

const r1 = (n: number) => Math.round(n * 10) / 10;
const boxOf = (rc: DOMRect | { left: number; top: number; right: number; bottom: number }): Box => [r1(rc.left), r1(rc.top), r1(rc.right), r1(rc.bottom)];

// What the viewer actually sees of an element: product of opacity up the tree, 0 if any ancestor is display:none / visibility:hidden.
function effOpacity(el: Element): number {
  let o = 1;
  for (let e: Element | null = el; e; e = e.parentElement) {
    const cs = getComputedStyle(e);
    if (cs.display === "none" || cs.visibility === "hidden") return 0;
    o *= parseFloat(cs.opacity || "1");
  }
  return o;
}

// Handwriting reveals with clip-path: inset(-10% X% -10% 0); the share already drawn is 1 - X%.
function revealOf(el: Element): number {
  let p = 1;
  for (let e: Element | null = el; e; e = e.parentElement) {
    const m = /inset\(([^)]*)\)/.exec(getComputedStyle(e).clipPath || "");
    if (!m) continue;
    const parts = m[1].trim().split(/\s+/);
    const right = parseFloat(parts[1] ?? "0");
    if (!isNaN(right) && /%/.test(parts[1] ?? "")) p = Math.min(p, Math.max(0, Math.min(1, 1 - right / 100)));
  }
  return p;
}

function fontClass(ff: string): "hand" | "mono" | "other" {
  if (/WBHand/i.test(ff)) return "hand";
  if (/mono/i.test(ff)) return "mono";
  return "other";
}

interface TextOut { text: string; font: string; size: number; lines: number; box: Box; rects: Box[]; opacity: number; reveal: number }
interface ShapeOut { kind: string; box: Box; pts?: [number, number][]; sub?: number[]; closed?: boolean; filled?: boolean; stroked?: boolean; width?: number; opacity: number; reveal: number; bg?: string; fill?: string; alpha?: string; fillAlpha?: number }

// Which cells of a picture are opaque: a 32x32 grid over the picture's box as a string of "0"/"1" (row by row).  A character picture's box holds a lot of transparent corners, so the layout
// check asks the grid, not the box, whether a text is really covered.  Omitted when the browser will not let us read the pixels.
const ALPHA_GRID = 32;
function alphaGrid(img: HTMLImageElement): string | undefined {
  try {
    if (!img.complete || !img.naturalWidth) return undefined;
    const c = document.createElement("canvas");
    c.width = ALPHA_GRID;
    c.height = ALPHA_GRID;
    const g = c.getContext("2d");
    if (!g) return undefined;
    g.drawImage(img, 0, 0, ALPHA_GRID, ALPHA_GRID);
    const d = g.getImageData(0, 0, ALPHA_GRID, ALPHA_GRID).data;
    let out = "";
    for (let i = 0; i < ALPHA_GRID * ALPHA_GRID; i++) out += d[i * 4 + 3] > 40 ? "1" : "0";
    return out;
  } catch {
    return undefined;
  }
}

function collectText(root: Element, texts: TextOut[]) {
  const isSvg = (e: Element) => e instanceof SVGElement;
  const all = [root, ...Array.from(root.querySelectorAll("*"))];
  for (const el of all) {
    if (el instanceof SVGElement && el.tagName.toLowerCase() === "tspan") continue; // measured through its <text>
    let own = "";
    for (const n of Array.from(el.childNodes)) if (n.nodeType === 3 && n.nodeValue) own += n.nodeValue;
    const svgText = el instanceof SVGElement && el.tagName.toLowerCase() === "text";
    const text = svgText ? (el.textContent ?? "") : own;
    if (!text.trim()) continue;
    const cs = getComputedStyle(el);
    const rects: Box[] = [];
    if (svgText || isSvg(el)) {
      const rc = el.getBoundingClientRect();
      if (rc.width > 0 && rc.height > 0) rects.push(boxOf(rc));
    } else {
      for (const n of Array.from(el.childNodes)) {
        if (n.nodeType !== 3 || !n.nodeValue || !n.nodeValue.trim()) continue;
        const range = document.createRange();
        range.selectNodeContents(n);
        for (const rc of Array.from(range.getClientRects())) if (rc.width > 0 && rc.height > 0) rects.push(boxOf(rc));
      }
    }
    if (!rects.length) continue;
    const box: Box = [Math.min(...rects.map((b) => b[0])), Math.min(...rects.map((b) => b[1])), Math.max(...rects.map((b) => b[2])), Math.max(...rects.map((b) => b[3]))];
    const tops: number[] = [];
    for (const b of rects) if (!tops.some((t) => Math.abs(t - b[1]) < (b[3] - b[1]) * 0.5)) tops.push(b[1]);
    texts.push({
      text: text.replace(/\s+$/g, ""), font: fontClass(cs.fontFamily), size: parseFloat(cs.fontSize), lines: tops.length,
      box, rects, opacity: r1(effOpacity(el) * 1000) / 1000, reveal: revealOf(el),
    });
  }
}

// Points along the drawn part of a path, one run per subpath ("M ..." starts a new one: an arrow is a shaft plus a head subpath).  `sub[i]` is the subpath of pts[i].
function pathPoints(el: SVGGeometryElement, share: number): { pts: [number, number][]; sub: number[] } {
  const ctm = el.getScreenCTM();
  const pts: [number, number][] = [];
  const sub: number[] = [];
  if (!ctm) return { pts, sub };
  const d = el.getAttribute("d") ?? "";
  const parts = el.tagName.toLowerCase() === "path" && !/m/.test(d.replace(/M/g, "")) ? d.split(/(?=M)/).filter((s) => s.trim()) : [];
  const measure = (g: SVGGeometryElement, si: number) => {
    const len = g.getTotalLength();
    if (!(len > 0)) return;
    const n = Math.min(160, Math.max(4, Math.ceil(len / 8)));
    for (let i = 0; i <= n; i++) {
      const p = g.getPointAtLength((len * share * i) / n).matrixTransform(ctm);
      pts.push([r1(p.x), r1(p.y)]);
      sub.push(si);
    }
  };
  if (parts.length > 1) {
    parts.forEach((part, si) => {
      const c = el.cloneNode(false) as SVGGeometryElement;
      c.setAttribute("d", part);
      c.removeAttribute("style");
      el.parentNode!.appendChild(c);
      try { measure(c, si); } finally { c.remove(); }
    });
  } else {
    measure(el, 0);
  }
  return { pts, sub };
}

function collectShapes(root: Element, shapes: ShapeOut[]) {
  const all = [root, ...Array.from(root.querySelectorAll("*"))];
  for (const el of all) {
    const tag = el.tagName.toLowerCase();
    const cs = getComputedStyle(el);
    const opacity = r1(effOpacity(el) * 1000) / 1000;
    if (el instanceof SVGGeometryElement && ["path", "rect", "circle", "ellipse", "line", "polyline", "polygon"].includes(tag)) {
      const stroked = !!cs.stroke && cs.stroke !== "none" && parseFloat(cs.strokeWidth || "0") > 0;
      const filled = !!cs.fill && cs.fill !== "none" && !/rgba\([^)]*,\s*0\)$/.test(cs.fill) && cs.fill !== "transparent";
      if (!stroked && !filled) continue;
      const rc = el.getBoundingClientRect();
      if (!(rc.width > 0 || rc.height > 0)) continue;
      // Hand-drawn strokes use pathLength=1 + dasharray 1 + dashoffset (1 - progress): the drawn share is 1 - dashoffset.
      let reveal = 1;
      if (el.getAttribute("pathLength") === "1" && /^1(px)?$/.test((cs.strokeDasharray || "").trim())) reveal = Math.max(0, Math.min(1, 1 - parseFloat(cs.strokeDashoffset || "0")));
      const closed = tag === "rect" || tag === "circle" || tag === "ellipse" || tag === "polygon" || (tag === "path" && /z\s*$/i.test(el.getAttribute("d") ?? ""));
      const s: ShapeOut = { kind: tag, box: boxOf(rc), closed, filled, stroked, width: parseFloat(cs.strokeWidth || "0"), opacity, reveal, fill: cs.fill, fillAlpha: parseFloat(cs.fillOpacity || "1") };
      if (tag === "path" || tag === "line" || tag === "polyline") {
        const pp = pathPoints(el, reveal);
        s.pts = pp.pts;
        s.sub = pp.sub;
      }
      shapes.push(s);
    } else if (el instanceof HTMLImageElement) {
      const rc = el.getBoundingClientRect();
      if (rc.width > 0 && rc.height > 0) shapes.push({ kind: "image", box: boxOf(rc), closed: true, filled: true, opacity, reveal: revealOf(el), alpha: alphaGrid(el) });
    } else if (el instanceof HTMLElement) {
      const bw = parseFloat(cs.borderTopWidth || "0") * (cs.borderTopStyle === "none" ? 0 : 1);
      // A background only counts when it is actually visible (decorative particle layers carry almost transparent colours).
      const m = /rgba?\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*(?:,\s*([\d.]+))?\s*\)/.exec(cs.backgroundColor || "");
      const alpha = m ? (m[1] === undefined ? 1 : parseFloat(m[1])) : 0;
      const hasBg = alpha >= 0.15;
      if (hasBg || bw > 0) {
        const rc = el.getBoundingClientRect();
        if (rc.width > 0 && rc.height > 0) shapes.push({ kind: "panel", box: boxOf(rc), closed: true, filled: hasBg, stroked: bw > 0, opacity, reveal: revealOf(el), bg: cs.backgroundColor, fillAlpha: alpha } as ShapeOut);
      }
    }
  }
}

function unionBox(rects: Box[]): Box | null {
  if (!rects.length) return null;
  return [Math.min(...rects.map((b) => b[0])), Math.min(...rects.map((b) => b[1])), Math.max(...rects.map((b) => b[2])), Math.max(...rects.map((b) => b[3]))];
}

// The board is the element with overflow: hidden that holds the layers: the svg's parent, or its grandparent when a camera wrapper sits in between.
function boardOf(svg: Element): HTMLElement | null {
  for (let e: Element | null = svg.parentElement, i = 0; e && i < 2; e = e.parentElement, i++) {
    if (getComputedStyle(e).overflow === "hidden") return e as HTMLElement;
  }
  return null;
}

// The first matching svg in document order is the bottom layer (the layers after it are html, svg-top and html-top).
function findBoardSvg(): SVGSVGElement | null {
  for (const s of Array.from(document.querySelectorAll("svg"))) {
    if (s.getAttribute("viewBox") === "0 0 1920 1080" && s.nextElementSibling instanceof HTMLDivElement && boardOf(s)) return s as SVGSVGElement;
  }
  return null;
}

function outline(el: Element, depth: number, out: string[]) {
  const cs = getComputedStyle(el);
  const rc = el.getBoundingClientRect();
  const own = Array.from(el.childNodes).filter((n) => n.nodeType === 3 && n.nodeValue && n.nodeValue.trim()).map((n) => n.nodeValue!.trim()).join("|").slice(0, 40);
  out.push(`${"  ".repeat(depth)}${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""} [${r1(rc.left)},${r1(rc.top)},${r1(rc.width)}x${r1(rc.height)}] op=${cs.opacity} pos=${cs.position} ov=${cs.overflow}${own ? ` "${own}"` : ""}`);
  if (depth < 7) for (const c of Array.from(el.children)) outline(c, depth + 1, out);
}

function measure(frame: number, dump: boolean) {
  const svg = findBoardSvg();
  if (!svg) return { frame, scene: "other" };
  const board = boardOf(svg) as HTMLElement;
  const overlay = svg.nextElementSibling as HTMLElement;
  // layers after the html layer: the optional top layers (stroke svg first, then writes and character images)
  const zoomEl = svg.parentElement!.hasAttribute("data-wb-zoom") ? svg.parentElement! : null;
  const after = Array.from(svg.parentElement!.children).slice(Array.from(svg.parentElement!.children).indexOf(overlay) + 1);
  const topSvg = after.find((e) => e instanceof SVGSVGElement) ?? null;
  const topHtml = after.find((e) => e instanceof HTMLDivElement) ?? null;
  const items: unknown[] = [];
  const addItem = (layer: string, idx: number, el: Element) => {
    const texts: TextOut[] = [];
    const shapes: ShapeOut[] = [];
    collectText(el, texts);
    collectShapes(el, shapes);
    if (texts.length || shapes.length) items.push({ layer, idx, tag: el.tagName.toLowerCase(), texts, shapes });
  };
  Array.from(svg.children).forEach((c, i) => addItem("svg", i, c));
  Array.from(overlay.children).forEach((c, i) => addItem("html", i, c));
  if (topSvg) Array.from(topSvg.children).forEach((c, i) => addItem("svg-top", i, c));
  if (topHtml) Array.from(topHtml.children).forEach((c, i) => addItem("html-top", i, c));
  // Every layer that is not an ancestor of the board (captions, logo badge, progress bar ...).
  const chain = new Set<Element>();
  for (let e: Element | null = board; e; e = e.parentElement) chain.add(e);
  const overlays: unknown[] = [];
  for (let e: Element | null = board; e && e.parentElement; e = e.parentElement) {
    for (const sib of Array.from(e.parentElement.children)) {
      if (chain.has(sib) || ["SCRIPT", "STYLE"].includes(sib.tagName)) continue;
      const texts: TextOut[] = [];
      const shapes: ShapeOut[] = [];
      collectText(sib, texts);
      collectShapes(sib, shapes);
      if (texts.length || shapes.length) overlays.push({ tag: sib.tagName.toLowerCase(), box: unionBox([...texts.map((t) => t.box), ...shapes.map((s) => s.box)]), texts, shapes });
    }
  }
  const out: Record<string, unknown> = {
    frame, scene: "whiteboard", viewport: { w: window.innerWidth, h: window.innerHeight },
    board: boxOf(board.getBoundingClientRect()), boardOpacity: r1(effOpacity(board) * 1000) / 1000, items, overlays,
    zoom: zoomEl ? parseFloat(zoomEl.getAttribute("data-wb-zoom") ?? "1") : 1,   // camera zoom: >1 means content is cropped on purpose
  };
  if (dump) { const lines: string[] = []; outline(document.body, 0, lines); out.dump = lines; }
  return out;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const paints = () => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())));

// The hand font is added to document.fonts by WhiteboardScene itself (FontFace.load).  NOTE: document.fonts.check("… WBHand") is vacuously TRUE while that face is
// not registered yet (first version of this probe measured with the fallback font and every hand-written box came out too narrow), so wait for the face itself.
function handFontLoaded(): boolean {
  let ok = false;
  document.fonts.forEach((f) => { if (/WBHand/i.test(f.family) && f.status === "loaded") ok = true; });
  return ok;
}
function fontsLoading(): boolean {
  let busy = false;
  document.fonts.forEach((f) => { if (f.status === "loading") busy = true; });
  return busy;
}
// Cheap signature of the whole text layout: if two reads a moment apart agree, the fonts have been applied.
function layoutSignature(): number {
  const svg = findBoardSvg();
  if (!svg) return 0;
  let sum = 0;
  const texts: TextOut[] = [];
  collectText(boardOf(svg) as Element, texts);
  for (const t of texts) sum += (t.box[2] - t.box[0]) * 7 + (t.box[3] - t.box[1]);
  return Math.round(sum);
}

async function settle(): Promise<boolean> {
  const t0 = Date.now();
  await document.fonts.ready;
  while ((!handFontLoaded() || fontsLoading()) && Date.now() - t0 < 10000) await sleep(25);
  await paints();
  let prev = layoutSignature();
  for (let i = 0; i < 12; i++) {
    await sleep(60);
    await paints();
    const cur = layoutSignature();
    if (cur === prev) return handFontLoaded();
    prev = cur;
  }
  return false; // never stabilised
}

const Probe: React.FC<{ frames: number[]; dump?: boolean }> = ({ frames, dump }) => {
  const frame = useCurrentFrame();
  useEffect(() => {
    if (!frames.includes(frame)) return;
    const handle = delayRender(`layout probe frame ${frame}`, { timeoutInMilliseconds: 60000 });
    (async () => {
      try {
        const stable = findBoardSvg() ? await settle() : true;
        const payload = JSON.stringify({ ...measure(frame, !!dump), fontsReady: handFontLoaded(), stable });
        console.log("@@LAYOUT " + payload.length + " " + payload);
      } catch (e) {
        console.log("@@LAYOUT-ERROR " + frame + " " + String(e));
      } finally {
        continueRender(handle);
      }
    })();
  }, [frame]);
  return null;
};

const ProbedExplainer: React.FC<ProbeProps> = (props) => (
  <>
    <Explainer {...props} />
    <Probe frames={props.probe?.frames ?? []} dump={props.probe?.dump} />
  </>
);

// Same duration rule as src/Root.tsx calculateMetadata (last cut end + 1 s, 30 fps).
const calculateMetadata: CalculateMetadataFunction<ProbeProps> = async ({ props }) => {
  const cuts = props.cuts || [];
  if (cuts.length === 0) return { durationInFrames: 30 * 60 };
  return { durationInFrames: Math.ceil((Math.max(...cuts.map((c) => c.out_seconds || 0)) + 1) * 30) };
};

const Root: React.FC = () => (
  <Composition
    id="LayoutProbe"
    component={ProbedExplainer}
    durationInFrames={30 * 60}
    fps={30}
    width={1920}
    height={1080}
    defaultProps={{ cuts: [], overlays: [], captions: [], audio: {} } as ProbeProps}
    calculateMetadata={calculateMetadata}
  />
);

registerRoot(Root);
