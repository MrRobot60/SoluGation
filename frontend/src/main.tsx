// Police embarquée (aucun appel à un service tiers, aucune adresse IP transmise).
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-700.css";
import "./styles/theme.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router";

import { PageAccueil, PageAVenir, Protege } from "./pages/Autres";
import { PageAdministration } from "./pages/Administration";
import { PageBibliotheque } from "./pages/Bibliotheque";
import { PageEbios } from "./pages/Ebios";
import { PageJournal } from "./pages/Journal";
import { PageRapports } from "./pages/Rapports";
import { PageReglages } from "./pages/Reglages";
import { PageReunions } from "./pages/Reunions";
import { PageRisques } from "./pages/Risques";
import { PageScans } from "./pages/Scans";
import { PageConnexion } from "./pages/Connexion";
import { PageDefinirMotDePasse, PageMotDePasseOublie } from "./pages/MotDePasse";
import { PageDocuments } from "./pages/Documents";
import { PageMesures } from "./pages/Mesures";
import { PagePlanAction } from "./pages/PlanAction";
import { PageNouveauProjet } from "./pages/NouveauProjet";
import { PageTableauDeBord } from "./pages/TableauDeBord";

// La documentation (et son moteur de rendu) ne se charge qu'à l'ouverture de l'Aide.
const PageAide = lazy(() => import("./pages/Aide").then((m) => ({ default: m.PageAide })));
const aide = <Suspense fallback={<div aria-busy="true" className="min-h-dvh" />}><PageAide /></Suspense>;

const client = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: true } } });

const routeur = createBrowserRouter([
  { path: "/connexion", element: <PageConnexion /> },
  { path: "/mot-de-passe-oublie", element: <PageMotDePasseOublie /> },
  { path: "/mot-de-passe/nouveau", element: <PageDefinirMotDePasse nature="reinitialisation" /> },
  { path: "/invitation", element: <PageDefinirMotDePasse nature="invitation" /> },
  {
    element: <Protege />,
    children: [
      { path: "/", element: <PageAccueil /> },
      { path: "/projets/nouveau", element: <PageNouveauProjet /> },
      { path: "/administration", element: <PageAdministration /> },
      { path: "/bibliotheque", element: <PageBibliotheque /> },
      { path: "/aide", element: aide },
      { path: "/aide/:page", element: aide },
      { path: "/projets/:projetId", element: <PageTableauDeBord /> },
      { path: "/projets/:projetId/documents", element: <PageDocuments /> },
      { path: "/projets/:projetId/mesures", element: <PageMesures /> },
      { path: "/projets/:projetId/plan-action", element: <PagePlanAction /> },
      { path: "/projets/:projetId/rapports", element: <PageRapports /> },
      { path: "/projets/:projetId/ebios", element: <PageEbios /> },
      { path: "/projets/:projetId/risques", element: <PageRisques /> },
      { path: "/projets/:projetId/reglages", element: <PageReglages /> },
      { path: "/projets/:projetId/scans", element: <PageScans /> },
      { path: "/projets/:projetId/reunions", element: <PageReunions /> },
      { path: "/projets/:projetId/journal", element: <PageJournal /> },
      { path: "/journal", element: <PageJournal /> },
      { path: "/projets/:projetId/:rubrique", element: <PageAVenir /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

createRoot(document.getElementById("racine")!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <RouterProvider router={routeur} />
    </QueryClientProvider>
  </StrictMode>,
);
