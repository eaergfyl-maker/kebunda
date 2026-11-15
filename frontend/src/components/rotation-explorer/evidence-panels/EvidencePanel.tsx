import { ProvenanceBadge } from "@/components/common/ui";
import { useT } from "@/i18n/LanguageProvider";
import { DIM_COLOR, DIM_SHORT } from "@/styles/theme";

import type { PanelProps } from "./panelRegistry";

/** Pillar 2. Observed facts first (with their source and how they were obtained), then model results. */
export function EvidencePanel({ strategy }: PanelProps) {
  const { t } = useT();
  const observed = strategy.explanation.evidence.filter((e) => e.kind === "observed");
  const modelled = strategy.explanation.evidence.filter((e) => e.kind === "modelled");
  return (
    <div className="grid-2">
      <div>
        <div className="eyebrow" style={{ marginBottom: 8 }}>{t("Observed: satellites and soil survey")}</div>
        <ul className="evidence-list">
          {observed.map((e) => (
            <li key={e.id} className="evidence-item">
              <div className="row-wrap">
                <span className="chip" style={{ background: "transparent", border: `1px solid ${DIM_COLOR[e.dimension]}`, color: DIM_COLOR[e.dimension] }}>{t(DIM_SHORT[e.dimension])}</span>
                <ProvenanceBadge access={e.access} source={e.source} />
              </div>
              <strong>{e.statement}</strong>
              <p>{e.detail}</p>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <div className="eyebrow" style={{ marginBottom: 8 }}>{t("Modelled: this rotation on this field")}</div>
        <ul className="evidence-list">
          {modelled.map((e) => (
            <li key={e.id} className="evidence-item is-model">
              <div className="row-wrap">
                <span className="chip" style={{ background: "transparent", border: `1px solid ${DIM_COLOR[e.dimension]}`, color: DIM_COLOR[e.dimension] }}>{t(DIM_SHORT[e.dimension])}</span>
                <ProvenanceBadge access="model" compact />
              </div>
              <strong>{e.statement}</strong>
              <p>{e.detail}</p>
              <p className="xs faint">{t("Method:")} {e.dataset}</p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
