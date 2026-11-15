/**
 * "What can your farm do?" Constraints in plain language: water, equipment, livestock,
 * appetite for change, and crops that are off the table.
 * Changing a constraint re-runs the rotation search (a second or so).
 *
 * OWNER: Member 3.
 * TODO (Member 3): frost-window and planting-date overrides ("I cannot plant before May 10"),
 *   passed as new constraint fields once the backend accepts them
 *   (backend/app/models/schemas/requests.py: Constraints).
 * TODO (Member 3): save and name constraint sets per field ("with the neighbour's drill").
 */
import { useRotationOptions } from "@/hooks/useData";
import { useKebunda } from "@/hooks/useKebunda";
import { useUnits } from "@/hooks/useUnits";
import { useT } from "@/i18n/LanguageProvider";
import type { FieldOverview, RiskTolerance } from "@/types/api";

export function ConstraintsPanel({ field }: { field: FieldOverview }) {
  const { data: options } = useRotationOptions();
  const { constraints, setConstraint, resetConstraints } = useKebunda();
  const units = useUnits();
  const { t, tName } = useT();
  const mgmt = field.farm.management;
  const irrigatedByDefault = mgmt.irrigation.type !== "none";
  const irrigated = constraints.irrigation_available ?? irrigatedByDefault;
  const allocation = constraints.water_allocation_mm ?? (mgmt.irrigation.allocation_mm || 400);
  const equipment = constraints.equipment ?? mgmt.equipment;
  const excluded = constraints.exclude_crops ?? [];
  const risk: RiskTolerance = constraints.risk_tolerance ?? "medium";
  const cashCrops = (options?.crops ?? []).filter((c) => c.role !== "cover");
  const changed = Object.keys(constraints).length > 0;

  const toggleEquipment = (id: string) => setConstraint("equipment", equipment.includes(id) ? equipment.filter((e) => e !== id) : [...equipment, id]);
  const toggleExcluded = (id: string) => {
    const next = excluded.includes(id) ? excluded.filter((e) => e !== id) : [...excluded, id];
    setConstraint("exclude_crops", next.length ? next : undefined);
  };

  return (
    <div className="stack">
      <fieldset className="constraint-group">
        <legend>{t("Water")}</legend>
        <label className="check">
          <input type="checkbox" checked={irrigated} onChange={(e) => setConstraint("irrigation_available", e.target.checked === irrigatedByDefault ? undefined : e.target.checked)} />
          {t("This field can be irrigated")}
        </label>
        {irrigated && (
          <label className="stack-sm">
            <span className="small spread"><span>{t("Water you can apply in a year")}</span><strong className="num">{units.water(allocation)}</strong></span>
            <input type="range" min={100} max={1200} step={10} value={allocation} style={{ ["--pct" as string]: `${((allocation - 100) / 1100) * 100}%`, ["--track-fill" as string]: "var(--dim-water)" }}
              onChange={(e) => setConstraint("water_allocation_mm", Number(e.target.value))} />
          </label>
        )}
      </fieldset>

      <fieldset className="constraint-group">
        <legend>{t("Equipment on the farm")}</legend>
        <div className="check-grid">
          {(options?.equipment ?? []).map((e) => (
            <label key={e.id} className="check"><input type="checkbox" checked={equipment.includes(e.id)} onChange={() => toggleEquipment(e.id)} />{t(e.label)}</label>
          ))}
        </div>
        <label className="check">
          <input type="checkbox" checked={constraints.custom_hire_available ?? mgmt.custom_hire_available} onChange={(e) => setConstraint("custom_hire_available", e.target.checked)} />
          {t("I can hire or borrow what I do not own")}
        </label>
      </fieldset>

      <fieldset className="constraint-group">
        <legend>{t("How much change are you open to?")}</legend>
        <div className="segmented" role="group" aria-label={t("Appetite for change")}>
          {(options?.risk_tolerance ?? []).map((r) => (
            <button key={r.id} aria-pressed={risk === r.id} title={t(r.help)} onClick={() => setConstraint("risk_tolerance", r.id === "medium" ? undefined : r.id)}>{t(r.label)}</button>
          ))}
        </div>
        <p className="xs faint">{t(options?.risk_tolerance.find((r) => r.id === risk)?.help ?? "")}</p>
        <div className="check-grid">
          <label className="check"><input type="checkbox" checked={constraints.allow_cover_crops ?? true} onChange={(e) => setConstraint("allow_cover_crops", e.target.checked ? undefined : false)} />{t("Consider cover crops")}</label>
          <label className="check"><input type="checkbox" checked={constraints.allow_tillage_change ?? true} onChange={(e) => setConstraint("allow_tillage_change", e.target.checked ? undefined : false)} />{t("Consider less tillage")}</label>
          <label className="check"><input type="checkbox" checked={constraints.livestock ?? mgmt.livestock} onChange={(e) => setConstraint("livestock", e.target.checked)} />{t("Livestock can graze covers")}</label>
        </div>
      </fieldset>

      <fieldset className="constraint-group">
        <legend>{t("Crops I will not grow")}</legend>
        <div className="row-wrap">
          {cashCrops.map((c) => (
            <button key={c.id} className={`crop-toggle ${excluded.includes(c.id) ? "is-off" : ""}`} aria-pressed={excluded.includes(c.id)} onClick={() => toggleExcluded(c.id)}>
              {tName(c.name).replace(/ \(.*\)/, "")}
            </button>
          ))}
        </div>
      </fieldset>
      {changed && <button className="btn btn-ghost btn-sm" style={{ alignSelf: "flex-start" }} onClick={resetConstraints}>{t("Reset to this field's defaults")}</button>}
    </div>
  );
}
