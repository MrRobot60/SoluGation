import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useAnalyses, useDemanderSuggestions, useMoi, useStatuerSuggestion, useSuggestionsEbios } from "../../api/hooks";
import type { SuggestionEbios } from "../../api/types";
import { IconeEtincelle } from "../Icones";
import { ECHELLE } from "./Objets";

const QUOI: Record<number, string> = {
  1: "des événements redoutés et des biens supports pour les valeurs métier qui n'en ont pas",
  2: "des couples source de risque / objectif visé adaptés au projet",
  3: "des scénarios stratégiques et leurs chemins d'attaque pour les couples retenus",
  4: "un scénario opérationnel pour chaque chemin d'attaque qui n'en a pas",
};

/** Champs modifiables avant acceptation, par type de proposition (chemin dans le contenu, libellé, nature). */
const EDITABLES: Record<SuggestionEbios["type_objet"], { chemin: string[]; libelle: string; zone?: boolean; echelle?: boolean }[]> = {
  evenement_redoute: [{ chemin: ["description"], libelle: "Événement redouté", zone: true }, { chemin: ["impacts"], libelle: "Impacts", zone: true },
                      { chemin: ["gravite"], libelle: "Gravité", echelle: true }],
  bien_support: [{ chemin: ["nom"], libelle: "Bien support" }, { chemin: ["type_bien"], libelle: "Type" }, { chemin: ["description"], libelle: "Description", zone: true }],
  couple: [{ chemin: ["source", "libelle"], libelle: "Source de risque" }, { chemin: ["objectif", "libelle"], libelle: "Objectif visé" },
           { chemin: ["pertinence"], libelle: "Pertinence", echelle: true }, { chemin: ["justification"], libelle: "Justification", zone: true }],
  scenario_strategique: [{ chemin: ["intitule"], libelle: "Scénario stratégique" }, { chemin: ["description"], libelle: "Description", zone: true },
                         { chemin: ["gravite"], libelle: "Gravité", echelle: true }],
  scenario_operationnel: [{ chemin: ["intitule"], libelle: "Scénario opérationnel" }, { chemin: ["mode_operatoire"], libelle: "Mode opératoire", zone: true },
                          { chemin: ["vraisemblance"], libelle: "Vraisemblance", echelle: true }],
};

const lire = (o: Record<string, unknown>, chemin: string[]): unknown => chemin.reduce<unknown>((v, k) => (v as Record<string, unknown> | undefined)?.[k], o);
function ecrire(o: Record<string, unknown>, chemin: string[], valeur: unknown): Record<string, unknown> {
  const [tete, ...reste] = chemin;
  return { ...o, [tete]: reste.length ? ecrire((o[tete] as Record<string, unknown>) ?? {}, reste, valeur) : valeur };
}

