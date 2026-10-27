import { useEffect, useRef, useState, type ComponentType, type ReactNode } from "react";
import { Link, NavLink, useNavigate, useParams } from "react-router";

import { useDeconnexion, useMoi, useProjets } from "../api/hooks";
import { useTheme, type ChoixTheme } from "../lib/theme";
import { Cloche } from "./Cloche";
import {
  IconeAuto, IconeBouclier, IconeCalendrier, IconeChevronHautBas, IconeCouches, IconeDocument, IconeLune,
  IconeMesures, IconePlus, IconeRapports, IconeRecherche, IconeReglages, IconeSoleil, IconeTableau, IconeTache,
} from "./Icones";

/** Icône SoluGation : symbole sur tuile claire (lisible en clair comme en sombre), coins façon iOS. */
export function Logo({ taille = 30, decoratif = false }: { taille?: number; decoratif?: boolean }) {
  return (
    <img
      src={taille > 64 ? "/marque/icone-512.png" : "/marque/icone-128.png"}
      alt={decoratif ? "" : "SoluGation"}
      width={taille}
      height={taille}
      style={{ borderRadius: taille * 0.2237 }}
      className="shrink-0 shadow-[0_1px_2px_rgb(0_0_0/0.08),inset_0_0_0_0.5px_rgb(0_0_0/0.06)] select-none"
      draggable={false}
    />
  );
}

type Rubrique = { chemin: string; libelle: string; Icone: ComponentType<{ taille?: number }>; mobile?: string };
const RUBRIQUES: Rubrique[] = [
  { chemin: "", libelle: "Tableau de bord", Icone: IconeTableau, mobile: "Accueil" },
  { chemin: "mesures", libelle: "Mesures", Icone: IconeMesures, mobile: "Mesures" },
  { chemin: "documents", libelle: "Documents", Icone: IconeDocument, mobile: "Documents" },
  { chemin: "plan-action", libelle: "Plan d'action", Icone: IconeTache, mobile: "Actions" },
  { chemin: "scans", libelle: "Scans de vulnérabilités", Icone: IconeRecherche },
  { chemin: "risques", libelle: "Risques et dérogations", Icone: IconeBouclier },
  { chemin: "ebios", libelle: "EBIOS RM", Icone: IconeCouches },
  { chemin: "reunions", libelle: "Réunions", Icone: IconeCalendrier },
  { chemin: "rapports", libelle: "Rapports", Icone: IconeRapports },
];

function SelecteurProjet({ projetId }: { projetId: string }) {
  const { data } = useProjets();
  const [ouvert, setOuvert] = useState(false);
  const zone = useRef<HTMLDivElement>(null);
  const projets = data?.results ?? [];
  const courant = projets.find((p) => p.id === projetId);

  useEffect(() => {
    if (!ouvert) return;
    const fermer = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !zone.current?.contains(e.target as Node)) setOuvert(false);
    };
    document.addEventListener("mousedown", fermer);
    document.addEventListener("keydown", fermer);
    return () => {
      document.removeEventListener("mousedown", fermer);
      document.removeEventListener("keydown", fermer);
    };
  }, [ouvert]);

  return (
    <div ref={zone} className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={ouvert}
        onClick={() => setOuvert((o) => !o)}
        className="flex w-full items-center gap-2.5 rounded-2xl bg-remplissage px-3 py-2.5 text-left"
      >
        <span className="flex min-w-0 flex-1 flex-col gap-px">
          <span className="truncate text-sm font-semibold">{courant?.nom ?? "Projet"}</span>
          <span className="text-xs text-texte-2">{projets.length} projet{projets.length > 1 ? "s" : ""}</span>
        </span>
        <IconeChevronHautBas taille={14} className="text-texte-2" />
      </button>
      {ouvert && (
        <ul role="listbox" aria-label="Projets" className="verre absolute inset-x-0 top-full z-20 mt-2 max-h-72 overflow-auto rounded-[18px] p-1.5">
          {projets.map((p) => (
            <li key={p.id} role="option" aria-selected={p.id === projetId}>
              <Link
                to={`/projets/${p.id}`}
                onClick={() => setOuvert(false)}
                className={`block rounded-xl px-3 py-2.5 text-sm ${p.id === projetId ? "bg-accent-doux font-semibold text-accent-texte" : "hover:bg-remplissage"}`}
              >
                {p.nom}
              </Link>
            </li>
          ))}
          <li className="mt-1 border-t border-separateur pt-1">
            <Link to="/projets/nouveau" onClick={() => setOuvert(false)}
              className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold text-accent-texte hover:bg-remplissage">
              <IconePlus taille={16} /> Nouveau projet
            </Link>
          </li>
        </ul>
      )}
    </div>
  );
}

