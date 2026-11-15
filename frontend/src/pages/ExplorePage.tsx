/**
 * Landing page: the map, the five benchmark farms, and "click anywhere" for a live field.
 *
 * OWNER: Member 3 (layout). The map itself belongs to Member 2 (components/map).
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ErrorNotice, Loading, SupportNotJudgment } from "@/components/common/ui";
import { FieldMap } from "@/components/map/FieldMap";
import { primeCache } from "@/hooks/useAsync";
import { useFarms, useSources } from "@/hooks/useData";
import { useUnits } from "@/hooks/useUnits";
import { useT } from "@/i18n/LanguageProvider";
import { api, ApiError } from "@/services/apiClient";
import type { FarmSummary } from "@/types/api";

const STEPS = [
  { n: 1, title: "Read the field", text: "24 years of NASA weather and satellite records, SoilGrids soil, FAO GAEZ suitability and five years of Sentinel-2 crop cycles are fused for the field, with every source's pixel size and reliability shown." },
  { n: 2, title: "Say what matters", text: "Set five priorities in plain words, and what the farm can and cannot do: water, equipment, livestock, markets, appetite for change." },
  { n: 3, title: "Compare rotations", text: "Hundreds of rotations are simulated month by month. At least three, always including the current one, are explained: why, evidence, benefits, gaps, and what to check locally." },
  { n: 4, title: "Stress-test them", text: "Turn up the heat, cut the rain or the water allocation, and see which rotation still holds." },
];

function FarmCard({ farm, onOpen }: { farm: FarmSummary; onOpen: () => void }) {
  const units = useUnits();
  const { t, tName } = useT();
  return (
    <button className="farm-card" onClick={onOpen}>
      <span className="eyebrow">{farm.region}</span>
      <h3>{farm.short_name}</h3>
      <p className="farm-card-headline">{farm.headline}</p>
      <dl className="farm-card-facts">
        <div><dt>{t("Grows now")}</dt><dd>{tName(farm.baseline_name)}</dd></div>
        <div><dt>{t("Water")}</dt><dd>{t(farm.irrigation)}</dd></div>
        <div><dt>{t("Soil")}</dt><dd>{farm.soil_series} {farm.soil_texture}, {t("{n}% organic matter", { n: farm.organic_matter_pct ?? "–" })}</dd></div>
        <div><dt>{t("Climate")}</dt><dd>{t("{rain} a year · {temp} average", { rain: units.water(farm.annual_precip_mm, 0), temp: units.temp(farm.mean_annual_temp_c) })}</dd></div>
      </dl>
      <div className="row-wrap">{farm.challenge_tags.slice(0, 3).map((t) => <span key={t} className="chip">{t}</span>)}</div>
      <span className="farm-card-cta">{t("Explore this field →")}</span>
    </button>
  );
}

export function ExplorePage() {
  const navigate = useNavigate();
  const { t } = useT();
  const { data: farms, loading, error } = useFarms();
  const { data: sources } = useSources();
  const [analyzing, setAnalyzing] = useState(false);
  const [customError, setCustomError] = useState<ApiError | null>(null);

  const analyzePoint = async (lat: number, lon: number) => {
    setAnalyzing(true);
    setCustomError(null);
    try {
      const overview = await api.createCustomField({ lat, lon });
      primeCache(`field:${overview.id}`, overview);
      navigate(`/field/${overview.id}`);
    } catch (e) {
      setCustomError(e instanceof ApiError ? e : new ApiError(0, "unexpected", "The field could not be built."));
    } finally {
      setAnalyzing(false);
    }
  };

  const live = sources ? sources.status_counts.live ?? 0 : null;
  return (
    <div className="explore">
      <section className="hero">
        <div className="container hero-inner">
          <div className="hero-copy">
            <span className="eyebrow hero-eyebrow">{t("NASA Earth observations · Sentinel-2 · SoilGrids · your priorities")}</span>
            <h1>{t("What should this field grow next, and the year after that?")}</h1>
            <p>{t("Kebunda reads a field's weather, soil and satellite record, then compares crop rotations side by side: what each would do for your water, your soil and your income, how sure anyone can be, and what to check with the people who know your ground.")}</p>
            <div className="row-wrap">
              <a className="btn btn-primary" href="#farms">{t("Start with a real field")}</a>
              <a className="btn" href="#map">{t("Or click anywhere on the map")}</a>
            </div>
          </div>
          <ol className="hero-steps">
            {STEPS.map((s) => (
              <li key={s.n}><span>{s.n}</span><div><strong>{t(s.title)}</strong><p>{t(s.text)}</p></div></li>
            ))}
          </ol>
        </div>
      </section>

      <div className="container stack" style={{ gap: 32, paddingTop: 32, paddingBottom: 48 }}>
        <section id="farms" className="stack">
          <div>
            <h2>{t("Five real fields, five different problems")}</h2>
            <p className="muted" style={{ maxWidth: "75ch" }}>
              {t("Each benchmark is an actual Malaysian coordinate with data pulled from NASA and global services: the SoilGrids estimate under it, the crops satellites saw on it, and its weather since 2001. They load instantly and work offline.")}
            </p>
          </div>
          {error && <ErrorNotice error={error} title="The farm list could not be loaded" />}
          {loading && <Loading height={220} label="Loading farms" />}
          {farms && <div className="farm-grid">{farms.map((f) => <FarmCard key={f.id} farm={f} onOpen={() => navigate(`/field/${f.id}`)} />)}</div>}
        </section>

        <section id="map" className="stack">
          <div>
            <h2>{t("Or pick any field")}</h2>
            <p className="muted" style={{ maxWidth: "75ch" }}>
              {t("Click the map to query NASA POWER live for that spot, then build a full field from it. Switch on a NASA layer to see greenness, soil moisture, rainfall or surface temperature for any month of the last four years.")}
            </p>
          </div>
          {customError && <ErrorNotice error={customError} title="That field could not be built" />}
          {farms ? <FieldMap farms={farms} onSelect={(id) => navigate(`/field/${id}`)} onAnalyzePoint={analyzePoint} analyzing={analyzing} height={560} defaultLayerId={null} /> : <Loading height={560} label="Loading map" />}
          <p className="xs faint">
            {t("Map layers are served live by NASA GIBS (the service behind NASA Worldview).")}
            {live !== null && <> {t("{live} of the {total} datasets on the challenge list are pulled live without any API key; the rest are curated, used as map layers, or named as gaps.", { live, total: sources!.sources.length })} <a href="/methods">{t("Data and methods")}</a>.</>}
          </p>
        </section>

        <SupportNotJudgment />
      </div>
    </div>
  );
}
