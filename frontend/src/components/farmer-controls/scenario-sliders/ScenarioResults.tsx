/**
 * What the scenario does: to the weather, to each rotation's fit and income, and to each crop.
 *
 * OWNER: Member 3.
 * Tipping-point explorer (Member 3). useSweep(fieldId, strategies, "rain_pct") returns fit
 *   and net return across a dial's whole range plus `crossings` (where the leader changes).
 *   DONE: TippingOverview (below) shows all dials as small multiples.
 */
import { useState } from "react";

import { Loading } from "@/components/common/ui";
import { box, extent, linePath, niceTicks, scale, Svg, YAxis } from "@/components/timelines/chartKit";
import { useSweep } from "@/hooks/useData";
import { useUnits } from "@/hooks/useUnits";
import { CHART, ROLE_COLOR } from "@/styles/theme";
import type { ScenarioKey, Strategy, StrategyRole, StressTestResponse } from "@/types/api";

const SHIFT_LABEL: Record<string, string> = {
  annual_precip_mm: "Rain and snow per year", reference_et_mm: "Air's thirst (ET0) per year", heat_days_35: "Days at 35 °C (95 °F) or hotter",
  frost_days: "Frost days", erosivity_r: "Erosive power of rain", rain_per_wet_day_mm: "Rain on a typical wet day", irrigation_allocation_mm: "Irrigation you can pump",
};

