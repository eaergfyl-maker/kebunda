/**
 * Satellite vs. ground truth, and the resolution gap.
 *
 * Three things a farmer should see before trusting a pixel:
 *   1. the same rainfall measured three ways, and how each compares with the gauges;
 *   2. how big each dataset's pixel is next to the field (log scale);
 *   3. whether the crop calendar the tool assumed matches what MODIS actually saw.
 *
 * OWNER: Member 2.
 * TODO (Member 2): CoCoRaHS rain-gauge vs. GPM IMERG chart. CoCoRaHS has a keyless export
 *   (data.cocorahs.org/export). Add a connector next to backend/app/services/usda_connectors/
 *   ground_truth.py, expose daily totals for the nearest stations, and plot storm-by-storm
 *   scatter (gauge on x, satellite on y) here: it is the most convincing picture of what
 *   a 10 km pixel misses.
 * TODO (Member 2): soil-moisture probe upload. Let a farmer drop a CSV from their own probe and
 *   draw it against the 55 km wetness series.
 */
import { ProvenanceBadge } from "@/components/common/ui";
import { Term } from "@/components/common/glossary/Term";
import { MONTHS, useUnits } from "@/hooks/useUnits";
import { CHART } from "@/styles/theme";
import type { CalendarValidation, FieldOverview } from "@/types/api";

import { box, innerW, LegendRow, linePath, MonthAxis, niceTicks, scale, Svg, YAxis } from "./chartKit";
import { LocalAdviceNote, Takeaway } from "./Takeaway";

const SOURCE = {
  ground: { label: "Rain gauge (MetMalaysia via NOAA GHCN)", color: CHART.ground },
  imerg: { label: "GPM IMERG satellite (10 km)", color: CHART.imerg },
  merra2: { label: "MERRA-2 weather model (55 km)", color: "#9db8c6" },
} as const;
type SourceId = keyof typeof SOURCE;

