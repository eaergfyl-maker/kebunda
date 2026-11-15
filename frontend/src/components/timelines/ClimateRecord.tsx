/**
 * The long record: 24 years of NASA data as (1) a year-by-month drought fingerprint and
 * (2) annual series with their trend.
 *
 * OWNER: Member 2.
 * TODO (Member 2): GRACE-FO groundwater trend view. `field.groundwater` carries the regional
 *   trend and local well context; a monthly GRACE series could be added to the backend observation
 *   set (services/nasa_connectors/missions.py) and drawn here as a declining line with the
 *   irrigation seasons shaded.
 * TODO (Member 2): brush to select a span of years and recompute the averages for it.
 */
import { useState } from "react";

import { Term } from "@/components/common/glossary/Term";
import { useUnits } from "@/hooks/useUnits";
import { useMonths, useT } from "@/i18n/LanguageProvider";
import { CHART } from "@/styles/theme";
import type { FieldOverview } from "@/types/api";

import { box, extent, innerW, linePath, niceTicks, scale, Svg, trendLine, YAxis } from "./chartKit";
import { LocalAdviceNote, Takeaway } from "./Takeaway";

type SeriesId = "precip_mm" | "heat_days_35" | "tmean_c" | "max_1day_mm" | "warm_season_wet_root" | "erosive_days";

/** Diverging colour for a moisture anomaly z-score: brown = drier than normal, teal = wetter. */
function anomalyColor(z: number | null): string {
  if (z === null) return "#eee8da";
  const t = Math.max(-2.2, Math.min(2.2, z)) / 2.2;
  if (Math.abs(t) < 0.12) return "#f1ebdc";
  const a = (0.18 + 0.82 * Math.abs(t)).toFixed(2);
  return t < 0 ? `rgba(160, 96, 38, ${a})` : `rgba(32, 124, 134, ${a})`;
}

