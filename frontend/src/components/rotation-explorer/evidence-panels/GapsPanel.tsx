import { Term } from "@/components/common/glossary/Term";
import { ScoreBar } from "@/components/common/ui";
import { DIM_COLOR, DIM_SHORT } from "@/styles/theme";
import type { GapItem } from "@/types/api";
import { DIMENSIONS } from "@/types/api";

import type { PanelProps } from "./panelRegistry";

const KIND: Record<GapItem["kind"], string> = {
  data: "Missing or borrowed data", resolution: "Pixel too coarse", model: "Model limit", validation: "Satellite check", blind_spot: "Invisible from orbit",
};
const SEVERITY: Record<GapItem["severity"], string> = { high: "chip-bad", medium: "chip-warn", low: "chip-info", standing: "" };

/** Pillar 4. What is thin or missing for this field, how sure each score is, and how to close each gap. */
export function GapsPanel({ strategy }: PanelProps) {
  const g = strategy.explanation.gaps;
  const specific = g.items.filter((i) => i.kind !== "blind_spot");
  const standing = g.items.filter((i) => i.kind === "blind_spot");
  return (
    <div className="stack">
      <div className="conf-grid">
        {DIMENSIONS.map((d) => (
          <div key={d} className="conf-cell">
            <div className="spread small">
              <strong style={{ color: DIM_COLOR[d] }}>{DIM_SHORT[d]}</strong>
              <span className={`chip ${g.confidence[d].label === "high" ? "chip-good" : g.confidence[d].label === "moderate" ? "chip-warn" : "chip-bad"}`}>{g.confidence[d].label}</span>
            </div>
            <ScoreBar value={g.confidence[d].combined * 100} color={DIM_COLOR[d]} label={`${DIM_SHORT[d]} confidence`} />
            <div className="xs faint num">score ± {g.score_uncertainty[d]} pts · data {Math.round(g.confidence[d].data * 100)} · model {Math.round(g.confidence[d].model * 100)}</div>
          </div>
        ))}
      </div>
      <p className="small muted"><Term id="confidence">Confidence</Term>: {g.statement}</p>

      {specific.length > 0 && (
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>Gaps specific to this field and rotation</div>
          <ul className="gap-list">
            {specific.map((i) => <Gap key={i.id} item={i} />)}
          </ul>
        </div>
      )}
      <div>
        <div className="eyebrow" style={{ marginBottom: 8 }}>What no satellite can observe</div>
        <ul className="gap-list is-standing">
          {standing.map((i) => <Gap key={i.id} item={i} />)}
        </ul>
      </div>
    </div>
  );
}

function Gap({ item }: { item: GapItem }) {
  return (
    <li className="gap-item">
      <div className="row-wrap">
        <span className={`chip ${SEVERITY[item.severity]}`}>{KIND[item.kind]}</span>
        <strong>{item.topic}</strong>
      </div>
      <p>{item.detail}</p>
      <p className="gap-close"><span aria-hidden>→ </span><strong>To close it:</strong> {item.close_by}</p>
    </li>
  );
}