const THEMES: { cle: ChoixTheme; libelle: string; Icone: ComponentType<{ taille?: number }> }[] = [
  { cle: "systeme", libelle: "Système", Icone: IconeAuto },
  { cle: "clair", libelle: "Clair", Icone: IconeSoleil },
  { cle: "sombre", libelle: "Sombre", Icone: IconeLune },
];

function ChoixDuTheme() {
  const { choix, choisir } = useTheme();
  return (
    <div role="radiogroup" aria-label="Apparence" className="flex rounded-full bg-remplissage p-[3px]">
      {THEMES.map(({ cle, libelle, Icone }) => (
        <button
          key={cle}
          type="button"
          role="radio"
          aria-checked={choix === cle}
          aria-label={libelle}
          title={libelle}
          onClick={() => choisir(cle)}
          className={`flex h-8 flex-1 items-center justify-center rounded-full transition-colors duration-200 ease-ios ${choix === cle ? "bg-groupe text-texte shadow-groupe" : "text-texte-2"}`}
        >
          <Icone taille={16} />
        </button>
      ))}
    </div>
  );
}

function BarreLaterale({ projetId, referentiels }: { projetId: string; referentiels?: ReactNode }) {
  const { data: moi } = useMoi();
  const deconnexion = useDeconnexion();
  const naviguer = useNavigate();
  const base = `/projets/${projetId}`;
  return (
    <nav
      aria-label="Navigation principale"
      className="verre sticky top-3 hidden max-h-[calc(100dvh-24px)] w-[248px] shrink-0 flex-col gap-[22px] overflow-y-auto rounded-verre px-3 pt-[18px] pb-3.5 lg:flex"
    >
      <div className="flex items-center gap-2.5 px-2">
        <Logo decoratif />
        <span className="flex-1 text-[17px] font-bold tracking-[-0.02em]">SoluGation</span>
        <Cloche compacte />
      </div>
      <SelecteurProjet projetId={projetId} />
      <ul className="flex flex-col gap-0.5">
        {RUBRIQUES.map(({ chemin, libelle, Icone }) => (
          <li key={chemin || "accueil"}>
            <NavLink
              to={chemin ? `${base}/${chemin}` : base}
              end
              className={({ isActive }) =>
                `flex min-h-10 items-center gap-3 rounded-xl px-3 text-sm transition-colors duration-200 ease-ios ${
                  isActive ? "bg-accent-doux font-semibold text-accent-texte" : "font-medium hover:bg-remplissage [&>svg]:text-texte-2"
                }`
              }
            >
              <Icone />
              {libelle}
            </NavLink>
          </li>
        ))}
      </ul>
      {referentiels}
      <div className="mt-auto flex flex-col gap-2.5">
        <Link to={`${base}/reglages`} className="flex min-h-10 items-center gap-3 rounded-xl px-3 text-sm font-medium hover:bg-remplissage [&>svg]:text-texte-2">
          <IconeReglages />
          Réglages
        </Link>
        {(moi?.est_admin || moi?.est_admin_instance) && (
          <NavLink to="/administration"
            className={({ isActive }) => `flex min-h-10 items-center gap-3 rounded-xl px-3 text-sm font-medium [&>svg]:text-texte-2 ${isActive ? "bg-remplissage font-semibold" : "hover:bg-remplissage"}`}>
            <IconeBouclier />
            Administration
          </NavLink>
        )}
        <div className="px-1"><ChoixDuTheme /></div>
        <div className="mt-1 flex items-center gap-2.5 border-t border-separateur px-3 pt-2.5">
          <span aria-hidden="true" className="flex size-8 shrink-0 items-center justify-center rounded-full bg-remplissage text-xs font-bold text-texte-2">
            {initiales(moi?.nom_complet ?? "")}
          </span>
          <span className="flex min-w-0 flex-1 flex-col gap-px">
            <span className="truncate text-[13px] font-semibold">{moi?.nom_complet}</span>
            <span className="truncate text-xs text-texte-2">{moi?.role?.libelle ?? moi?.organisation.nom}</span>
          </span>
          <button
            type="button"
            onClick={() => deconnexion.mutate(undefined, { onSettled: () => naviguer("/connexion") })}
            className="rounded-lg px-1.5 py-2 text-xs font-medium text-accent-texte"
          >
            Quitter
          </button>
        </div>
      </div>
    </nav>
  );
}

