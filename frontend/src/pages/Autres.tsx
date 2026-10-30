import { Link, Navigate, Outlet, useLocation, useParams } from "react-router";

import { ErreurApi } from "../api/client";
import { useMoi, useProjets } from "../api/hooks";
import { Disposition } from "../composants/Disposition";
import { VisiteGuidee } from "../composants/VisiteGuidee";

/** Routes protégées : sans session valide, retour à la connexion. */
export function Protege() {
  const { data, error, isPending } = useMoi();
  const location = useLocation();
  if (isPending) return <div aria-busy="true" className="min-h-dvh" />;
  if (error instanceof ErreurApi && [401, 403].includes(error.statut)) {
    return <Navigate to="/connexion" replace state={{ depuis: location.pathname }} />;
  }
  if (!data) return <p className="p-8 text-sm text-texte-2">Le serveur est injoignable.</p>;
  // Double authentification imposée et pas encore configurée : le serveur refuse tout le reste, on va à Mon compte.
  if (data.double_auth.requise && !data.double_auth.active && location.pathname !== "/compte") return <Navigate to="/compte" replace />;
  return (
    <>
      <Outlet />
      <VisiteGuidee />
    </>
  );
}

/** « / » : ouvre le premier projet accessible. */
export function PageAccueil() {
  const { data, isPending } = useProjets();
  if (isPending) return <div aria-busy="true" className="min-h-dvh" />;
  const premier = data?.results[0];
  if (premier) return <Navigate to={`/projets/${premier.id}`} replace />;
  return (
    <main className="flex min-h-dvh items-center justify-center px-4">
      <div className="verre max-w-md rounded-verre p-8 text-center">
        <h1 className="text-xl font-bold">Aucun projet pour le moment</h1>
        <p className="mt-2 text-sm text-texte-2">Vous n'êtes acteur d'aucun projet d'homologation.</p>
        <Link to="/projets/nouveau" className="bouton-accent mt-6 inline-flex h-[50px] items-center rounded-full px-6 text-[15px] font-semibold">
          Créer un projet
        </Link>
      </div>
    </main>
  );
}

const TITRES: Record<string, string> = {
  mesures: "Mesures",
  documents: "Documents",
  "plan-action": "Plan d'action",
  risques: "Risques et dérogations",
  ebios: "EBIOS RM",
  reunions: "Réunions",
  rapports: "Rapports",
  journal: "Journal d'audit",
  reglages: "Réglages",
};

/** Rubriques des étapes suivantes. */
export function PageAVenir() {
  const { projetId, rubrique = "" } = useParams();
  return (
    <Disposition>
      <div className="flex flex-col gap-1.5 lg:pt-2.5">
        <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">{TITRES[rubrique] ?? "Rubrique"}</h1>
        <p className="text-[15px] text-texte-2">Cet écran arrive dans une prochaine étape.</p>
        <Link to={`/projets/${projetId}`} className="mt-3 text-[15px] font-semibold text-accent-texte">
          Retour au tableau de bord
        </Link>
      </div>
    </Disposition>
  );
}
