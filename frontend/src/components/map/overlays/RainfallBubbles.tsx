import { CircleMarker, Tooltip } from "react-leaflet";

import { useUnits } from "@/hooks/useUnits";
import { useT } from "@/i18n/LanguageProvider";

import type { OverlayProps } from "./overlayRegistry";

/** Wetter sites get a bigger, darker circle. Thresholds are in mm per year. */
const colorFor = (mm: number) => (mm < 1500 ? "#9cc5d9" : mm < 2500 ? "#4f8fb5" : "#1f5f8b");
const radiusFor = (mm: number) => 6 + Math.sqrt(Math.max(mm, 0)) * 0.35;

/**
 * One bubble per farm, sized by yearly rain. Not interactive, so clicks fall through to the
 * farm pins and the point probe underneath.
 */
export function RainfallBubbles({ farms }: OverlayProps) {
  const units = useUnits();
  const { t } = useT();
  return (
    <>
      {farms.map((f) => (
        <CircleMarker
          key={f.id}
          center={[f.lat, f.lon]}
          radius={radiusFor(f.annual_precip_mm)}
          pathOptions={{
            color: colorFor(f.annual_precip_mm), weight: 1.5, fillColor: colorFor(f.annual_precip_mm),
            fillOpacity: 0.35, interactive: false,
          }}
        >
          <Tooltip direction="bottom" opacity={1} permanent={false}>
            <strong>{f.short_name}</strong>
            <br />
            {t("{r}/yr of rain", { r: units.water(f.annual_precip_mm) })}
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  );
}