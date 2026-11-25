// Small time-based tweens. The stage asks for frames only while a tween runs, so an idle figure costs nothing.
export const ease = {
  linear: (t) => t,
  out: (t) => 1 - Math.pow(1 - t, 3),
  inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  // a short drop that lands with one small bounce (a block put down on the desk)
  land: (t) => {
    if (t < 0.8) { const u = t / 0.8; return u * u; }
    const u = (t - 0.8) / 0.2;
    return 1 - 0.06 * Math.sin(Math.PI * u);
  },
};

export class Animator {
  constructor() {
    this.tweens = new Set();
    this.instant = false;          // reduced motion: every tween jumps to its end
  }
  // from/to: numbers; step(v) applies the value; returns a promise that resolves at the end (or when cancelled)
  // key: an object the tween moves; a new tween with the same key stops the old one first (a note moved twice in a row ends where the last move says)
  tween({ from = 0, to = 1, ms = 400, delay = 0, curve = ease.out, step, done, key }) {
    if (key !== undefined) for (const tw of [...this.tweens]) if (tw.key === key) { this.tweens.delete(tw); tw.resolve(); }
    return new Promise((resolve) => {
      if (this.instant || ms <= 0) { step(to); if (done) done(); resolve(); return; }
      const tw = { from, to, ms, delay, curve, step, done, resolve, t0: null, key };
      this.tweens.add(tw);
    });
  }
  wait(ms) {
    return this.tween({ ms, step: () => {} });
  }
  get busy() { return this.tweens.size > 0; }
  tick(now) {
    for (const tw of [...this.tweens]) {
      if (tw.t0 === null) tw.t0 = now;
      const el = now - tw.t0 - tw.delay;
      if (el < 0) continue;
      const k = Math.min(1, el / tw.ms);
      tw.step(tw.from + (tw.to - tw.from) * tw.curve(k));
      if (k >= 1) { this.tweens.delete(tw); if (tw.done) tw.done(); tw.resolve(); }
    }
  }
  // the figure was off screen for dt ms: running tweens continue where they stopped instead of jumping ahead
  shift(dt) {
    for (const tw of this.tweens) if (tw.t0 !== null) tw.t0 += dt;
  }
  cancelAll() {
    for (const tw of [...this.tweens]) { this.tweens.delete(tw); tw.resolve(); }
  }
}
