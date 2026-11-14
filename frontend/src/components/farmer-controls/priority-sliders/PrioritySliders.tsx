/**
 * "What matters most on your farm?" Five sliders, one per goal, plus one-click presets.
 * Moving a slider only re-ranks rotations that are already simulated, so it is instant.
 *
 * OWNER: Member 3.
 * TODO (Member 3): a "rank them" alternative for people who dislike sliders: drag the five
 *   goals into order and convert the order to weights (10, 8, 6, 4, 2).
 * TODO (Member 3): voice-friendly mode: read each goal aloud and accept "more" / "less".
 */
import "../controls.css";

import { useRotationOptions } from "@/hooks/useData";
import { useFieldShift } from "@/hooks/useFieldShift";
import { DIM_COLOR, DIM_ICON } from "@/styles/theme";
import type { DimensionId, Priorities } from "@/types/api";

const WORDS = ["Ignore", "Minor", "Minor", "Some", "Some", "Matters", "Matters", "Important", "Important", "Critical", "Critical"];

export function PrioritySliders({ effective, defaults }: { effective: Priorities; defaults: Priorities }) {
  const { data: options } = useRotationOptions();
  const { priorities, setPriority, setPriorities } = useFieldShift();
  const touched = Object.keys(priorities).length > 0;
  const activePreset = options?.priority_presets.find((p) => (Object.keys(p.priorities) as DimensionId[]).every((d) => p.priorities[d] === effective[d]));

  return (
    <div className="stack">
      <div className="row-wrap" role="group" aria-label="Priority presets">
        {options?.priority_presets.map((p) => (
          <button key={p.id} className={`btn btn-sm ${activePreset?.id === p.id ? "btn-primary" : ""}`} title={p.description} onClick={() => setPriorities(p.priorities)}>{p.label}</button>
        ))}
        {touched && <button className="btn btn-ghost btn-sm" onClick={() => setPriorities({})}>Reset to this field's defaults</button>}
      </div>
      <div className="slider-list">
        {(options?.dimensions ?? []).map((d) => {
          const v = effective[d.id];
          return (
            <div key={d.id} className="slider-row">
              <div className="slider-head">
                <span className="slider-icon" aria-hidden>{DIM_ICON[d.id]}</span>
                <label htmlFor={`prio-${d.id}`}><strong>{d.label}</strong></label>
                <span className="slider-word" style={{ color: DIM_COLOR[d.id] }}>{WORDS[Math.round(v)]}</span>
              </div>
              <input
                id={`prio-${d.id}`} type="range" min={0} max={10} step={1} value={v} aria-valuetext={`${WORDS[Math.round(v)]} (${v} of 10)`}
                style={{ ["--pct" as string]: `${v * 10}%`, ["--track-fill" as string]: DIM_COLOR[d.id] }}
                onChange={(e) => setPriority(d.id, Number(e.target.value))}
              />
              <p className="xs faint">{d.help}{defaults[d.id] !== v && <span> · field default: {WORDS[Math.round(defaults[d.id])].toLowerCase()}</span>}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
