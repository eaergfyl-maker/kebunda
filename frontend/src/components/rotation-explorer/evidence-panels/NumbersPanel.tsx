import { Term } from "@/components/common/glossary/Term";
import { useUnits } from "@/hooks/useUnits";
import { useT } from "@/i18n/LanguageProvider";
import { box, extent, linePath, niceTicks, scale, Svg, YAxis } from "@/components/timelines/chartKit";
import { CHART, ROLE_COLOR } from "@/styles/theme";

import type { PanelProps } from "./panelRegistry";

const FACTOR_LABEL: Record<string, string> = {
  water: "water", heat: "heat", timing: "late planting", salinity: "salt", ph: "soil pH", drainage: "wet soil",
  humidity: "humid-climate disease", rotation: "crop sequence", establishment: "establishment year", growth_window: "short window",
};

/** Extra panel: per-crop yields and budgets, plus net return replayed through 2001-2024 weather. */
export function NumbersPanel({ strategy, baseline }: PanelProps) {
  const units = useUnits();
  const { t, tName } = useT();
  const h = strategy.history;
  const bh = baseline.history;
  return (
    <div className="stack">
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr><th>{t("Crop")}</th><th className="num">{t("Expected yield")}</th><th>{t("Held back by")}</th><th className="num">{t("Irrigation")}</th><th className="num">{t("Nitrogen bought")}</th><th className="num">{t("Revenue")}</th><th className="num">{t("Cost")}</th><th className="num">{t("Net / ha")}</th></tr>
          </thead>
          <tbody>
            {strategy.economics.map((e, i) => {
              const limits = Object.entries(e.yield_factors ?? {}).filter(([, v]) => v < 0.97).sort((a, b) => a[1] - b[1]).slice(0, 2);
              return (
                <tr key={i}>
                  <td><strong>{tName(e.crop_name)}</strong>{e.kind === "cover" && <span className="chip" style={{ marginLeft: 6 }}>{t("cover")}</span>}</td>
                  <td className="num">{e.yield !== null ? `${e.yield.toLocaleString()} ${e.yield_unit}/ha` : "—"}{e.relative_yield !== null && <div className="xs faint">{t("{n}% of local reference", { n: Math.round((e.relative_yield ?? 0) * 100) })}</div>}</td>
                  <td className="small">{limits.length ? limits.map(([k, v]) => `${t(FACTOR_LABEL[k] ?? k)} (−${Math.round((1 - v) * 100)}%)`).join(", ") : e.kind === "cover" ? "" : t("nothing notable")}</td>
                  <td className="num">{e.irrigation_mm ? units.water(e.irrigation_mm) : "—"}</td>
                  <td className="num">{e.n_applied_kg_ha ? units.nitrogen(e.n_applied_kg_ha) : "—"}</td>
                  <td className="num">{units.money(e.revenue)}</td>
                  <td className="num">{units.money(e.cost)}</td>
                  <td className="num"><strong style={{ color: e.net < 0 ? "var(--bad)" : undefined }}>{units.money(e.net)}</strong></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="xs faint">{t("Per hectare for one pass through the rotation, in ringgit. Costs exclude land rent and subsidies. Yields are local reference yields adjusted by the model for water, heat, timing and crop sequence.")}</p>

      {h && (
        <div>
          <h4>{t("If the last 23 years repeated")}</h4>
          <p className="small muted">
            {t("Real weather from each year since {y} is run through the rotation, with every crop of the rotation grown every year.", { y: h.years[0] })}{" "}
            {t("The")} <Term id="bad_year">{t("bad-year")}</Term> {t("figure also includes price swings.")}
          </p>
          <HistoryChart h={h} bh={strategy.role === "baseline" ? null : bh} color={ROLE_COLOR[strategy.role]} />
          <div className="grid-auto" style={{ marginTop: 8 }}>
            <div className="benefit-tile"><div className="eyebrow">{t("Average year")}</div><div className="benefit-value num">{units.money(h.mean_net_per_ha)}/ha</div></div>
            <div className="benefit-tile"><div className="eyebrow">{t("Bad year (1 in 5)")}</div><div className="benefit-value num">{units.money(h.bad_year_net_per_ha)}/ha</div></div>
            <div className="benefit-tile"><div className="eyebrow">{t("Swing from weather alone")}</div><div className="benefit-value num">±{units.money(h.weather_sd_per_ha)}</div></div>
            <div className="benefit-tile"><div className="eyebrow">{t("Hardest years")}</div><div className="benefit-value num" style={{ fontSize: "1.1rem" }}>{h.worst_years.join(", ")}</div></div>
          </div>
        </div>
      )}
    </div>
  );
}

function HistoryChart({ h, bh, color }: { h: NonNullable<PanelProps["strategy"]["history"]>; bh: PanelProps["baseline"]["history"]; color: string }) {
  const { t } = useT();
  const b = box(720, 200);
  const [lo, hi] = extent([...h.net_per_ha, ...(bh?.net_per_ha ?? []), 0], 0.1);
  const x = scale(0, h.years.length - 1, b.left + 6, b.width - b.right - 6);
  const y = scale(lo, hi, b.height - b.bottom, b.top);
  return (
    <Svg b={b} label={t("Net return per hectare by weather year")}>
      <YAxis b={b} ticks={niceTicks(lo, hi, 4)} y={y} format={(v) => `RM ${v}`} title={t("net RM/ha")} />
      <line x1={b.left} x2={b.width - b.right} y1={y(0)} y2={y(0)} stroke={CHART.faint} strokeWidth={1} />
      {bh && <path d={linePath(bh.net_per_ha, x, y)} fill="none" stroke={ROLE_COLOR.baseline} strokeWidth={1.8} strokeDasharray="5 4" />}
      <path d={linePath(h.net_per_ha, x, y)} fill="none" stroke={color} strokeWidth={2.4} />
      {h.net_per_ha.map((v, i) => (
        <circle key={i} cx={x(i)} cy={y(v)} r={h.worst_years.includes(h.years[i]) ? 4.5 : 2.6} fill={h.worst_years.includes(h.years[i]) ? CHART.temp : color}>
          <title>{t("{y} weather: RM {v}/ha", { y: h.years[i], v })}</title>
        </circle>
      ))}
      {h.years.map((yr, i) => i % 3 === 0 && <text key={yr} x={x(i)} y={b.height - b.bottom + 14} fontSize={10} fill={CHART.faint} textAnchor="middle">{yr}</text>)}
      {bh && <text x={b.width - b.right} y={b.top + 4} fontSize={10} fill={ROLE_COLOR.baseline} textAnchor="end">{t("dashed: current rotation")}</text>}
    </Svg>
  );
}
