// Measure the real layout of a whiteboard lesson: bundle probe/index.tsx, visit frames without taking pictures, collect the `@@LAYOUT` console lines.
// Driven by docs/whiteboard_layout_check.py.  Runs on THIS machine only.
// Usage:  node probe/layout_probe.mjs <job.json>
//
// job = { "propsPath": ".../props.json" (already staged, with a "probe": {"frames": [...]} field), "publicDir": ".../public", "out": ".../layout.json",
//         "ranges": [[from, to], ...],      // inclusive frame ranges to visit (the whiteboard cuts)
//         "step": 3,                        // visit from, from+step, ... (Remotion everyNthFrame); wanted frames must be of that form
//         "mode": "range" | "single",       // range: one renderFrames call per range; single: one call per wanted frame (for timing comparison)
//         "concurrency": 2, "timeoutMs": 600000 }
// Output: { "meta": {...timings}, "frames": { "<frame>": payload }, "errors": [...] }
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const composerDir = path.resolve(here, "..");
const job = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
const log = (...a) => console.log(...a);
process.on("uncaughtException", (e) => { console.error((e && e.stack) || e); process.exit(1); });
process.on("unhandledRejection", (e) => { console.error((e && e.stack) || e); process.exit(1); });

// Same private fontconfig as render_chunks.mjs, so the boxes are measured with the fonts the final frames are drawn with (DejaVu + the hand font).
function setupFonts() {
  const fontsDir = path.join(composerDir, "render-fonts");
  const template = path.join(fontsDir, "fonts.conf");
  if (!fs.existsSync(template)) { log("fonts: system fontconfig (render-fonts missing!)"); return; }
  const work = fs.mkdtempSync(path.join(os.tmpdir(), "om-probe-fonts-"));
  const cache = path.join(work, "cache");
  fs.mkdirSync(cache);
  const conf = fs.readFileSync(template, "utf-8").replaceAll("@FONTS_DIR@", fontsDir).replaceAll("@CACHE_DIR@", cache);
  const confPath = path.join(work, "fonts.conf");
  fs.writeFileSync(confPath, conf);
  process.env.FONTCONFIG_FILE = confPath;
  delete process.env.FONTCONFIG_PATH;
  process.on("exit", () => { try { fs.rmSync(work, { recursive: true, force: true }); } catch {} });
  try {
    const m = (q) => execFileSync("fc-match", [q, "--format=%{family} (%{file})"], { env: process.env }).toString().trim();
    log(`fonts: private fontconfig; monospace -> ${m("monospace")}; sans-serif -> ${m("sans-serif")}`);
  } catch { log("fonts: private fontconfig set"); }
}
setupFonts();

const { bundle } = await import("@remotion/bundler");
const { openBrowser, renderFrames, selectComposition } = await import("@remotion/renderer");
const inputProps = JSON.parse(fs.readFileSync(job.propsPath, "utf-8"));
const wanted = new Set(inputProps.probe?.frames ?? []);
const step = Math.max(1, Number(job.step || 1));

const t0 = Date.now();
const serveUrl = await bundle({ entryPoint: path.join(composerDir, "probe", "index.tsx"), publicDir: job.publicDir });
const tBundle = Date.now() - t0;
log(`bundle ok ${(tBundle / 1000).toFixed(1)}s`);

const browser = await openBrowser("chrome", { chromiumOptions: {} });
const composition = await selectComposition({ serveUrl, id: "LayoutProbe", inputProps, puppeteerInstance: browser, timeoutInMilliseconds: job.timeoutMs });
log(`composition ${composition.id} frames=${composition.durationInFrames} fps=${composition.fps} ${composition.width}x${composition.height}`);

const frames = {};
const errors = [];
const bad = [];
const onBrowserLog = (l) => {
  const text = l.text || "";
  if (text.startsWith("@@LAYOUT-ERROR")) { errors.push(text.slice(0, 300)); return; }
  if (!text.startsWith("@@LAYOUT ")) return;
  const rest = text.slice(9);
  const sp = rest.indexOf(" ");
  const n = Number(rest.slice(0, sp));
  const body = rest.slice(sp + 1);
  if (body.length !== n) { bad.push({ declared: n, got: body.length }); return; }  // truncated or mangled line
  try { const p = JSON.parse(body); frames[p.frame] = p; } catch (e) { bad.push({ parse: String(e).slice(0, 100) }); }
};

const callFrames = async (lo, hi, nth) => {
  await renderFrames({
    composition, serveUrl, inputProps, imageFormat: "none", outputDir: null, frameRange: [lo, hi], everyNthFrame: nth,
    concurrency: job.concurrency || 2, puppeteerInstance: browser, timeoutInMilliseconds: job.timeoutMs,
    onStart: () => {}, onFrameUpdate: () => {}, onBrowserLog,
  });
};

const t1 = Date.now();
let visited = 0, calls = 0;
if ((job.mode || "range") === "single") {
  for (const f of [...wanted].sort((a, b) => a - b)) { await callFrames(f, f, 1); visited += 1; calls += 1; }
} else {
  for (const [lo, hi] of job.ranges) { await callFrames(lo, hi, step); visited += Math.floor((hi - lo) / step) + 1; calls += 1; }
}
const tRender = Date.now() - t1;
await browser.close({ silent: true });

const missing = [...wanted].filter((f) => !(f in frames));
const meta = { bundleMs: tBundle, framesMs: tRender, visited, calls, wanted: wanted.size, got: Object.keys(frames).length, missing: missing.length, badLines: bad.length, errors: errors.length, mode: job.mode || "range", step };
fs.mkdirSync(path.dirname(job.out), { recursive: true });
fs.writeFileSync(job.out, JSON.stringify({ meta, frames, errors, bad, missing }));
log(`probe done: ${JSON.stringify(meta)}`);
