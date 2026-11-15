import { useT } from "@/i18n/LanguageProvider";
import { DIM_COLOR } from "@/styles/theme";
import type { Reason } from "@/types/api";

import type { PanelProps } from "./panelRegistry";

const DRIVER: Record<Reason["driver"], { label: string; color: string }> = {
  priority: { label: "Your priority", color: "#1f3a2b" },
  "co-benefit": { label: "Bonus", color: "#4f8f4a" },
  climate: { label: "Climate record", color: "#c8553d" },
  soil: { label: "Your soil", color: "#8a5a3c" },
  pest: { label: "Pest pressure", color: "#9a5ba0" },
  market: { label: "Local market", color: "#c9952b" },
  reference: { label: "Reference", color: "#6b7570" },
  strength: { label: "Holds up", color: "#3f8a4d" },
  strain: { label: "Under strain", color: "#b8472f" },
};

/** Pillar 1. Each reason is tagged with what drove it, so the logic is inspectable. */
export function WhyPanel({ strategy }: PanelProps) {
  const { t } = useT();
  return (
    <ul className="why-list">
      {strategy.explanation.why.map((r, i) => {
        const d = DRIVER[r.driver] ?? DRIVER.reference;
        return (
          <li key={i} className="why-item" style={{ borderLeftColor: r.dimension ? DIM_COLOR[r.dimension] : d.color }}>
            <span className="why-driver" style={{ color: d.color }}>{t(d.label)}</span>
            <p>{r.text}</p>
          </li>
        );
      })}
      {strategy.issues.length > 0 && (
        <li className="why-item" style={{ borderLeftColor: "var(--warn)" }}>
          <span className="why-driver" style={{ color: "var(--warn)" }}>{t("Fit notes")}</span>
          <p>{strategy.issues.join(" ")}</p>
        </li>
      )}
    </ul>
  );
}
