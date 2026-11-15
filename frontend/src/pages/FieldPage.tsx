/**
 * The field dashboard. Top to bottom it follows the farmer's questions:
 * what is this field like -> when is it exposed -> what matters to me -> what could I grow
 * -> would that hold up -> how far can I trust this.
 *
 * OWNER: Member 3 (layout and section order). Each section's content is owned by the
 * component it renders: map and timelines by Member 2, the rest by Member 3.
 *
 * TODO (Member 3): a sticky "decision bar" that keeps the current top-fit rotation and fit
 *   score visible while scrolling, and a guided first-visit tour of the six sections.
 */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ExportButtons } from "@/components/common/export/ExportButtons";
import { Term } from "@/components/common/glossary/Term";
import { Card, ErrorNotice, Loading, ProvenanceBadge, Stat, Tabs } from "@/components/common/ui";
import { ConstraintsPanel } from "@/components/farmer-controls/priority-sliders/ConstraintsPanel";
import { PrioritySliders } from "@/components/farmer-controls/priority-sliders/PrioritySliders";
import { ScenarioResults, TippingOverview, TippingPoints } from "@/components/farmer-controls/scenario-sliders/ScenarioResults";
import { ScenarioSliders } from "@/components/farmer-controls/scenario-sliders/ScenarioSliders";
import { FieldMap } from "@/components/map/FieldMap";
import { StrategyExplorer } from "@/components/rotation-explorer/StrategyExplorer";
import { TimelinePanel } from "@/components/timelines/TimelinePanel";
import { useComparison, useFarms, useField, useStressTest } from "@/hooks/useData";
import { isNeutral, useFieldShift } from "@/hooks/useFieldShift";
import { useUnits } from "@/hooks/useUnits";
import { DIM_COLOR, DIM_SHORT } from "@/styles/theme";
import type { FieldOverview } from "@/types/api";

const SECTIONS = [
  { id: "field", label: "The field" },
  { id: "seasons", label: "Seasons and exposure" },
  { id: "priorities", label: "Your priorities" },
  { id: "rotations", label: "Rotations" },
  { id: "stress", label: "Stress test" },
  { id: "trust", label: "Data and trust" },
];

