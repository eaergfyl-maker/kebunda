import { CircleMarker, Popup, useMapEvents } from "react-leaflet";

import { usePowerPoint } from "@/hooks/useData";
import { useUnits } from "@/hooks/useUnits";

import type { OverlayProps } from "./overlayRegistry";

/**
 * Click anywhere: a live, keyless NASA POWER query for that coordinate, with the option to
 * build a full custom field there (POWER + IMERG + MODIS + SRTM + SSURGO + CDL).
 */
export function PointProbe({ probe, setProbe, onAnalyzePoint, analyzing }: OverlayProps) {
  const units = useUnits();
  useMapEvents({
    click: (e) => setProbe({ lat: e.latlng.lat, lon: e.latlng.lng }),
  });
  const { data, loading, error } = usePowerPoint(probe);
  if (!probe) return null;
  return (
    // keyed by position so each click mounts a fresh marker; its "add" event opens the result
    // straight away, without a second click on the marker
    <CircleMarker key={`${probe.lat},${probe.lon}`} center={[probe.lat, probe.lon]} radius={7}
      eventHandlers={{ add: (e) => window.setTimeout(() => e.target.openPopup(), 0) }} pathOptions={{ color: "#fff", weight: 2, fillColor: "#c8553d", fillOpacity: 1 }}>
      <Popup autoPan closeButton closeOnClick={false} minWidth={260} maxWidth={300}>
        <div className="probe">
          <div className="eyebrow">NASA POWER · live query</div>
          <div className="probe-coord num">{probe.lat.toFixed(3)}°, {probe.lon.toFixed(3)}°</div>
          {loading && <p className="small muted">Pulling 24 years of daily records from NASA…</p>}
          {error && <p className="small" style={{ color: "var(--bad)" }}>{error.message}</p>}
          {data && (
            <>
              <dl className="probe-grid">
                <div><dt>Rain and snow</dt><dd className="num">{units.water(data.annual_precip_mm)}/yr</dd></div>
                <div><dt>Air's thirst (ET0)</dt><dd className="num">{units.water(data.annual_et0_mm)}/yr</dd></div>
                <div><dt>Average temp</dt><dd className="num">{units.temp(data.mean_annual_temp_c)}</dd></div>
                <div><dt>Frost-free</dt><dd className="num">{Math.round(data.frost.frost_free_days_median)} days</dd></div>
                <div><dt>Days ≥ {units.temp(35)}</dt><dd className="num">{Math.round(data.monthly.heat_days_35.reduce((a, b) => a + b, 0))}/yr</dd></div>
                <div><dt>Warming</dt><dd className="num">{units.tempDelta(data.trends.tmean_c?.per_decade ?? 0)}/decade</dd></div>
              </dl>
              {onAnalyzePoint && (
                <button className="btn btn-primary btn-sm" style={{ width: "100%", marginTop: 8 }} disabled={analyzing} onClick={() => onAnalyzePoint(probe.lat, probe.lon)}>
                  {analyzing ? "Building this field…" : "Explore rotations for this spot →"}
                </button>
              )}
              <p className="xs faint" style={{ marginTop: 6 }}>MERRA-2 cell about 50 km wide, 2001-2024. Soil and crop history are added when you explore the spot (U.S. only for soil).</p>
            </>
          )}
        </div>
      </Popup>
    </CircleMarker>
  );
}
