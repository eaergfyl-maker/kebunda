import "./pages.css";

import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { GlossaryDrawer } from "@/components/common/glossary/GlossaryDrawer";
import { Segmented } from "@/components/common/ui";
import { useFieldShift, type UnitSystem } from "@/hooks/useFieldShift";

import { PAGES } from "./pageRegistry";

/** Header, navigation, units toggle, glossary and footer around every page. */
export function AppShell({ children }: { children: ReactNode }) {
  const { units, setUnits } = useFieldShift();
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  return (
    <div className="shell">
      <header className="shell-header no-print">
        <div className="container shell-header-inner">
          <NavLink to="/" className="brand" aria-label="FieldShift home">
            <img src="/assets/fieldshift-mark.svg" alt="" width={34} height={34} />
            <span>
              <strong>FieldShift</strong>
              <em>Rotations that fit your field</em>
            </span>
          </NavLink>
          <nav className="shell-nav" aria-label="Main">
            {PAGES.filter((p) => p.nav).map((p) => (
              <NavLink key={p.path} to={p.path} end className={({ isActive }) => `shell-link ${isActive ? "is-active" : ""}`}>{p.nav}</NavLink>
            ))}
          </nav>
          <div className="row">
            <Segmented<UnitSystem> label="Units" value={units} onChange={setUnits} options={[{ id: "metric", label: "mm · °C · ha" }, { id: "us", label: "in · °F · ac" }]} />
            <button className="btn" onClick={() => setGlossaryOpen(true)}>Glossary</button>
          </div>
        </div>
      </header>
      <main>{children}</main>
      <footer className="shell-footer">
        <div className="container stack-sm">
          <p>
            <strong>FieldShift supports, and never replaces, farmer judgment and local agronomic expertise.</strong>{" "}
            Take anything here to your district Department of Agriculture (DOA) officer, MARDI or your farmers' association before acting on it.
          </p>
          <p className="xs">
            Built for the 2026 NASA Space Apps Challenge, “Field Shift: Adapting Farms with NASA Data”. Earth observations from NASA POWER, GPM IMERG,
            SMAP, GRACE-FO, SRTM, MODIS and GIBS; Copernicus Sentinel-2 crop greenness; ISRIC SoilGrids soil; FAO GAEZ crop suitability; MetMalaysia rain gauges via NOAA GHCN; prices from FAMA and DOA.
            NASA does not endorse this tool.
          </p>
        </div>
      </footer>
      <GlossaryDrawer open={glossaryOpen} onClose={() => setGlossaryOpen(false)} />
    </div>
  );
}