function Proposition({ s, parent, projetId, lectureSeule }: { s: SuggestionEbios; parent?: string; projetId: string; lectureSeule: boolean }) {
  const statuer = useStatuerSuggestion(projetId);
  const [contenu, setContenu] = useState(s.contenu);
  const [edition, setEdition] = useState(false);
  const champs = EDITABLES[s.type_objet];
  const chemins = (contenu.chemins as { description: string }[] | undefined) ?? [];

  return (
    <li className="flex flex-col gap-2 rounded-2xl bg-partiel/10 px-3.5 py-3">
      <span className="text-xs font-semibold text-partiel-texte">{s.type_libelle}{parent ? ` · pour « ${parent} »` : ""}</span>
      {edition ? (
        <div className="flex flex-col gap-2.5">
          {champs.map((c) => {
            const v = lire(contenu, c.chemin);
            return c.echelle ? (
              <div key={c.libelle} role="radiogroup" aria-label={c.libelle} className="flex items-center gap-2">
                <span className="w-28 text-xs font-semibold text-texte-2">{c.libelle}</span>
                {[1, 2, 3, 4].map((n) => (
                  <button key={n} type="button" role="radio" aria-checked={v === n} onClick={() => setContenu(ecrire(contenu, c.chemin, n))}
                    className={`h-8 min-w-8 rounded-full text-[13px] font-semibold ${v === n ? "bg-accent text-white" : "bg-groupe text-texte-2"}`}>{n}</button>
                ))}
              </div>
            ) : (
              <label key={c.libelle} className="flex flex-col gap-1">
                <span className="text-xs font-semibold text-texte-2">{c.libelle}</span>
                {c.zone ? (
                  <textarea rows={3} value={(v as string) ?? ""} onChange={(e) => setContenu(ecrire(contenu, c.chemin, e.target.value))}
                    className="resize-y rounded-xl bg-groupe px-3 py-2 text-sm outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)]" />
                ) : (
                  <input value={(v as string) ?? ""} onChange={(e) => setContenu(ecrire(contenu, c.chemin, e.target.value))}
                    className="rounded-xl bg-groupe px-3 py-2 text-sm outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)]" />
                )}
              </label>
            );
          })}
          {chemins.map((ch, i) => (
            <label key={i} className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-texte-2">Chemin d'attaque {i + 1}</span>
              <textarea rows={2} value={ch.description} onChange={(e) => setContenu({ ...contenu, chemins: chemins.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)) })}
                className="resize-y rounded-xl bg-groupe px-3 py-2 text-sm outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)]" />
            </label>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-1 text-sm leading-snug">
          {champs.map((c) => {
            const v = lire(contenu, c.chemin);
            if (v === undefined || v === "") return null;
            return c.echelle ? (
              <span key={c.libelle} className="text-[13px] text-texte-2">{c.libelle} : {String(v)} ({ECHELLE[v as number]})</span>
            ) : (
              <span key={c.libelle} className={c.zone ? "whitespace-pre-line text-texte-2" : "font-semibold"}>{String(v)}</span>
            );
          })}
          {chemins.length > 0 && (
            <ul className="mt-1 flex list-disc flex-col gap-0.5 pl-5 text-[13px] text-texte-2">
              {chemins.map((ch, i) => <li key={i}>{ch.description}</li>)}
            </ul>
          )}
        </div>
      )}
      {!lectureSeule && (
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={statuer.isPending}
            onClick={() => statuer.mutate({ id: s.id, decision: "valide", contenu: edition ? contenu : undefined })}
            className="bouton-accent h-9 rounded-full px-4 text-[13px] font-semibold">{edition ? "Accepter avec corrections" : "Accepter"}</button>
          {!edition && <button type="button" onClick={() => setEdition(true)} className="h-9 rounded-full bg-groupe px-4 text-[13px] font-semibold">Corriger</button>}
          <button type="button" disabled={statuer.isPending} onClick={() => statuer.mutate({ id: s.id, decision: "rejete" })}
            className="h-9 rounded-full px-3 text-[13px] font-semibold text-texte-2">Rejeter</button>
        </div>
      )}
      {statuer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{statuer.error.message}</p>}
    </li>
  );
}

export function PanneauPropositions({ atelier, projetId, lectureSeule, parents }: {
  atelier: number; projetId: string; lectureSeule: boolean; parents: Record<string, string>;
}) {
  const { data: moi } = useMoi();
  const { data: suggestions = [] } = useSuggestionsEbios(projetId);
  const { data: analyses = [] } = useAnalyses(projetId, "suggestion_ebios");
  const demander = useDemanderSuggestions(projetId);
  const client = useQueryClient();
  const derniere = analyses[0];
  const enCours = Boolean(derniere && (derniere.etat === "en_attente" || derniere.etat === "en_cours"));
  const precedent = useRef(derniere?.etat);
  useEffect(() => {
    if (precedent.current && precedent.current !== derniere?.etat && !enCours) client.invalidateQueries({ queryKey: ["ebios", projetId, "suggestions"] });
    precedent.current = derniere?.etat;
  }, [derniere?.etat, enCours, client, projetId]);

  if (!moi?.organisation.ia_activee || !QUOI[atelier]) return null;
  const siennes = suggestions.filter((s) => s.atelier === atelier);
  const fournisseur = siennes[0]?.fournisseur;

  return (
    <section aria-label="Propositions de l'IA" className="flex flex-col gap-2.5 rounded-groupe bg-groupe px-4 py-3.5 shadow-groupe">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <IconeEtincelle taille={17} className="shrink-0 text-accent-texte" />
        <p role="status" className="min-w-0 flex-1 text-[13px] leading-snug text-texte-2">
          {enCours ? <span className="font-medium text-texte">L'IA prépare ses propositions…</span>
            : siennes.length ? <><span className="font-semibold text-texte">{siennes.length} proposition{siennes.length > 1 ? "s" : ""} à relire</span>
              {fournisseur === "factice" ? " (mode test hors ligne)" : ""} : rien n'est ajouté à l'analyse sans votre accord.</>
            : derniere?.etat === "echec" ? <span className="text-manquant-texte">Dernière demande en échec : {derniere.erreur}</span>
            : `L'IA peut proposer ${QUOI[atelier]}, que vous acceptez, corrigez ou rejetez.`}
        </p>
        {!lectureSeule && siennes.length === 0 && (
          <button type="button" disabled={enCours || demander.isPending} onClick={() => demander.mutate(atelier)}
            className="h-9 shrink-0 rounded-full bg-accent-doux px-4 text-[13px] font-semibold text-accent-texte disabled:opacity-45">
            Proposer avec l'IA
          </button>
        )}
      </div>
      {demander.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{demander.error.message}</p>}
      {siennes.length > 0 && (
        <ul className="flex flex-col gap-2">
          {siennes.map((s) => <Proposition key={s.id} s={s} parent={s.parent_id ? parents[s.parent_id] : undefined} projetId={projetId} lectureSeule={lectureSeule} />)}
        </ul>
      )}
    </section>
  );
}
