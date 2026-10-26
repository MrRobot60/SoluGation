import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useAnalyses, useLancerAnalyse, useMoi, useRecommandations, useStatuerRecommandation } from "../api/hooks";
import type { RecommandationIA, Tache } from "../api/types";
import { IconeEtincelle } from "./Icones";
import { quand } from "../lib/format";

const EFFORTS: Record<string, string> = { faible: "Effort faible", moyen: "Effort moyen", eleve: "Effort élevé" };

/** Dernière recommandation utile d'une tâche : celle en attente, sinon la dernière acceptée. */
export function recommandationDe(recos: RecommandationIA[], tacheId: string) {
  const siennes = recos.filter((r) => r.tache === tacheId);
  return siennes.find((r) => r.statut_validation === "a_valider") ?? siennes.find((r) => r.statut_validation === "valide");
}

/** Suit une génération en arrière-plan et rafraîchit recommandations et tâches quand elle se termine. */
function useSuiviRecommandations(projetId: string) {
  const { data: analyses = [] } = useAnalyses(projetId, "recommandation");
  const client = useQueryClient();
  const derniere = analyses[0];
  const enCours = Boolean(derniere && (derniere.etat === "en_attente" || derniere.etat === "en_cours"));
  const precedent = useRef(derniere?.etat);
  useEffect(() => {
    if (precedent.current && precedent.current !== derniere?.etat && !enCours) {
      client.invalidateQueries({ queryKey: ["recommandations-ia", projetId] });
    }
    precedent.current = derniere?.etat;
  }, [derniere?.etat, enCours, client, projetId]);
  return { derniere, enCours };
}

export function BandeauRecommandations({ projetId, lectureSeule, nbSansRecommandation }: {
  projetId: string; lectureSeule: boolean; nbSansRecommandation: number;
}) {
  const { data: moi } = useMoi();
  const { data: recos = [] } = useRecommandations(projetId);
  const { derniere, enCours } = useSuiviRecommandations(projetId);
  const lancer = useLancerAnalyse(projetId, "recommandation");
  const aRelire = recos.filter((r) => r.statut_validation === "a_valider").length;
  if (!moi?.organisation.ia_activee || (nbSansRecommandation === 0 && aRelire === 0 && !enCours)) return null;

  return (
    <div role="status" aria-live="polite" className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-groupe bg-groupe px-4 py-3 shadow-groupe">
      <IconeEtincelle taille={17} className="shrink-0 text-accent-texte" />
      <p className="min-w-0 flex-1 text-[13px] leading-snug text-texte-2">
        {enCours ? (
          <span className="flex items-center gap-2 font-medium text-texte">
            <span aria-hidden="true" className="size-3.5 animate-spin rounded-full border-2 border-accent border-t-transparent motion-reduce:animate-none" />
            Rédaction des recommandations en cours…
          </span>
        ) : derniere?.etat === "echec" ? (
          <span className="font-medium text-manquant-texte">Échec de la génération : {derniere.erreur}</span>
        ) : aRelire > 0 ? (
          <><span className="font-semibold text-texte">{aRelire} recommandation{aRelire > 1 ? "s" : ""} de l'IA à relire</span> : ouvrez la tâche pour l'accepter ou la rejeter.</>
        ) : (
          "L'IA peut proposer, pour chaque tâche ouverte, les étapes pour combler le manquement et la preuve à fournir. Rien n'est appliqué sans votre accord."
        )}
      </p>
      {!lectureSeule && nbSansRecommandation > 0 && (
        <button type="button" disabled={enCours || lancer.isPending} onClick={() => lancer.mutate({})}
          className="h-9 shrink-0 rounded-full bg-accent-doux px-4 text-[13px] font-semibold text-accent-texte disabled:opacity-45">
          Proposer des recommandations
        </button>
      )}
      {lancer.error && <p role="alert" className="w-full text-[13px] font-medium text-manquant-texte">{lancer.error.message}</p>}
    </div>
  );
}

export function CarteRecommandation({ tache, projetId, lectureSeule }: { tache: Tache; projetId: string; lectureSeule: boolean }) {
  const { data: moi } = useMoi();
  const { data: recos = [] } = useRecommandations(projetId);
  const { enCours } = useSuiviRecommandations(projetId);
  const lancer = useLancerAnalyse(projetId, "recommandation");
  const statuer = useStatuerRecommandation(projetId);
  const reco = recommandationDe(recos, tache.id);
  const close = tache.statut === "terminee" || tache.statut === "abandonnee";
  if (!moi?.organisation.ia_activee && !reco) return null;

  if (!reco || reco.statut_validation === "rejete") {
    if (lectureSeule || close || !moi?.organisation.ia_activee) return null;
    return (
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" disabled={enCours || lancer.isPending} onClick={() => lancer.mutate({ taches: [tache.id] })}
          className="flex h-9 items-center gap-1.5 rounded-full bg-accent-doux px-4 text-[13px] font-semibold text-accent-texte disabled:opacity-45">
          <IconeEtincelle taille={14} /> {enCours ? "Rédaction en cours…" : "Demander une recommandation à l'IA"}
        </button>
        {lancer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{lancer.error.message}</p>}
      </div>
    );
  }

  const aValider = reco.statut_validation === "a_valider";
  return (
    <section aria-labelledby="titre-reco" className={`flex flex-col gap-2.5 rounded-2xl px-3.5 py-3 ${aValider ? "bg-partiel/10" : "bg-remplissage"}`}>
      <h2 id="titre-reco" className={`flex items-center gap-1.5 text-xs font-semibold ${aValider ? "text-partiel-texte" : "text-texte-2"}`}>
        <IconeEtincelle taille={15} />
        {aValider ? "Recommandation de l'IA, à relire" : `Recommandation acceptée par ${reco.valide_par_nom} · ${quand(reco.valide_le!)}`}
      </h2>
      <p className="text-sm leading-relaxed font-medium">{reco.texte}</p>
      <ol className="flex list-decimal flex-col gap-1 pl-5 text-sm leading-snug">
        {reco.etapes.map((e, i) => <li key={i}>{e}</li>)}
      </ol>
      {reco.preuve_suggeree && (
        <p className="text-[13px] leading-snug"><span className="font-semibold">Preuve suggérée : </span>{reco.preuve_suggeree}</p>
      )}
      <p className="text-xs text-texte-3">
        {reco.effort && `${EFFORTS[reco.effort]} · `}
        {reco.fournisseur === "factice" ? "mode test hors ligne, sans valeur de conseil · " : ""}
        proposée {quand(reco.cree_le)}
      </p>
      {aValider && !lectureSeule && (
        <>
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={statuer.isPending} onClick={() => statuer.mutate({ id: reco.id, decision: "valide" })}
              className="bouton-accent h-9 rounded-full px-4 text-[13px] font-semibold">Accepter</button>
            <button type="button" disabled={statuer.isPending} onClick={() => statuer.mutate({ id: reco.id, decision: "rejete" })}
              className="h-9 rounded-full bg-remplissage px-4 text-[13px] font-semibold">Rejeter</button>
          </div>
          <p className="text-xs text-texte-2">
            Acceptée, ses étapes s'ajoutent à la description ; la preuve suggérée remplace une preuve vide ou générique.
          </p>
        </>
      )}
      {statuer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{statuer.error.message}</p>}
    </section>
  );
}
