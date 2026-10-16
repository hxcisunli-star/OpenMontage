import React, { useEffect, useState } from "react";
import {
  AbsoluteFill,
  continueRender,
  delayRender,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { resolveAsset } from "../lib/resolveAsset";

/**
 * WhiteboardScene — "teacher writing on a whiteboard" scene.
 *
 * Canvas is 1920x1080. All `at` / `dur` values are seconds relative to the
 * start of the cut, so timings can be taken straight from real narration
 * durations.
 */

export const WB_FONT_FILE = "fonts/ZCOOLKuaiLe-Regular.ttf";
const WB_FONT = "WBHand";
const MONO = "'JetBrains Mono','Fira Code','DejaVu Sans Mono',monospace";

export type WbStrokeShape =
  | { shape: "rect"; x: number; y: number; w: number; h: number }
  | { shape: "line"; x1: number; y1: number; x2: number; y2: number }
  | { shape: "arrow"; x1: number; y1: number; x2: number; y2: number }
  | { shape: "circle"; cx: number; cy: number; r: number }
  | { shape: "underline"; x: number; y: number; w: number };

export type WbArrayOp =
  | { type: "compare"; at: number; i: number; j: number; dur?: number }
  | { type: "swap"; at: number; i: number; j: number; dur?: number }
  | { type: "done"; at: number; slots: number[] };

export interface WbMemCell {
  id: string;
  name: string; // variable name drawn above the box, e.g. "a"
  value: string; // value shown inside the box (final value of a copy)
  x: number; // top-left of the box
  y: number;
  w?: number;
  h?: number;
  addr?: string; // address label drawn below the box, e.g. "…f504"
  addrAt?: number; // when the address label appears (default: right after the box)
  at: number; // box starts drawing
  from?: string; // id of the cell whose value is copied in ("clone gate")
  copyDur?: number; // seconds the copied value takes to fly across
  sets?: { at: number; value: string }[]; // value rewrites (flash + colour)
  dimAt?: number; // cell greys out (function returned)
  until?: number; // cell fades away
  small?: boolean; // smaller value text (addresses in pointer cells)
}

export interface WbMemArrow {
  from: string;
  to: string;
  at: number;
  until?: number;
  dur?: number;
  color?: string;
}

export type WbItem =
  | { kind: "memory"; cells: WbMemCell[]; arrows?: WbMemArrow[] }
  | {
      kind: "write";
      text: string;
      x: number;
      y: number;
      at: number;
      dur?: number;
      size?: number;
      color?: string;
      align?: "left" | "center";
      until?: number; // fade out at this time (seconds)
      font?: "hand" | "mono";
    }
  | ({ kind: "stroke"; at: number; dur?: number; color?: string; width?: number; until?: number } & WbStrokeShape)
  | {
      kind: "image";
      src: string; // key must be "src" so video_compose stages the file
      x: number;
      y: number;
      w: number;
      h: number;
      at: number;
      dur?: number;
      reveal?: "down" | "wipe" | "fade";
      until?: number;
    }
  | {
      kind: "array";
      values: number[];
      x: number; // left edge of first cell
      y: number; // top of cells
      at: number; // cells start drawing
      cell?: number;
      ops?: WbArrayOp[];
      showIndex?: boolean;
    }
  | {
      kind: "code";
      lines: string[];
      x: number;
      y: number;
      at: number;
      lineDur?: number;
      lineGap?: number; // seconds between line starts (default = lineDur)
      lineAts?: number[]; // explicit start time per line; overrides at + i*lineGap
      size?: number;
      highlights?: { at: number; line: number; span?: number; color?: string }[];
    };

export interface WbPointerKey {
  at: number;
  x: number;
  y: number;
}

export interface WhiteboardData {
  items: WbItem[];
  pointer?: WbPointerKey[];
  boardColor?: string;
  inkColor?: string;
  accentColor?: string;
  fadeOutSeconds?: number;
}

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

// 1 until `until`, then fades to 0 over 0.4s
const fadeAfter = (t: number, until?: number) =>
  until === undefined ? 1 : clamp01(1 - (t - until) / 0.4);
const easeInOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

function useWbFont() {
  const [handle] = useState(() => delayRender("whiteboard-font"));
  useEffect(() => {
    let done = false;
    const finish = () => {
      if (!done) {
        done = true;
        continueRender(handle);
      }
    };
    try {
      const face = new FontFace(WB_FONT, `url(${staticFile(WB_FONT_FILE)})`);
      face
        .load()
        .then((f) => {
          document.fonts.add(f);
          finish();
        })
        .catch((e) => {
          console.warn("whiteboard font failed to load", e);
          finish();
        });
    } catch (e) {
      console.warn("whiteboard font error", e);
      finish();
    }
    return finish;
  }, [handle]);
}

// Deterministic pseudo-random wobble so hand-drawn lines look the same on every render.
function wobble(seed: number, amp: number): number {
  const s = Math.sin(seed * 12.9898) * 43758.5453;
  return (s - Math.floor(s) - 0.5) * 2 * amp;
}

function wobblyLine(x1: number, y1: number, x2: number, y2: number, seed: number): string {
  const mx = (x1 + x2) / 2 + wobble(seed, 3);
  const my = (y1 + y2) / 2 + wobble(seed + 1, 3);
  return `M ${x1 + wobble(seed + 2, 1.5)} ${y1 + wobble(seed + 3, 1.5)} Q ${mx} ${my} ${x2 + wobble(seed + 4, 1.5)} ${y2 + wobble(seed + 5, 1.5)}`;
}

function shapePath(s: WbStrokeShape, seed: number): string {
  switch (s.shape) {
    case "rect": {
      const { x, y, w, h } = s;
      return (
        `M ${x + wobble(seed, 2)} ${y + wobble(seed + 1, 2)} ` +
        `L ${x + w + wobble(seed + 2, 2)} ${y + wobble(seed + 3, 2)} ` +
        `L ${x + w + wobble(seed + 4, 2)} ${y + h + wobble(seed + 5, 2)} ` +
        `L ${x + wobble(seed + 6, 2)} ${y + h + wobble(seed + 7, 2)} ` +
        `L ${x + wobble(seed, 2)} ${y + wobble(seed + 1, 2) - 1}`
      );
    }
    case "line":
      return wobblyLine(s.x1, s.y1, s.x2, s.y2, seed);
    case "underline":
      return wobblyLine(s.x, s.y, s.x + s.w, s.y + wobble(seed + 9, 4), seed);
    case "arrow": {
      const { x1, y1, x2, y2 } = s;
      const ang = Math.atan2(y2 - y1, x2 - x1);
      const head = 26;
      const a1 = ang + Math.PI - 0.45;
      const a2 = ang + Math.PI + 0.45;
      return (
        `${wobblyLine(x1, y1, x2, y2, seed)} ` +
        `M ${x2 + Math.cos(a1) * head} ${y2 + Math.sin(a1) * head} L ${x2} ${y2} ` +
        `L ${x2 + Math.cos(a2) * head} ${y2 + Math.sin(a2) * head}`
      );
    }
    case "circle": {
      const { cx, cy, r } = s;
      const rx = r + wobble(seed, 4);
      const ry = r + wobble(seed + 1, 4);
      return (
        `M ${cx - rx} ${cy} ` +
        `A ${rx} ${ry} 0 1 1 ${cx + rx} ${cy} ` +
        `A ${rx + 5} ${ry + 3} 0 1 1 ${cx - rx + 6} ${cy - 4}`
      );
    }
  }
}

const Ink: React.FC<{
  d: string;
  progress: number;
  color: string;
  width?: number;
}> = ({ d, progress, color, width = 6 }) => (
  <path
    d={d}
    pathLength={1}
    fill="none"
    stroke={color}
    strokeWidth={width}
    strokeLinecap="round"
    strokeLinejoin="round"
    strokeDasharray={1}
    strokeDashoffset={1 - clamp01(progress)}
    style={{ opacity: progress > 0 ? 1 : 0 }}
  />
);

const Handwriting: React.FC<{
  item: Extract<WbItem, { kind: "write" }>;
  ink: string;
}> = ({ item, ink }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const size = item.size ?? 64;
  const chars = Array.from(item.text).length;
  const dur = item.dur ?? Math.max(0.6, chars * 0.12);
  const p = interpolate(frame, [item.at * fps, (item.at + dur) * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fade = fadeAfter(frame / fps, item.until);
  if (p <= 0 || fade <= 0) return null;
  const center = item.align === "center";
  return (
    <div
      style={{
        position: "absolute",
        left: item.x,
        top: item.y,
        transform: center ? "translateX(-50%) rotate(-0.6deg)" : "rotate(-0.6deg)",
        transformOrigin: "left center",
        fontFamily: item.font === "mono" ? MONO : `${WB_FONT}, 'Noto Sans SC', 'PingFang SC', sans-serif`,
        fontSize: size,
        lineHeight: 1.25,
        color: item.color ?? ink,
        whiteSpace: "pre",
        clipPath: `inset(-10% ${(1 - p) * 100}% -10% 0)`,
        textShadow: "0.6px 0.6px 0 rgba(0,0,0,0.25)",
        opacity: fade,
      }}
    >
      {item.text}
    </div>
  );
};

const StrokeItem: React.FC<{
  item: Extract<WbItem, { kind: "stroke" }>;
  index: number;
  ink: string;
}> = ({ item, index, ink }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const dur = item.dur ?? 0.7;
  const p = interpolate(frame, [item.at * fps, (item.at + dur) * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <g opacity={fadeAfter(frame / fps, item.until)}>
      <Ink
        d={shapePath(item, index * 17 + 3)}
        progress={easeInOut(p)}
        color={item.color ?? ink}
        width={item.width ?? 6}
      />
    </g>
  );
};

const ArrayBoard: React.FC<{
  item: Extract<WbItem, { kind: "array" }>;
  index: number;
  ink: string;
  accent: string;
}> = ({ item, index, ink, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const cell = item.cell ?? 150;
  const gap = 18;
  const n = item.values.length;
  const ops = [...(item.ops ?? [])].sort((a, b) => a.at - b.at);
  const slotX = (s: number) => item.x + s * (cell + gap);

  // slot -> value index; element k currently sits at slot posOf[k]
  const posOf = item.values.map((_, k) => k);
  const moving: { k: number; from: number; to: number; e: number; lift: number }[] = [];
  const doneSlots = new Set<number>();

  for (const op of ops) {
    if (op.type === "swap") {
      const dur = op.dur ?? 0.9;
      // op.i / op.j are slot numbers; find the elements currently sitting in them
      if (t >= op.at + dur) {
        const ki = posOf.findIndex((s) => s === op.i);
        const kj = posOf.findIndex((s) => s === op.j);
        posOf[ki] = op.j;
        posOf[kj] = op.i;
      } else if (t >= op.at) {
        const e = easeInOut(clamp01((t - op.at) / dur));
        const ki = posOf.findIndex((s) => s === op.i);
        const kj = posOf.findIndex((s) => s === op.j);
        moving.push({ k: ki, from: op.i, to: op.j, e, lift: -cell * 0.8 });
        moving.push({ k: kj, from: op.j, to: op.i, e, lift: cell * 0.8 });
        break;
      }
    } else if (op.type === "done" && t >= op.at) {
      op.slots.forEach((s) => doneSlots.add(s));
    }
  }

  const activeCompare = ops.find(
    (op) => op.type === "compare" && t >= op.at && t < op.at + (op.dur ?? 1.2)
  ) as Extract<WbArrayOp, { type: "compare" }> | undefined;
  const activeSwap = moving.length > 0;

  return (
    <g>
      {item.values.map((v, k) => {
        const appear = item.at + k * 0.18;
        const p = easeInOut(
          clamp01((frame - appear * fps) / (0.6 * fps))
        );
        if (p <= 0) return null;
        const mv = moving.find((m) => m.k === k);
        const slot = posOf[k];
        const x = mv ? slotX(mv.from) + (slotX(mv.to) - slotX(mv.from)) * mv.e : slotX(slot);
        const y = item.y + (mv ? Math.sin(Math.PI * mv.e) * mv.lift : 0);
        const done = doneSlots.has(slot) && !mv;
        const stroke = done ? "#15803D" : ink;
        const d = shapePath(
          { shape: "rect", x: 0, y: 0, w: cell, h: cell },
          index * 31 + k * 7
        );
        return (
          <g key={k} transform={`translate(${x}, ${y})`}>
            {done && (
              <rect x={0} y={0} width={cell} height={cell} fill="rgba(34,197,94,0.14)" rx={6} />
            )}
            <Ink d={d} progress={p} color={stroke} width={done ? 8 : 6} />
            <text
              x={cell / 2}
              y={cell / 2 + cell * 0.18}
              textAnchor="middle"
              fontFamily={`${WB_FONT}, sans-serif`}
              fontSize={cell * 0.55}
              fill={stroke}
              opacity={clamp01(p * 2 - 0.6)}
            >
              {v}
            </text>
          </g>
        );
      })}

      {item.showIndex !== false &&
        item.values.map((_, s) => {
          const p = clamp01((frame - (item.at + 0.9) * fps) / (0.5 * fps));
          return (
            <text
              key={`i${s}`}
              x={slotX(s) + cell / 2}
              y={item.y + cell + 46}
              textAnchor="middle"
              fontFamily={`${WB_FONT}, sans-serif`}
              fontSize={34}
              fill="#64748B"
              opacity={p}
            >
              [{s}]
            </text>
          );
        })}

      {activeCompare && !activeSwap && (
        <g>
          {[activeCompare.i, activeCompare.j].map((s, n2) => {
            const dur = activeCompare.dur ?? 1.2;
            const p = easeInOut(clamp01((t - activeCompare.at) / (dur * 0.45)));
            return (
              <Ink
                key={n2}
                d={shapePath(
                  { shape: "circle", cx: slotX(s) + cell / 2, cy: item.y + cell / 2, r: cell * 0.78 },
                  index * 13 + n2 * 5
                )}
                progress={p}
                color={accent}
                width={7}
              />
            );
          })}
        </g>
      )}
    </g>
  );
};

const MemoryBoard: React.FC<{
  item: Extract<WbItem, { kind: "memory" }>;
  index: number;
  ink: string;
  accent: string;
}> = ({ item, index, ink, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const byId = new Map(item.cells.map((c) => [c.id, c]));
  const W = (c: WbMemCell) => c.w ?? 190;
  const H = (c: WbMemCell) => c.h ?? 120;
  const BOX = 0.5; // seconds to draw a box

  // value shown in a cell at time s (copies show their value after the flight)
  const valueAt = (c: WbMemCell, s: number): string => {
    const sets = [...(c.sets ?? [])].sort((a, b) => a.at - b.at);
    let v = c.value;
    // a cell with sets starts from its `value` and rewrites; `value` is the initial one
    for (const st of sets) if (s >= st.at) v = st.value;
    return v;
  };
  // value in the source at copy time (before any later set)
  const valueBefore = (c: WbMemCell, s: number): string => valueAt(c, s);

  const cellAlpha = (c: WbMemCell) => {
    if (c.until === undefined) return 1;
    return clamp01(1 - (t - c.until) / 0.5);
  };

  return (
    <g>
      {item.cells.map((c, k) => {
        const alpha = cellAlpha(c);
        if (alpha <= 0 || t < c.at) return null;
        const boxP = easeInOut(clamp01((t - c.at) / BOX));
        const dimmed = c.dimAt !== undefined && t >= c.dimAt;
        const dimP = c.dimAt === undefined ? 0 : clamp01((t - c.dimAt) / 0.5);
        const col = dimmed ? "#94A3B8" : ink;
        const flyStart = c.at + BOX;
        const flyDur = c.copyDur ?? 1.0;
        const src = c.from ? byId.get(c.from) : undefined;
        const arrived = !src || t >= flyStart + flyDur;
        const lastSet = [...(c.sets ?? [])].filter((s) => t >= s.at).sort((a, b) => b.at - a.at)[0];
        const sinceSet = lastSet ? t - lastSet.at : 99;
        const sinceArrive = src ? t - (flyStart + flyDur) : 99;
        const flash = Math.max(clamp01(1 - sinceSet / 1.0), clamp01(1 - sinceArrive / 0.8));
        const pop = 1 + 0.12 * Math.sin(Math.PI * clamp01(Math.min(sinceSet, sinceArrive) / 0.5));
        const cx = c.x + W(c) / 2;
        const cy = c.y + H(c) / 2;
        const size = c.small ? 34 : 68;
        const shown = valueAt(c, t);
        const d = shapePath({ shape: "rect", x: 0, y: 0, w: W(c), h: H(c) }, index * 41 + k * 11);
        // flying value (copy)
        let fly: React.ReactNode = null;
        if (src && t >= flyStart && t < flyStart + flyDur) {
          const e = easeInOut(clamp01((t - flyStart) / flyDur));
          const sx = src.x + W(src) / 2;
          const sy = src.y + H(src) / 2;
          fly = (
            <text
              x={sx + (cx - sx) * e}
              y={sy + (cy - sy) * e - Math.sin(Math.PI * e) * 70 + size * 0.34}
              textAnchor="middle"
              fontFamily={`${WB_FONT}, sans-serif`}
              fontSize={size}
              fill={accent}
            >
              {valueBefore(src, flyStart)}
            </text>
          );
        }
        return (
          <g key={c.id} opacity={alpha * (1 - 0.65 * dimP)}>
            <g transform={`translate(${c.x}, ${c.y})`}>
              {flash > 0 && (
                <rect x={0} y={0} width={W(c)} height={H(c)} rx={8} fill={`rgba(250,204,21,${0.5 * flash})`} />
              )}
              <g transform={`translate(${(W(c) / 2) * (1 - pop)}, ${(H(c) / 2) * (1 - pop)}) scale(${pop})`}>
                <Ink d={d} progress={boxP} color={col} width={6} />
              </g>
            </g>
            <text
              x={cx}
              y={c.y - 16}
              textAnchor="middle"
              fontFamily="'DejaVu Sans Mono', 'Noto Sans SC', monospace"
              fontWeight={700}
              fontSize={36}
              fill={col}
              opacity={boxP}
            >
              {c.name}
            </text>
            {arrived && shown !== "" && (
              <text
                x={cx}
                y={cy + size * 0.34}
                textAnchor="middle"
                fontFamily={`${WB_FONT}, 'Noto Sans SC', sans-serif`}
                fontSize={size}
                fill={flash > 0.05 ? accent : col}
              >
                {shown}
              </text>
            )}
            {fly}
            {c.addr && (
              <text
                x={cx}
                y={c.y + H(c) + 34}
                textAnchor="middle"
                fontFamily="'DejaVu Sans Mono', monospace"
                fontSize={26}
                fill="#64748B"
                opacity={clamp01((t - (c.addrAt ?? c.at + BOX)) / 0.5)}
              >
                {c.addr}
              </text>
            )}
          </g>
        );
      })}
      {(item.arrows ?? []).map((a, i) => {
        const s = byId.get(a.from);
        const e = byId.get(a.to);
        if (!s || !e) return null;
        const fade = fadeAfter(t, a.until);
        const p = easeInOut(clamp01((t - a.at) / (a.dur ?? 0.8)));
        if (p <= 0 || fade <= 0) return null;
        const scx = s.x + W(s) / 2, scy = s.y + H(s) / 2;
        const ecx = e.x + W(e) / 2, ecy = e.y + H(e) / 2;
        const dx = ecx - scx, dy = ecy - scy;
        let x1: number, y1: number, x2: number, y2: number;
        if (Math.abs(dx) >= Math.abs(dy)) {
          x1 = dx > 0 ? s.x + W(s) : s.x; y1 = scy;
          x2 = dx > 0 ? e.x - 8 : e.x + W(e) + 8; y2 = ecy;
        } else {
          x1 = scx; y1 = dy > 0 ? s.y + H(s) + 40 : s.y - 44;
          x2 = ecx; y2 = dy > 0 ? e.y - 44 : e.y + H(e) + 44;
        }
        return (
          <g key={`ar${i}`} opacity={fade}>
            <Ink d={shapePath({ shape: "arrow", x1, y1, x2, y2 }, index * 23 + i * 5)} progress={p} color={a.color ?? accent} width={7} />
          </g>
        );
      })}
    </g>
  );
};

const CodeBoard: React.FC<{
  item: Extract<WbItem, { kind: "code" }>;
  ink: string;
}> = ({ item, ink }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const size = item.size ?? 38;
  const lineH = size * 1.5;
  const lineDur = item.lineDur ?? 1.2;
  const gap = item.lineGap ?? lineDur;
  const highlights = [...(item.highlights ?? [])].sort((a, b) => a.at - b.at);
  const current = [...highlights].reverse().find((h) => t >= h.at);

  return (
    <div style={{ position: "absolute", left: item.x, top: item.y }}>
      {current && (
        <div
          style={{
            position: "absolute",
            left: -16,
            right: -16,
            top: current.line * lineH - 2,
            height: lineH * (current.span ?? 1),
            background: current.color ?? "rgba(250,204,21,0.45)",
            borderRadius: 6,
            transition: "none",
          }}
        />
      )}
      {item.lines.map((line, i) => {
        const start = item.lineAts?.[i] ?? item.at + i * gap;
        const p = clamp01((frame - start * fps) / (lineDur * fps));
        // keep the row's height while it is still unwritten so lines never shift
        if (p <= 0) return <div key={i} style={{ height: lineH }} />;
        return (
          <div
            key={i}
            style={{
              position: "relative",
              height: lineH,
              fontFamily: MONO,
              fontSize: size,
              color: ink,
              whiteSpace: "pre",
              clipPath: `inset(-10% ${(1 - p) * 100}% -10% 0)`,
            }}
          >
            {line}
          </div>
        );
      })}
    </div>
  );
};

const ImageItem: React.FC<{ item: Extract<WbItem, { kind: "image" }> }> = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const dur = item.dur ?? 1.2;
  const reveal = item.reveal ?? "down";
  const p = easeInOut(
    clamp01((frame - item.at * fps) / (dur * fps))
  );
  const fade = fadeAfter(frame / fps, item.until);
  if (p <= 0 || fade <= 0) return null;
  const clip =
    reveal === "down"
      ? `inset(0 0 ${(1 - p) * 100}% 0)`
      : reveal === "wipe"
        ? `inset(0 ${(1 - p) * 100}% 0 0)`
        : "none";
  return (
    <Img
      src={resolveAsset(item.src)}
      style={{
        position: "absolute",
        left: item.x,
        top: item.y,
        width: item.w,
        height: item.h,
        objectFit: "contain",
        clipPath: clip,
        opacity: (reveal === "fade" ? p : 1) * fade,
      }}
    />
  );
};

const Pointer: React.FC<{ keys: WbPointerKey[] }> = ({ keys }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (keys.length === 0) return null;
  const t = frame / fps;
  const sorted = [...keys].sort((a, b) => a.at - b.at);
  let x = sorted[0].x;
  let y = sorted[0].y;
  if (t >= sorted[sorted.length - 1].at) {
    x = sorted[sorted.length - 1].x;
    y = sorted[sorted.length - 1].y;
  } else if (t > sorted[0].at) {
    const idx = sorted.findIndex((k) => k.at > t);
    const a = sorted[idx - 1];
    const b = sorted[idx];
    const e = easeInOut(clamp01((t - a.at) / (b.at - a.at)));
    x = a.x + (b.x - a.x) * e;
    y = a.y + (b.y - a.y) * e;
  }
  const bob = Math.sin(frame / 6) * 2;
  return (
    <g transform={`translate(${x}, ${y + bob}) rotate(38) scale(0.6)`}>
      <rect x={-9} y={-6} width={18} height={26} rx={4} fill="#1E3A8A" />
      <rect x={-13} y={20} width={26} height={100} rx={8} fill="#F8FAFC" stroke="#1E293B" strokeWidth={3} />
      <rect x={-13} y={20} width={26} height={22} rx={6} fill="#2563EB" />
      <circle cx={0} cy={132} r={22} fill="#F5C9A6" stroke="#B45309" strokeWidth={2.5} />
    </g>
  );
};

export const WhiteboardScene: React.FC<{ data: WhiteboardData }> = ({ data }) => {
  useWbFont();
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const board = data.boardColor ?? "#FBFBF8";
  const ink = data.inkColor ?? "#111827";
  const accent = data.accentColor ?? "#DC2626";
  const fadeOut = data.fadeOutSeconds ?? 0.4;

  const enter = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 10 });
  const exit = interpolate(
    frame,
    [durationInFrames - fadeOut * fps, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const writes = data.items.filter((i) => i.kind === "write") as Extract<WbItem, { kind: "write" }>[];
  const strokes = data.items.filter((i) => i.kind === "stroke") as Extract<WbItem, { kind: "stroke" }>[];
  const arrays = data.items.filter((i) => i.kind === "array") as Extract<WbItem, { kind: "array" }>[];
  const codes = data.items.filter((i) => i.kind === "code") as Extract<WbItem, { kind: "code" }>[];
  const images = data.items.filter((i) => i.kind === "image") as Extract<WbItem, { kind: "image" }>[];
  const memories = data.items.filter((i) => i.kind === "memory") as Extract<WbItem, { kind: "memory" }>[];

  return (
    <AbsoluteFill style={{ background: "#CBD5E1", opacity: enter * exit }}>
      <AbsoluteFill
        style={{
          top: 28,
          left: 28,
          right: 28,
          bottom: 28,
          width: "auto",
          height: "auto",
          borderRadius: 18,
          background: board,
          boxShadow: "0 0 0 10px #94A3B8, 0 12px 40px rgba(15,23,42,0.35)",
          backgroundImage:
            "linear-gradient(rgba(148,163,184,0.16) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.16) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
          overflow: "hidden",
        }}
      >
        <svg
          width={1920}
          height={1080}
          viewBox="0 0 1920 1080"
          style={{ position: "absolute", left: -28, top: -28 }}
        >
          {strokes.map((s, i) => (
            <StrokeItem key={`s${i}`} item={s} index={i} ink={ink} />
          ))}
          {arrays.map((a, i) => (
            <ArrayBoard key={`a${i}`} item={a} index={i} ink={ink} accent={accent} />
          ))}
          {memories.map((m, i) => (
            <MemoryBoard key={`m${i}`} item={m} index={i} ink={ink} accent={accent} />
          ))}
          <Pointer keys={data.pointer ?? []} />
        </svg>
        <div style={{ position: "absolute", left: -28, top: -28, width: 1920, height: 1080 }}>
          {images.map((im, i) => (
            <ImageItem key={`im${i}`} item={im} />
          ))}
          {writes.map((w, i) => (
            <Handwriting key={`w${i}`} item={w} ink={ink} />
          ))}
          {codes.map((c, i) => (
            <CodeBoard key={`c${i}`} item={c} ink={ink} />
          ))}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