export function SatelliteVsGround({ field, validation }: { field: FieldOverview; validation?: CalendarValidation | null }) {
  const units = useUnits();
  const cmp = field.fusion.precip_comparison;
  const fused = field.fusion.precip;
  const ids = (["ground", "imerg", "merra2"] as SourceId[]).filter((id) => cmp.monthly_normals[id]?.some((v) => v !== null));
  const b = box(720, 230);
  const band = innerW(b) / 12;
  const all = ids.flatMap((id) => cmp.monthly_normals[id] ?? []).filter((v): v is number => v !== null);
  const top = Math.max(...all, 1) * 1.1;
  const y = scale(0, top, b.height - b.bottom, b.top);
  const x = (m: number) => b.left + band * (m + 0.5);
  const barW = (band * 0.78) / ids.length;

  const layers = field.fusion.layers.filter((l) => l.native_resolution_m && l.access !== "unavailable");
  const fieldW = field.fusion.field_width_m;
  const logMax = Math.log10(400_000);
  const logMin = Math.log10(20);
  const imergBias = cmp.vs_ground?.["imerg"]?.bias_pct;
  const sentence = !fused.has_ground
    ? "No rain gauge record was available here, so the rainfall figures are an average of satellite and model estimates. Treat them as a rough guide."
    : imergBias !== undefined && imergBias !== null
      ? `Against rain gauges, the satellite rain estimate runs about ${Math.abs(Math.round(imergBias))}% ${imergBias > 0 ? "higher" : "lower"} at this field, so the tool blends gauge, satellite and model data instead of trusting any one of them.`
      : "The tool blends rain gauge, satellite and model data instead of trusting any one of them.";
  const pos = (m: number) => ((Math.log10(Math.max(20, m)) - logMin) / (logMax - logMin)) * 100;

  return (
    <div className="stack">
      <div>
        <h4>The same rain, measured three ways</h4>
        <p className="small muted">
          A rain gauge catches what falls on one spot. A satellite estimates rain from cloud and microwave signals over a square
          miles across. They never agree exactly, so FieldShift blends them into <Term id="fused_rain">fused rainfall</Term>,
          trusting each source by how closely it tracked the gauges at this field.
        </p>
        <Takeaway>{sentence}</Takeaway>
        <Svg b={b} label="Monthly rainfall from gauges, satellite and weather model">
          <YAxis b={b} ticks={niceTicks(0, top, 4)} y={y} format={(v) => units.waterValue(v).toFixed(units.system === "us" ? 1 : 0)} title={`${units.waterUnit} per month`} />
          {ids.map((id, k) => (cmp.monthly_normals[id] ?? []).map((v, m) => v !== null && (
            <rect key={`${id}${m}`} x={x(m) - (barW * ids.length) / 2 + k * barW} y={y(v)} width={barW - 1.5} height={Math.max(0, y(0) - y(v))} rx={2} fill={SOURCE[id].color}>
              <title>{`${MONTHS[m]} · ${SOURCE[id].label}: ${units.water(v)}`}</title>
            </rect>
          )))}
          <path d={linePath(fused.monthly_mm, x, y)} fill="none" stroke={CHART.et} strokeWidth={2.4} />
          {fused.monthly_mm.map((v, m) => <circle key={m} cx={x(m)} cy={y(v)} r={3} fill={CHART.et} />)}
          <MonthAxis b={b} x={x} />
        </Svg>
        <LegendRow items={[...ids.map((id) => ({ color: SOURCE[id].color, label: SOURCE[id].label, swatch: "box" as const })), { color: CHART.et, label: "Fused estimate used by the models" }]} />

        <div className="table-scroll" style={{ marginTop: 10 }}>
          <table className="table">
            <thead>
              <tr><th>Source</th><th className="num">Per year</th><th className="num">Against gauges</th><th className="num">Tracks gauges</th><th className="num">Heavy-rain days</th><th className="num">Weight in the blend</th></tr>
            </thead>
            <tbody>
              {ids.map((id) => {
                const st = id === "ground" ? null : cmp.vs_ground?.[id];
                return (
                  <tr key={id}>
                    <td><span className="dot" style={{ background: SOURCE[id].color, marginRight: 6 }} />{SOURCE[id].label}</td>
                    <td className="num">{units.water(fused.annual_by_source[id] ?? 0)}</td>
                    <td className="num">{st ? `${st.bias_pct > 0 ? "+" : ""}${st.bias_pct.toFixed(0)}%` : "reference"}</td>
                    <td className="num">{st?.correlation != null ? `r = ${st.correlation.toFixed(2)}` : "—"}</td>
                    <td className="num">{cmp.heavy_rain_days_per_year[id] ?? "—"}/yr</td>
                    <td className="num"><strong>{Math.round((fused.weights[id] ?? 0) * 100)}%</strong></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!fused.has_ground && <p className="notice notice-warn" style={{ marginTop: 8 }}>No gauge-based record was available here, so the satellite and model estimates are averaged with default error assumptions.</p>}
        <p className="xs faint" style={{ marginTop: 6 }}>{fused.method} Heavy-rain days are days above 25 mm (1 in).</p>
      </div>

      <div>
        <h4>How big is a pixel next to this field?</h4>
        <p className="small muted">
          Each bar is the width of one <Term id="resolution">pixel</Term>, on a scale where every step is ten times larger.
          Anything wider than the field (gold line) describes the neighbourhood, not the field. The model never invents detail
          inside a pixel; it widens the uncertainty instead.
        </p>
        <div className="ladder">
          <div className="ladder-key"><i /> Width of your field: {units.distance(fieldW)}</div>
          {[...layers].sort((a, c) => (a.native_resolution_m ?? 0) - (c.native_resolution_m ?? 0)).map((l) => (
            <div key={l.id} className="ladder-row">
              <div className="ladder-label">
                <span>{l.label}</span>
                <ProvenanceBadge access={l.access} compact />
              </div>
              <div className="ladder-track">
                <div className="ladder-bar" style={{ width: `${pos(l.native_resolution_m ?? 20)}%`, background: (l.native_resolution_m ?? 0) > fieldW ? "#c9a37a" : "#6a9f4c" }} />
                <i className="ladder-fieldmark" style={{ left: `${pos(fieldW)}%` }} />
                <span className="ladder-value num">{units.distance(l.native_resolution_m ?? 0)}</span>
              </div>
              <div className="ladder-conf num" title="How much weight the tool gives this layer for this field (0-100)">{Math.round(l.confidence * 100)}</div>
            </div>
          ))}
          <div className="ladder-axis xs faint"><span>{units.distance(20)}</span><span>{units.distance(200)}</span><span>{units.distance(2000)}</span><span>{units.distance(20000)}</span><span>{units.distance(200000)}</span></div>
        </div>
        <p className="xs faint">The number at right is the confidence (0-100) the tool assigns each layer for this field: its access quality times how well a pixel that size can represent one field.</p>
      </div>

      {validation && (
        <div>
          <h4>Does the satellite agree with the crop calendar we assumed?</h4>
          <p className="small muted">{validation.explanation}</p>
          <CalendarCheck v={validation} />
        </div>
      )}
      <LocalAdviceNote />
    </div>
  );
}

function CalendarCheck({ v }: { v: CalendarValidation }) {
  const b = box(720, 170);
  const band = innerW(b) / 12;
  const x = (m: number) => b.left + band * (m + 0.5);
  const y = scale(0, 1, b.height - b.bottom, b.top);
  return (
    <>
      <Svg b={b} label="Modelled green cover against observed MODIS greenness">
        <YAxis b={b} ticks={[0, 0.25, 0.5, 0.75, 1]} y={y} />
        <path d={`${linePath(v.modelled_green, x, y)}L${x(11)},${y(0)}L${x(0)},${y(0)}Z`} fill="#6a9f4c" opacity={0.18} />
        <path d={linePath(v.modelled_green, x, y)} fill="none" stroke="#6a9f4c" strokeWidth={2} strokeDasharray="5 4" />
        <path d={linePath(v.observed_ndvi, x, y)} fill="none" stroke={CHART.ink} strokeWidth={2.5} />
        {v.observed_ndvi.map((n, m) => n !== null && <circle key={m} cx={x(m)} cy={y(n)} r={3} fill={CHART.ink} />)}
        <MonthAxis b={b} x={x} />
      </Svg>
      <LegendRow items={[
        { color: CHART.ink, label: "What MODIS saw (NDVI, 250 m)" },
        { color: "#6a9f4c", label: "Green cover the model assumed for the current rotation", dash: true },
      ]} />
      <p className="small" style={{ marginTop: 4 }}>
        <span className={`chip ${v.agreement === "strong" ? "chip-good" : v.agreement === "fair" ? "chip-warn" : "chip-bad"}`}>{v.agreement} agreement</span>{" "}
        {v.correlation !== null && <span className="muted num">correlation {v.correlation.toFixed(2)} across the twelve months</span>}
      </p>
    </>
  );
}