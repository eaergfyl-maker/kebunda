/**
 * What-if dials: warmer seasons, more or less rain, heavier storms, less irrigation water.
 * Each move re-runs every compared rotation under the shifted climate (see ScenarioResults).
 *
 * OWNER: Member 3.
 * TODO (Member 3): market shock dials (crop price, fertiliser and fuel cost) once the backend
 *   scenario accepts them (backend/app/services/scenario_simulator/simulator.py: LIMITS).
 * TODO (Member 3): "replay a year" presets: pick 2012 or 2019 from the record and stress-test
 *   against that exact year (field.series has every month since 2001).
 */
import "../controls.css";

import { Term } from "@/components/common/glossary/Term";
import { useScenarioPresets } from "@/hooks/useData";
import { isNeutral, NEUTRAL_SCENARIO, useFieldShift } from "@/hooks/useFieldShift";
import { useUnits } from "@/hooks/useUnits";
import type { Scenario, ScenarioKey } from "@/types/api";

const COLOR: Record<ScenarioKey, string> = {
  temp_delta_c: "var(--hz-heat)", rain_pct: "var(--dim-water)", storm_intensity_pct: "var(--hz-storm)", water_cap_pct: "var(--hz-drought)",
};
const ORDER: ScenarioKey[] = ["temp_delta_c", "rain_pct", "storm_intensity_pct", "water_cap_pct"];

export function ScenarioSliders({ irrigated }: { irrigated: boolean }) {
  const { data } = useScenarioPresets();
  const { scenario, setScenario } = useFieldShift();
  const units = useUnits();
  if (!data) return null;

  const show = (key: ScenarioKey, v: number): string => {
    if (key === "temp_delta_c") return v === 0 ? "as today" : `${units.tempDelta(v)} ${v > 0 ? "warmer" : "cooler"}`;
    if (key === "rain_pct") return v === 0 ? "as today" : `${v > 0 ? "+" : ""}${v}% rain`;
    if (key === "storm_intensity_pct") return v === 0 ? "as today" : `storms ${v}% heavier`;
    return v === 100 ? "full allocation" : v === 0 ? "no irrigation" : `${v}% of allocation`;
  };
  const same = (a: Scenario, b: Scenario) => ORDER.every((k) => a[k] === b[k]);

  return (
    <div className="stack">
      <div className="row-wrap" role="group" aria-label="Scenario presets">
        {data.presets.filter((p) => irrigated || p.id !== "water_cut").map((p) => (
          <button key={p.id} className={`btn btn-sm ${same(p.scenario, scenario) ? "btn-primary" : ""}`} title={p.description}
            onClick={() => setScenario(irrigated ? p.scenario : { ...p.scenario, water_cap_pct: 100 })}>{p.label}</button>
        ))}
      </div>
      <div className="slider-list">
        {ORDER.filter((k) => irrigated || k !== "water_cap_pct").map((key) => {
          const lim = data.limits[key];
          const v = scenario[key];
          const pct = ((v - lim.min) / (lim.max - lim.min)) * 100;
          const neutral = NEUTRAL_SCENARIO[key];
          return (
            <div key={key} className="slider-row">
              <div className="slider-head">
                <label htmlFor={`sc-${key}`}><strong>{lim.label}</strong></label>
                <span className="slider-word num" style={{ color: v === neutral ? "var(--ink-faint)" : COLOR[key] }}>{show(key, v)}</span>
              </div>
              <input id={`sc-${key}`} type="range" min={lim.min} max={lim.max} step={lim.step} value={v} aria-valuetext={show(key, v)}
                style={{ ["--pct" as string]: `${pct}%`, ["--track-fill" as string]: COLOR[key] }}
                onChange={(e) => setScenario({ ...scenario, [key]: Number(e.target.value) })} />
              <p className="xs faint">{lim.plain}</p>
            </div>
          );
        })}
      </div>
      <p className="xs faint">
        A <Term id="stress_test">stress test</Term> shifts the weather actually observed here from 2001 to 2024. {data.note}
        {!isNeutral(scenario) && <> <button className="btn btn-ghost btn-sm" onClick={() => setScenario(NEUTRAL_SCENARIO)}>Back to today's climate</button></>}
      </p>
    </div>
  );
}
