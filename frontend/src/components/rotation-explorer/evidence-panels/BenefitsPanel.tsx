import { Delta } from "@/components/common/ui";
import { useUnits } from "@/hooks/useUnits";
import { DIM_COLOR, DIM_SHORT } from "@/styles/theme";
import type { BenefitItem, DimensionId } from "@/types/api";
import { DIMENSIONS } from "@/types/api";

import type { PanelProps } from "./panelRegistry";

/** Pillar 3. Every change against the current rotation, gains and costs alike, with its confidence. */
export function BenefitsPanel({ strategy, baseline }: PanelProps) {
  const units = useUnits();
  if (strategy.role === "baseline") {
    return (
      <div className="stack">
        <p className="muted">This is the reference every alternative is measured against. Its own numbers:</p>
        <div className="grid-auto">
          {strategy.headline_numbers.map((h) => (
            <div key={h.label} className="benefit-tile">
              <div className="eyebrow">{h.label}</div>
              <div className="benefit-value num">{units.metric(h.value, h.unit)}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }
  const items = strategy.explanation.benefits.items;
  const byDim = DIMENSIONS.map((d) => ({ d, rows: items.filter((b) => b.dimension === d) })).filter((g) => g.rows.length);
  return (
    <div className="stack">
      <p>{strategy.explanation.benefits.summary}</p>
      <div className="table-scroll">
        <table className="table benefits-table">
          <thead>
            <tr><th>What changes</th><th className="num">Now</th><th className="num">With this rotation</th><th className="num">Change</th><th>How sure</th></tr>
          </thead>
          <tbody>
            {byDim.map(({ d, rows }) => rows.map((b, i) => <Row key={b.metric} b={b} d={d} first={i === 0} span={rows.length} units={units} />))}
          </tbody>
        </table>
      </div>
      <p className="xs faint">
        Compared with “{baseline.name}”. Ranges in brackets are the plausible spread given data and model confidence for that topic.
        Dollar figures exclude land cost and are for ranking options, not budgeting.
      </p>
    </div>
  );
}

function Row({ b, d, first, span, units }: { b: BenefitItem; d: DimensionId; first: boolean; span: number; units: ReturnType<typeof useUnits> }) {
  const sign = b.delta > 0 ? "+" : "";
  const deltaText = b.unit.startsWith("$") ? `${b.delta < 0 ? "−" : "+"}${units.money(Math.abs(b.delta))}` : `${sign}${units.metric(b.delta, b.unit).replace(/^\+/, "")}`;
  return (
    <tr>
      <td>
        {first && <span className="benefit-dim" style={{ color: DIM_COLOR[d] }} data-span={span}>{DIM_SHORT[d]}</span>}
        <strong>{b.label}</strong>
        <div className="xs faint">{b.meaning}</div>
      </td>
      <td className="num muted">{units.metric(b.baseline, b.unit)}</td>
      <td className="num"><strong>{units.metric(b.value, b.unit)}</strong></td>
      <td className="num">
        <Delta direction={b.direction} rising={b.delta > 0}>{b.direction === "same" ? "about the same" : deltaText}</Delta>
        {b.range && b.direction !== "same" && (
          <div className="xs faint num">[{units.metric(b.range[0], b.unit)} to {units.metric(b.range[1], b.unit)}]</div>
        )}
      </td>
      <td><span className={`chip ${b.confidence === "high" ? "chip-good" : b.confidence === "moderate" ? "chip-warn" : "chip-bad"}`}>{b.confidence}</span></td>
    </tr>
  );
}
