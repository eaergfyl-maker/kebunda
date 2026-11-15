/**
 * Small farmer-facing helpers for the timeline charts.
 *
 * OWNER: Member 2.
 * Takeaway: one plain sentence that says what a chart means for a decision.
 * LocalAdviceNote: a reminder that the tool supports, and never replaces, local expertise.
 */
import type { ReactNode } from "react";

export function Takeaway({ children }: { children: ReactNode }) {
  return <p className="takeaway" aria-live="polite">{children}</p>;
}

export function LocalAdviceNote() {
  return (
    <p className="local-advice">
      This is a guide to support your own judgement, not a replacement for it. Before you change what you plant,
      check with your local agriculture officer (DOA, MADA or MARDI).
    </p>
  );
}