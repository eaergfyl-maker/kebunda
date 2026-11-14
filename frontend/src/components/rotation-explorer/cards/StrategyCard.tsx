/**
 * One rotation strategy at a glance: what it is, how well it fits, how it scores on the
 * five goals (with the current rotation marked on each bar), and four headline numbers.
 *
 * OWNER: Member 3.
 * TODO (Member 3): "pin" button to keep a strategy visible while priorities change, and a
 *   share link that encodes field, priorities and the pinned rotation in the URL.
 */
import { Delta, ScoreBar } from "@/components/common/ui";
import { useUnits } from "@/hooks/useUnits";
import { DIM_COLOR, DIM_SHORT, ROLE_COLOR } from "@/styles/theme";
import type { Strategy } from "@/types/api";
import { DIMENSIONS } from "@/types/api";

import { SequenceStrip } from "../sequence-builder/SequenceStrip";

export function FitDial({ value, color, size = 64 }: { value: number; color: string; size?: number }) {
  const r = size / 2 - 5;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Fit ${Math.round(value)} out of 100`} className="fit-dial">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--paper-sunk)" strokeWidth={6} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={6} strokeLinecap="round"
        strokeDasharray={`${(value / 100) * c} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: "stroke-dasharray 420ms var(--ease)" }} />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" fontSize={size * 0.3} fontWeight={650} fill="var(--ink)" fontFamily="var(--font-display)">{Math.round(value)}</text>
    </svg>
  );
}

export function StrategyCard({ strategy, baseline, selected, isTop, tied, onSelect }: {
  strategy: Strategy; baseline: Strategy; selected: boolean; isTop: boolean; tied: boolean; onSelect: () => void;
}) {
  const units = useUnits();
  const color = ROLE_COLOR[strategy.role];
  const isBase = strategy.role === "baseline";
  const unc = strategy.explanation.gaps.score_uncertainty;
  const change = strategy.fit.change;
  return (
    <article className={`strategy-card ${selected ? "is-selected" : ""}`} style={{ ["--role" as string]: color }}>
      <button className="strategy-card-hit" onClick={onSelect} aria-pressed={selected} aria-label={`Show details for ${strategy.title}: ${strategy.name}`} />
      <header className="strategy-card-head">
        <div style={{ minWidth: 0 }}>
          <div className="row-wrap">
            <span className="strategy-role" style={{ background: color }}>{strategy.title}</span>
            {isTop && <span className="chip chip-good">Best fit{tied ? " (tied)" : ""}</span>}
            {!isTop && tied && <span className="chip">Tied with best</span>}
          </div>
          <h3 className="strategy-name">{strategy.name}</h3>
          <p className="small muted">{strategy.tagline}</p>
        </div>
        <div className="strategy-fit">
          <FitDial value={strategy.fit.fit} color={color} />
          <span className="xs faint">fit for your goals</span>
        </div>
      </header>

      <SequenceStrip years={strategy.year_labels} compact />
      <div className="row-wrap xs">
        <span className="chip">{strategy.tillage_label}</span>
        {!isBase && change.new_crops.length > 0 && <span className="chip chip-info">{change.new_crops.length} new crop{change.new_crops.length > 1 ? "s" : ""}</span>}
        {!isBase && change.adds_cover_crops && <span className="chip chip-info">adds cover crops</span>}
        {!isBase && change.tillage_change && <span className="chip chip-info">tillage change</span>}
        {strategy.equipment_needed.length > 0 && <span className="chip chip-warn">needs equipment</span>}
      </div>

      <div className="strategy-scores">
        {DIMENSIONS.map((d) => (
          <div key={d} className="strategy-score-row">
            <span className="small">{DIM_SHORT[d]}</span>
            <ScoreBar value={strategy.scores[d]} color={DIM_COLOR[d]} baseline={isBase ? undefined : baseline.scores[d]} uncertainty={unc[d]} label={DIM_SHORT[d]} />
            <span className="small num">{Math.round(strategy.scores[d])}</span>
          </div>
        ))}
      </div>

      <dl className="strategy-numbers">
        {strategy.headline_numbers.map((h) => {
          const diff = h.value - h.baseline;
          const tol = Math.max(Math.abs(h.baseline) * 0.03, 0.05);
          const direction = Math.abs(diff) <= tol ? "same" : (diff > 0) === h.higher_is_better ? "better" : "worse";
          return (
            <div key={h.label}>
              <dt>{h.label}</dt>
              <dd className="num">{units.metric(h.value, h.unit)}</dd>
              {!isBase && <Delta direction={direction} rising={diff > 0}>{direction === "same" ? "same" : `${diff > 0 ? "+" : "−"}${units.metric(Math.abs(diff), h.unit).replace(/^[−+]/, "")}`}</Delta>}
            </div>
          );
        })}
      </dl>
      <span className="strategy-open small">{selected ? "Showing the full explanation below ↓" : "See why, evidence, gaps and risks →"}</span>
    </article>
  );
}
