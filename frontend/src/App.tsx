import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { KebundaProvider } from "@/hooks/useKebunda";
import { LanguageProvider, useT } from "@/i18n/LanguageProvider";
import { AppShell } from "@/pages/AppShell";
import { PAGES } from "@/pages/pageRegistry";

function NotFound() {
  const { t } = useT();
  return (
    <div className="container" style={{ padding: "64px 24px" }}>
      <h1>{t("Nothing grows here")}</h1>
      <p className="muted" style={{ margin: "8px 0 16px" }}>{t("That page does not exist.")}</p>
      <Link className="btn btn-primary" to="/">{t("Back to the fields")}</Link>
    </div>
  );
}

/** Routes come from pages/pageRegistry.tsx. Add pages there, not here. */
export default function App() {
  return (
    <LanguageProvider>
    <KebundaProvider>
      <BrowserRouter>
        <AppShell>
          <Routes>
            {PAGES.map((p) => <Route key={p.path} path={p.path} element={p.element} />)}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </KebundaProvider>
    </LanguageProvider>
  );
}
