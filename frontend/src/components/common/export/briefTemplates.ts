/**
 * Export templates for the Agronomy Field Brief.
 *
 * OWNER: Member 3.
 *
 * A template turns the field overview and the comparison into a file. To add a format,
 * add one entry to EXPORT_TEMPLATES: it appears as a download button automatically.
 * The Markdown brief follows the interface language (English or Bahasa Malaysia); text
 * written by the backend stays as the API returns it.
 *
 * TODO (Member 3): DOA / MARDI extension-officer PDF layout. The printable page (pages/BriefPage.tsx) already
 *   prints cleanly to PDF from the browser; a dedicated A4 layout with a signature
 *   block and the office's intake questions would make it a hand-in document.
 * TODO (Member 3): a short "read it to me" summary template written for text-to-speech.
 * TODO (Member 3): CSV of the month-by-month calendar (strategy.months) for farm-record software.
 */
import { translate, translateName, type Lang } from "@/i18n/LanguageProvider";
import type { CompareResponse, FieldOverview, Strategy } from "@/types/api";
import { DIMENSIONS } from "@/types/api";

export interface ExportContext {
  field: FieldOverview;
  comparison: CompareResponse;
  /** Risk-review ticks keyed "fieldId:strategyId:riskId". */
  reviewed: Record<string, boolean>;
  /** Interface language; defaults to English. */
  lang?: Lang;
}

export interface ExportTemplate {
  id: string;
  label: string;
  filename: (ctx: ExportContext) => string;
  mime: string;
  build: (ctx: ExportContext) => string;
}

const DIM_NAME = { water: "Water", soil: "Soil health", erosion: "Soil cover", pest: "Pest break", income: "Income" } as const;
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const money = (v: number) => `${v < 0 ? "-" : ""}RM ${Math.abs(Math.round(v)).toLocaleString("en-MY")}`;
/** Soil loss arrives in tons/acre/yr; the brief reports tonnes per hectare. */
const tHa = (tonsAc: number) => (tonsAc * 2.2417).toFixed(1);

function strategySection(s: Strategy, ctx: ExportContext): string {
  const lang = ctx.lang ?? "en";
  const t = (text: string, vars?: Record<string, string | number>) => translate(lang, text, vars);
  const m = s.metrics;
  const ex = s.explanation;
  const lines: string[] = [];
  lines.push(`## ${s.role === "baseline" ? t("Current rotation") : t(s.title)}: ${translateName(lang, s.name)}`);
  lines.push("");
  lines.push(`*${t(s.tillage_label)}. ${t("Fit for the stated priorities: {fit}/100 (rank {rank} of {n}).", { fit: Math.round(s.fit.fit), rank: s.rank, n: ctx.comparison.strategies.length })}*`);
  lines.push("");
  lines.push(`| ${DIMENSIONS.map((d) => t(DIM_NAME[d])).join(" | ")} |`);
  lines.push(`| ${DIMENSIONS.map(() => "---:").join(" | ")} |`);
  lines.push(`| ${DIMENSIONS.map((d) => `${Math.round(s.scores[d])} ±${ex.gaps.score_uncertainty[d]}`).join(" | ")} |`);
  lines.push("");
  lines.push(t("Key numbers: irrigation {irr} mm/yr; crop water stress {ws}%; bare soil {bare} months/yr; erosion {ero} t/ha/yr ({tol}x tolerable); purchased N {n} kg/ha/yr; net return {net}/ha/yr", {
    irr: m.irrigation_mm_yr, ws: m.water_stress_pct, bare: m.bare_months_per_year, ero: tHa(m.soil_loss_tons_ac_yr),
    tol: m.soil_loss_vs_tolerable, n: m.n_fertilizer_kg_ha_yr, net: money(m.net_return_per_ha_yr),
  }) + (s.history ? `; ${t("bad year (1 in 5) {v}/ha", { v: money(s.history.bad_year_net_per_ha) })}.` : "."));
  lines.push("");
  lines.push(`### 1. ${t("Why it was suggested")}`);
  ex.why.forEach((r) => lines.push(`- ${r.text}`));
  lines.push("");
  lines.push(`### 2. ${t("Supporting evidence")}`);
  ex.evidence.forEach((e) => lines.push(`- **${e.statement}.** ${e.detail} _(${e.source ?? "model"}${e.access ? `, ${e.access}` : ""})_`));
  lines.push("");
  lines.push(`### 3. ${t("Expected benefits and costs (against the current rotation)")}`);
  if (s.role === "baseline") lines.push(t("The reference the alternatives are measured against."));
  else {
    lines.push(`| ${t("Outcome")} | ${t("Now")} | ${t("With this rotation")} | ${t("Change")} | ${t("Confidence")} |`);
    lines.push("| --- | ---: | ---: | ---: | --- |");
    ex.benefits.items.forEach((b) => lines.push(`| ${t(b.label)} (${b.unit}) | ${b.baseline} | ${b.value} | ${b.delta > 0 ? "+" : ""}${b.delta} (${t(b.direction)}) | ${t(b.confidence)} |`));
  }
  lines.push("");
  lines.push(`### 4. ${t("Information gaps and model uncertainty")}`);
  lines.push(ex.gaps.statement);
  ex.gaps.items.forEach((g) => lines.push(`- **${g.topic}.** ${g.detail} ${t("To close it:")} ${g.close_by}`));
  lines.push("");
  lines.push(`### 5. ${t("Risks needing local review")}`);
  ex.risks.forEach((r) => {
    const done = ctx.reviewed[`${ctx.comparison.field_id}:${s.id}:${r.id}`];
    lines.push(`- [${done ? "x" : " "}] **${r.title}** (${r.who.map((w) => t(w)).join(", ")}). ${r.detail}`);
  });
  lines.push("");
  return lines.join("\n");
}

