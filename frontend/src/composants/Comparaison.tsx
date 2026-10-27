import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { Rapport } from "../api/types";

type Ecart = { avant: number; apres: number; ecart: number | null };
type Mesure = { referentiel: string; identifiant: string; intitule: string; statut: string };
interface Resultat {
  avant: { id: string; version: number; date_donnees: string };
  apres: { id: string; version: number; date_donnees: string };
  chiffres: Record<string, Ecart>;
  referentiels: { code: string; nom: string; nouveau?: boolean; retire?: boolean; taux_conformite?: Ecart; taux_evaluation?: Ecart }[];
  manquements: { apparus: Mesure[]; resolus: Mesure[]; aggraves: Mesure[]; ameliores: Mesure[]; partiel: boolean };
  documents: { intitule: string; avant: string | null; apres: string }[];
  taches: { nouvelles: string[]; sorties: string[] };
  registre: { risques: { intitule: string; avant: string | null; apres: string }[] } | null;
  sections: { cle: string; titre: string; identique: boolean; segments: { type: "egal" | "ajout" | "retrait"; texte: string }[] }[];
}

/** Libellé et sens favorable (hausse = mieux ?) de chaque indicateur comparé. */
const INDICATEURS: [string, string, boolean][] = [
  ["conformite.conforme", "Mesures conformes", true], ["conformite.partiel", "Mesures partielles", false],
  ["conformite.manquant", "Mesures manquantes", false], ["conformite.non_evalue", "Mesures non évaluées", false],
  ["manquements", "Manquements", false], ["taches.ouvertes", "Tâches ouvertes", false], ["taches.en_retard", "Tâches en retard", false],
  ["taches.closes", "Tâches clôturées", true], ["documents.valide", "Documents validés", true], ["documents.attendu", "Documents à déposer", false],
  ["risques.total", "Risques résiduels", false], ["risques.acceptes", "Risques acceptés", true], ["derogations.acceptees", "Dérogations en cours", false],
];
const dateFr = (iso: string) => new Date(iso).toLocaleDateString("fr-FR");

function Delta({ e, mieuxSiHausse, suffixe = "" }: { e: Ecart; mieuxSiHausse: boolean; suffixe?: string }) {
  if (!e.ecart) return <span className="text-texte-3">=</span>;
  const bien = mieuxSiHausse ? e.ecart > 0 : e.ecart < 0;
  return <span className={`font-semibold ${bien ? "text-conforme-texte" : "text-manquant-texte"}`}>{e.ecart > 0 ? "+" : ""}{e.ecart}{suffixe}</span>;
}

function Liste({ titre, elements, vide }: { titre: string; elements: string[]; vide?: string }) {
  if (elements.length === 0 && !vide) return null;
  return (
    <div className="flex flex-col gap-1">
      <h4 className="text-[13px] font-semibold">{titre} <span className="font-normal text-texte-2">· {elements.length}</span></h4>
      {elements.length === 0 ? <p className="text-[13px] text-texte-2">{vide}</p> : (
        <ul className="flex flex-col gap-0.5 text-[13px] text-texte-2">{elements.slice(0, 40).map((x) => <li key={x}>• {x}</li>)}</ul>
      )}
    </div>
  );
}

