import type { ReactNode } from "react";
import { Link, useParams } from "react-router";

import { useTableauDeBord } from "../api/hooks";
import type { TableauDeBord as Donnees } from "../api/types";
import { CarteMesures } from "../composants/CarteMesures";
import { nomCourt } from "../composants/statuts";
import { Disposition } from "../composants/Disposition";
import { IconeCloche, IconeDepot, IconeRecherche } from "../composants/Icones";
import { Activite, AValider, PourVous } from "../composants/Listes";
import { Synthese } from "../composants/Synthese";
import { pourcentage } from "../lib/format";

const ETAT_HOMOLOGATION: Record<string, string> = {
  brouillon: "En préparation",
  en_cours: "Homologation en cours",
  en_attente_decision: "En attente de décision",
  homologue: "Homologué",
  refuse: "Homologation refusée",
  archive: "Archivé",
};

function ReferentielsDuProjet({ d }: { d: Donnees }) {
  return (
    <div className="flex flex-col gap-2.5 px-3">
      <span className="text-xs font-semibold text-texte-2">Référentiels du projet</span>
      {d.referentiels.map((r) => {
        const applicables = r.total - r.statuts.non_applicable;
        const pct = applicables ? (r.statuts.conforme / applicables) * 100 : 0;
        return (
          <div key={r.id} className="flex flex-col gap-1.5">
            <div className="flex justify-between gap-2 text-[13px]">
              <span className="truncate" title={r.nom}>{nomCourt(r)}</span>
              <span className="whitespace-nowrap text-texte-2">{pourcentage(r.statuts.conforme, applicables)}</span>
            </div>
            <div aria-hidden="true" className="h-1 rounded-full bg-piste">
              <div className="h-1 rounded-full bg-conforme" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BoutonVerre({ libelle, children, pastille }: { libelle: string; children: ReactNode; pastille?: boolean }) {
  return (
    <button type="button" aria-label={libelle} className="relative flex size-11 items-center justify-center rounded-full">
      {children}
      {pastille && <span aria-hidden="true" className="absolute top-2.5 right-[11px] size-2 rounded-full bg-alerte" />}
    </button>
  );
}

function Contenu({ d }: { d: Donnees }) {
  const base = `/projets/${d.projet.id}`;
  const p = d.projet;
  return (
    <div className="flex flex-col">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1 lg:gap-1.5 lg:pt-2.5">
          <span className="text-[13px] font-semibold text-texte-2">
            {ETAT_HOMOLOGATION[p.statut] ?? p.statut_libelle} · {p.type_bien_libelle.toLowerCase()} · niveau {p.niveau_vise_libelle.toLowerCase()}
          </span>
          <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[clamp(32px,4.2vw,48px)] lg:tracking-[-0.035em]">
            {p.nom}
          </h1>
        </div>
        <div className="hidden items-center gap-2.5 lg:flex">
          <div className="verre flex items-center rounded-full p-[3px]">
            <BoutonVerre libelle="Rechercher"><IconeRecherche /></BoutonVerre>
            <BoutonVerre libelle="Notifications" pastille><IconeCloche /></BoutonVerre>
          </div>
          {!p.lecture_seule && (
            <Link to={`${base}/documents`} className="bouton-accent flex h-[50px] items-center gap-2 rounded-full px-[22px] text-[15px] font-semibold">
              <IconeDepot taille={17} />
              Déposer un document
            </Link>
          )}
        </div>
      </div>

      <div className="mt-5 lg:mt-[26px]">
        <CarteMesures referentiels={d.referentiels} />
      </div>
      <Synthese d={d} />

      <div className="mt-7 flex flex-wrap items-start gap-7">
        <div className="min-w-0 flex-[999_1_460px]"><PourVous d={d} base={base} /></div>
        <div className="flex min-w-0 flex-[1_1_340px] flex-col gap-7">
          <AValider d={d} base={base} />
          <Activite d={d} base={base} />
        </div>
      </div>
    </div>
  );
}

export function PageTableauDeBord() {
  const { projetId } = useParams();
  const { data, isPending, error } = useTableauDeBord(projetId);

  if (error) {
    return (
      <Disposition>
        <div className="verre mx-auto mt-24 max-w-md rounded-verre p-8 text-center">
          <h1 className="text-xl font-bold">Projet introuvable</h1>
          <p className="mt-2 text-sm text-texte-2">Il n'existe pas ou vous n'y avez pas accès.</p>
          <Link to="/" className="mt-5 inline-block text-[15px] font-semibold text-accent-texte">Revenir à mes projets</Link>
        </div>
      </Disposition>
    );
  }
  if (isPending) {
    return (
      <Disposition>
        <div aria-busy="true" aria-label="Chargement du tableau de bord" className="flex flex-col gap-6 pt-4">
          <div className="h-12 w-72 animate-pulse rounded-2xl bg-remplissage" />
          <div className="h-[300px] animate-pulse rounded-verre bg-remplissage" />
          <div className="h-56 animate-pulse rounded-groupe bg-remplissage" />
        </div>
      </Disposition>
    );
  }
  return (
    <Disposition referentiels={<ReferentielsDuProjet d={data} />}>
      <Contenu d={data} />
    </Disposition>
  );
}
