/**
 * Small shared building blocks. Anything used by more than one area belongs here.
 * Keep them dumb: props in, markup out, no data fetching.
 */
import type { CSSProperties, ReactNode } from "react";

import type { ApiError } from "@/services/apiClient";
import { ACCESS_LABEL, scoreTone } from "@/styles/theme";
import type { Access } from "@/types/api";

import "./common.css";

export function Card({ title, subtitle, action, children, className = "", id }: {
  title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; id?: string;
}) {
  return (
    <section className={`card ${className}`} id={id}>
      {(title || action) && (
        <header className="card-head">
          <div>
            {title && <h3>{title}</h3>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {action && <div className="no-print">{action}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function Loading({ label = "Loading", height = 120 }: { label?: string; height?: number }) {
  return (
    <div className="skeleton" style={{ height }} role="status" aria-live="polite">
      <span className="sr-only">{label}…</span>
    </div>
  );
}

export function ErrorNotice({ error, title = "This could not be loaded" }: { error: ApiError; title?: string }) {
  return (
    <div className="notice notice-bad" role="alert">
      <strong>{title}.</strong> {error.message}
      {error.hint && <div className="small" style={{ marginTop: 4 }}>{error.hint}</div>}
    </div>
  );
}

/** Where a number came from: live from the provider, curated, a stand-in product, or missing. */
export function ProvenanceBadge({ access, source, compact = false }: { access: Access | null | undefined; source?: string | null; compact?: boolean }) {
  const meta = ACCESS_LABEL[access ?? "unavailable"];
  return (
    <span className={`chip chip-${meta.tone}`} title={`${source ? source + ". " : ""}${meta.help}`}>
      <span className="dot" style={{ background: "currentColor", opacity: 0.7 }} />
      {compact ? meta.label : source ? `${source} · ${meta.label}` : meta.label}
    </span>
  );
}

export function Stat({ label, value, sub, tone }: { label: ReactNode; value: ReactNode; sub?: ReactNode; tone?: "good" | "warn" | "bad" }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value num ${tone ? `tone-${tone}` : ""}`}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

/**
 * Change against the baseline. Colour says whether the change is good for the farm;
 * the arrow says which way the number moved (`rising`), so "erosion down" reads green with a down arrow.
 */
export function Delta({ direction, rising, children }: { direction: "better" | "worse" | "same"; rising?: boolean; children: ReactNode }) {
  const arrow = direction === "same" || rising === undefined ? "•" : rising ? "▲" : "▼";
  return <span className={`delta delta-${direction} num`}><span aria-hidden>{arrow}</span> {children}</span>;
}

/** 0-100 bar with an optional marker for the baseline and a ± uncertainty whisker. */
export function ScoreBar({ value, color, baseline, uncertainty, label, height = 8 }: {
  value: number; color?: string; baseline?: number; uncertainty?: number; label?: string; height?: number;
}) {
  const tone = scoreTone(value);
  const fill = color ?? (tone === "good" ? "var(--good)" : tone === "warn" ? "var(--warn)" : "var(--bad)");
  const lo = Math.max(0, value - (uncertainty ?? 0));
  const hi = Math.min(100, value + (uncertainty ?? 0));
  return (
    <div className="scorebar" style={{ height }} role="img" aria-label={`${label ?? "Score"} ${Math.round(value)} out of 100`}>
      <div className="scorebar-fill" style={{ width: `${value}%`, background: fill }} />
      {uncertainty ? <div className="scorebar-whisker" style={{ left: `${lo}%`, width: `${hi - lo}%` }} /> : null}
      {baseline !== undefined && <div className="scorebar-mark" style={{ left: `${baseline}%` }} title={`Current rotation: ${Math.round(baseline)}`} />}
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange, label }: {
  tabs: { id: T; label: ReactNode; badge?: ReactNode }[]; value: T; onChange: (id: T) => void; label: string;
}) {
  return (
    <div className="tabs no-print" role="tablist" aria-label={label}>
      {tabs.map((t) => (
        <button key={t.id} role="tab" className="tab" aria-selected={t.id === value} onClick={() => onChange(t.id)}>
          {t.label}
          {t.badge !== undefined && <span className="tab-badge">{t.badge}</span>}
        </button>
      ))}
    </div>
  );
}

export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: { id: T; label: ReactNode }[]; value: T; onChange: (id: T) => void; label: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.id} aria-pressed={o.id === value} onClick={() => onChange(o.id)}>{o.label}</button>
      ))}
    </div>
  );
}

/** The framing the challenge asks for, shown wherever a recommendation appears. */
export function SupportNotJudgment({ text }: { text?: string }) {
  return (
    <aside className="support-note">
      <span aria-hidden className="support-icon">🤝</span>
      <p>
        <strong>A second opinion, not a prescription.</strong>{" "}
        {text ?? "FieldShift surfaces patterns and possibilities from public data. It supports, and never replaces, your judgment and the advice of local agronomists, Extension agents and crop advisers."}
      </p>
    </aside>
  );
}

export function Meter({ value, max = 1, color = "var(--forest)", width = 64 }: { value: number; max?: number; color?: string; width?: number }) {
  const pct = Math.max(0, Math.min(1, value / max)) * 100;
  const style: CSSProperties = { width };
  return (
    <span className="meter" style={style} aria-hidden>
      <span style={{ width: `${pct}%`, background: color }} />
    </span>
  );
}