export function ScenarioResults({ result, refreshing }: { result: StressTestResponse; refreshing: boolean }) {
  const units = useUnits();
  const rows = result.strategies;
  const maxFit = 100;
  const fmtShift = (key: string, v: number | null) => {
    if (v === null) return "—";
    if (key.endsWith("_mm")) return units.water(v);
    if (key === "erosivity_r") return v.toLocaleString();
    return String(v);
  };
  return (
    <div className={`stack ${refreshing ? "refreshing" : ""}`}>
      <div className={`notice ${result.ranking_changed ? "notice-warn" : "notice-info"}`}>
        <strong>{result.ranking_changed ? "The ranking changes under this scenario." : "The ranking holds under this scenario."}</strong> {result.verdict}
      </div>

      <div>
        <h4>What this scenario does to the weather here</h4>
        <div className="shift-grid">
          {Object.entries(result.climate_shift).filter(([, v]) => v.today !== null).map(([key, v]) => (
            <div key={key} className={`shift-cell ${v.delta ? "is-changed" : ""}`}>
              <div className="xs faint">{SHIFT_LABEL[key] ?? key}</div>
              <div className="num"><span className="muted">{fmtShift(key, v.today)}</span> → <strong>{fmtShift(key, v.scenario)}</strong></div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h4>How each rotation holds up</h4>
        <div className="stress-list">
          {rows.map((r) => {
            const color = ROLE_COLOR[(r.role as StrategyRole) ?? "match"] ?? ROLE_COLOR.match;
            const net = r.metrics.net_return_per_acre_yr;
            const irr = r.metrics.irrigation_mm_yr;
            return (
              <div key={r.id} className="stress-row">
                <div className="stress-name">
                  <span className="dot" style={{ background: color }} />
                  <div>
                    <strong>{r.name}</strong>
                    {!r.feasible && <span className="chip chip-bad" style={{ marginLeft: 6 }}>no longer fits</span>}
                    {r.flags.map((f, i) => <div key={i} className="xs" style={{ color: "var(--bad)" }}>⚠ {f}</div>)}
                  </div>
                </div>
                <div className="stress-bars" title={`Fit today ${r.fit.today}, under scenario ${r.fit.scenario}`}>
                  <div className="stress-bar"><span style={{ width: `${(r.fit.today / maxFit) * 100}%`, background: color, opacity: 0.3 }} /><em className="num">{Math.round(r.fit.today)}</em></div>
                  <div className="stress-bar"><span style={{ width: `${(r.fit.scenario / maxFit) * 100}%`, background: color }} /><em className="num">{Math.round(r.fit.scenario)}</em></div>
                </div>
                <div className="stress-nums small num">
                  <div><span className="faint">Net/acre</span> {units.money(net.today)} → <strong style={{ color: net.delta < -15 ? "var(--bad)" : net.delta > 15 ? "var(--good)" : undefined }}>{units.money(net.scenario)}</strong></div>
                  {r.bad_year_net_per_acre && <div><span className="faint">Bad year</span> {units.money(r.bad_year_net_per_acre.today)} → <strong>{units.money(r.bad_year_net_per_acre.scenario)}</strong></div>}
                  {irr && (irr.today > 0 || irr.scenario > 0) && <div><span className="faint">Irrigation</span> {units.water(irr.today)} → <strong>{units.water(irr.scenario)}</strong></div>}
                  <div><span className="faint">Water stress</span> {r.metrics.water_stress_pct.today}% → <strong>{r.metrics.water_stress_pct.scenario}%</strong></div>
                  <div><span className="faint">Erosion</span> {units.soilLoss(r.metrics.soil_loss_tons_ac_yr.today)} → <strong>{units.soilLoss(r.metrics.soil_loss_tons_ac_yr.scenario)}</strong></div>
                </div>
                <div className="stress-yields xs">
                  {r.yields.map((y, i) => (
                    <span key={i} className={`chip ${y.change_pct <= -10 ? "chip-bad" : y.change_pct >= 5 ? "chip-good" : ""}`} title={y.limiting ? `Most limited by ${y.limiting}` : undefined}>
                      {y.crop_name.replace(/ \(.*\)/, "")} {y.change_pct > 0 ? "+" : ""}{y.change_pct}%
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
        <p className="xs faint" style={{ marginTop: 6 }}>Pale bar: fit under today's climate. Solid bar: fit under the scenario. Chips show each crop's yield change.</p>
      </div>
    </div>
  );
}

/** Fit of every strategy as one dial is swept across its range, with the points where the leader changes. */
export function TippingPoints({ fieldId, strategies, irrigated }: { fieldId: string; strategies: Strategy[]; irrigated: boolean }) {
  const [param, setParam] = useState<ScenarioKey>(irrigated ? "water_cap_pct" : "rain_pct");
  const [measure, setMeasure] = useState<"fit" | "net">("net");
  const { data, loading } = useSweep(fieldId, strategies, param);
  const options: { id: ScenarioKey; label: string }[] = [
    { id: "rain_pct", label: "Rainfall" }, { id: "temp_delta_c", label: "Temperature" }, { id: "storm_intensity_pct", label: "Storm intensity" },
    ...(irrigated ? [{ id: "water_cap_pct" as ScenarioKey, label: "Irrigation water" }] : []),
  ];
  const b = box(720, 240, { right: 20 });
  return (
    <div className="stack-sm">
      <div className="spread" style={{ flexWrap: "wrap" }}>
        <h4>Where do the rotations trade places?</h4>
        <div className="row-wrap no-print">
          <select value={param} onChange={(e) => setParam(e.target.value as ScenarioKey)} aria-label="Dial to sweep">{options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}</select>
          <select value={measure} onChange={(e) => setMeasure(e.target.value as "fit" | "net")} aria-label="Measure"><option value="net">Net return per acre</option><option value="fit">Fit score</option></select>
        </div>
      </div>
      {loading || !data ? <Loading height={200} label="Sweeping the scenario range" /> : (() => {
        const all = data.series.flatMap((s) => s[measure]);
        const [lo, hi] = extent(all, 0.08);
        const x = scale(0, data.values.length - 1, b.left + 6, b.width - b.right - 6);
        const y = scale(lo, hi, b.height - b.bottom, b.top);
        const roleOf = (id: string | null) => strategies.find((s) => s.id === id)?.role ?? "match";
        return (
          <>
            <Svg b={b} label={`${measure === "net" ? "Net return" : "Fit"} of each rotation across the ${data.label.toLowerCase()} range`}>
              <YAxis b={b} ticks={niceTicks(lo, hi, 4)} y={y} format={(v) => (measure === "net" ? `$${v}` : String(v))} title={measure === "net" ? "net $/acre" : "fit (0-100)"} />
              {data.crossings.map((c, i) => {
                const i0 = data.values.indexOf(c.between[0]);
                return <rect key={i} x={x(i0)} width={x(i0 + 1) - x(i0)} y={b.top} height={b.height - b.top - b.bottom} fill="#e9b44c" opacity={0.18} />;
              })}
              {data.series.map((s) => (
                <g key={s.id}>
                  <path d={linePath(s[measure], x, y)} fill="none" stroke={ROLE_COLOR[roleOf(s.id)]} strokeWidth={roleOf(s.id) === "baseline" ? 1.8 : 2.4} strokeDasharray={roleOf(s.id) === "baseline" ? "5 4" : undefined} />
                  {s[measure].map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r={s.feasible[i] ? 2.8 : 4} fill={s.feasible[i] ? ROLE_COLOR[roleOf(s.id)] : "#fff"} stroke={ROLE_COLOR[roleOf(s.id)]}><title>{`${s.name}: ${v} at ${data.values[i]} ${data.unit}`}</title></circle>)}
                </g>
              ))}
              {data.values.map((v, i) => <text key={i} x={x(i)} y={b.height - b.bottom + 14} fontSize={10} fill={CHART.faint} textAnchor="middle">{v > 0 && param !== "water_cap_pct" ? "+" : ""}{v}{data.unit.startsWith("%") ? "%" : "°C"}</text>)}
            </Svg>
            <div className="chart-legend">
              {data.series.map((s) => <span key={s.id} className="chart-legend-item"><span className="chart-swatch-line" style={{ borderTopColor: ROLE_COLOR[roleOf(s.id)], borderTopStyle: roleOf(s.id) === "baseline" ? "dashed" : "solid" }} />{s.name.length > 46 ? s.name.slice(0, 44) + "…" : s.name}</span>)}
            </div>
            <p className="small muted">
              {data.crossings.length
                ? data.crossings.map((c, i) => <span key={i}>Between {c.between[0]} and {c.between[1]} {data.unit}, the best-fitting rotation changes from “{c.from}” to “{c.to}”. </span>)
                : "The same rotation fits best across this whole range: the choice is robust to this dial."}
              {" "}Shaded bands mark where the leader changes; hollow points are where a rotation stops fitting the season.
            </p>
          </>
        );
      })()}
    </div>
  );
}

/** One compact chart for a single dial, with a plain-language verdict underneath. */
function SweepMini({ fieldId, strategies, param, title, measure }: { fieldId: string; strategies: Strategy[]; param: ScenarioKey; title: string; measure: "fit" | "net" }) {
  const { data, loading } = useSweep(fieldId, strategies, param);
  const b = box(340, 130, { left: 38, right: 8, top: 8, bottom: 22 });
  const roleOf = (id: string | null) => strategies.find((s) => s.id === id)?.role ?? "match";
  const fmtX = (v: number, unit: string) => `${v > 0 && param !== "water_cap_pct" ? "+" : ""}${v}${unit.startsWith("%") ? "%" : "°C"}`;
  return (
    <div className="mini-card">
      <strong className="small">{title}</strong>
      {loading || !data ? <Loading height={130} label="Sweeping" /> : (() => {
        const [lo, hi] = extent(data.series.flatMap((s) => s[measure]), 0.08);
        const x = scale(0, data.values.length - 1, b.left + 4, b.width - b.right - 4);
        const y = scale(lo, hi, b.height - b.bottom, b.top);
        const last = data.values.length - 1;
        const mid = Math.floor(last / 2);
        const robust = data.crossings.length === 0;
        return (
          <>
            <Svg b={b} label={`${title}: ${measure === "net" ? "net return" : "fit"} of each rotation`}>
              <YAxis b={b} ticks={niceTicks(lo, hi, 3)} y={y} format={(v) => (measure === "net" ? `$${v}` : String(v))} />
              {data.crossings.map((c, i) => {
                const i0 = data.values.indexOf(c.between[0]);
                return <rect key={i} x={x(i0)} width={x(i0 + 1) - x(i0)} y={b.top} height={b.height - b.top - b.bottom} fill="#e9b44c" opacity={0.2} />;
              })}
              {data.series.map((s) => (
                <path key={s.id} d={linePath(s[measure], x, y)} fill="none" stroke={ROLE_COLOR[roleOf(s.id)]} strokeWidth={roleOf(s.id) === "baseline" ? 1.4 : 2} strokeDasharray={roleOf(s.id) === "baseline" ? "4 3" : undefined} />
              ))}
              {[0, mid, last].map((i) => <text key={i} x={x(i)} y={b.height - 6} fontSize={9} fill={CHART.faint} textAnchor="middle">{fmtX(data.values[i], data.unit)}</text>)}
            </Svg>
            <span className={`chip ${robust ? "chip-good" : "chip-warn"}`}>
              {robust ? "Same winner across the range" : `Winner changes at ${data.crossings[0].between[0]} to ${data.crossings[0].between[1]} ${data.unit}`}
            </span>
          </>
        );
      })()}
    </div>
  );
}

/** Small multiples: every dial's tipping points side by side, so the farmer sees which risk matters most. */
export function TippingOverview({ fieldId, strategies, irrigated }: { fieldId: string; strategies: Strategy[]; irrigated: boolean }) {
  const [measure, setMeasure] = useState<"fit" | "net">("net");
  const dials: { id: ScenarioKey; title: string }[] = [
    { id: "rain_pct", title: "Rainfall" }, { id: "temp_delta_c", title: "Temperature" }, { id: "storm_intensity_pct", title: "Storm intensity" },
    ...(irrigated ? [{ id: "water_cap_pct" as ScenarioKey, title: "Irrigation water" }] : []),
  ];
  return (
    <div className="stack-sm">
      <div className="spread" style={{ flexWrap: "wrap" }}>
        <h4>Which dial could change the winner?</h4>
        <select className="no-print" value={measure} onChange={(e) => setMeasure(e.target.value as "fit" | "net")} aria-label="Measure for overview charts">
          <option value="net">Net return per acre</option><option value="fit">Fit score</option>
        </select>
      </div>
      <div className="mini-grid">
        {dials.map((d) => <SweepMini key={d.id} fieldId={fieldId} strategies={strategies} param={d.id} title={d.title} measure={measure} />)}
      </div>
      <p className="xs faint">Each chart varies one dial across its range. A shaded band means a different rotation takes the lead there; no band means your best choice is robust to that dial.</p>
    </div>
  );
}
