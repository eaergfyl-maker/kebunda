/**
 * Data and methods: every dataset on the challenge list and how it is used, and how the
 * models work in plain language. Full formulas live in docs/agronomy-models/.
 *
 * OWNER: Member 3.
 */
import { Term } from "@/components/common/glossary/Term";
import { Card, ErrorNotice, Loading, SupportNotJudgment } from "@/components/common/ui";
import { useSources } from "@/hooks/useData";
import { useT } from "@/i18n/LanguageProvider";
import type { DataSource } from "@/types/api";

const STATUS: Record<DataSource["status"], { label: string; cls: string; help: string }> = {
  live: { label: "Live, no key", cls: "chip-good", help: "Pulled from the provider for the field." },
  key: { label: "Live with a free key", cls: "chip-info", help: "Live when an optional key is set; curated fallback otherwise." },
  curated: { label: "Curated", cls: "chip-info", help: "Assembled from published sources and shipped with the app." },
  proxy: { label: "Stand-in product", cls: "chip-warn", help: "A related NASA product stands in; said so wherever it is shown." },
  map: { label: "Map layer", cls: "", help: "Shown on the map through NASA GIBS." },
  planned: { label: "Named gap", cls: "", help: "Not ingested yet; listed as an information gap." },
};

type ModelDef = { title: string; text: (t: (s: string) => string) => JSX.Element };
const MODELS: ModelDef[] = [
  { title: "Crop calendar", text: (t) => <>{t("Planting and harvest months come from this field's own temperatures using")} <Term id="gdd">{t("growing degree days")}</Term>{t(", not a regional table. A warmer scenario moves the dates.")}</> },
  { title: "Soil cover", text: (t) => <>{t("Each month's cover is living canopy plus decaying residue. Tillage buries residue; cover crops add it. Under 30% cover counts as bare.")}</> },
  { title: "Water", text: (t) => <>{t("A monthly soil-water budget: rain, minus runoff (from storm size, soil group and cover), minus evaporation and crop use, with irrigation up to the allocation.")} <Term id="water_stress">{t("Water stress")}</Term> {t("cuts yield by each crop's known sensitivity.")}</> },
  { title: "Erosion", text: (t) => <>{t("The standard")} <Term id="rusle">RUSLE</Term> {t("equation, with the cover factor computed month by month so that bare soil in a stormy month costs more than bare soil in a dry one.")}</> },
  { title: "Soil carbon and nitrogen", text: (t) => <>{t("Residue and roots add carbon; warmth and tillage burn it off. Legumes and legume covers credit nitrogen to the next crop; leftover nitrate leaches with drainage.")}</> },
  { title: "Pests and disease", text: (t) => <>{t("Scored from the years between host crops, the mix of")} <Term id="functional_group">{t("crop types")}</Term>{t(", and the spread of planting seasons.")}</> },
  { title: "Income and its swings", text: (t) => <>{t("Yields from local reference yields adjusted for water, heat and crop sequence. Every year's real weather since 2001 is replayed through each rotation to find its")} <Term id="bad_year">{t("bad-year")}</Term> {t("income.")}</> },
  { title: "Fusion and confidence", text: (t) => <>{t("Three rainfall sources are blended by how well each matched the gauges here. Coarse soil wetness is rescaled with the field's own soil texture. Every layer is scored for how well a pixel that size can represent one field.")}</> },
];

export function MethodsPage() {
  const { data, loading, error } = useSources();
  const { t } = useT();
  const groups = data ? [...new Set(data.sources.map((s) => s.group))] : [];
  return (
    <div className="container stack" style={{ gap: 28, padding: "32px 24px 56px" }}>
      <header className="stack-sm">
        <span className="eyebrow">{t("Data and methods")}</span>
        <h1>{t("What goes in, and how the answers are made")}</h1>
        <p className="muted" style={{ maxWidth: "78ch" }}>
          {t("Kebunda is deliberately a set of simple, inspectable models rather than a black box. Each sentence in an explanation is built from a number the models produced for that field, and each number carries where it came from.")}
        </p>
      </header>

      <Card title={t("How the models work")} subtitle={t("Eight small models, one month at a time. They rank rotations against each other on one field; they do not predict a yield.")}>
        <div className="model-grid">
          {MODELS.map((m, i) => (
            <div key={m.title} className="model-cell"><span className="pillar-num">{i + 1}</span><div><strong>{t(m.title)}</strong><p className="small muted">{m.text(t)}</p></div></div>
          ))}
        </div>
      </Card>

      <Card title={t("Every dataset on the challenge list")} subtitle={t("What is pulled live, what is curated, what stands in for something else, and what is still a gap.")}>
        {error && <ErrorNotice error={error} />}
        {loading && <Loading height={300} />}
        {data && (
          <>
            <div className="row-wrap" style={{ marginBottom: 12 }}>
              {(Object.keys(STATUS) as DataSource["status"][]).filter((s) => data.status_counts[s]).map((s) => (
                <span key={s} className={`chip ${STATUS[s].cls}`} title={t(STATUS[s].help)}>{data.status_counts[s]} · {t(STATUS[s].label)}</span>
              ))}
            </div>
            <div className="table-scroll">
              <table className="table">
                <thead><tr><th>{t("Dataset")}</th><th>{t("From")}</th><th>{t("Status")}</th><th>{t("How Kebunda uses it")}</th></tr></thead>
                <tbody>
                  {groups.map((g) => [
                    <tr key={g} className="group-row"><td colSpan={4}>{g}</td></tr>,
                    ...data.sources.filter((s) => s.group === g).map((s) => (
                      <tr key={s.id}>
                        <td><a href={s.url} target="_blank" rel="noreferrer"><strong>{s.name}</strong></a></td>
                        <td className="small">{s.agency}</td>
                        <td><span className={`chip ${STATUS[s.status].cls}`} title={t(STATUS[s.status].help)}>{t(STATUS[s.status].label)}</span></td>
                        <td className="small">{s.use}</td>
                      </tr>
                    )),
                  ])}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      <Card title={t("What this tool cannot do")}>
        <ul className="brief-list">
          <li>{t("It cannot see below the surface: compaction, drainage, nematodes, soil life and disease carry-over are invisible from orbit.")}</li>
          <li>{t("It does not know your varieties, your contracts, your lease, your labour or your lender.")}</li>
          <li>{t("Its weather inputs are pixels 10 to 55 km wide and its soil is a 250 m estimate; your field varies inside both.")}</li>
          <li>{t("Its yields and ringgit figures rank options. They are not a budget and not a forecast.")}</li>
          <li>{t("Scenario dials shift past weather. They are stress tests, not climate projections.")}</li>
        </ul>
        <div style={{ marginTop: 14 }}><SupportNotJudgment /></div>
      </Card>
    </div>
  );
}
