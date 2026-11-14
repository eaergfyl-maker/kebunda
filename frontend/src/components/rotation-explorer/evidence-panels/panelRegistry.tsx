/**
 * The five explanations every strategy must give, as tabs.
 *
 * OWNER: Member 3.
 *
 * The first five entries are the challenge's required dimensions and should stay, in this
 * order. To add a sixth view (say, a market-price sensitivity chart or a carbon-credit
 * estimate), write a component that takes PanelProps and add one entry to PANELS.
 *
 * TODO (Member 3), good additions:
 *   - Crop market price sensitivity chart: strategy.economics has revenue and cost per crop;
 *     add sliders for price shocks and redraw net return per strategy.
 *   - Photo or note attachments on each risk item for the Extension visit.
 *   - "Explain it to me simply" toggle that swaps each panel for its two-sentence summary
 *     (strategy.explanation.benefits.summary is already one).
 */
import type { ComponentType } from "react";

import type { CompareResponse, FieldOverview, Strategy } from "@/types/api";

import { BenefitsPanel } from "./BenefitsPanel";
import { EvidencePanel } from "./EvidencePanel";
import { GapsPanel } from "./GapsPanel";
import { NumbersPanel } from "./NumbersPanel";
import { RisksPanel } from "./RisksPanel";
import { WhyPanel } from "./WhyPanel";

export interface PanelProps {
  strategy: Strategy;
  baseline: Strategy;
  comparison: CompareResponse;
  field: FieldOverview;
}

export interface PanelDef {
  id: string;
  /** 1-5 for the challenge's required dimensions; undefined for extras. */
  number?: number;
  label: string;
  question: string;
  count?: (s: Strategy) => number | undefined;
  Component: ComponentType<PanelProps>;
}

export const PANELS: PanelDef[] = [
  { id: "why", number: 1, label: "Why suggested", question: "Why is this option on the table for this field?", Component: WhyPanel },
  { id: "evidence", number: 2, label: "Evidence", question: "What do satellites, the soil survey and the models actually show?",
    count: (s) => s.explanation.evidence.length, Component: EvidencePanel },
  { id: "benefits", number: 3, label: "Benefits and costs", question: "What changes against what you do now, and by how much?",
    count: (s) => (s.role === "baseline" ? undefined : s.explanation.benefits.improves), Component: BenefitsPanel },
  { id: "gaps", number: 4, label: "What we cannot see", question: "Where is the data thin, and what can no satellite tell you?",
    count: (s) => s.explanation.gaps.items.length, Component: GapsPanel },
  { id: "risks", number: 5, label: "Check locally", question: "What should you, Extension or your crop adviser verify before acting?",
    count: (s) => s.explanation.risks.length, Component: RisksPanel },
  { id: "numbers", label: "The numbers", question: "Yields, costs and returns behind the scores.", Component: NumbersPanel },
];
