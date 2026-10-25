import "./styles/theme.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router";

import { PageAccueil, PageAVenir, Protege } from "./pages/Autres";
import { PageConnexion } from "./pages/Connexion";
import { PageDocuments } from "./pages/Documents";
import { PageMesures } from "./pages/Mesures";
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
      { path: "/projets/:projetId", element: <PageTableauDeBord /> },
      { path: "/projets/:projetId/documents", element: <PageDocuments /> },
      { path: "/projets/:projetId/mesures", element: <PageMesures /> },
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
