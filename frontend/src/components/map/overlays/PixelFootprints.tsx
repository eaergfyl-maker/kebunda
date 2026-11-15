import { Rectangle, Tooltip } from "react-leaflet";

import { useUnits } from "@/hooks/useUnits";
import { useT } from "@/i18n/LanguageProvider";

import type { OverlayProps } from "./overlayRegistry";

const COLORS = ["#c8553d", "#c9952b", "#2f7fa3", "#4f8f4a", "#9a5ba0"];

/** Square of `size_m` metres centred on a coordinate, as Leaflet bounds. */
function square(lat: number, lon: number, size_m: number): [[number, number], [number, number]] {
  const dLat = size_m / 2 / 111_320;
  const dLon = size_m / 2 / (111_320 * Math.cos((lat * Math.PI) / 180));
  return [[lat - dLat, lon - dLon], [lat + dLat, lon + dLon]];
}

/**
 * The resolution gap, drawn to scale: the field itself, and one square per dataset showing
 * how much ground a single pixel of that dataset covers. Zoom out to see the 55 km cell;
 * zoom in to see that a 250 m NDVI pixel is the only one smaller than the field.
 */
export function PixelFootprints({ field }: OverlayProps) {
  const units = useUnits();
  const { t } = useT();
  if (!field) return null;
  const { lat, lon } = field.farm;
  const sizes = new Map<number, string[]>();
  for (const layer of field.fusion.layers) {
    const res = layer.native_resolution_m;
    if (!res || res < 200 || res > 80_000 || layer.access === "unavailable") continue;
    sizes.set(res, [...(sizes.get(res) ?? []), layer.label]);
  }
  const rows = [...sizes.entries()].sort((a, b) => b[0] - a[0]);
  return (
    <>
      {rows.map(([size, labels], i) => (
        <Rectangle
          key={size} bounds={square(lat, lon, size)} interactive
          pathOptions={{ color: COLORS[i % COLORS.length], weight: 1.5, dashArray: "6 5", fill: true, fillOpacity: 0.03 }}
        >
          <Tooltip sticky>
            <strong>{t("One pixel: {d} across", { d: units.distance(size) })}</strong>
            <br />
            {labels.join(" · ")}
          </Tooltip>
        </Rectangle>
      ))}
      <Rectangle bounds={square(lat, lon, field.fusion.field_width_m)} pathOptions={{ color: "#1f3a2b", weight: 2.5, fillColor: "#e9b44c", fillOpacity: 0.55 }}>
        <Tooltip sticky>
          <strong>{field.farm.short_name}</strong>
          <br />
          {t("The field: {a}, about {d} across", { a: units.area(field.farm.area_ha), d: units.distance(field.fusion.field_width_m) })}
        </Tooltip>
      </Rectangle>
    </>
  );
}
