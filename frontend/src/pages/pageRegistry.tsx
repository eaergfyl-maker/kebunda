/**
 * Every page in the app. Routing and the top navigation are generated from this list.
 *
 * OWNER: Member 3.
 *
 * To add a page: create pages/MyPage.tsx and add one entry here. Set `nav` to show it in
 * the header. Use `:id` in the path for a field-specific page and read it with useParams().
 *
 * TODO (Member 3): a "Compare two fields" page, a "Crop library" page built on
 *   GET /soil-crops/catalog and /soil-crops/suitability/{id}, and an onboarding walkthrough.
 */
import type { ReactElement } from "react";

import { BriefPage } from "./BriefPage";
import { ExplorePage } from "./ExplorePage";
import { FieldPage } from "./FieldPage";
import { MethodsPage } from "./MethodsPage";

export interface PageDef {
  path: string;
  /** Header label. Omit to keep the page out of the navigation. */
  nav?: string;
  element: ReactElement;
}

export const PAGES: PageDef[] = [
  { path: "/", nav: "Explore fields", element: <ExplorePage /> },
  { path: "/field/:id", element: <FieldPage /> },
  { path: "/field/:id/brief", element: <BriefPage /> },
  { path: "/methods", nav: "Data and methods", element: <MethodsPage /> },
];
