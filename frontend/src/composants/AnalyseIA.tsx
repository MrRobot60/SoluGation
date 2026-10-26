import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";

import { useAnalyses, useLancerAnalyse, useMoi } from "../api/hooks";
import { IconeEtincelle } from "./Icones";
import { quand } from "../lib/format";

/** Lancement et suivi de l'analyse IA des documents déposés. Les conclusions partent en « à valider » :
 *  la carte renvoie vers l'écran Mesures, où le RSSI ou l'autorité d'homologation les acceptent ou les rejettent. */
export function CarteAnalyseIA({ projetId, lectureSeule, nbDocuments }: { projetId: string; lectureSeule: boolean; nbDocuments: number }) {
  const { data: moi } = useMoi();
  const { data: analyses = [] } = useAnalyses(projetId, "analyse_documentaire");
  const lancer = useLancerAnalyse(projetId, "analyse_documentaire");
  const client = useQueryClient();
  const derniere = analyses[0];
  const enCours = derniere && (derniere.etat === "en_attente" || derniere.etat === "en_cours");

  // Fin d'une analyse suivie : les propositions et le tableau de bord changent.
  const etatPrecedent = useRef(derniere?.etat);
  useEffect(() => {
    if (etatPrecedent.current && etatPrecedent.current !== derniere?.etat && !enCours) {
      for (const cle of ["resultats-ia", "tableau-de-bord"]) client.invalidateQueries({ queryKey: [cle, projetId] });
    }
    etatPrecedent.current = derniere?.etat;
  }, [derniere?.etat, enCours, client, projetId]);

  if (moi && !moi.organisation.ia_activee) {
    return (
      <p className="flex items-center gap-2 rounded-groupe bg-groupe px-4 py-3.5 text-sm text-texte-2 shadow-groupe">
        <IconeEtincelle taille={16} /> L'IA est désactivée pour votre organisation : aucun document n'est envoyé à un fournisseur.
      </p>
    );
  }

  const ignores = derniere?.documents_analyses.filter((d) => !d.analyse) ?? [];
  const analysesOk = derniere?.documents_analyses.filter((d) => d.analyse) ?? [];

  return (
    <section aria-labelledby="titre-analyse" className="flex flex-col gap-3 rounded-groupe bg-groupe px-4 py-4 shadow-groupe">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <h2 id="titre-analyse" className="flex items-center gap-2 text-[17px] font-bold">
            <IconeEtincelle taille={18} className="text-accent-texte" /> Analyse IA
            {derniere?.fournisseur === "factice" && (
              <span className="rounded-full bg-remplissage px-2 py-0.5 text-[11px] font-semibold text-texte-2">mode test hors ligne</span>
            )}
          </h2>
          <p className="text-[13px] leading-snug text-texte-2">
            L'IA lit la dernière version de chaque document et propose, mesure par mesure, ce qui est couvert, partiel ou absent,
            avec les passages cités. Chaque proposition est à valider par le RSSI ou l'autorité d'homologation.
          </p>
        </div>
        {!lectureSeule && (
          <button type="button" disabled={enCours || lancer.isPending || nbDocuments === 0} onClick={() => lancer.mutate({})}
            className="bouton-accent h-10 shrink-0 rounded-full px-5 text-[14px] font-semibold disabled:opacity-45">
            {enCours ? "Analyse en cours…" : derniere ? "Relancer l'analyse" : "Analyser les documents"}
          </button>
        )}
      </div>

      {nbDocuments === 0 && !derniere && <p className="text-[13px] text-texte-2">Déposez au moins un document pour lancer l'analyse.</p>}
      {lancer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{lancer.error.message}</p>}

      {derniere && (
        <div role="status" aria-live="polite" className="flex flex-col gap-2 rounded-2xl bg-remplissage px-3.5 py-3 text-sm">
          {enCours && (
            <span className="flex items-center gap-2.5">
              <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-accent border-t-transparent motion-reduce:animate-none" />
              Analyse en cours, lancée par {derniere.demandee_par_nom} {quand(derniere.cree_le)}.
            </span>
          )}
          {derniere.etat === "echec" && (
            <span className="font-medium text-manquant-texte">Échec de l'analyse {quand(derniere.cree_le)} : {derniere.erreur}</span>
          )}
          {derniere.etat === "terminee" && (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>
                <span className="font-semibold">{derniere.nb_a_valider} proposition{derniere.nb_a_valider > 1 ? "s" : ""} à valider</span>
                <span className="text-texte-2">
                  {analysesOk.length > 0 && ` · ${analysesOk.length} document${analysesOk.length > 1 ? "s" : ""} analysé${analysesOk.length > 1 ? "s" : ""}`}
                  {` · ${quand(derniere.fin_le ?? derniere.cree_le)}`}
                </span>
              </span>
              {derniere.nb_a_valider > 0 && (
                <Link to={`/projets/${projetId}/mesures?filtre=ia`} className="text-[13px] font-semibold text-accent-texte">Voir les propositions</Link>
              )}
            </div>
          )}
          {analysesOk.some((d) => d.tronque) && (
            <span className="text-[13px] text-partiel-texte">Document très long : seule la première partie a été analysée.</span>
          )}
          {ignores.length > 0 && (
            <ul className="flex flex-col gap-0.5 text-[13px] text-texte-2">
              {ignores.map((d) => <li key={d.id}>Non analysé : « {d.nom} » ({d.raison})</li>)}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
