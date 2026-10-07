// Render many frame ranges (muted H.264 parts) and/or still frames, bundling the composer once per process.
// Used by docs/whiteboard_render.py, locally and (as the job payload) on the remote render machine.
// Usage:  node render-tools/render_chunks.mjs <jobs.json>
//
// jobs.json = {
//   "propsPath": ".../props.json", "publicDir": ".../public", "composition": "Explainer",
//   "concurrency": 2,            // browser tabs PER PROCESS
//   "workers": 8,                // parallel processes (each with its own Chrome).  One Remotion process cannot use more
//                                // than ~2 cores (serial bottleneck), so parallelism must come from processes.
//   "timeoutMs": 7200000,
//   "render": {                  // optional performance profile (all keys optional; whitelisted pass-through, absent = Remotion defaults)
//     "gl": "angle-egl",         //   chromiumOptions.gl: null | angle | egl | swiftshader | vulkan | angle-egl | swangle
//     "chromeMode": "headless-shell" | "chrome-for-testing",
//     "hardwareAcceleration": "disabled" | "if-possible" | "required",   // NVENC on Linux (needs "videoBitrate", not crf)
//     "videoBitrate": "6M", "x264Preset": "veryfast", "jpegQuality": 80,
//     "restartEvery": 4        //   restart Chrome after this many parts (guards against ANGLE memory growth)
//   },
//   "chunks": [{"out": ".../K1.p0.mp4", "from": 0, "to": 839}],   // inclusive frame ranges, muted h264
//   "stills": [{"out": ".../t001.png", "frame": 120}]
// }
// Output settings match the CLI defaults used by the full render (h264, yuv420p, crf 18); audio is added later by ffmpeg.
// Machine-readable progress lines for the caller:  "@@progress <file> <renderedFrames> <totalFrames>"  and  "@@done <file>".
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const composerDir = path.resolve(here, "..");
const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
const log = (...a) => console.log(...a);
const isChild = process.env.OM_CHILD === "1";
const workers = isChild ? 1 : Math.max(1, Number(jobs.workers || 1));
const tasks = [
  ...(jobs.chunks || []).map((c) => ({ kind: "chunk", weight: c.to - c.from + 1, item: c })),
  ...(jobs.stills || []).map((s) => ({ kind: "still", weight: 4, item: s })),
];

// ---------------------------------------------------------------------------------------------------------------
// Parent mode: split the work over several child processes (greedy balance by frame count) and relay their output.
// ---------------------------------------------------------------------------------------------------------------
if (workers > 1 && tasks.length > 1) {
  const n = Math.min(workers, tasks.length);
  const buckets = Array.from({ length: n }, () => ({ weight: 0, chunks: [], stills: [] }));
  for (const t of [...tasks].sort((a, b) => b.weight - a.weight)) {
    const b = buckets.reduce((m, x) => (x.weight < m.weight ? x : m));
    b.weight += t.weight;
    (t.kind === "chunk" ? b.chunks : b.stills).push(t.item);
  }
  log(`workers: ${n} processes x concurrency ${jobs.concurrency || 1} (${tasks.length} tasks, ${tasks.reduce((s, t) => s + t.weight, 0)} frames)`);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "om-workers-"));
  // Bundle ONCE here and let every child reuse it (saves N bundles and avoids webpack-cache races between processes).
  const { bundle: bundleOnce } = await import("@remotion/bundler");
  const tb = Date.now();
  const sharedServeUrl = await bundleOnce({ entryPoint: path.join(composerDir, "src", "index.tsx"), publicDir: jobs.publicDir, outDir: path.join(tmp, "bundle") });
  log(`bundle ok ${((Date.now() - tb) / 1000).toFixed(1)}s (shared by ${n} processes)`);
  const kids = [];
  let failed = false;
  const results = buckets.map((b, i) => new Promise((resolve) => {
    // Ordered by frame so each child renders its parts front to back.
    b.chunks.sort((x, y) => x.from - y.from);
    const jf = path.join(tmp, `job_${i}.json`);
    fs.writeFileSync(jf, JSON.stringify({ ...jobs, workers: 1, serveUrl: sharedServeUrl, chunks: b.chunks, stills: b.stills }));
    const child = spawn(process.execPath, [fileURLToPath(import.meta.url), jf], {
      env: { ...process.env, OM_CHILD: "1" }, stdio: ["ignore", "pipe", "pipe"],
    });
    kids.push(child);
    const relay = (stream) => {
      let buf = "";
      stream.on("data", (d) => {
        buf += d.toString();
        let k;
        while ((k = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, k); buf = buf.slice(k + 1);
          if (line.startsWith("@@") || line.startsWith("chunk ") || line.startsWith("still ")) log(line);
          else if (line.trim() && !line.startsWith("  ")) log(`[w${i}] ${line}`);  // errors, fonts, composition info
        }
      });
    };
    relay(child.stdout); relay(child.stderr);
    child.on("exit", (code) => {
      if (code !== 0 && !failed) { failed = true; kids.forEach((k) => k.kill("SIGTERM")); log(`worker ${i} failed (exit ${code})`); }
      resolve(code);
    });
  }));
  const onSignal = () => { kids.forEach((k) => k.kill("SIGTERM")); process.exit(143); };
  process.on("SIGTERM", onSignal); process.on("SIGINT", onSignal);
  const codes = await Promise.all(results);
  try { fs.rmSync(tmp, { recursive: true, force: true }); } catch {}
  log(failed ? "FAILED" : "all done");
  process.exit(codes.every((c) => c === 0) ? 0 : 1);
}

