import { CircleMarker, Tooltip } from "react-leaflet";

import type { OverlayProps } from "./overlayRegistry";

/** Clickable benchmark-farm markers. The open farm is drawn larger and in wheat gold. */
export function FarmPins({ farms, selectedId, onSelect }: OverlayProps) {
  return (
    <>
      {farms.map((f) => {
        const selected = f.id === selectedId;
        return (
          <CircleMarker
            key={f.id} center={[f.lat, f.lon]} radius={selected ? 11 : 8}
            pathOptions={{ color: "#fff", weight: 2.5, fillColor: selected ? "#e9b44c" : "#1f3a2b", fillOpacity: 1 }}
            eventHandlers={{ click: () => onSelect(f.id) }}
          >
            <Tooltip direction="top" offset={[0, -8]} opacity={1} className="farm-tooltip">
              <strong>{f.short_name}</strong>
              <br />
              {f.baseline_name}
              <br />
              <span className="faint">{f.irrigation} · {f.soil_series} {f.soil_texture}</span>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </>
  );
}
