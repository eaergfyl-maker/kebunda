/**
 * Net return by year: what each rotation would have earned in every one of the 24 weather
 * years, drawn together so a farmer can see which plans swing most and which bad years hurt.
 *
 * OWNER: Member 2.
 */
import { useState } from "react";

import { useUnits } from "@/hooks/useUnits";
import { useT } from "@/i18n/LanguageProvider";
import { CHART, ROLE_COLOR } from "@/styles/theme";
import type { Strategy } from "@/types/api";

import { box, extent, innerW, linePath, niceTicks, scale, Svg, YAxis } from "./chartKit";
import { LocalAdviceNote, Takeaway } from "./Takeaway";

const PALETTE = ["#2c6e91", "#c9952b", "#9a5ba0", "#4f8f4a", "#c8553d"];

export function NetReturnByYear({ strategies }: { strategies: Strategy[] }) {
  const units = useUnits();
  const { t } = useT();
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const withHistory = strategies.filter((s): s is Strategy & { history: NonNullable<Strategy["history"]> } => s.history !== null);

  let alt = 0;
  const colorOf = new Map<string, string>(
    withHistory.map((s) => [s.id, s.role === "baseline" ? ROLE_COLOR[s.role] ?? CHART.ink : PALETTE[alt++ % PALETTE.length]]),
  );
  const toggle = (id: string) =>
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  if (!withHistory.length) {
    return <div className="notice notice-warn">{t("Year-by-year returns were not available for these rotations.")}</div>;
  }

  const years = withHistory[0].history.years;
  const n = years.length;
  const visible = withHistory.filter((s) => !hidden.has(s.id));
  const [lo0, hi0] = extent(visible.flatMap((s) => s.history.net_per_ha), 0.1);
  const lo = Math.min(lo0, 0);
  const hi = Math.max(hi0, 0);

  const b = box(720, 250);
  const x = scale(0, Math.max(n - 1, 1), b.left + 8, b.width - b.right - 8);
  const y = scale(lo, hi, b.height - b.bottom, b.top);
  const bandW = innerW(b) / Math.max(n, 1);
  const baseline = withHistory.find((s) => s.role === "baseline") ?? withHistory[0];
  const worst = new Set(baseline.history.worst_years);

  // one plain sentence: the best-earning alternative against the current rotation
  let best: (typeof withHistory)[number] | null = null;
  for (const s of withHistory) {
    if (s !== baseline && (!best || s.history.mean_net_per_ha > best.history.mean_net_per_ha)) best = s;
  }
  const money = (v: number) => units.money(v);
  const sentence = best
    ? t(best.history.mean_net_per_ha >= baseline.history.mean_net_per_ha
        ? "In a typical year, {name} earns about {diff} per hectare more than your current rotation. In a bad year it earns {bad}, against {base} for the current one."
        : "In a typical year, {name} earns about {diff} per hectare less than your current rotation. In a bad year it earns {bad}, against {base} for the current one.",
      { name: t(best.title), diff: money(Math.abs(best.history.mean_net_per_ha - baseline.history.mean_net_per_ha)), bad: money(best.history.bad_year_net_per_ha), base: money(baseline.history.bad_year_net_per_ha) })
    : t("In a typical year your current rotation earns {avg} per hectare, and about {bad} in a bad year.", { avg: money(baseline.history.mean_net_per_ha), bad: money(baseline.history.bad_year_net_per_ha) });

  return (
    <div className="stack">
      <p className="small muted" style={{ maxWidth: "70ch" }}>
        {t("What each rotation would have earned on this field in every year of the weather record, per hectare after costs. Lines that swing far up and down are riskier; shaded columns are the worst years for your current rotation.")}
      </p>

      <Takeaway>{sentence}</Takeaway>

      <div className="row-wrap no-print">
        {withHistory.map((s) => {
          const off = hidden.has(s.id);
          return (
            <button key={s.id} type="button" className="chip" aria-pressed={!off} onClick={() => toggle(s.id)}
              style={{ opacity: off ? 0.45 : 1, cursor: "pointer", border: "none" }}>
              <span className="dot" style={{ background: colorOf.get(s.id) }} /> {s.role === "baseline" ? t("Current rotation") : t(s.title)}
            </button>
          );
        })}
      </div>

      <Svg b={b} label={t("Net return per hectare by weather year")}>
        <YAxis b={b} ticks={niceTicks(lo, hi, 4)} y={y} format={(v) => units.money(v)} />
        {years.map((yr, i) => worst.has(yr) && (
          <rect key={`w${yr}`} x={x(i) - bandW / 2} y={b.top} width={bandW} height={b.height - b.bottom - b.top} fill="#c8553d" opacity={0.1}>
            <title>{t("{y}: one of the worst years for the current rotation", { y: yr })}</title>
          </rect>
        ))}
        {lo < 0 && hi > 0 && <line x1={b.left} x2={b.width - b.right} y1={y(0)} y2={y(0)} stroke={CHART.ink} strokeWidth={1.2} strokeDasharray="4 3" opacity={0.6} />}
        {visible.map((s) => {
          const c = colorOf.get(s.id) ?? CHART.ink;
          const isBase = s.role === "baseline";
          return (
            <g key={s.id}>
              <path d={linePath(s.history.net_per_ha, x, y)} fill="none" stroke={c} strokeWidth={isBase ? 2.8 : 2} strokeDasharray={isBase ? undefined : "6 4"} strokeLinejoin="round" />
              {s.history.net_per_ha.map((v, i) => (
                <circle key={i} cx={x(i)} cy={y(v)} r={2.6} fill={c}>
                  <title>{`${years[i]} · ${isBase ? t("Current rotation") : t(s.title)}: ${units.money(v)}/ha`}</title>
                </circle>
              ))}
            </g>
          );
        })}
        {years.map((yr, i) => i % 3 === 0 && (
          <text key={yr} x={x(i)} y={b.height - b.bottom + 14} fontSize={10} fill={CHART.faint} textAnchor="middle">{yr}</text>
        ))}
      </Svg>

      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr><th>{t("Rotation")}</th><th className="num">{t("Average year")}</th><th className="num">{t("A bad year")}</th><th className="num">{t("Swing from weather")}</th></tr>
          </thead>
          <tbody>
            {withHistory.map((s) => (
              <tr key={s.id}>
                <td><span className="dot" style={{ background: colorOf.get(s.id), marginRight: 6 }} />{s.role === "baseline" ? t("Current rotation") : t(s.title)}</td>
                <td className="num">{units.money(s.history.mean_net_per_ha)}</td>
                <td className="num">{units.money(s.history.bad_year_net_per_ha)}</td>
                <td className="num">±{units.money(s.history.weather_sd_per_ha)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="xs faint">
        {t("Simulated from 24 years of weather. Prices and costs are planning averages from DOA, FAMA and MARDI sources, excluding land rent and subsidies, so treat them as a way to compare rotations, not a budget.")}
      </p>
      <LocalAdviceNote />
    </div>
  );
}