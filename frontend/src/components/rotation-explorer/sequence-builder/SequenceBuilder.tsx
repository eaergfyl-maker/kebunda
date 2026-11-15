/**
 * Build-your-own rotation. The farmer adds years and crops, then Kebunda scores the
 * result with the same models as its own suggestions, or adopts it as the current rotation.
 *
 * OWNER: Member 3.
 *
 * TODO (Member 3): drag-and-drop. Replace the add/remove buttons with draggable crop chips
 *   (dnd-kit) dropped onto year columns, with the crop palette grouped by crop type.
 * DONE (Member 3): live fit hints. useSuitability marks crops that do not mature on this field:
 *   they are greyed out in the pickers, flagged on the chip with the reason on hover, and
 *   summarised in a warning under the years.
 * TODO (Member 3): equipment and herbicide-carryover filter drawer that hides crops the farm
 *   cannot plant or harvest, driven by constraints.equipment.
 */
import { useMemo, useState } from "react";

import { useRotationOptions, useSuitability } from "@/hooks/useData";
import { useKebunda } from "@/hooks/useKebunda";
import { useT } from "@/i18n/LanguageProvider";
import { GROUP_COLOR } from "@/styles/theme";
import type { RotationSpec, Tillage } from "@/types/api";

const MAX_YEARS = 6;
const MAX_PER_YEAR = 3;

export function SequenceBuilder({ fieldId, baselineYears, baselineTillage }: { fieldId?: string; baselineYears: string[][]; baselineTillage: Tillage }) {
  const { data: options } = useRotationOptions();
  const { data: suit } = useSuitability(fieldId ?? null);
  const { customStrategies, setCustomStrategies, baselineOverride, setBaselineOverride } = useKebunda();
  const { t, tName } = useT();
  const [years, setYears] = useState<string[][]>(() => customStrategies[0]?.years ?? baselineYears.map((y) => [...y]));
  const [tillage, setTillage] = useState<Tillage>((customStrategies[0]?.tillage as Tillage) ?? baselineTillage);
  const [name, setName] = useState(customStrategies[0]?.name ?? "My rotation");

  const crops = options?.crops ?? [];
  const fit = useMemo(() => Object.fromEntries((suit?.rows ?? []).map((r) => [r.crop_id, r])), [suit]);
  const whyNot = (cid: string) => {
    const r = fit[cid];
    if (!r || r.feasible) return "";
    return [...r.limiting_factors, ...r.reasons].filter(Boolean).join("; ") || t("Does not suit this field");
  };
  const optionLabel = (c: { id: string; name: string }) => (fit[c.id] && !fit[c.id].feasible ? `${tName(c.name)} (${t("will not mature here")})` : tName(c.name));
  const inUse = new Set(years.flat());
  const renderOption = (c: { id: string; name: string }) => (
    <option key={c.id} value={c.id} disabled={Boolean(fit[c.id] && !fit[c.id].feasible) && !inUse.has(c.id)} title={whyNot(c.id)}>{optionLabel(c)}</option>
  );
  const problems = [...inUse].filter((cid) => fit[cid] && !fit[cid].feasible);
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
              <span className="eyebrow">{t("Year {n}", { n: yi + 1 })}</span>
              {years.length > 1 && <button className="btn btn-ghost btn-sm" onClick={() => update((d) => { d.splice(yi, 1); })} aria-label={t("Remove year {n}", { n: yi + 1 })}>✕</button>}
            </div>
            <div className="stack-sm">
              {year.length === 0 && <span className="builder-fallow">{t("Fallow: nothing planted")}</span>}
              {year.map((cid, ci) => {
                const c = byId[cid];
                return (
                  <span key={ci} className="builder-chip" style={{ borderColor: GROUP_COLOR[c?.functional_group ?? ""] ?? "#aaa" }}>
                    <span className="dot" style={{ background: GROUP_COLOR[c?.functional_group ?? ""] ?? "#aaa" }} />
                    {tName(c?.name ?? cid)}
                    {fit[cid] && !fit[cid].feasible && <span className="chip chip-warn" title={whyNot(cid)}>⚠ {t("poor fit")}</span>}
                    <button onClick={() => update((d) => { d[yi].splice(ci, 1); })} aria-label={t("Remove {x}", { x: tName(c?.name ?? cid) })}>✕</button>
                  </span>
                );
              })}
              {year.length < MAX_PER_YEAR && (
                <select value="" aria-label={t("Add a crop to year {n}", { n: yi + 1 })} onChange={(e) => e.target.value && update((d) => { d[yi].push(e.target.value); })}>
                  <option value="">{year.length ? t("+ then plant…") : t("+ add a crop…")}</option>
                  <optgroup label={t("Crops to harvest")}>{cash.map(renderOption)}</optgroup>
                  <optgroup label={t("Cover crops")}>{covers.map(renderOption)}</optgroup>
                </select>
              )}
            </div>
          </div>
        ))}
        {years.length < MAX_YEARS && (
          <button className="builder-add" onClick={() => setYears((y) => [...y, []])}>{t("+ Add a year")}</button>
        )}
      </div>

      {problems.length > 0 && (
        <p className="notice notice-warn">
          <strong>{t("Heads up:")}</strong> {problems.map((cid) => `${tName(byId[cid]?.name ?? cid)}: ${whyNot(cid)}`).join(" · ")}. {problems.length > 1 ? t("Check with a local agronomist before relying on these crops.") : t("Check with a local agronomist before relying on this crop.")}
        </p>
      )}

      <div className="row-wrap">
        <label className="row small">{t("Name")} <input type="text" value={name} maxLength={40} onChange={(e) => setName(e.target.value)} style={{ width: 170 }} /></label>
        <label className="row small">
          {t("Tillage")}
          <select value={tillage} onChange={(e) => setTillage(e.target.value as Tillage)}>
            {(options?.tillage_systems ?? []).map((tl) => <option key={tl.id} value={tl.id}>{t(tl.label)}</option>)}
          </select>
        </label>
      </div>

      <div className="row-wrap">
        <button className="btn btn-primary" disabled={empty} onClick={() => setCustomStrategies([spec])}>
          {scored ? t("✓ Scored below") : t("Score my rotation")}
        </button>
        <button className="btn" disabled={empty} title={t("Use this as the rotation every alternative is compared against")}
          onClick={() => setBaselineOverride({ name: "Your current rotation", years, tillage })}>
          {t("This is what I grow now")}
        </button>
        {customStrategies.length > 0 && <button className="btn btn-ghost" onClick={() => setCustomStrategies([])}>{t("Remove my rotation")}</button>}
        {baselineOverride && <button className="btn btn-ghost" onClick={() => setBaselineOverride(null)}>{t("Restore the original baseline")}</button>}
      </div>
      <p className="xs faint">
        {t("List crops in the order they are planted within a year: two paddy seasons, or a vegetable followed by a legume. Leave a year empty for a fallow. A cover crop listed after a cash crop grows until the next crop is planted. The model works out planting months from this field's rainfall and temperatures.")}
      </p>
    </div>
  );
}
