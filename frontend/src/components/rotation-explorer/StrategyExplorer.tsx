/**
 * The rotation explorer: at least three strategies side by side (always including the
 * current rotation), then the selected one explained in five parts.
 *
 * OWNER: Member 3. This file is wiring: cards live in cards/, the five explanations in
 * evidence-panels/ (registered in panelRegistry.tsx), the builder in sequence-builder/.
 */
import "./rotation.css";

import { useEffect, useState } from "react";

import { Term } from "@/components/common/glossary/Term";
import { Card, Segmented, SupportNotJudgment, Tabs } from "@/components/common/ui";
import { useT } from "@/i18n/LanguageProvider";
import { ROLE_COLOR } from "@/styles/theme";
import type { CompareResponse, FieldOverview } from "@/types/api";

import { CompareMatrix } from "./cards/CompareMatrix";
import { StrategyCard } from "./cards/StrategyCard";
import { PANELS } from "./evidence-panels/panelRegistry";
import { SequenceBuilder } from "./sequence-builder/SequenceBuilder";

export function StrategyExplorer({ field, comparison, refreshing }: { field: FieldOverview; comparison: CompareResponse; refreshing: boolean }) {
  const { t, tName } = useT();
  const strategies = comparison.strategies;
  const baseline = strategies[0];
  const [selectedId, setSelectedId] = useState<string>(comparison.summary.top_id);
  const [panel, setPanel] = useState(PANELS[0].id);
  const [view, setView] = useState<"cards" | "table">("cards");
  const [builderOpen, setBuilderOpen] = useState(false);

  // keep a valid selection when the strategy set changes (new priorities, constraints or field)
  useEffect(() => {
    if (!strategies.some((s) => s.id === selectedId)) setSelectedId(comparison.summary.top_id);
  }, [strategies, selectedId, comparison.summary.top_id]);

  const selected = strategies.find((s) => s.id === selectedId) ?? baseline;
  const def = PANELS.find((p) => p.id === panel) ?? PANELS[0];
  const tied = new Set(comparison.summary.tied_ids);

  return (
    <div className="stack" id="rotations">
      <Card
        title={t("Rotation strategies, side by side")}
        subtitle={<>{comparison.summary.statement} {t("Scores are 0-100; the black tick on each bar is your current rotation and the whisker is the")} <Term id="confidence">{t("uncertainty")}</Term>.</>}
        action={<Segmented label={t("View")} value={view} onChange={setView} options={[{ id: "cards", label: t("Cards") }, { id: "table", label: t("Table") }]} />}
      >
        {(comparison.baseline_assumed || comparison.baseline_note) && (
          <p className={`notice ${comparison.baseline_assumed ? "notice-warn" : "notice-info"}`} style={{ marginBottom: 12 }}>
            <strong>{t("About the")} <Term id="baseline">{t("current rotation")}</Term>:</strong> {comparison.baseline_note}{" "}
            <button className="btn btn-sm" onClick={() => setBuilderOpen(true)}>{t("Correct it")}</button>
          </p>
        )}
        <div className={refreshing ? "refreshing" : ""}>
          {view === "cards" ? (
            <div className="strategy-grid">
              {strategies.map((s) => (
                <StrategyCard key={s.id} strategy={s} baseline={baseline} selected={s.id === selected.id}
                  isTop={s.id === comparison.summary.top_id} tied={tied.has(s.id) || (s.id === comparison.summary.top_id && tied.size > 0)}
                  onSelect={() => setSelectedId(s.id)} />
              ))}
            </div>
          ) : (
            <CompareMatrix strategies={strategies} selectedId={selected.id} onSelect={setSelectedId} />
          )}
        </div>
        <p className="xs faint" style={{ marginTop: 10 }}>
          {t("Searched {a} crop sequences from {b} crops that fit this field, simulated {c} variants, and kept options that differ meaningfully from one another.", { a: comparison.search.rotations_screened, b: comparison.search.crops_considered.length, c: comparison.search.rotations_simulated })}
        </p>
      </Card>

      <Card
        title={<><span className="dot" style={{ background: ROLE_COLOR[selected.role], marginRight: 8, width: 12, height: 12 }} />{selected.role === "baseline" ? t("Your current rotation") : t(selected.title)}: {tName(selected.name)}</>}
        subtitle={t(def.question)}
      >
        <Tabs label={t("Explanation")} value={def.id} onChange={setPanel}
          tabs={PANELS.map((p) => ({ id: p.id, label: p.number ? <><span className="pillar-num">{p.number}</span>{t(p.label)}</> : t(p.label), badge: p.count?.(selected) }))} />
        <div className={`panel-body fade-in ${refreshing ? "refreshing" : ""}`} key={`${selected.id}:${def.id}`}>
          <def.Component strategy={selected} baseline={baseline} comparison={comparison} field={field} />
        </div>
        <div style={{ marginTop: 16 }}><SupportNotJudgment /></div>
      </Card>

      <Card
        title={t("Build your own rotation")}
        subtitle={t("Have something else in mind, or is the current rotation shown wrong? Put it together and score it with the same models.")}
        action={<button className="btn btn-sm" onClick={() => setBuilderOpen((o) => !o)}>{builderOpen ? t("Hide builder") : t("Open builder")}</button>}
      >
        {builderOpen ? <SequenceBuilder fieldId={field.id} baselineYears={baseline.years} baselineTillage={baseline.tillage} />
          : <p className="small muted">{t("Add years, pick crops and cover crops, choose a tillage system. Your rotation appears as an extra card above.")}</p>}
      </Card>
    </div>
  );
}
