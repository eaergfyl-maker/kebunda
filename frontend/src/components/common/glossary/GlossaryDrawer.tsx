import { useEffect, useMemo, useState } from "react";

import { useT } from "@/i18n/LanguageProvider";
import { localizeEntry } from "@/i18n/glossary.ms";

import { GLOSSARY, GLOSSARY_TOPICS, type GlossaryTopic } from "./glossaryData";

/** Slide-over dictionary of every term in glossaryData.ts, searchable and grouped by topic. */
export function GlossaryDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t, lang } = useT();
  const [query, setQuery] = useState("");
  const [topic, setTopic] = useState<GlossaryTopic | "All">("All");

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const entries = useMemo(() => {
    const q = query.trim().toLowerCase();
    return GLOSSARY.map((g) => localizeEntry(g, lang)).filter((g) => (topic === "All" || g.topic === topic) &&
      (!q || `${g.term} ${g.also ?? ""} ${g.plain}`.toLowerCase().includes(q)));
  }, [query, topic, lang]);

  if (!open) return null;
  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={t("Plain-language glossary")}>
        <div className="drawer-head stack-sm">
          <div className="spread">
            <h2>{t("Plain-language glossary")}</h2>
            <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label={t("Close glossary")}>{t("Close")} ✕</button>
          </div>
          <p className="small muted">{t("Every technical word in Kebunda, explained the way a neighbour would, with why it matters for a rotation decision.")}</p>
          <input type="text" placeholder={t("Search, e.g. NDVI or evapotranspiration")} value={query} onChange={(e) => setQuery(e.target.value)} autoFocus />
          <div className="row-wrap">
            {(["All", ...GLOSSARY_TOPICS] as const).map((tp) => (
              <button key={tp} className={`btn btn-sm ${topic === tp ? "btn-primary" : ""}`} onClick={() => setTopic(tp)}>{t(tp)}</button>
            ))}
          </div>
        </div>
        <div className="drawer-body">
          {entries.length === 0 && <p className="muted small">{t("No term matches “{q}”.", { q: query })}</p>}
          {entries.map((g) => (
            <article key={g.id} className="glossary-entry">
              <h4>{g.term}{g.also && <span className="also">{g.also}</span>}</h4>
              <p>{g.plain}</p>
              <p className="why"><strong>{t("Why it matters:")}</strong> {g.why}</p>
            </article>
          ))}
        </div>
      </aside>
    </>
  );
}
