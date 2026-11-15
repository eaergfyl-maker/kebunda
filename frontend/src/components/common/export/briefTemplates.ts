/**
 * Export templates for the Agronomy Field Brief.
 *
 * OWNER: Member 3.
 *
 * A template turns the field overview and the comparison into a file. To add a format,
 * add one entry to EXPORT_TEMPLATES: it appears as a download button automatically.
 *
 * TODO (Member 3): DOA / MARDI extension-officer PDF layout. The printable page (pages/BriefPage.tsx) already
 *   prints cleanly to PDF from the browser; a dedicated letter-size layout with a signature
 *   block and the office's intake questions would make it a hand-in document.
 * TODO (Member 3): multi-language brief (Spanish first) and a short "read it to me" summary
 *   template written for text-to-speech.
 * TODO (Member 3): CSV of the month-by-month calendar (strategy.months) for farm-record software.
 */
import type { CompareResponse, FieldOverview, Strategy } from "@/types/api";
import { DIMENSIONS } from "@/types/api";

export interface ExportContext {
  field: FieldOverview;
  comparison: CompareResponse;
  /** Risk-review ticks keyed "fieldId:strategyId:riskId". */
  reviewed: Record<string, boolean>;
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
const money = (v: number) => `${v < 0 ? "-" : ""}$${Math.abs(Math.round(v)).toLocaleString()}`;

function strategySection(s: Strategy, ctx: ExportContext): string {
  const m = s.metrics;
  const ex = s.explanation;
  const lines: string[] = [];
  lines.push(`## ${s.role === "baseline" ? "Current rotation" : s.title}: ${s.name}`);
  lines.push("");
  lines.push(`*${s.tillage_label}. Fit for the stated priorities: ${Math.round(s.fit.fit)}/100 (rank ${s.rank} of ${ctx.comparison.strategies.length}).*`);
  lines.push("");
  lines.push(`| ${DIMENSIONS.map((d) => DIM_NAME[d]).join(" | ")} |`);
  lines.push(`| ${DIMENSIONS.map(() => "---:").join(" | ")} |`);
  lines.push(`| ${DIMENSIONS.map((d) => `${Math.round(s.scores[d])} ±${ex.gaps.score_uncertainty[d]}`).join(" | ")} |`);
  lines.push("");
  lines.push(`Key numbers: irrigation ${m.irrigation_mm_yr} mm/yr; crop water stress ${m.water_stress_pct}%; bare soil ${m.bare_months_per_year} months/yr; ` +
    `erosion ${m.soil_loss_tons_ac_yr} tons/ac/yr (${m.soil_loss_vs_tolerable}x tolerable); purchased N ${m.n_fertilizer_kg_ha_yr} kg/ha/yr; ` +
    `net return ${money(m.net_return_per_ha_yr)}/ac/yr` + (s.history ? `; bad year (1 in 5) ${money(s.history.bad_year_net_per_ha)}/ac.` : "."));
  lines.push("");
  lines.push("### 1. Why it was suggested");
  ex.why.forEach((r) => lines.push(`- ${r.text}`));
  lines.push("");
  lines.push("### 2. Supporting evidence");
  ex.evidence.forEach((e) => lines.push(`- **${e.statement}.** ${e.detail} _(${e.source ?? "model"}${e.access ? `, ${e.access}` : ""})_`));
  lines.push("");
  lines.push("### 3. Expected benefits and costs (against the current rotation)");
  if (s.role === "baseline") lines.push("This is the reference the alternatives are measured against.");
  else {
    lines.push("| Outcome | Now | With this rotation | Change | Confidence |");
    lines.push("| --- | ---: | ---: | ---: | --- |");
    ex.benefits.items.forEach((b) => lines.push(`| ${b.label} (${b.unit}) | ${b.baseline} | ${b.value} | ${b.delta > 0 ? "+" : ""}${b.delta} (${b.direction}) | ${b.confidence} |`));
  }
  lines.push("");
  lines.push("### 4. Information gaps and model uncertainty");
  lines.push(ex.gaps.statement);
  ex.gaps.items.forEach((g) => lines.push(`- **${g.topic}.** ${g.detail} To close it: ${g.close_by}`));
  lines.push("");
  lines.push("### 5. Risks needing local review");
  ex.risks.forEach((r) => {
    const done = ctx.reviewed[`${ctx.comparison.field_id}:${s.id}:${r.id}`];
    lines.push(`- [${done ? "x" : " "}] **${r.title}** (${r.who.join(", ")}). ${r.detail}`);
  });
  lines.push("");
  return lines.join("\n");
}

export function buildMarkdownBrief(ctx: ExportContext): string {
  const { field, comparison } = ctx;
  const f = field.farm;
  const c = field.climate;
  const lines: string[] = [];
  lines.push(`# Agronomy Field Brief: ${f.name}`);
  lines.push("");
  lines.push(`> ${comparison.disclaimer}`);
  lines.push("");
  lines.push(`Prepared ${new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })} with FieldShift. ` +
    `Location ${f.lat.toFixed(3)}, ${f.lon.toFixed(3)}${f.district ? ` (${f.district}, ${f.state})` : ""}. Field size ${f.area_ha.toFixed(1)} ha.`);
  lines.push("");
  lines.push("## The field");
  lines.push(`- **Soil:** ${field.soil.series} ${field.soil.texture_class}, ${field.soil.organic_matter_pct}% organic matter, hydrologic group ${field.soil.hydrologic_group}, ` +
    `pH ${field.soil.ph}, ${String(field.soil.drainage_class).toLowerCase()} (USDA SSURGO).`);
  lines.push(`- **Climate ${c.years[0]}-${c.years[c.years.length - 1]}:** ${field.fusion.precip.annual_mm} mm precipitation/yr (fused), reference ET ${c.annual_et0_mm} mm/yr, ` +
    `mean ${c.mean_annual_temp_c} C, about ${c.frost.frost_free_days_median} frost-free days (NASA POWER, GPM IMERG, Daymet).`);
  lines.push(`- **Water:** ${f.management.irrigation.label}${f.management.irrigation.allocation_mm ? `, ${f.management.irrigation.allocation_mm} mm/yr available` : ""}. ${f.water_context.note}`);
  lines.push(`- **Current rotation:** ${f.baseline_rotation.name}. ${comparison.baseline_note ?? ""}`);
  lines.push("");
  lines.push("## What the record shows");
  field.insights.facts.forEach((x) => lines.push(`- **${x.headline}.** ${x.detail} _(${x.source ?? "n/a"})_`));
  lines.push("");
  lines.push("## Priorities stated by the farmer (0-10)");
  lines.push(DIMENSIONS.map((d) => `${comparison.priority_labels[d]}: **${comparison.priorities[d]}**`).join("; ") + ".");
  lines.push("");
  lines.push(`## Summary\n${comparison.summary.statement}`);
  lines.push("");
  comparison.strategies.forEach((s) => lines.push(strategySection(s, ctx)));
  lines.push("## Data sources and how much weight each carries");
  lines.push("| Layer | Source | Access | Pixel size | Confidence for this field |");
  lines.push("| --- | --- | --- | ---: | ---: |");
  field.fusion.layers.forEach((l) => lines.push(`| ${l.label} | ${l.source ?? ""} | ${l.access ?? ""} | ${l.native_resolution_m ? `${l.native_resolution_m} m` : "n/a"} | ${Math.round(l.confidence * 100)} |`));
  lines.push("");
  lines.push("_Scores are planning estimates from a monthly model. Dollar figures exclude land cost and rank options; they are not a budget._");
  return lines.join("\n");
}

export const EXPORT_TEMPLATES: ExportTemplate[] = [
  { id: "markdown", label: "Download brief (Markdown)", mime: "text/markdown", filename: (c) => `fieldshift-brief-${slug(c.field.farm.short_name)}.md`, build: buildMarkdownBrief },
  {
    id: "json", label: "Download data (JSON)", mime: "application/json", filename: (c) => `fieldshift-data-${slug(c.field.farm.short_name)}.json`,
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