export function ClimateRecord({ field }: { field: FieldOverview }) {
  const units = useUnits();
  const { t } = useT();
  const { months: MONTHS, initials: MONTH_INITIALS } = useMonths();
  const [series, setSeries] = useState<SeriesId>("heat_days_35");
  const [hover, setHover] = useState<{ y: number; m: number } | null>(null);
  const years = field.series.years;
  const z = field.series.wet_root_z;

  const depth = (v: number) => units.waterValue(v).toFixed(units.system === "us" ? 1 : 0);
  // fmt formats a value on the axis; delta formats a change per decade for the trend sentence
  const options: { id: SeriesId; label: string; fmt: (v: number) => string; delta: (v: number) => string; color: string; zeroBased: boolean }[] = [
    { id: "heat_days_35", label: t("Days at {temp} or hotter", { temp: units.temp(35) }), fmt: (v) => v.toFixed(0), delta: (v) => t("{n} days", { n: v.toFixed(1) }), color: CHART.temp, zeroBased: true },
    { id: "precip_mm", label: t("Yearly rainfall"), fmt: depth, delta: (v) => units.water(v), color: CHART.precip, zeroBased: true },
    { id: "max_1day_mm", label: t("Wettest single day"), fmt: depth, delta: (v) => units.water(v), color: "#2c6e91", zeroBased: true },
    { id: "erosive_days", label: t("Heavy-rain days"), fmt: (v) => v.toFixed(0), delta: (v) => t("{n} days", { n: v.toFixed(1) }), color: "#2c6e91", zeroBased: true },
    { id: "tmean_c", label: t("Average temperature"), fmt: (v) => units.tempValue(v).toFixed(1), delta: (v) => units.tempDelta(v).replace("+", ""), color: CHART.temp, zeroBased: false },
    { id: "warm_season_wet_root", label: t("Growing-season soil wetness (0-1)"), fmt: (v) => v.toFixed(2), delta: (v) => v.toFixed(3), color: CHART.moisture, zeroBased: false },
  ];
  const opt = options.find((o) => o.id === series)!;
  const values = field.climate.annual[series] ?? [];
  const trend = field.climate.trends[series];
  const fit = trendLine(values);
  const yearZ = years
    .map((yr, yi) => {
      const v = (z[yi] ?? []).filter((q): q is number => q !== null);
      return { yr, m: v.length ? v.reduce((a, c) => a + c, 0) / v.length : null };
    })
    .filter((r): r is { yr: number; m: number } => r.m !== null);
  const driestYear = yearZ.length ? yearZ.reduce((a, c) => (c.m < a.m ? c : a)) : null;
  const wettestYear = yearZ.length ? yearZ.reduce((a, c) => (c.m > a.m ? c : a)) : null;

  const b = box(720, 220);
  const x = scale(0, years.length - 1, b.left + 8, b.width - b.right - 8);
  const [lo, hi] = extent(values, 0.12);
  const floor = opt.zeroBased ? 0 : lo;
  const y = scale(floor, hi, b.height - b.bottom, b.top);
  const cellW = innerW(box(720, 0, { left: 40, right: 8 })) / years.length;

  return (
    <div className="stack">
      {driestYear && wettestYear && (
        <Takeaway>
          {t("Since {y0}, the soil here was driest in {dry} and wettest in {wet}. Use the squares below to see whether dry spells are becoming more common, and the second chart to see whether rain, heat or temperature is changing.", { y0: years[0], dry: driestYear.yr, wet: wettestYear.yr })}
        </Takeaway>
      )}
      <div>
        <h4>{t("Drought fingerprint: every month since {y}", { y: years[0] })}</h4>
        <p className="small muted">
          {t("Each square is one month. Brown means the")} <Term id="root_zone_anomaly">{t("root zone")}</Term> {t("was drier than normal for that month; teal means wetter. Read down a column to see one year, across a row to see how a month has changed.")}
        </p>
        <div className="table-scroll">
          <svg viewBox={`0 0 720 ${12 * 15 + 26}`} style={{ width: "100%", minWidth: 520, height: "auto", display: "block" }} role="img" aria-label={t("Root-zone soil moisture anomaly by month and year")}>
            {MONTH_INITIALS.map((l, m) => <text key={m} x={30} y={m * 15 + 11.5} fontSize={9.5} fill={CHART.faint} textAnchor="end">{l}</text>)}
            {years.map((yr, yi) => (
              <g key={yr}>
                {z[yi]?.map((v, m) => (
                  <rect key={m} x={40 + yi * cellW} y={m * 15} width={cellW - 1.5} height={13.5} rx={2} fill={anomalyColor(v)}
                    stroke={hover?.y === yi && hover.m === m ? CHART.ink : "none"} onMouseEnter={() => setHover({ y: yi, m })} onMouseLeave={() => setHover(null)} />
                ))}
                {(yi % 2 === 0 || years.length < 14) && <text x={40 + yi * cellW + cellW / 2} y={12 * 15 + 13} fontSize={9.5} fill={CHART.faint} textAnchor="middle">{`'${String(yr).slice(2)}`}</text>}
              </g>
            ))}
          </svg>
        </div>
        <div className="spread small" style={{ flexWrap: "wrap", marginTop: 4 }}>
          <span className="muted" aria-live="polite">
            {hover && z[hover.y]?.[hover.m] !== null && z[hover.y]?.[hover.m] !== undefined
              ? <><strong>{MONTHS[hover.m]} {years[hover.y]}</strong>: {t(describeZ(z[hover.y][hover.m] as number))} · {t("{r} of rain", { r: units.water(field.series.precip[hover.y][hover.m] ?? 0) })}</>
              : t("Hover a square for the month.")}
          </span>
          <span className="anomaly-scale"><span>{t("much drier")}</span><i style={{ background: "linear-gradient(to right, rgb(160,96,38), #f1ebdc, rgb(32,124,134))" }} /><span>{t("much wetter")}</span></span>
        </div>
      </div>

      <div>
        <div className="spread" style={{ flexWrap: "wrap", marginBottom: 6 }}>
          <h4>{t("Year by year, with the trend")}</h4>
          <select value={series} onChange={(e) => setSeries(e.target.value as SeriesId)} aria-label={t("Series to chart")}>
            {options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </div>
        <Svg b={b} label={opt.label}>
          <YAxis b={b} ticks={niceTicks(floor, hi, 4)} y={y} format={opt.fmt} />
          {opt.zeroBased && values.map((v, i) => v !== null && (
            <rect key={i} x={x(i) - 8} y={y(v)} width={16} height={Math.max(0, y(0) - y(v))} rx={3} fill={opt.color} opacity={0.3}>
              <title>{`${years[i]}: ${opt.fmt(v)}`}</title>
            </rect>
          ))}
          <path d={linePath(values, x, y)} fill="none" stroke={opt.color} strokeWidth={2} />
          {values.map((v, i) => v !== null && <circle key={i} cx={x(i)} cy={y(v)} r={3} fill={opt.color}><title>{`${years[i]}: ${opt.fmt(v)}`}</title></circle>)}
          {fit && <line x1={x(0)} x2={x(years.length - 1)} y1={y(fit.at(0))} y2={y(fit.at(years.length - 1))} stroke={CHART.ink} strokeWidth={1.6} strokeDasharray={trend?.significant ? undefined : "5 4"} />}
          {years.map((yr, i) => i % 3 === 0 && <text key={yr} x={x(i)} y={b.height - b.bottom + 14} fontSize={10} fill={CHART.faint} textAnchor="middle">{yr}</text>)}
        </Svg>
        {trend && (
          <p className="small" style={{ marginTop: 4 }}>
            <span className={`chip ${trend.significant ? "chip-warn" : ""}`}>{trend.significant ? t("Clear trend") : t("No clear trend yet")}</span>{" "}
            <span className="muted">
              {t(trend.per_decade >= 0 ? "Rising by {x} per decade" : "Falling by {x} per decade", { x: opt.delta(Math.abs(trend.per_decade)) })}
              {trend.significant ? "." : `. ${t("A dashed line means the change could be chance: 24 years is a short record.")}`}
            </span>
          </p>
        )}
      </div>
      <LocalAdviceNote />
    </div>
  );
}

function describeZ(z: number): string {
  if (z <= -1.5) return "far drier than normal";
  if (z <= -0.6) return "drier than normal";
  if (z < 0.6) return "about normal";
  if (z < 1.5) return "wetter than normal";
  return "far wetter than normal";
}