function initiales(nom: string) {
  return nom.split(/\s+/).filter(Boolean).slice(0, 2).map((m) => m[0]?.toUpperCase()).join("");
}

function BarreOnglets({ projetId }: { projetId: string }) {
  const base = `/projets/${projetId}`;
  return (
    <div className="fixed inset-x-4 bottom-[max(20px,env(safe-area-inset-bottom))] z-30 flex items-center gap-2.5 lg:hidden">
      <nav aria-label="Navigation principale" className="verre-barre flex flex-1 rounded-full p-1">
        {RUBRIQUES.filter((r) => r.mobile).map(({ chemin, mobile, Icone }) => (
          <NavLink
            key={chemin || "accueil"}
            to={chemin ? `${base}/${chemin}` : base}
            end
            className={({ isActive }) =>
              `flex flex-1 flex-col items-center gap-0.5 rounded-full pt-[7px] pb-1.5 text-[10px] ${
                isActive ? "bg-remplissage font-semibold text-accent-texte" : "font-medium"
              }`
            }
          >
            <Icone taille={22} />
            {mobile}
          </NavLink>
        ))}
      </nav>
      <Link
        to={`${base}/documents`}
        aria-label="Déposer un document"
        className="verre-barre flex size-[60px] shrink-0 items-center justify-center rounded-full text-accent-texte"
      >
        <IconePlus taille={24} />
      </Link>
    </div>
  );
}

/** Mobile : logo, sélecteur de projet (avec « Nouveau projet ») et notifications, sur toutes les pages. */
function BarreMobile({ projetId }: { projetId: string }) {
  return (
    <div className="mb-4 flex items-center gap-2.5 lg:hidden">
      <Logo />
      <div className="min-w-0 flex-1"><SelecteurProjet projetId={projetId} /></div>
      <Cloche />
    </div>
  );
}

export function Disposition({ children, referentiels }: { children: ReactNode; referentiels?: ReactNode }) {
  const { projetId: dansUrl = "" } = useParams();
  const { data: projets } = useProjets();
  const projetId = dansUrl || projets?.results[0]?.id || ""; // pages hors projet (administration) : premier projet accessible
  return (
    <div className="flex min-h-dvh items-start gap-3 p-0 lg:p-3">
      <BarreLaterale projetId={projetId} referentiels={referentiels} />
      <main className="min-w-0 flex-1 px-4 pt-4 pb-[130px] lg:px-[clamp(12px,2.5vw,36px)] lg:pt-[18px] lg:pb-12">
        <BarreMobile projetId={projetId} />
        {children}
      </main>
      <BarreOnglets projetId={projetId} />
    </div>
  );
}
