import "./styles/theme.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
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
import { PageDocuments } from "./pages/Documents";
import { PageMesures } from "./pages/Mesures";
import { PagePlanAction } from "./pages/PlanAction";
import { PageNouveauProjet } from "./pages/NouveauProjet";
import { PageTableauDeBord } from "./pages/TableauDeBord";

const client = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: true } } });

const routeur = createBrowserRouter([
  { path: "/connexion", element: <PageConnexion /> },
  {
    element: <Protege />,
    children: [
      { path: "/", element: <PageAccueil /> },
      { path: "/projets/nouveau", element: <PageNouveauProjet /> },
      { path: "/administration", element: <PageAdministration /> },
      { path: "/bibliotheque", element: <PageBibliotheque /> },
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