export function FieldPage() {
  const { id = "" } = useParams();
  const { resetForField, constraints, scenario } = useFieldShift();
  const { data: farms } = useFarms();
  const { data: field, loading, error } = useField(id);
  const comparison = useComparison(field ? id : null);
  const stress = useStressTest(field ? id : null, comparison.data?.strategies ?? null);
  const [controlTab, setControlTab] = useState<"priorities" | "constraints">("priorities");

  // a different field starts from its own defaults
  useEffect(() => {
    resetForField();
    window.scrollTo({ top: 0 });
  }, [id, resetForField]);

  if (error) return <div className="container" style={{ padding: "48px 24px" }}><ErrorNotice error={error} title="This field could not be loaded" /><p style={{ marginTop: 12 }}><Link to="/">← Back to all fields</Link></p></div>;
  if (loading || !field) return <div className="container stack" style={{ padding: "32px 24px" }}><Loading height={180} label="Loading field" /><Loading height={420} /></div>;

  const cmp = comparison.data && comparison.data.field_id === id ? comparison.data : null;
  const irrigated = constraints.irrigation_available ?? field.farm.management.irrigation.type !== "none";

  return (
    <div className="field-page">
      <FieldHero field={field} />
      <nav className="section-nav no-print" aria-label="Sections">
        <div className="container section-nav-inner">
          {SECTIONS.map((s) => <a key={s.id} href={`#${s.id}`}>{s.label}</a>)}
          <span style={{ flex: 1 }} />
          {cmp && <Link className="btn btn-sm btn-primary" to={`/field/${id}/brief`}>Field Brief</Link>}
        </div>
      </nav>

      <div className="container stack" style={{ gap: 28, paddingTop: 24, paddingBottom: 56 }}>
        <section id="field" className="field-top">
          <Card title="What the record shows" subtitle={`Facts from ${field.insights.period} of NASA records and the USDA soil survey. Each carries its source.`}>
            <ul className="fact-list">
              {field.insights.facts.map((f) => (
                <li key={f.id} className="fact" style={{ borderLeftColor: DIM_COLOR[f.dimension] }}>
                  <div className="row-wrap">
                    <span className="xs" style={{ color: DIM_COLOR[f.dimension], fontWeight: 700 }}>{DIM_SHORT[f.dimension].toUpperCase()}</span>
                    <ProvenanceBadge access={f.access} source={f.source} />
                    {f.trend?.significant && <span className="chip chip-warn">clear trend</span>}
                  </div>
                  <strong>{f.headline}</strong>
                  <p>{f.detail}</p>
                </li>
              ))}
            </ul>
          </Card>
          <div className="stack">
            <FieldMap farms={farms ?? []} selectedId={id} onSelect={() => undefined} field={field} height={460} />
            <p className="xs faint">
              The gold square is the field. Dashed squares show how much ground a single <Term id="resolution">pixel</Term> of each dataset covers:
              zoom out to find the 55 km weather cell.
            </p>
          </div>
        </section>

        <section id="seasons">
          <TimelinePanel field={field} comparison={cmp} />
        </section>

        <section id="priorities" className="controls-and-results">
          <Card title="What matters on your farm?" subtitle="Your answers decide the ranking. There is no single best rotation, only the best one for these goals." className="controls-card">
            <Tabs label="Farmer inputs" value={controlTab} onChange={setControlTab}
              tabs={[{ id: "priorities", label: "Priorities" }, { id: "constraints", label: "What the farm can do", badge: Object.keys(constraints).length || undefined }]} />
            <div style={{ paddingTop: 16 }}>
              {controlTab === "priorities"
                ? (cmp ? <PrioritySliders effective={cmp.priorities} defaults={field.farm.default_priorities} /> : <Loading height={320} />)
                : <ConstraintsPanel field={field} />}
            </div>
          </Card>
          <div className="results-col">
            {comparison.error && <ErrorNotice error={comparison.error} title="The rotations could not be compared" />}
            {!cmp && !comparison.error && <Card title="Simulating rotations for this field"><Loading height={420} label="Simulating rotations" /></Card>}
            {cmp && <StrategyExplorer field={field} comparison={cmp} refreshing={comparison.refreshing} />}
          </div>
        </section>

        <section id="stress">
          <Card title="Would it hold up? Stress-test the rotations"
            subtitle="Shift the weather this field has actually had since 2001 and re-run every rotation: planting dates, water, heat, erosion and income all respond.">
            <div className="stress-layout">
              <div><ScenarioSliders irrigated={irrigated} /></div>
              <div className="stack">
                {isNeutral(scenario) && <p className="notice notice-info">Move a dial or pick a preset to see how each rotation responds. Below: how the rotations compare across one dial's whole range.</p>}
                {stress.error && <ErrorNotice error={stress.error} />}
                {!isNeutral(scenario) && !stress.data && !stress.error && <Loading height={260} label="Running the scenario" />}
                {!isNeutral(scenario) && stress.data && <ScenarioResults result={stress.data} refreshing={stress.refreshing} />}
                {cmp && <TippingOverview fieldId={id} strategies={cmp.strategies} irrigated={irrigated} />}
                {cmp && <TippingPoints fieldId={id} strategies={cmp.strategies} irrigated={irrigated} />}
              </div>
            </div>
          </Card>
        </section>

        <section id="trust" className="stack">
          <TrustCard field={field} />
          {cmp && (
            <Card title="Take it with you" subtitle="A brief for your County Extension agent or crop adviser: the field, your priorities, each rotation's five explanations and the checklist.">
              <ExportButtons field={field} comparison={cmp} />
            </Card>
          )}
        </section>
      </div>
    </div>
  );
}

function FieldHero({ field }: { field: FieldOverview }) {
  const units = useUnits();
  const f = field.farm;
  const c = field.climate;
  const gw = field.groundwater;
  return (
    <header className="field-hero">
      <div className="container">
        <Link to="/" className="field-back no-print">← All fields</Link>
        <div className="field-hero-grid">
          <div>
            <span className="eyebrow hero-eyebrow">{f.region}{f.county ? ` · ${f.county} County, ${f.state}` : ""} · {units.area(f.area_ha)}</span>
            <h1>{f.name}</h1>
            <p className="field-headline">{f.headline}</p>
            <p className="field-story">{f.story}</p>
            <div className="row-wrap">{f.challenge_tags.map((t) => <span key={t} className="chip chip-hero">{t}</span>)}</div>
          </div>
          <div className="field-stats">
            <Stat label="Grows now" value={<span style={{ fontSize: "1.05rem" }}>{f.baseline_rotation.name}</span>} sub={f.management.irrigation.label} />
            <Stat label={<Term id="fused_rain">Rain and snow</Term>} value={`${units.water(field.fusion.precip.annual_mm, units.system === "us" ? 1 : 0)}`} sub={`a year · air could take ${units.water(c.annual_et0_mm, 0)}`} />
            <Stat label="Soil" value={<span style={{ fontSize: "1.05rem" }}>{field.soil.series} {field.soil.texture_class}</span>} sub={<>{field.soil.organic_matter_pct}% <Term id="organic_matter">organic matter</Term> · group <Term id="hsg">{field.soil.hydrologic_group}</Term></>} />
            <Stat label={<Term id="frost_free">Frost-free season</Term>} value={`${Math.round(c.frost.frost_free_days_median)} days`} sub={`${Math.round(c.monthly.heat_days_35.reduce((a, b) => a + b, 0))} days a year reach ${units.temp(35)}`} />
            {gw.tws_trend_cm_yr !== null && (
              <Stat label={<Term id="grace">Regional water storage</Term>} tone={gw.tws_trend_cm_yr < -0.3 ? "bad" : undefined}
                value={`${gw.tws_trend_cm_yr > 0 ? "+" : ""}${units.system === "us" ? (gw.tws_trend_cm_yr / 2.54).toFixed(1) + " in" : gw.tws_trend_cm_yr.toFixed(1) + " cm"}/yr`} sub="GRACE satellites, ~200 mi footprint" />
            )}
            <Stat label="Slope" value={`${(field.soil.representative_slope_pct ?? field.terrain?.slope_pct ?? 0).toFixed(1)}%`} sub={field.terrain ? `${units.distance(field.terrain.elevation_m)} elevation` : "soil survey"} />
          </div>
        </div>
      </div>
    </header>
  );
}

/** How much weight each data layer carries for this field, and anything that failed to load. */
function TrustCard({ field }: { field: FieldOverview }) {
  const units = useUnits();
  const conf = field.fusion.confidence;
  return (
    <Card title="Where the numbers come from, and how far to trust them"
      subtitle="Every layer, how it was obtained, how big its pixel is next to this field, and the weight the tool gives it. Nothing is hidden behind the scores.">
      <div className="table-scroll">
        <table className="table">
          <thead><tr><th>Layer</th><th>Source</th><th>How obtained</th><th className="num">Pixel</th><th className="num">vs. field</th><th>Brought to field scale by</th><th className="num">Weight</th></tr></thead>
          <tbody>
            {field.fusion.layers.map((l) => (
              <tr key={l.id}>
                <td><strong>{l.label}</strong><div className="xs faint">{l.used_for}</div></td>
                <td className="small">{l.source}</td>
                <td><ProvenanceBadge access={l.access} compact /></td>
                <td className="num">{l.native_resolution_m ? units.distance(l.native_resolution_m) : "—"}</td>
                <td className="num">{l.pixel_to_field_ratio ? `${l.pixel_to_field_ratio >= 1 ? Math.round(l.pixel_to_field_ratio) : l.pixel_to_field_ratio.toFixed(1)}×` : "—"}</td>
                <td className="small muted">{l.harmonisation}{l.access === "proxy" || l.access === "unavailable" ? <div className="xs" style={{ color: "var(--warn)" }}>{l.note}</div> : null}</td>
                <td className="num"><strong>{Math.round(l.confidence * 100)}</strong></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small muted" style={{ marginTop: 10 }}>
        All layers are resampled to calendar months and referenced to the field: {field.fusion.target_grid.toLowerCase()}.
        Overall <Term id="confidence">confidence</Term> for this field: <strong>{Math.round(conf.overall * 100)}/100</strong>.
        {field.issues.length > 0 && <> Not retrieved: {field.issues.map((i) => i.layer).join(", ")}.</>}{" "}
        <Link to="/methods">How the models work →</Link>
      </p>
    </Card>
  );
}