export function Comparaison({ rapports }: { rapports: Rapport[] }) {
  const tries = [...rapports].sort((a, b) => a.version - b.version);
  const [a, setA] = useState(tries[tries.length - 2]?.id ?? "");
  const [b, setB] = useState(tries[tries.length - 1]?.id ?? "");
  const { data: c, error, isFetching } = useQuery({
    queryKey: ["comparaison", a, b], queryFn: () => api<Resultat>(`/api/rapports/comparer/?a=${a}&b=${b}`), enabled: Boolean(a && b && a !== b),
  });
  const choix = (valeur: string, changer: (v: string) => void, libelle: string) => (
    <select aria-label={libelle} value={valeur} onChange={(e) => changer(e.target.value)} className="rounded-full bg-groupe px-4 py-2 text-[14px] font-semibold shadow-groupe outline-none">
      {tries.map((r) => <option key={r.id} value={r.id}>v{r.version} · {r.statut_validation === "valide" ? "validée" : "brouillon"} · {dateFr(r.cree_le)}</option>)}
    </select>
  );
  const m = c?.manquements;
  const vue = (x: Mesure) => `${x.referentiel} ${x.identifiant} — ${x.intitule}`;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        {choix(a, setA, "Version de référence")}<span className="text-texte-2" aria-hidden="true">→</span>{choix(b, setB, "Version comparée")}
        {isFetching && <span className="text-[13px] text-texte-2">Comparaison…</span>}
      </div>
      {a === b && <p className="text-[14px] text-texte-2">Choisissez deux versions différentes.</p>}
      {error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{error.message}</p>}
      {c && (
        <>
          <p className="text-[13px] text-texte-2">
            Données du {dateFr(c.avant.date_donnees)} (v{c.avant.version}) comparées à celles du {dateFr(c.apres.date_donnees)} (v{c.apres.version}),
            à partir des instantanés figés de chaque version.
          </p>

          <section aria-labelledby="cmp-chiffres" className="overflow-hidden rounded-groupe bg-groupe shadow-groupe">
            <h3 id="cmp-chiffres" className="px-4 pt-4 pb-2 text-[17px] font-bold">Indicateurs</h3>
            <table className="w-full text-[14px]">
              <thead><tr className="text-left text-xs text-texte-2"><th className="px-4 py-2 font-medium">Indicateur</th>
                <th className="px-2 py-2 text-right font-medium">v{c.avant.version}</th><th className="px-2 py-2 text-right font-medium">v{c.apres.version}</th>
                <th className="px-4 py-2 text-right font-medium">Écart</th></tr></thead>
              <tbody className="divide-y divide-separateur">
                {INDICATEURS.filter(([k]) => c.chiffres[k]).map(([k, libelle, sens]) => (
                  <tr key={k}><td className="px-4 py-2">{libelle}</td><td className="px-2 py-2 text-right tabular-nums">{c.chiffres[k].avant}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{c.chiffres[k].apres}</td>
                    <td className="px-4 py-2 text-right tabular-nums"><Delta e={c.chiffres[k]} mieuxSiHausse={sens} /></td></tr>
                ))}
                {c.referentiels.filter((r) => r.taux_conformite).map((r) => (
                  <tr key={r.code}><td className="px-4 py-2">Conformité {r.nom}{r.nouveau ? " (ajouté)" : ""}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{r.taux_conformite!.avant} %</td><td className="px-2 py-2 text-right tabular-nums">{r.taux_conformite!.apres} %</td>
                    <td className="px-4 py-2 text-right tabular-nums"><Delta e={r.taux_conformite!} mieuxSiHausse suffixe=" pt" /></td></tr>
                ))}
              </tbody>
            </table>
          </section>

          <section aria-label="Évolutions" className="grid gap-4 rounded-groupe bg-groupe px-4 py-4 shadow-groupe sm:grid-cols-2">
            <Liste titre="Manquements résolus" elements={m!.resolus.map(vue)} vide="Aucun." />
            <Liste titre="Nouveaux manquements" elements={m!.apparus.map(vue)} vide="Aucun." />
            <Liste titre="Passés de partiel à manquant" elements={m!.aggraves.map(vue)} />
            <Liste titre="Passés de manquant à partiel" elements={m!.ameliores.map(vue)} />
            <Liste titre="Nouvelles tâches ouvertes" elements={c.taches.nouvelles} />
            <Liste titre="Tâches clôturées ou abandonnées" elements={c.taches.sorties} />
            <Liste titre="Documents dont l'état a changé" elements={c.documents.map((d) => `${d.intitule} : ${d.avant ?? "nouveau"} → ${d.apres}`)} />
            {c.registre && <Liste titre="Risques résiduels dont l'état a changé" elements={c.registre.risques.map((r) => `${r.intitule} : ${r.avant ?? "nouveau"} → ${r.apres}`)} />}
            {m!.partiel && <p className="text-xs text-texte-3 sm:col-span-2">Les listes de manquements portent sur les manquements figés dans chaque rapport (80 au plus) : les écarts chiffrés, eux, sont complets.</p>}
          </section>

          <section aria-labelledby="cmp-texte" className="flex flex-col gap-4">
            <h3 id="cmp-texte" className="px-1 text-[17px] font-bold">Texte du rapport <span className="text-[13px] font-normal text-texte-2">· <span className="rounded bg-conforme/20 px-1 text-conforme-texte">ajouté</span> <span className="rounded bg-manquant/15 px-1 text-manquant-texte line-through">retiré</span></span></h3>
            {c.sections.map((s) => (
              <article key={s.cle} aria-label={s.titre} className="flex flex-col gap-1.5 rounded-groupe bg-groupe px-4 py-4 shadow-groupe">
                <h4 className="text-[15px] font-bold">{s.titre} {s.identique && <span className="text-[13px] font-normal text-texte-2">· inchangé</span>}</h4>
                <p className="text-[14px] leading-relaxed whitespace-pre-line">
                  {s.segments.map((x, i) => x.type === "egal" ? <span key={i}>{x.texte}</span>
                    : x.type === "ajout" ? <ins key={i} className="rounded bg-conforme/20 text-conforme-texte no-underline">{x.texte}</ins>
                    : <del key={i} className="rounded bg-manquant/15 text-manquant-texte">{x.texte}</del>)}
                </p>
              </article>
            ))}
          </section>
        </>
      )}
    </div>
  );
}
