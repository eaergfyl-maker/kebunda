/**
 * Layer switcher, opacity, date scrubber and legend for the map.
 *
 * OWNER: Member 2. Driven entirely by layers/layerRegistry.ts.
 *
 * TODO (Member 2): animated seasonal scrubber. Add a play button that steps `date` through
 *   `steps` on an interval so a farmer can watch green-up and harvest sweep across the district.
 * TODO (Member 2): side-by-side "swipe" compare of two dates (leaflet-side-by-side) for
 *   before/after a drought or flood.
 */
import { useMemo } from "react";

import { Term } from "@/components/common/glossary/Term";
import { useUnits } from "@/hooks/useUnits";
import { useT } from "@/i18n/LanguageProvider";

import { BASE_LAYERS, GROUP_LABEL, GROUP_ORDER, monthSteps, snapDate, type MapLayerDef } from "../layers/layerRegistry";

export interface LayerPanelProps {
  layers: MapLayerDef[];
  activeId: string | null;
  onActive: (id: string | null) => void;
  baseId: string;
  onBase: (id: string) => void;
  opacity: number;
  onOpacity: (v: number) => void;
  date: string;
  onDate: (d: string) => void;
}

export function LayerPanel({ layers, activeId, onActive, baseId, onBase, opacity, onOpacity, date, onDate }: LayerPanelProps) {
  const units = useUnits();
  const { t, locale } = useT();
  const active = layers.find((l) => l.id === activeId) ?? null;
  const steps = useMemo(() => monthSteps(48, new Date(), locale), [locale]);
  const stepIndex = Math.max(0, steps.findIndex((s) => s.date.slice(0, 7) === date.slice(0, 7)));
  const grouped = GROUP_ORDER.map((g) => ({ group: g, items: layers.filter((l) => l.group === g) })).filter((g) => g.items.length);

  return (
    <div className="layer-panel">
      <div className="layer-panel-section">
        <div className="eyebrow">{t("NASA view")}</div>
        <button className={`layer-option ${activeId === null ? "is-active" : ""}`} onClick={() => onActive(null)}>
          <span className="layer-radio" /> {t("Map only")}
        </button>
        {grouped.map(({ group, items }) => (
          <div key={group}>
            <div className="layer-group-label">{t(GROUP_LABEL[group])}</div>
            {items.map((l) => (
              <button key={l.id} className={`layer-option ${activeId === l.id ? "is-active" : ""}`} onClick={() => onActive(l.id)} title={t(l.plain)}>
                <span className="layer-radio" />
                <span className="layer-title">{t(l.title)}</span>
                <span className="layer-mission">{l.mission}</span>
              </button>
            ))}
          </div>
        ))}
      </div>

      {active && (
        <div className="layer-panel-section layer-detail">
          <p className="small">{t(active.plain)}</p>
          <p className="xs faint">
            {t("One")} <Term id="resolution">{t("pixel")}</Term> ≈ {t("{d} wide", { d: units.distance(active.resolution_m) })}
            {active.temporal !== "static" && <> · {t("showing")} {formatShown(active, date, locale)}</>}
          </p>
          {active.temporal !== "static" && (
            <label className="stack-sm">
              <span className="xs faint spread"><span>{steps[0].label}</span><strong className="num">{steps[stepIndex]?.label}</strong><span>{steps[steps.length - 1].label}</span></span>
              <input
                type="range" min={0} max={steps.length - 1} step={1} value={stepIndex} aria-label={t("Date of the satellite view")}
                style={{ ["--pct" as string]: `${(stepIndex / (steps.length - 1)) * 100}%` }}
                onChange={(e) => onDate(steps[Number(e.target.value)].date)}
              />
            </label>
          )}
          <label className="stack-sm">
            <span className="xs faint">{t("See-through")}</span>
            <input
              type="range" min={0.2} max={1} step={0.05} value={opacity} aria-label={t("Layer opacity")}
              style={{ ["--pct" as string]: `${((opacity - 0.2) / 0.8) * 100}%` }}
              onChange={(e) => onOpacity(Number(e.target.value))}
            />
          </label>
          {active.legend && <Legend legend={active.legend} />}
        </div>
      )}

      <div className="layer-panel-section">
        <div className="eyebrow">{t("Background")}</div>
        <div className="row-wrap" style={{ marginTop: 6 }}>
          {BASE_LAYERS.map((b) => (
            <button key={b.id} className={`btn btn-sm ${baseId === b.id ? "btn-primary" : ""}`} onClick={() => onBase(b.id)}>{t(b.title)}</button>
          ))}
        </div>
      </div>
    </div>
  );
}

function formatShown(layer: MapLayerDef, date: string, locale: string): string {
  const d = new Date(`${snapDate(layer, date)}T00:00:00Z`);
  if (layer.temporal === "yearly") return String(d.getUTCFullYear());
  if (layer.temporal === "monthly") return d.toLocaleDateString(locale, { month: "long", year: "numeric", timeZone: "UTC" });
  return d.toLocaleDateString(locale, { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
}

/** Colour ramp with end labels. Stops are approximate guides to the GIBS colour maps. */
export function Legend({ legend }: { legend: NonNullable<MapLayerDef["legend"]> }) {
  const stops = legend.stops;
  const min = stops[0][0];
  const max = stops[stops.length - 1][0];
  const gradient = stops.map(([v, c]) => `${c} ${((v - min) / (max - min || 1)) * 100}%`).join(", ");
  return (
    <div className="legend">
      <div className="legend-ramp" style={{ background: `linear-gradient(to right, ${gradient})` }} />
      <div className="spread xs faint num"><span>{min}</span><span>{legend.unit}</span><span>{max}</span></div>
    </div>
  );
}
