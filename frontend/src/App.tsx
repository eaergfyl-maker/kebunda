import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { FieldShiftProvider } from "@/hooks/useFieldShift";
import { AppShell } from "@/pages/AppShell";
import { PAGES } from "@/pages/pageRegistry";

function NotFound() {
  return (
    <div className="container" style={{ padding: "64px 24px" }}>
      <h1>Nothing grows here</h1>
      <p className="muted" style={{ margin: "8px 0 16px" }}>That page does not exist.</p>
      <Link className="btn btn-primary" to="/">Back to the fields</Link>
    </div>
  );
}

/** Routes come from pages/pageRegistry.tsx. Add pages there, not here. */
export default function App() {
  return (
    <FieldShiftProvider>
      <BrowserRouter>
        <AppShell>
          <Routes>
            {PAGES.map((p) => <Route key={p.path} path={p.path} element={p.element} />)}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </FieldShiftProvider>
  );
}
