/**
 * Printable Agronomy Field Brief: one document a farmer can hand to an Extension agent or
 * crop adviser. Uses the browser's print dialog for paper or PDF.
 *
 * OWNER: Member 3. See components/common/export/briefTemplates.ts for the download formats.
 */
import { Link, useParams } from "react-router-dom";

import { ExportButtons } from "@/components/common/export/ExportButtons";
import { ErrorNotice, Loading, SupportNotJudgment } from "@/components/common/ui";
import { SequenceStrip } from "@/components/rotation-explorer/sequence-builder/SequenceStrip";
import { useComparison, useField } from "@/hooks/useData";
import { useFieldShift } from "@/hooks/useFieldShift";
import { useUnits } from "@/hooks/useUnits";
import { DIM_SHORT } from "@/styles/theme";
import { DIMENSIONS } from "@/types/api";

export function BriefPage() {
  const { id = "" } = useParams();
  const { data: field, error } = useField(id);
  const { data: cmp, error: cmpError } = useComparison(field ? id : null);
  const { reviewed } = useFieldShift();
  const units = useUnits();

  if (error || cmpError) return <div className="container" style={{ padding: 48 }}><ErrorNotice error={(error ?? cmpError)!} /></div>;
  if (!field || !cmp) return <div className="container" style={{ padding: 48 }}><Loading height={400} label="Preparing the brief" /></div>;
  const f = field.farm;
  return (
    <div className="brief container">
      <div className="spread no-print" style={{ flexWrap: "wrap", marginBottom: 20 }}>
        <Link to={`/field/${id}`}>← Back to the field</Link>
        <ExportButtons field={field} comparison={cmp} showPrintLink={false} />
      </div>

      <header className="brief-head">
        <span className="eyebrow">Agronomy Field Brief · {new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}</span>
        <h1>{f.name}</h1>
        <p className="muted">
          {f.lat.toFixed(3)}°, {f.lon.toFixed(3)}°{f.county ? ` · ${f.county} County, ${f.state}` : ""} · {units.area(f.area_ha)} · {f.management.irrigation.label}
        </p>
        <SupportNotJudgment text={cmp.disclaimer} />
      </header>

      <section className="brief-section">
        <h2>The field</h2>
        <ul className="brief-list">
          <li><strong>Soil:</strong> {field.soil.series} {field.soil.texture_class}, {field.soil.organic_matter_pct}% organic matter, hydrologic group {field.soil.hydrologic_group}, pH {field.soil.ph}, {String(field.soil.drainage_class).toLowerCase()}.</li>
          <li><strong>Climate {field.climate.years[0]}–{field.climate.years[field.climate.years.length - 1]}:</strong> {units.water(field.fusion.precip.annual_mm)} of precipitation a year, reference ET {units.water(field.climate.annual_et0_mm)}, about {Math.round(field.climate.frost.frost_free_days_median)} frost-free days.</li>
          <li><strong>Current rotation:</strong> {f.baseline_rotation.name}. {cmp.baseline_note}</li>
          <li><strong>Priorities stated (0–10):</strong> {DIMENSIONS.map((d) => `${DIM_SHORT[d]} ${cmp.priorities[d]}`).join(" · ")}.</li>
        </ul>
        <h3 style={{ marginTop: 14 }}>What the record shows</h3>
        <ul className="brief-list">
          {field.insights.facts.map((x) => <li key={x.id}><strong>{x.headline}.</strong> {x.detail} <span className="faint xs">({x.source}{x.access ? `, ${x.access}` : ""})</span></li>)}
        </ul>
      </section>

      <section className="brief-section">
        <h2>Rotations compared</h2>
        <p>{cmp.summary.statement}</p>
        <table className="table" style={{ marginTop: 10 }}>
          <thead><tr><th>Rotation</th><th className="num">Fit</th>{DIMENSIONS.map((d) => <th key={d} className="num">{DIM_SHORT[d]}</th>)}<th className="num">Bare months</th><th className="num">Erosion</th><th className="num">Net / acre</th></tr></thead>
          <tbody>
            {cmp.strategies.map((s) => (
              <tr key={s.id}>
                <td><strong>{s.role === "baseline" ? "Current" : s.title}</strong><div className="xs">{s.name} · {s.tillage_label}</div></td>
                <td className="num"><strong>{Math.round(s.fit.fit)}</strong></td>
                {DIMENSIONS.map((d) => <td key={d} className="num">{Math.round(s.scores[d])}</td>)}
                <td className="num">{s.metrics.bare_months_per_year}</td>
                <td className="num">{units.soilLoss(s.metrics.soil_loss_tons_ac_yr)}</td>
                <td className="num">{units.money(s.metrics.net_return_per_acre_yr)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {cmp.strategies.map((s) => {
        const ex = s.explanation;
        return (
          <section key={s.id} className="brief-section brief-strategy">
            <h2>{s.role === "baseline" ? "Current rotation" : s.title}: {s.name}</h2>
            <SequenceStrip years={s.year_labels} />
            <h3>1. Why it was suggested</h3>
            <ul className="brief-list">{ex.why.map((r, i) => <li key={i}>{r.text}</li>)}</ul>
            <h3>2. Supporting evidence</h3>
            <ul className="brief-list">{ex.evidence.map((e) => <li key={e.id}><strong>{e.statement}.</strong> {e.detail} <span className="faint xs">({e.source})</span></li>)}</ul>
            <h3>3. Expected benefits and costs</h3>
            {s.role === "baseline" ? <p className="muted">The reference the alternatives are measured against.</p> : (
              <table className="table">
                <thead><tr><th>Outcome</th><th className="num">Now</th><th className="num">This rotation</th><th>Direction</th><th>Confidence</th></tr></thead>
                <tbody>{ex.benefits.items.map((b) => <tr key={b.metric}><td>{b.label}</td><td className="num">{units.metric(b.baseline, b.unit)}</td><td className="num">{units.metric(b.value, b.unit)}</td><td>{b.direction}</td><td>{b.confidence}</td></tr>)}</tbody>
              </table>
            )}
            <h3>4. Information gaps and uncertainty</h3>
            <p className="small">{ex.gaps.statement}</p>
            <ul className="brief-list">{ex.gaps.items.map((g) => <li key={g.id}><strong>{g.topic}.</strong> {g.detail} <em>To close it: {g.close_by}</em></li>)}</ul>
            <h3>5. Risks needing local review</h3>
            <ul className="brief-checklist">
              {ex.risks.map((r) => (
                <li key={r.id}>
                  <span className="brief-box" aria-hidden>{reviewed[`${cmp.field_id}:${s.id}:${r.id}`] ? "☑" : "☐"}</span>
                  <div><strong>{r.title}</strong> <span className="faint xs">({r.who.join(", ")})</span><div className="small">{r.detail}</div></div>
                </li>
              ))}
            </ul>
          </section>
        );
      })}

      <section className="brief-section">
        <h2>Notes from the review</h2>
        <div className="brief-notes" />
        <p className="xs faint">Scores are planning estimates from a monthly model. Dollar figures exclude land cost; they rank options and are not a budget.</p>
      </section>
    </div>
  );
}
