import { useId, useState, type ReactNode } from "react";

import { GLOSSARY_BY_ID } from "./glossaryData";

/**
 * Wrap any technical word to make it explain itself on hover, focus or tap:
 *
 *   <Term id="ndvi">greenness</Term>
 *
 * Unknown ids render the children unchanged, so a typo never breaks a page.
 */
export function Term({ id, children }: { id: string; children?: ReactNode }) {
  const entry = GLOSSARY_BY_ID[id];
  const [open, setOpen] = useState(false);
  const popId = useId();
  if (!entry) return <>{children}</>;
  return (
    <span className="term" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button" className="term-trigger" aria-describedby={open ? popId : undefined} aria-expanded={open}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
      >
        {children ?? entry.term}
      </button>
      {open && (
        <span role="tooltip" id={popId} className="term-pop">
          <strong>{entry.term}</strong>
          {entry.plain}
          <em>Why it matters: {entry.why}</em>
        </span>
      )}
    </span>
  );
}