export function buildMarkdownBrief(ctx: ExportContext): string {
  const lang = ctx.lang ?? "en";
  const t = (text: string, vars?: Record<string, string | number>) => translate(lang, text, vars);
  const { field, comparison } = ctx;
  const f = field.farm;
  const c = field.climate;
  const lines: string[] = [];
  lines.push(`# ${t("Agronomy Field Brief")}: ${f.name}`);
  lines.push("");
  lines.push(`> ${comparison.disclaimer}`);
  lines.push("");
  lines.push(t("Prepared {date} with Kebunda. Location {lat}, {lon}{place}. Field size {ha} ha.", {
    date: new Date().toLocaleDateString(lang === "ms" ? "ms-MY" : "en-MY", { year: "numeric", month: "long", day: "numeric" }),
    lat: f.lat.toFixed(3), lon: f.lon.toFixed(3), place: f.district ? ` (${f.district}, ${f.state})` : "", ha: f.area_ha.toFixed(1),
  }));
  lines.push("");
  lines.push(`## ${t("The field")}`);
  lines.push(`- **${t("Soil")}:** ${field.soil.series} ${field.soil.texture_class}, ${t("{n}% organic matter", { n: field.soil.organic_matter_pct })}, ${t("hydrologic group")} ${field.soil.hydrologic_group}, ` +
    `pH ${field.soil.ph}, ${String(field.soil.drainage_class).toLowerCase()} (${field.soil.provenance?.source ?? "ISRIC SoilGrids"}).`);
  lines.push(`- **${t("Climate")} ${c.years[0]}-${c.years[c.years.length - 1]}:** ` + t("{rain} mm rainfall/yr (fused), reference ET {et} mm/yr, mean {temp} °C (NASA POWER, GPM IMERG, MetMalaysia gauges).", {
    rain: field.fusion.precip.annual_mm, et: c.annual_et0_mm, temp: c.mean_annual_temp_c,
  }));
  lines.push(`- **${t("Water")}:** ${t(f.management.irrigation.label)}${f.management.irrigation.allocation_mm ? `, ${t("{n} mm/yr available", { n: f.management.irrigation.allocation_mm })}` : ""}. ${f.water_context.note}`);
  lines.push(`- **${t("Current rotation")}:** ${translateName(lang, f.baseline_rotation.name)}. ${comparison.baseline_note ?? ""}`);
  lines.push("");
  lines.push(`## ${t("What the record shows")}`);
  field.insights.facts.forEach((x) => lines.push(`- **${x.headline}.** ${x.detail} _(${x.source ?? "n/a"})_`));
  lines.push("");
  lines.push(`## ${t("Priorities stated by the farmer (0-10)")}`);
  lines.push(DIMENSIONS.map((d) => `${t(comparison.priority_labels[d])}: **${comparison.priorities[d]}**`).join("; ") + ".");
  lines.push("");
  lines.push(`## ${t("Summary")}\n${comparison.summary.statement}`);
  lines.push("");
  comparison.strategies.forEach((s) => lines.push(strategySection(s, ctx)));
  lines.push(`## ${t("Data sources and how much weight each carries")}`);
  lines.push(`| ${t("Layer")} | ${t("Source")} | ${t("Access")} | ${t("Pixel size")} | ${t("Confidence for this field")} |`);
  lines.push("| --- | --- | --- | ---: | ---: |");
  field.fusion.layers.forEach((l) => lines.push(`| ${l.label} | ${l.source ?? ""} | ${l.access ?? ""} | ${l.native_resolution_m ? `${l.native_resolution_m} m` : "n/a"} | ${Math.round(l.confidence * 100)} |`));
  lines.push("");
  lines.push(`_${t("Scores are planning estimates from a monthly model. Ringgit figures exclude land cost and rank options; they are not a budget.")}_`);
  return lines.join("\n");
}

export const EXPORT_TEMPLATES: ExportTemplate[] = [
  { id: "markdown", label: "Download brief (Markdown)", mime: "text/markdown", filename: (c) => `kebunda-brief-${slug(c.field.farm.short_name)}.md`, build: buildMarkdownBrief },
  {
    id: "json", label: "Download data (JSON)", mime: "application/json", filename: (c) => `kebunda-data-${slug(c.field.farm.short_name)}.json`,
    build: (c) => JSON.stringify({ exported_at: new Date().toISOString(), field: c.field, comparison: c.comparison }, null, 2),
  },
];

export function downloadText(filename: string, mime: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: `${mime};charset=utf-8` }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
