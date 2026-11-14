/**
 * Tiny SVG chart kit shared by every timeline. No chart library: the charts here are simple,
 * and hand-drawn SVG keeps the bundle small and the styling fully ours.
 *
 * All charts draw in a fixed coordinate system (viewBox) and scale with their container.
 */
import type { ReactNode } from "react";

import { MONTH_INITIALS } from "@/hooks/useUnits";
import { CHART } from "@/styles/theme";

export interface Box {
  width: number;
  height: number;
  top: number;
  right: number;
  bottom: number;
  left: number;
}
export const box = (width = 720, height = 240, m: Partial<Box> = {}): Box => ({ width, height, top: 14, right: 16, bottom: 26, left: 44, ...m });
export const innerW = (b: Box) => b.width - b.left - b.right;
export const innerH = (b: Box) => b.height - b.top - b.bottom;

export const scale = (d0: number, d1: number, r0: number, r1: number) => (v: number) =>
  d1 === d0 ? (r0 + r1) / 2 : r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);

/** Round axis ticks (1, 2, 2.5 or 5 times a power of ten). */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (!isFinite(min) || !isFinite(max) || min === max) return [min];
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-6; v += step) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}

export function extent(values: (number | null | undefined)[], pad = 0): [number, number] {
  const v = values.filter((x): x is number => x !== null && x !== undefined && isFinite(x));
  if (!v.length) return [0, 1];
  const lo = Math.min(...v);
  const hi = Math.max(...v);
  const p = (hi - lo) * pad;
  return [lo - p, hi + p];
}

export function Svg({ b, children, label }: { b: Box; children: ReactNode; label: string }) {
  return (
    <svg viewBox={`0 0 ${b.width} ${b.height}`} role="img" aria-label={label} style={{ width: "100%", height: "auto", display: "block", overflow: "visible" }}>
      {children}
    </svg>
  );
}

export function YAxis({ b, ticks, y, format = (v) => String(v), title, side = "left", color = CHART.faint }: {
  b: Box; ticks: number[]; y: (v: number) => number; format?: (v: number) => string; title?: string; side?: "left" | "right"; color?: string;
}) {
  const x = side === "left" ? b.left : b.width - b.right;
  return (
    <g>
      {ticks.map((t) => (
        <g key={t}>
          {side === "left" && <line x1={b.left} x2={b.width - b.right} y1={y(t)} y2={y(t)} stroke={CHART.grid} strokeWidth={1} />}
          <text x={side === "left" ? x - 6 : x + 6} y={y(t) + 3.5} fontSize={10} fill={color} textAnchor={side === "left" ? "end" : "start"}>{format(t)}</text>
        </g>
      ))}
      {title && (
        <text x={side === "left" ? 10 : b.width - 4} y={b.top - 3} fontSize={10} fill={color} textAnchor={side === "left" ? "start" : "end"} fontWeight={600}>{title}</text>
      )}
    </g>
  );
}

/** Twelve month letters under a chart. `x(m)` is the centre of month m. */
export function MonthAxis({ b, x, months = 12 }: { b: Box; x: (m: number) => number; months?: number }) {
  return (
    <g>
      {Array.from({ length: months }, (_, m) => (
        <text key={m} x={x(m)} y={b.height - b.bottom + 14} fontSize={10} fill={CHART.faint} textAnchor="middle">{MONTH_INITIALS[m % 12]}</text>
      ))}
    </g>
  );
}

/** SVG path through points, breaking the line at nulls. */
export function linePath(values: (number | null | undefined)[], x: (i: number) => number, y: (v: number) => number): string {
  let d = "";
  let pen = false;
  values.forEach((v, i) => {
    if (v === null || v === undefined || !isFinite(v)) {
      pen = false;
      return;
    }
    d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
    pen = true;
  });
  return d;
}

export function LegendRow({ items }: { items: { color: string; label: ReactNode; dash?: boolean; swatch?: "line" | "box" }[] }) {
  return (
    <div className="chart-legend">
      {items.map((it, i) => (
        <span key={i} className="chart-legend-item">
          {it.swatch === "box"
            ? <span className="chart-swatch-box" style={{ background: it.color }} />
            : <span className="chart-swatch-line" style={{ borderTopColor: it.color, borderTopStyle: it.dash ? "dashed" : "solid" }} />}
          {it.label}
        </span>
      ))}
    </div>
  );
}

/** Least-squares line through (i, value) pairs, for drawing a trend over an annual series. */
export function trendLine(values: (number | null)[]): { at: (i: number) => number } | null {
  const pts = values.map((v, i) => [i, v] as const).filter((p): p is readonly [number, number] => p[1] !== null);
  if (pts.length < 4) return null;
  const mx = pts.reduce((a, p) => a + p[0], 0) / pts.length;
  const my = pts.reduce((a, p) => a + p[1], 0) / pts.length;
  const sxx = pts.reduce((a, p) => a + (p[0] - mx) ** 2, 0);
  const slope = sxx ? pts.reduce((a, p) => a + (p[0] - mx) * (p[1] - my), 0) / sxx : 0;
  return { at: (i) => my + slope * (i - mx) };
}
