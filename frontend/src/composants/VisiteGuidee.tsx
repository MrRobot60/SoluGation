import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { useLocation, useNavigate } from "react-router";

import { useMoi, useProjets, useVisite } from "../api/hooks";

/** Une étape : la page à ouvrir (relative au projet, ou absolue si elle commence par « / ») et l'élément mis en avant. */
type Etape = { page: string; cible?: string; titre: string; texte: string };

const ETAPES: Etape[] = [
  { page: "", titre: "Tableau de bord", texte: "L'état de l'homologation en un coup d'œil : conformité par référentiel, ce qui vous attend, échéances. Ce projet est fictif : testez librement, puis archivez-le." },
  { page: "mesures", titre: "Mesures", texte: "Chaque exigence des référentiels choisis, avec son statut : conforme, partiel, manquant ou non applicable. Un manquement crée une tâche dans le plan d'action." },
  { page: "documents", titre: "Documents", texte: "La checklist des pièces attendues, avec responsable et échéance. Chaque dépôt est contrôlé, empreinté (SHA-256) et versionné. Si l'IA est activée, elle propose ce qu'une pièce couvre : un humain valide." },
  { page: "plan-action", titre: "Plan d'action", texte: "Un manquement, une tâche : responsable, échéance, preuve attendue, commentaires et historique. L'IA peut recommander comment combler l'écart." },
  { page: "scans", titre: "Scans de vulnérabilités", texte: "Importez un rapport Nessus, OpenVAS ou CSV : les vulnérabilités deviennent des constats, puis des tâches." },
  { page: "risques", titre: "Risques et dérogations", texte: "Les risques résiduels et les dérogations, acceptés de façon datée et nominative." },
  { page: "ebios", titre: "EBIOS RM", texte: "Les cinq ateliers de la méthode, guidés et optionnels, activables par projet." },
  { page: "reunions", titre: "Réunions", texte: "Planifiez avec les acteurs : invitation d'agenda par mail, ordre du jour, compte rendu et tâches décidées." },
  { page: "rapports", titre: "Rapports", texte: "Le rapport d'état des lieux en PDF, à tout moment. Chaque version validée est figée ; deux versions se comparent." },
  { page: "journal", titre: "Journal d'audit", texte: "Toute action est tracée dans un journal en ajout seul, chaîné par hachage : qui, quand, quoi." },
  { page: "reglages", titre: "Réglages du projet", texte: "Acteurs et rôles, notifications, revue périodique, décision d'homologation et archivage." },
  { page: "/bibliotheque", titre: "Bibliothèque", texte: "Les référentiels de l'installation, leurs mesures et les correspondances entre référentiels." },
  { page: "/aide", cible: '[data-visite="aide"]', titre: "Aide", texte: "La documentation complète, avec recherche. Ce bouton ouvre l'aide de l'écran où vous êtes. Vous pourrez revoir cette visite depuis l'Aide." },
];

const CLE_ETAPE = "sg-visite-etape";
const CLE_PROJET = "sg-visite-projet";
const CLE_PAUSE = "sg-visite-pause";

// Stockage navigateur : simple confort (reprendre où l'on s'était arrêté), l'état de référence est sur le compte.
function lire(stockage: () => Storage, cle: string) {
  try { return stockage().getItem(cle); } catch { return null; }
}
function ecrire(stockage: () => Storage, cle: string, valeur: string | null) {
  try { if (valeur === null) stockage().removeItem(cle); else stockage().setItem(cle, valeur); } catch { /* stockage indisponible */ }
}
const local = () => window.localStorage;
const session = () => window.sessionStorage;

/** Relance la visite (depuis l'Aide). */
export function oublierVisite() {
  ecrire(local, CLE_ETAPE, null);
  ecrire(local, CLE_PROJET, null);
  ecrire(session, CLE_PAUSE, null);
  window.dispatchEvent(new Event("sg-visite-revoir"));
}

function elementVisible(selecteur: string) {
  return [...document.querySelectorAll<HTMLElement>(selecteur)].find((e) => e.getClientRects().length && e.offsetWidth > 0) ?? null;
}