// ---------------------------------------------------------------------------------------------------------------
// Single-process mode (also what every child runs).
// ---------------------------------------------------------------------------------------------------------------
const { bundle } = await import("@remotion/bundler");
const { openBrowser, renderMedia, renderStill, selectComposition } = await import("@remotion/renderer");
const inputProps = JSON.parse(fs.readFileSync(jobs.propsPath, "utf-8"));

// Deterministic fonts: the SAME fonts + fontconfig on every machine, so local and remote frames are pixel-identical.
// render-fonts/ (DejaVu + fonts.conf with @FONTS_DIR@ / @CACHE_DIR@ placeholders) sits next to this script's parent.
// Must run before any Chrome is launched (Chrome inherits process.env).  jobs.fontconfig === "system" opts out.
function setupFonts() {
  const fontsDir = path.join(composerDir, "render-fonts");
  const template = path.join(fontsDir, "fonts.conf");
  if (jobs.fontconfig === "system" || !fs.existsSync(template)) {
    log("fonts: system fontconfig (render-fonts not used)");
    return;
  }
  const work = fs.mkdtempSync(path.join(os.tmpdir(), "om-fonts-"));
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
  } catch (e) {
    log("fonts: private fontconfig set (fc-match not available to report)");
  }
}
setupFonts();

// Optional performance profile, whitelisted so a job file can never inject arbitrary options.
const R = jobs.render || {};
const chromiumOptions = {};
if (R.gl) chromiumOptions.gl = R.gl;
const browserOptions = { chromiumOptions, ...(R.chromeMode ? { chromeMode: R.chromeMode } : {}) };
const mediaExtra = {};
if (R.hardwareAcceleration) mediaExtra.hardwareAcceleration = R.hardwareAcceleration;
if (R.videoBitrate) mediaExtra.videoBitrate = R.videoBitrate;
if (R.x264Preset) mediaExtra.x264Preset = R.x264Preset;
if (R.jpegQuality) mediaExtra.jpegQuality = Number(R.jpegQuality);
if (Object.keys(R).length) log(`render profile: ${JSON.stringify(R)}`);

const t0 = Date.now();
const serveUrl = jobs.serveUrl || await bundle({
  entryPoint: path.join(composerDir, "src", "index.tsx"),
  publicDir: jobs.publicDir,
});
if (!jobs.serveUrl) log(`bundle ok ${((Date.now() - t0) / 1000).toFixed(1)}s`);

let browser = await openBrowser("chrome", browserOptions);
const composition = await selectComposition({
  serveUrl, id: jobs.composition || "Explainer", inputProps, puppeteerInstance: browser, timeoutInMilliseconds: jobs.timeoutMs,
});
log(`composition ${composition.id} frames=${composition.durationInFrames} fps=${composition.fps} ${composition.width}x${composition.height}`);
if (jobs.infoOut) fs.writeFileSync(jobs.infoOut, JSON.stringify({ durationInFrames: composition.durationInFrames, fps: composition.fps, width: composition.width, height: composition.height }));

let partsDone = 0;
for (const c of jobs.chunks || []) {
  if (R.restartEvery && partsDone > 0 && partsDone % Number(R.restartEvery) === 0) {
    await browser.close({ silent: true });
    browser = await openBrowser("chrome", browserOptions);
    log(`browser restarted after ${partsDone} parts`);
  }
  partsDone += 1;
  const t1 = Date.now();
  fs.mkdirSync(path.dirname(c.out), { recursive: true });
  const tmp = c.out + ".part.mp4";
  const name = path.basename(c.out);
  const total = c.to - c.from + 1;
  let lastPct = -1, lastRep = -100;
  await renderMedia({
    composition, serveUrl, inputProps, codec: "h264", outputLocation: tmp,
    frameRange: [c.from, c.to], muted: true, concurrency: jobs.concurrency || 2,
    puppeteerInstance: browser, timeoutInMilliseconds: jobs.timeoutMs, ...mediaExtra,
    onProgress: ({ progress, renderedFrames }) => {
      const pct = Math.floor(progress * 10) * 10;
      if (pct !== lastPct) { lastPct = pct; log(`  ${name} ${pct}%`); }
      if (renderedFrames - lastRep >= 10 || renderedFrames === total) { lastRep = renderedFrames; log(`@@progress ${name} ${renderedFrames} ${total}`); }
    },
  });
  fs.renameSync(tmp, c.out);
  log(`chunk ${name} frames ${c.from}-${c.to} done ${((Date.now() - t1) / 1000).toFixed(1)}s`);
  log(`@@done ${name}`);
}

for (const s of jobs.stills || []) {
  const t1 = Date.now();
  fs.mkdirSync(path.dirname(s.out), { recursive: true });
  await renderStill({
    composition, serveUrl, inputProps, frame: s.frame, output: s.out, imageFormat: "png",
    puppeteerInstance: browser, timeoutInMilliseconds: jobs.timeoutMs,
  });
  log(`still ${path.basename(s.out)} frame ${s.frame} ${((Date.now() - t1) / 1000).toFixed(1)}s`);
  log(`@@done ${path.basename(s.out)}`);
}

await browser.close({ silent: true });
log(`all done ${((Date.now() - t0) / 1000).toFixed(1)}s`);
