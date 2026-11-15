/**
 * Side-by-side matrix: every strategy as a column, every key outcome as a row, the best
 * value in each row highlighted. The quickest way to see trade-offs across all options.
 *
 * OWNER: Member 3.
 * TODO (Member 3): let the farmer choose which rows to show and remember the choice.
 */
import { useUnits } from "@/hooks/useUnits";
import { DIM_COLOR, DIM_SHORT, ROLE_COLOR } from "@/styles/theme";
import type { DimensionId, Metrics, Strategy } from "@/types/api";

const ROWS: { key: keyof Metrics; label: string; unit: string; higher: boolean; dim: DimensionId; irrigatedOnly?: boolean }[] = [
  { key: "irrigation_mm_yr", label: "Irrigation pumped", unit: "mm/yr", higher: false, dim: "water", irrigatedOnly: true },
  { key: "water_stress_pct", label: "Crop water stress", unit: "%", higher: false, dim: "water" },
  { key: "om_change_pct_points_10yr", label: "Organic matter in 10 years", unit: "% points", higher: true, dim: "soil" },
  { key: "n_fertilizer_kg_ha_yr", label: "Nitrogen bought", unit: "kg N/ha/yr", higher: false, dim: "soil" },
  { key: "living_root_months_per_year", label: "Months with living roots", unit: "months", higher: true, dim: "soil" },
  { key: "bare_months_per_year", label: "Months of bare soil", unit: "months", higher: false, dim: "erosion" },
  { key: "soil_loss_tons_ac_yr", label: "Soil erosion", unit: "tons/ac/yr", higher: false, dim: "erosion" },
  { key: "infiltration_pct", label: "Rain that soaks in", unit: "%", higher: true, dim: "erosion" },
  { key: "pest_break_score", label: "Pest and disease break", unit: "/100", higher: true, dim: "pest" },
  { key: "net_return_per_ha_yr", label: "Net return per hectare", unit: "RM/yr", higher: true, dim: "income" },
];

export function CompareMatrix({ strategies, selectedId, onSelect }: { strategies: Strategy[]; selectedId: string; onSelect: (id: string) => void }) {
  const units = useUnits();
  const irrigated = strategies.some((s) => s.metrics.irrigation_mm_yr > 0);
  const rows = ROWS.filter((r) => !r.irrigatedOnly || irrigated);
  return (
    <div className="table-scroll">
      <table className="table matrix">
        <thead>
          <tr>
            <th />
            {strategies.map((s) => (
              <th key={s.id} className={s.id === selectedId ? "is-selected" : ""}>
                <button onClick={() => onSelect(s.id)} className="matrix-head">
                  <span className="dot" style={{ background: ROLE_COLOR[s.role] }} /> {s.role === "baseline" ? "Now" : s.title}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Fit for your goals</strong></td>
            {strategies.map((s) => <td key={s.id} className={`num ${s.id === selectedId ? "is-selected" : ""}`}><strong>{Math.round(s.fit.fit)}</strong></td>)}
          </tr>
          {rows.map((r) => {
            const vals = strategies.map((s) => s.metrics[r.key] as number);
            const best = r.higher ? Math.max(...vals) : Math.min(...vals);
            return (
              <tr key={r.key}>
                <td><span className="matrix-dim" style={{ background: DIM_COLOR[r.dim] }} title={DIM_SHORT[r.dim]} />{r.label}</td>
                {strategies.map((s, i) => (
                  <td key={s.id} className={`num ${s.id === selectedId ? "is-selected" : ""} ${vals[i] === best && new Set(vals).size > 1 ? "is-best" : ""}`}>
                    {units.metric(vals[i], r.unit)}
                  </td>
                ))}
              </tr>
            );
          })}
          <tr>
            <td>Bad-year net return (1 in 5)</td>
            {strategies.map((s) => <td key={s.id} className={`num ${s.id === selectedId ? "is-selected" : ""}`}>{s.history ? units.money(s.history.bad_year_net_per_ha) : "—"}</td>)}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
