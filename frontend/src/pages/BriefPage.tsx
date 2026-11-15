/**
 * Printable Agronomy Field Brief: one document a farmer can hand to a DOA extension officer or
 * crop adviser. Uses the browser's print dialog for paper or PDF.
 *
 * OWNER: Member 3. See components/common/export/briefTemplates.ts for the download formats.
 */
import { Link, useParams } from "react-router-dom";

import { ExportButtons } from "@/components/common/export/ExportButtons";
import { ErrorNotice, Loading, SupportNotJudgment } from "@/components/common/ui";
import { SequenceStrip } from "@/components/rotation-explorer/sequence-builder/SequenceStrip";
import { useComparison, useField } from "@/hooks/useData";
import { useKebunda } from "@/hooks/useKebunda";
import { useUnits } from "@/hooks/useUnits";
import { useT } from "@/i18n/LanguageProvider";
import { DIM_SHORT } from "@/styles/theme";
import { DIMENSIONS } from "@/types/api";

export function BriefPage() {
  const { id = "" } = useParams();
  const { data: field, error } = useField(id);
  const { data: cmp, error: cmpError } = useComparison(field ? id : null);
  const { reviewed } = useKebunda();
  const units = useUnits();
  const { t, tName, locale } = useT();

  if (error || cmpError) return <div className="container" style={{ padding: 48 }}><ErrorNotice error={(error ?? cmpError)!} /></div>;
  if (!field || !cmp) return <div className="container" style={{ padding: 48 }}><Loading height={400} label="Preparing the brief" /></div>;
  const f = field.farm;
  return (
    <div className="brief container">
      <div className="spread no-print" style={{ flexWrap: "wrap", marginBottom: 20 }}>
        <Link to={`/field/${id}`}>{t("← Back to the field")}</Link>
        <ExportButtons field={field} comparison={cmp} showPrintLink={false} />
      </div>

      <header className="brief-head">
        <span className="eyebrow">{t("Agronomy Field Brief")} · {new Date().toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" })}</span>
        <h1>{f.name}</h1>
        <p className="muted">
          {f.lat.toFixed(3)}°, {f.lon.toFixed(3)}°{f.district ? ` · ${f.district}, ${f.state}` : ""} · {units.area(f.area_ha)} · {t(f.management.irrigation.label)}
        </p>
        <SupportNotJudgment text={cmp.disclaimer} />
      </header>

      <section className="brief-section">
        <h2>{t("The field")}</h2>
        <ul className="brief-list">
          <li><strong>{t("Soil")}:</strong> {field.soil.series} {field.soil.texture_class}, {t("{n}% organic matter", { n: field.soil.organic_matter_pct })}, {t("hydrologic group")} {field.soil.hydrologic_group}, pH {field.soil.ph}, {String(field.soil.drainage_class).toLowerCase()}.</li>
          <li><strong>{t("Climate")} {field.climate.years[0]}–{field.climate.years[field.climate.years.length - 1]}:</strong> {t("{rain} of rain a year, reference ET {et}, mean temperature {temp}.", { rain: units.water(field.fusion.precip.annual_mm), et: units.water(field.climate.annual_et0_mm), temp: units.temp(field.climate.mean_annual_temp_c, 1) })}</li>
          <li><strong>{t("Current rotation")}:</strong> {tName(f.baseline_rotation.name)}. {cmp.baseline_note}</li>
          <li><strong>{t("Priorities stated (0–10)")}:</strong> {DIMENSIONS.map((d) => `${t(DIM_SHORT[d])} ${cmp.priorities[d]}`).join(" · ")}.</li>
        </ul>
        <h3 style={{ marginTop: 14 }}>{t("What the record shows")}</h3>
        <ul className="brief-list">
          {field.insights.facts.map((x) => <li key={x.id}><strong>{x.headline}.</strong> {x.detail} <span className="faint xs">({x.source}{x.access ? `, ${x.access}` : ""})</span></li>)}
        </ul>
      </section>

      <section className="brief-section">
        <h2>{t("Rotations compared")}</h2>
        <p>{cmp.summary.statement}</p>
        <table className="table" style={{ marginTop: 10 }}>
          <thead><tr><th>{t("Rotation")}</th><th className="num">{t("Fit")}</th>{DIMENSIONS.map((d) => <th key={d} className="num">{t(DIM_SHORT[d])}</th>)}<th className="num">{t("Bare months")}</th><th className="num">{t("Erosion")}</th><th className="num">{t("Net / ha")}</th></tr></thead>
          <tbody>
            {cmp.strategies.map((s) => (
              <tr key={s.id}>
                <td><strong>{s.role === "baseline" ? t("Current") : t(s.title)}</strong><div className="xs">{tName(s.name)} · {t(s.tillage_label)}</div></td>
                <td className="num"><strong>{Math.round(s.fit.fit)}</strong></td>
                {DIMENSIONS.map((d) => <td key={d} className="num">{Math.round(s.scores[d])}</td>)}
                <td className="num">{s.metrics.bare_months_per_year}</td>
                <td className="num">{units.soilLoss(s.metrics.soil_loss_tons_ac_yr)}</td>
                <td className="num">{units.money(s.metrics.net_return_per_ha_yr)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {cmp.strategies.map((s) => {
        const ex = s.explanation;
        return (
          <section key={s.id} className="brief-section brief-strategy">
            <h2>{s.role === "baseline" ? t("Current rotation") : t(s.title)}: {tName(s.name)}</h2>
            <SequenceStrip years={s.year_labels} />
            <h3>1. {t("Why it was suggested")}</h3>
            <ul className="brief-list">{ex.why.map((r, i) => <li key={i}>{r.text}</li>)}</ul>
            <h3>2. {t("Supporting evidence")}</h3>
            <ul className="brief-list">{ex.evidence.map((e) => <li key={e.id}><strong>{e.statement}.</strong> {e.detail} <span className="faint xs">({e.source})</span></li>)}</ul>
            <h3>3. {t("Expected benefits and costs")}</h3>
            {s.role === "baseline" ? <p className="muted">{t("The reference the alternatives are measured against.")}</p> : (
              <table className="table">
                <thead><tr><th>{t("Outcome")}</th><th className="num">{t("Now")}</th><th className="num">{t("This rotation")}</th><th>{t("Direction")}</th><th>{t("Confidence")}</th></tr></thead>
                <tbody>{ex.benefits.items.map((b) => <tr key={b.metric}><td>{t(b.label)}</td><td className="num">{units.metric(b.baseline, b.unit)}</td><td className="num">{units.metric(b.value, b.unit)}</td><td>{t(b.direction)}</td><td>{t(b.confidence)}</td></tr>)}</tbody>
              </table>
            )}
            <h3>4. {t("Information gaps and uncertainty")}</h3>
            <p className="small">{ex.gaps.statement}</p>
            <ul className="brief-list">{ex.gaps.items.map((g) => <li key={g.id}><strong>{g.topic}.</strong> {g.detail} <em>{t("To close it:")} {g.close_by}</em></li>)}</ul>
            <h3>5. {t("Risks needing local review")}</h3>
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
        <h2>{t("Notes from the review")}</h2>
        <div className="brief-notes" />
        <p className="xs faint">{t("Scores are planning estimates from a monthly model. Ringgit figures exclude land cost; they rank options and are not a budget.")}</p>
      </section>
    </div>
  );
}
