import type { TableauDeBord } from "../api/types";
import { dateCourte, pourcentage } from "../lib/format";

function Chiffre({ libelle, valeur, suite, note, alerte }: {
  libelle: string; valeur: string; suite?: string; note?: string; alerte?: boolean;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 border-separateur px-[18px] py-4 lg:flex-1 lg:gap-1 lg:px-6 lg:py-5 lg:[&:not(:first-child)]:border-l">
      <span className="text-xs text-texte-2 lg:text-[13px]">{libelle}</span>
      <span className="whitespace-nowrap text-2xl font-bold tracking-[-0.03em] lg:text-[clamp(22px,1.9vw,30px)]">
        {valeur}
        {suite && <span className="text-sm font-medium text-texte-2 lg:text-base"> {suite}</span>}
      </span>
      {note && (
        <span className={`text-xs lg:text-[13px] ${alerte ? "font-semibold text-manquant-texte" : "text-texte-2"}`}>{note}</span>
      )}
    </div>
  );
}

/** Bande de verre posée sur le bas de la carte des mesures. */
export function Synthese({ d }: { d: TableauDeBord }) {
  const { evaluation, conformite, taches, echeances } = d;
  return (
    <section
      aria-label="Synthèse"
      className="verre relative -mt-[132px] grid grid-cols-2 rounded-[26px] lg:-mt-[168px] lg:flex lg:rounded-verre [&>*:nth-child(odd)]:border-r [&>*:nth-child(-n+2)]:border-b lg:[&>*]:border-b-0! lg:[&>*:nth-child(odd)]:border-r-0!"
    >
      <Chiffre libelle="Évaluation" valeur={pourcentage(evaluation.evaluees, evaluation.total)}
        note={`${evaluation.evaluees} mesures sur ${evaluation.total}`} />
      <Chiffre libelle="Conformité" valeur={String(conformite.conformes)} suite={`/ ${conformite.applicables}`}
        note="mesures applicables conformes" />
      <Chiffre libelle="Plan d'action" valeur={String(taches.ouvertes)} suite={taches.ouvertes > 1 ? "tâches" : "tâche"}
        note={taches.en_retard ? `dont ${taches.en_retard} en retard` : "aucune en retard"} alerte={taches.en_retard > 0} />
      <Chiffre libelle="Décision visée" valeur={dateCourte(echeances.decision)}
        note={echeances.prochain_document ? `prochaine pièce : ${dateCourte(echeances.prochain_document.echeance)}` : undefined} />
    </section>
  );
}
