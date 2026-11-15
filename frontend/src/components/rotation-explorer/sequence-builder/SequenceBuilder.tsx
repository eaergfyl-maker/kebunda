/**
 * Build-your-own rotation. The farmer adds years and crops, then FieldShift scores the
 * result with the same models as its own suggestions, or adopts it as the current rotation.
 *
 * OWNER: Member 3.
 *
 * TODO (Member 3): drag-and-drop. Replace the add/remove buttons with draggable crop chips
 *   (dnd-kit) dropped onto year columns, with the crop palette grouped by crop type.
 * TODO (Member 3): live fit hints. GET /soil-crops/suitability/{field_id} (useSuitability) says
 *   which crops fit this field and why; grey out the ones that do not mature here and show the
 *   limiting factor on hover.
 * TODO (Member 3): equipment and herbicide-carryover filter drawer that hides crops the farm
 *   cannot plant or harvest, driven by constraints.equipment.
 */
import { useMemo, useState } from "react";

import { useRotationOptions } from "@/hooks/useData";
import { useFieldShift } from "@/hooks/useFieldShift";
import { GROUP_COLOR } from "@/styles/theme";
import type { RotationSpec, Tillage } from "@/types/api";

const MAX_YEARS = 6;
const MAX_PER_YEAR = 3;

export function SequenceBuilder({ baselineYears, baselineTillage }: { baselineYears: string[][]; baselineTillage: Tillage }) {
  const { data: options } = useRotationOptions();
  const { customStrategies, setCustomStrategies, baselineOverride, setBaselineOverride } = useFieldShift();
  const [years, setYears] = useState<string[][]>(() => customStrategies[0]?.years ?? baselineYears.map((y) => [...y]));
  const [tillage, setTillage] = useState<Tillage>((customStrategies[0]?.tillage as Tillage) ?? baselineTillage);
  const [name, setName] = useState(customStrategies[0]?.name ?? "My rotation");

  const crops = options?.crops ?? [];
  const byId = useMemo(() => Object.fromEntries(crops.map((c) => [c.id, c])), [crops]);
  const cash = crops.filter((c) => c.role !== "cover");
  const covers = crops.filter((c) => c.role === "cover");
  const empty = !years.some((y) => y.length);
  const spec: RotationSpec = { id: "custom-1", name, years, tillage };
  const scored = customStrategies.length > 0 && JSON.stringify(customStrategies[0].years) === JSON.stringify(years) && customStrategies[0].tillage === tillage;

  const update = (fn: (draft: string[][]) => void) => setYears((prev) => {
    const draft = prev.map((y) => [...y]);
    fn(draft);
    return draft;
  });

  return (
    <div className="builder stack">
      <div className="builder-years">
        {years.map((year, yi) => (
          <div key={yi} className="builder-year">
            <div className="spread">
              <span className="eyebrow">Year {yi + 1}</span>
              {years.length > 1 && <button className="btn btn-ghost btn-sm" onClick={() => update((d) => { d.splice(yi, 1); })} aria-label={`Remove year ${yi + 1}`}>✕</button>}
            </div>
            <div className="stack-sm">
              {year.length === 0 && <span className="builder-fallow">Fallow: nothing planted</span>}
              {year.map((cid, ci) => {
                const c = byId[cid];
                return (
                  <span key={ci} className="builder-chip" style={{ borderColor: GROUP_COLOR[c?.functional_group ?? ""] ?? "#aaa" }}>
                    <span className="dot" style={{ background: GROUP_COLOR[c?.functional_group ?? ""] ?? "#aaa" }} />
                    {c?.name ?? cid}
                    <button onClick={() => update((d) => { d[yi].splice(ci, 1); })} aria-label={`Remove ${c?.name ?? cid}`}>✕</button>
                  </span>
                );
              })}
              {year.length < MAX_PER_YEAR && (
                <select value="" aria-label={`Add a crop to year ${yi + 1}`} onChange={(e) => e.target.value && update((d) => { d[yi].push(e.target.value); })}>
                  <option value="">{year.length ? "+ then plant…" : "+ add a crop…"}</option>
                  <optgroup label="Crops to harvest">{cash.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</optgroup>
                  <optgroup label="Cover crops">{covers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</optgroup>
                </select>
              )}
            </div>
          </div>
        ))}
        {years.length < MAX_YEARS && (
          <button className="builder-add" onClick={() => setYears((y) => [...y, []])}>+ Add a year</button>
        )}
      </div>

      <div className="row-wrap">
        <label className="row small">Name <input type="text" value={name} maxLength={40} onChange={(e) => setName(e.target.value)} style={{ width: 170 }} /></label>
        <label className="row small">
          Tillage
          <select value={tillage} onChange={(e) => setTillage(e.target.value as Tillage)}>
            {(options?.tillage_systems ?? []).map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
        </label>
      </div>

      <div className="row-wrap">
        <button className="btn btn-primary" disabled={empty} onClick={() => setCustomStrategies([spec])}>
          {scored ? "✓ Scored below" : "Score my rotation"}
        </button>
        <button className="btn" disabled={empty} title="Use this as the rotation every alternative is compared against"
          onClick={() => setBaselineOverride({ name: "Your current rotation", years, tillage })}>
          This is what I grow now
        </button>
        {customStrategies.length > 0 && <button className="btn btn-ghost" onClick={() => setCustomStrategies([])}>Remove my rotation</button>}
        {baselineOverride && <button className="btn btn-ghost" onClick={() => setBaselineOverride(null)}>Restore the original baseline</button>}
      </div>
      <p className="xs faint">
        List crops in the order they are planted within a year: two paddy seasons, or a vegetable followed by a legume. Leave a year empty for a fallow.
        A cover crop listed after a cash crop grows until the next crop is planted. The model works out planting and harvest months from this field's temperatures.
      </p>
    </div>
  );
}
