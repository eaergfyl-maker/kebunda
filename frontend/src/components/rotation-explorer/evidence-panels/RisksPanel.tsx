import { useFieldShift } from "@/hooks/useFieldShift";
import type { RiskItem } from "@/types/api";

import type { PanelProps } from "./panelRegistry";

const SEVERITY: Record<RiskItem["severity"], { label: string; cls: string }> = {
  critical: { label: "Check before anything else", cls: "chip-bad" },
  caution: { label: "Needs a plan", cls: "chip-warn" },
  check: { label: "Worth a conversation", cls: "chip-info" },
};

/**
 * Pillar 5. A working checklist: each item says who should review it, and ticks are remembered
 * in this browser so the list can be worked through over several visits.
 *
 * TODO (Member 3): extension office lookup. Link each "Extension officer" tag to the district
 *   DOA (Jabatan Pertanian) office for field.farm.district (the directory is public).
 */
export function RisksPanel({ strategy, comparison }: PanelProps) {
  const { reviewed, toggleReviewed } = useFieldShift();
  const risks = strategy.explanation.risks;
  const key = (r: RiskItem) => `${comparison.field_id}:${strategy.id}:${r.id}`;
  const done = risks.filter((r) => reviewed[key(r)]).length;
  const order = { critical: 0, caution: 1, check: 2 } as const;
  const sorted = [...risks].sort((a, b) => order[a.severity] - order[b.severity]);
  return (
    <div className="stack">
      <div className="spread" style={{ flexWrap: "wrap" }}>
        <p className="small muted" style={{ maxWidth: "68ch" }}>
          These are the questions this tool cannot answer. Take them to the people who can. Tick each one off as it is reviewed.
        </p>
        <span className="chip num">{done} of {risks.length} reviewed</span>
      </div>
      <ul className="risk-list">
        {sorted.map((r) => {
          const checked = Boolean(reviewed[key(r)]);
          return (
            <li key={r.id} className={`risk-item ${checked ? "is-done" : ""}`}>
              <label className="risk-check">
                <input type="checkbox" checked={checked} onChange={() => toggleReviewed(key(r))} aria-label={`Mark "${r.title}" as reviewed`} />
              </label>
              <div>
                <div className="row-wrap">
                  <strong>{r.title}</strong>
                  <span className={`chip ${SEVERITY[r.severity].cls}`}>{SEVERITY[r.severity].label}</span>
                  <span className="chip">{r.category}</span>
                </div>
                <p>{r.detail}</p>
                <div className="row-wrap xs" style={{ marginTop: 4 }}>
                  <span className="faint">Review with:</span>
                  {r.who.map((w) => <span key={w} className="who-tag">{w}</span>)}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
