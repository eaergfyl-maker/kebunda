/**
 * The interactive map: base map + one NASA GIBS layer + overlay plugins + controls.
 *
 * OWNER: Member 2. This file is only wiring. Add layers in layers/layerRegistry.ts and
 * overlays in overlays/overlayRegistry.tsx; you should rarely need to edit this component.
 */
import "leaflet/dist/leaflet.css";
import "./map.css";

import { useEffect, useMemo, useState } from "react";
import { MapContainer, ScaleControl, useMap } from "react-leaflet";

import { useGibsLayers } from "@/hooks/useData";
import type { FarmSummary, FieldOverview } from "@/types/api";

import { LayerPanel } from "./controls/LayerPanel";
import { BASE_LAYERS, buildLayerList, latestDate } from "./layers/layerRegistry";
import { BaseLayer, NasaLayer } from "./layers/NasaLayer";
import { OVERLAYS } from "./overlays/overlayRegistry";

export interface FieldMapProps {
  farms: FarmSummary[];
  selectedId?: string | null;
  onSelect: (id: string) => void;
  field?: FieldOverview | null;
  onAnalyzePoint?: (lat: number, lon: number) => void;
  analyzing?: boolean;
  height?: number | string;
  /** GIBS layer shown first. Null starts with the plain base map. */
  defaultLayerId?: string | null;
}

const USA: [number, number] = [39.5, -98.5];

/** Wheel-zoom only after the map is clicked, so scrolling the page never gets trapped in the map. */
function ScrollZoomOnFocus() {
  const map = useMap();
  useEffect(() => {
    map.scrollWheelZoom.disable();
    const on = () => map.scrollWheelZoom.enable();
    const off = () => map.scrollWheelZoom.disable();
    map.on("click", on);
    map.getContainer().addEventListener("mouseleave", off);
    return () => {
      map.off("click", on);
      map.getContainer().removeEventListener("mouseleave", off);
    };
  }, [map]);
  return null;
}

/** Fly to the open field, or back out to the country when none is open. */
function ViewController({ field }: { field: FieldOverview | null }) {
  const map = useMap();
  const lat = field?.farm.lat;
  const lon = field?.farm.lon;
  useEffect(() => {
    if (lat !== undefined && lon !== undefined) map.flyTo([lat, lon], 11, { duration: 0.9 });
    else map.flyTo(USA, 4, { duration: 0.6 });
  }, [lat, lon, map]);
  return null;
}

export function FieldMap({ farms, selectedId = null, onSelect, field = null, onAnalyzePoint, analyzing, height = 520, defaultLayerId = "MODIS_Terra_L3_NDVI_Monthly" }: FieldMapProps) {
  const { data: gibs } = useGibsLayers();
  const layers = useMemo(() => buildLayerList(gibs?.layers), [gibs]);
  const [activeId, setActiveId] = useState<string | null>(defaultLayerId);
  const [baseId, setBaseId] = useState(BASE_LAYERS[0].id);
  const [opacity, setOpacity] = useState(0.7);
  const [date, setDate] = useState<string>(() => new Date(Date.now() - 60 * 864e5).toISOString().slice(0, 10));
  const [probe, setProbe] = useState<{ lat: number; lon: number } | null>(null);
  const [enabled, setEnabled] = useState<Record<string, boolean>>(() => Object.fromEntries(OVERLAYS.map((o) => [o.id, o.defaultOn])));
  const [panelOpen, setPanelOpen] = useState(true);

  const active = layers.find((l) => l.id === activeId) ?? null;
  const base = BASE_LAYERS.find((b) => b.id === baseId) ?? BASE_LAYERS[0];
  const overlays = OVERLAYS.filter((o) => !o.needsField || field);

  // when a layer is first chosen, make sure the date is one it can serve
  useEffect(() => {
    if (active && active.temporal !== "static" && date > latestDate(active)) setDate(latestDate(active));
  }, [active, date]);

  return (
    <div className="fieldmap" style={{ height }}>
      <MapContainer center={field ? [field.farm.lat, field.farm.lon] : USA} zoom={field ? 11 : 4} minZoom={3} maxZoom={16} scrollWheelZoom={false} worldCopyJump className="fieldmap-canvas">
        <BaseLayer layer={base} />
        {active && <NasaLayer layer={active} date={date} opacity={opacity} />}
        {overlays.filter((o) => enabled[o.id]).map((o) => (
          <o.Component
            key={o.id} farms={farms} selectedId={selectedId} onSelect={onSelect} field={field}
            probe={probe} setProbe={setProbe} onAnalyzePoint={onAnalyzePoint} analyzing={analyzing}
          />
        ))}
        <ScaleControl position="bottomleft" />
        <ViewController field={field} />
        <ScrollZoomOnFocus />
      </MapContainer>

      <div className={`fieldmap-panel ${panelOpen ? "" : "is-collapsed"}`}>
        <button className="fieldmap-panel-toggle" onClick={() => setPanelOpen((o) => !o)} aria-expanded={panelOpen}>
          {panelOpen ? "Hide layers" : "Layers"}
        </button>
        {panelOpen && (
          <>
            <LayerPanel
              layers={layers} activeId={activeId} onActive={setActiveId} baseId={baseId} onBase={setBaseId}
              opacity={opacity} onOpacity={setOpacity} date={date} onDate={setDate}
            />
            <div className="layer-panel-section">
              <div className="eyebrow">On the map</div>
              {overlays.map((o) => (
                <label key={o.id} className="check" title={o.help} style={{ display: "flex", marginTop: 6 }}>
                  <input type="checkbox" checked={Boolean(enabled[o.id])} onChange={(e) => setEnabled((s) => ({ ...s, [o.id]: e.target.checked }))} />
                  {o.label}
                </label>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
