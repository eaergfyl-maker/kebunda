/**
 * Soil water through the rotation: how full the soil "tank" is, month by month, for the
 * current rotation and one alternative.
 *
 * OWNER: Member 2.
 */
import { useState } from "react";

import { translate, useMonths, useT, type Lang } from "@/i18n/LanguageProvider";
import { CHART, ROLE_COLOR } from "@/styles/theme";
import type { Strategy } from "@/types/api";

import { box, LegendRow, linePath, scale, Svg, YAxis } from "./chartKit";
import { LocalAdviceNote, Takeaway } from "./Takeaway";


function driest(s: Strategy) {
  const cells = s.months;
  if (!cells.length) return null;
  return cells.reduce((lo, c) => (c.soil_water_frac < lo.soil_water_frac ? c : lo), cells[0]);
}

/** One plain sentence for the farmer. 90% and 5 points are display thresholds, not agronomy rules. */
function takeaway(base: Strategy, other: Strategy | null, lang: Lang, MONTH_NAMES: string[]): string {
  const t = (s: string, v?: Record<string, string | number>) => translate(lang, s, v);
  const d = driest(base);
  if (!d) return "";
  const pct = Math.round(d.soil_water_frac * 100);
  let s = pct >= 90
    ? t("On your current rotation the soil stays well supplied with water all year.")
    : t("On your current rotation the soil is driest in {m}, when it holds about {p}% of its water.", { m: MONTH_NAMES[d.calendar_month], p: pct });
  const o = other ? driest(other) : null;
  if (other && o) {
    const diff = Math.round((o.soil_water_frac - d.soil_water_frac) * 100);
    if (Math.abs(diff) >= 5) s += " " + t(diff > 0 ? "{name} keeps {n} percentage points more water in the driest month." : "{name} keeps {n} percentage points less water in the driest month.", { name: t(other.title), n: Math.abs(diff) });
  }
  return s;
}

export function SoilWaterThroughRotation({ strategies }: { strategies: Strategy[] }) {
  const { t, lang } = useT();
  const { months: MONTH_NAMES, initials: MONTH_INITIALS } = useMonths();
  const baseline = strategies[0];
  const others = strategies.slice(1);
  const [compareId, setCompareId] = useState<string | null>(others[0]?.id ?? null);
  const compare = others.find((s) => s.id === compareId) ?? others[0] ?? null;
  const shown = compare ? [baseline, compare] : [baseline];

  const n = Math.max(...shown.map((s) => s.months.length), 1);
  const b = box(720, 250, { top: 26 });
  const x = scale(0, Math.max(n - 1, 1), b.left + 8, b.width - b.right - 8);
  const y = scale(0, 1, b.height - b.bottom, b.top);
  const labelEvery = n > 36 ? 3 : 1;
  const colorOf = (s: Strategy) => ROLE_COLOR[s.role] ?? CHART.moisture;

  return (
    <div className="stack">
      <div className="spread" style={{ flexWrap: "wrap" }}>
        <p className="small muted" style={{ maxWidth: "70ch" }}>
          {t("How full the soil's water store is at the end of each month, across the whole rotation. Dips show when a crop could be short of water; flat high stretches mean the soil stays well supplied.")}
        </p>
        {others.length > 0 && (
          <label className="row small no-print">
            {t("Compare with")}
            <select value={compare?.id ?? ""} onChange={(e) => setCompareId(e.target.value)}>
              {others.map((s) => <option key={s.id} value={s.id}>{t(s.title)}</option>)}
            </select>
          </label>
        )}
      </div>

      <Takeaway>{takeaway(baseline, compare, lang, MONTH_NAMES)}</Takeaway>

      <Svg b={b} label={t("Soil water by month through the rotation")}>
        <YAxis b={b} ticks={[0, 0.25, 0.5, 0.75, 1]} y={y} format={(v) => `${Math.round(v * 100)}%`} />
        {baseline.months.map((c, i) => (
          <g key={i}>
            {c.calendar_month === 0 && i > 0 && (
              <line x1={x(i) - 0.5} x2={x(i) - 0.5} y1={b.top} y2={b.height - b.bottom} stroke={CHART.rule} strokeDasharray="2 3" />
            )}
            {c.calendar_month === 0 && (
              <text x={x(i) + 3} y={b.top - 9} fontSize={9} fill={CHART.faint} fontWeight={600}>{t("Year {n}", { n: c.year_index + 1 })}</text>
            )}
            {i % labelEvery === 0 && (
              <text x={x(i)} y={b.height - b.bottom + 14} fontSize={9} fill={CHART.faint} textAnchor="middle">{MONTH_INITIALS[c.calendar_month]}</text>
            )}
          </g>
        ))}
        {shown.map((s) => (
          <g key={s.id}>
            <path d={linePath(s.months.map((c) => c.soil_water_frac), x, y)} fill="none" stroke={colorOf(s)} strokeWidth={2.4}
              strokeDasharray={s.role === "baseline" ? undefined : "6 4"} strokeLinejoin="round" />
            {s.months.map((c, i) => (
              <circle key={i} cx={x(i)} cy={y(c.soil_water_frac)} r={2.8} fill={colorOf(s)}>
                <title>{`${MONTH_NAMES[c.calendar_month]}, ${t("Year {n}", { n: c.year_index + 1 })} · ${t(s.title)}: ${Math.round(c.soil_water_frac * 100)}%`}</title>
              </circle>
            ))}
          </g>
        ))}
      </Svg>

      <LegendRow items={shown.map((s) => ({
        color: colorOf(s), dash: s.role !== "baseline",
        label: s.role === "baseline" ? t("Current rotation") : t(s.title),
      }))} />

      <div className="row-wrap small">
        {shown.map((s) => {
          const d = driest(s);
          return d ? (
            <span key={s.id} className="chip">
              {s.role === "baseline" ? t("Current rotation") : t(s.title)}: {t("driest in {m} (year {y}), {p}% full", { m: MONTH_NAMES[d.calendar_month], y: d.year_index + 1, p: Math.round(d.soil_water_frac * 100) })}
            </span>
          ) : null;
        })}
      </div>
      <p className="xs faint">{t("Simulated from fused rainfall, crop water use and irrigation for this field. It is a model output, not a probe reading.")}</p>
      <LocalAdviceNote />
    </div>
  );
}