type Rect = { top: number; left: number; width: number; height: number };

export function VisiteGuidee() {
  const { data: moi } = useMoi();
  const { data: projets } = useProjets();
  const visite = useVisite();
  const naviguer = useNavigate();
  const { pathname } = useLocation();
  const [pause, setPause] = useState(() => lire(session, CLE_PAUSE) === "1");
  const [etape, setEtape] = useState(() => Number(lire(local, CLE_ETAPE) ?? -1)); // -1 : accueil
  const [projet, setProjet] = useState(() => lire(local, CLE_PROJET));
  const [rect, setRect] = useState<Rect | null>(null);
  const titre = useRef<HTMLHeadingElement>(null);

  const active = !!moi && !moi.visite_terminee && !pause && !(moi.double_auth.requise && !moi.double_auth.active);
  const etapes = projet ? ETAPES : ETAPES.filter((e) => e.page.startsWith("/")); // lecture seule sans projet : pages générales
  const courante = etape >= 0 ? etapes[Math.min(etape, etapes.length - 1)] : null;
  const chemin = courante && (courante.page.startsWith("/") ? courante.page : `/projets/${projet}${courante.page ? `/${courante.page}` : ""}`);
  const selecteur = courante && (courante.cible ?? `a[href="${chemin}"]`);

  const aller = useCallback((n: number) => {
    setEtape(n);
    ecrire(local, CLE_ETAPE, String(n));
  }, []);

  const finir = () => {
    oublierVisite();
    setPause(true); // masque la visite sans attendre le rechargement du compte
    visite.mutate("terminer");
  };
  const plusTard = () => {
    ecrire(session, CLE_PAUSE, "1");
    setPause(true);
  };
  const commencer = () => {
    visite.mutate("demarrer", {
      onSuccess: (r) => {
        const id = r?.projet ?? projets?.results[0]?.id ?? null;
        setProjet(id);
        ecrire(local, CLE_PROJET, id);
        aller(0);
      },
    });
  };

  useEffect(() => {
    const revoir = () => { setPause(false); setEtape(-1); setProjet(null); };
    window.addEventListener("sg-visite-revoir", revoir);
    return () => window.removeEventListener("sg-visite-revoir", revoir);
  }, []);

  // Ouvre la page de l'étape.
  useEffect(() => {
    if (active && chemin && pathname !== chemin) naviguer(chemin);
  }, [active, chemin, pathname, naviguer]);

  // Suit l'élément mis en avant : la page se rend de façon asynchrone, se redimensionne, défile.
  useLayoutEffect(() => {
    if (!active || !selecteur) return setRect(null);
    const mesurer = () => {
      const r = elementVisible(selecteur)?.getBoundingClientRect();
      setRect((avant) => {
        if (!r) return null;
        const apres = { top: r.top, left: r.left, width: r.width, height: r.height };
        return avant && (Object.keys(apres) as (keyof Rect)[]).every((k) => avant[k] === apres[k]) ? avant : apres;
      });
    };
    mesurer();
    const suivi = setInterval(mesurer, 250);
    window.addEventListener("resize", mesurer);
    window.addEventListener("scroll", mesurer, true);
    return () => {
      clearInterval(suivi);
      window.removeEventListener("resize", mesurer);
      window.removeEventListener("scroll", mesurer, true);
    };
  }, [active, selecteur, pathname]);

  useEffect(() => {
    if (active) titre.current?.focus();
  }, [active, etape]);

  useEffect(() => {
    if (!active) return;
    const clavier = (e: KeyboardEvent) => {
      if (e.key === "Escape") plusTard();
      else if (courante && e.key === "ArrowRight") etape < etapes.length - 1 ? aller(etape + 1) : finir();
      else if (courante && e.key === "ArrowLeft" && etape > 0) aller(etape - 1);
    };
    document.addEventListener("keydown", clavier);
    return () => document.removeEventListener("keydown", clavier);
  });

  if (!active) return null;

  const derniere = etape >= etapes.length - 1;
  const largeur = Math.min(360, window.innerWidth - 32);
  let position: CSSProperties = { left: "50%", top: "50%", transform: "translate(-50%, -50%)" };
  if (courante && rect) {
    const aDroite = rect.left + rect.width + 16 + largeur <= window.innerWidth - 16;
    const enDessous = rect.top + rect.height + 260 <= window.innerHeight;
    position = aDroite
      ? { left: rect.left + rect.width + 16, top: Math.min(Math.max(16, rect.top - 8), window.innerHeight - 280) }
      : enDessous
        ? { left: Math.min(Math.max(16, rect.left), window.innerWidth - largeur - 16), top: rect.top + rect.height + 12 }
        : { left: Math.min(Math.max(16, rect.left), window.innerWidth - largeur - 16), bottom: window.innerHeight - rect.top + 12 };
  }

  return (
    <div className="fixed inset-0 z-50">
      {courante && rect ? (
        <div aria-hidden="true" className="pointer-events-none fixed rounded-xl shadow-[0_0_0_9999px_rgb(0_0_0/0.55)] ring-2 ring-accent transition-all duration-300 ease-ios"
          style={{ top: rect.top - 4, left: rect.left - 4, width: rect.width + 8, height: rect.height + 8 }} />
      ) : <div aria-hidden="true" className="fixed inset-0 bg-black/55" />}
      <div role="dialog" aria-modal="true" aria-labelledby="visite-titre" aria-describedby="visite-texte"
        className="verre fixed flex flex-col gap-3 rounded-verre p-5 transition-all duration-300 ease-ios" style={{ width: largeur, ...position }}>
        {courante ? (
          <>
            <span className="text-xs font-semibold text-texte-2 tabular-nums">Visite guidée · {etape + 1} / {etapes.length}</span>
            <h2 id="visite-titre" ref={titre} tabIndex={-1} className="text-[20px] font-bold tracking-[-0.02em] outline-none">{courante.titre}</h2>
            <p id="visite-texte" className="text-[15px] leading-relaxed text-texte-2">{courante.texte}</p>
            <div className="mt-1 flex items-center gap-2">
              <button type="button" onClick={finir} className="mr-auto text-[13px] font-medium text-texte-2">Passer</button>
              {etape > 0 && <button type="button" onClick={() => aller(etape - 1)} className="h-10 rounded-full bg-remplissage px-4 text-sm font-semibold">Précédent</button>}
              <button type="button" onClick={() => (derniere ? finir() : aller(etape + 1))}
                className="bouton-accent h-10 rounded-full px-5 text-sm font-semibold">{derniere ? "Terminer" : "Suivant"}</button>
            </div>
          </>
        ) : (
          <>
            <h2 id="visite-titre" ref={titre} tabIndex={-1} className="text-[22px] font-bold tracking-[-0.02em] outline-none">Bienvenue sur SoluGation</h2>
            <p id="visite-texte" className="text-[15px] leading-relaxed text-texte-2">
              {moi.lecture_seule
                ? "Une visite de deux minutes pour découvrir chaque écran. Votre compte est en lecture seule : rien ne sera modifié."
                : "Une visite de deux minutes pour découvrir chaque écran, sur un projet d'exemple créé pour vous. Rien n'est envoyé à personne."}
            </p>
            <button type="button" onClick={commencer} disabled={visite.isPending}
              className="bouton-accent mt-1 h-[50px] rounded-full text-[15px] font-semibold disabled:opacity-60">
              {visite.isPending ? "Préparation…" : "Commencer la visite"}
            </button>
            {visite.isError && <p role="alert" className="text-[13px] text-manquant-texte">La visite n'a pas pu démarrer. Réessayez.</p>}
            <div className="flex justify-between">
              <button type="button" onClick={plusTard} className="text-[13px] font-medium text-texte-2">Plus tard</button>
              <button type="button" onClick={finir} className="text-[13px] font-medium text-texte-2">Ne plus proposer</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
