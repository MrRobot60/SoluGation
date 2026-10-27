import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router";

import { useEditerRapport, useGenererRapport, useRapports, useTableauDeBord, useValiderRapport } from "../api/hooks";
import type { Rapport, SectionRapport } from "../api/types";
import { Comparaison } from "../composants/Comparaison";
import { Disposition } from "../composants/Disposition";
import { IconeEtincelle, IconeRapports } from "../composants/Icones";
import { quand } from "../lib/format";

const SOURCES: Record<SectionRapport["source"], { libelle: string; classe: string }> = {
  ia: { libelle: "Rédigé par l'IA", classe: "bg-partiel/15 text-partiel-texte" },
  modifie: { libelle: "Relu et modifié", classe: "bg-accent-doux text-accent-texte" },
  automatique: { libelle: "Texte automatique", classe: "bg-remplissage text-texte-2" },
};

function Ecart({ valeur, inverse = false }: { valeur?: number; inverse?: boolean }) {
  if (valeur === undefined || valeur === 0) return null;
  const favorable = inverse ? valeur < 0 : valeur > 0;
  return (
    <span className={`text-xs font-semibold ${favorable ? "text-conforme-texte" : "text-manquant-texte"}`}>
      {valeur > 0 ? "+" : ""}{valeur}<span className="sr-only"> depuis la version précédente</span>
    </span>
  );
}

function Chiffres({ r }: { r: Rapport }) {
  const c = r.chiffres;
  const e = c.evolution ?? undefined;
  const cases = [
    { n: c.conformite.conforme, libelle: "mesures conformes", ecart: <Ecart valeur={e?.conforme} /> },
    { n: c.nb_manquements, libelle: "manquements", ecart: <Ecart valeur={e && e.manquant + e.partiel} inverse /> },
    { n: c.taches_ouvertes, libelle: "tâches ouvertes", ecart: <Ecart valeur={e?.taches_ouvertes} inverse /> },
    { n: `${c.documents_valides} / ${c.documents_total}`, libelle: "documents validés", ecart: <Ecart valeur={e?.documents_valides} /> },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {cases.map((x) => (
        <div key={x.libelle} className="flex flex-col gap-0.5 rounded-2xl bg-remplissage px-3.5 py-3">
          <span className="flex items-baseline gap-2 text-[22px] leading-none font-bold tabular-nums">{x.n} {x.ecart}</span>
          <span className="text-xs text-texte-2">{x.libelle}</span>
        </div>
      ))}
    </div>
  );
}

function Redaction({ r }: { r: Rapport }) {
  const { etat, erreur, fournisseur, modele } = r.redaction;
  if (etat === "en_attente" || etat === "en_cours") {
    return (
      <p role="status" className="flex items-center gap-2 text-[13px] font-medium">
        <span aria-hidden="true" className="size-3.5 animate-spin rounded-full border-2 border-accent border-t-transparent motion-reduce:animate-none" />
        Rédaction par l'IA en cours… le texte automatique s'affiche en attendant.
      </p>
    );
  }
  if (etat === "echec") return <p className="text-[13px] text-manquant-texte">Rédaction IA indisponible ({erreur}) : texte automatique conservé.</p>;
  if (etat === "terminee") {
    return (
      <p className="flex items-center gap-1.5 text-[13px] text-texte-2">
        <IconeEtincelle taille={14} /> Rédigé par l'IA ({fournisseur === "factice" ? "mode test hors ligne" : `${fournisseur}, ${modele}`}) à partir
        des données du projet, sans aucun nom de personne. À relire avant validation.
      </p>
    );
  }
  return <p className="text-[13px] text-texte-2">Rédaction automatique à partir des données (IA désactivée ou non configurée).</p>;
}

function Detail({ r, lectureSeule, peutDecider, projetId }: { r: Rapport; lectureSeule: boolean; peutDecider: boolean; projetId: string }) {
  const editer = useEditerRapport(projetId);
  const valider = useValiderRapport(projetId);
  const [textes, setTextes] = useState<Record<string, string>>({});
  const enCours = r.redaction.etat === "en_attente" || r.redaction.etat === "en_cours";
  const brouillon = r.statut_validation === "a_valider";
  const editable = brouillon && !lectureSeule && !enCours;
  useEffect(() => setTextes(Object.fromEntries(r.sections.map((s) => [s.cle, s.texte]))), [r.id, r.modifie_le]);
  const modifiees = r.sections.filter((s) => (textes[s.cle] ?? s.texte) !== s.texte);
  const alertes = r.sections.reduce((n, s) => n + s.alertes.length, 0);

  return (
    <article aria-labelledby={`titre-v${r.version}`} className="flex flex-col gap-5 rounded-groupe bg-groupe px-4 py-5 shadow-groupe sm:px-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 id={`titre-v${r.version}`} className="text-[22px] font-bold tracking-[-0.02em]">Version {r.version}</h2>
          <p className="text-[13px] text-texte-2">
            Établie par {r.genere_par_nom} {quand(r.cree_le)}
            {r.statut_validation === "valide" && <> · <span className="font-semibold text-conforme-texte">validée par {r.valide_par_nom} {quand(r.valide_le!)}</span></>}
          </p>
        </div>
        <a href={`/api/rapports/${r.id}/pdf/`} download
          className={`flex h-10 items-center rounded-full px-4 text-[14px] font-semibold ${brouillon ? "bg-remplissage" : "bouton-accent"}`}>
          {brouillon ? "Aperçu PDF (brouillon)" : "Télécharger le PDF"}
        </a>
      </header>

      <Redaction r={r} />
      <Chiffres r={r} />
      {r.chiffres.evolution && Object.values(r.chiffres.evolution).some(Boolean) && (
        <p className="-mt-3 text-xs text-texte-3">Écarts mesurés depuis la version précédente.</p>
      )}

      {r.sections.map((s) => (
        <section key={s.cle} aria-labelledby={`s-${r.id}-${s.cle}`} className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 id={`s-${r.id}-${s.cle}`} className="text-[17px] font-bold">{s.titre}</h3>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${SOURCES[s.source].classe}`}>{SOURCES[s.source].libelle}</span>
          </div>
          {s.alertes.length > 0 && (
            <p className="text-[13px] font-medium text-partiel-texte">
              Chiffre{s.alertes.length > 1 ? "s" : ""} absent{s.alertes.length > 1 ? "s" : ""} des données du projet : {s.alertes.join(", ")}. À vérifier.
            </p>
          )}
          {editable ? (
            <textarea aria-label={`Texte de la section ${s.titre}`} value={textes[s.cle] ?? s.texte} rows={Math.min(14, Math.max(3, Math.ceil((textes[s.cle] ?? s.texte).length / 90)))}
              onChange={(e) => setTextes({ ...textes, [s.cle]: e.target.value })}
              className="resize-y rounded-2xl bg-remplissage px-3.5 py-3 text-[15px] leading-relaxed outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)]" />
          ) : (
            <p className="text-[15px] leading-relaxed whitespace-pre-line">{s.texte}</p>
          )}
        </section>
      ))}

      {brouillon && !lectureSeule && (
        <footer className="flex flex-col gap-2 border-t border-separateur pt-4">
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" disabled={modifiees.length === 0 || editer.isPending || enCours}
              onClick={() => editer.mutate({ id: r.id, sections: modifiees.map((s) => ({ cle: s.cle, texte: textes[s.cle] })) })}
              className="h-11 rounded-full bg-remplissage px-5 text-[15px] font-semibold disabled:opacity-45">
              {editer.isPending ? "Enregistrement…" : "Enregistrer les modifications"}
            </button>
            {peutDecider && (
              <button type="button" disabled={modifiees.length > 0 || valider.isPending || enCours} onClick={() => valider.mutate(r.id)}
                className="bouton-accent h-11 rounded-full px-5 text-[15px] font-semibold disabled:opacity-45">
                {valider.isPending ? "Génération du PDF…" : "Valider et figer le PDF"}
              </button>
            )}
          </div>
          <p className="text-xs text-texte-2">
            {peutDecider
              ? `Une fois validé, le texte n'est plus modifiable et le PDF est figé avec son empreinte SHA-256.${alertes ? " Des chiffres restent à vérifier." : ""}`
              : "La validation revient au RSSI, à l'autorité d'homologation ou à l'administrateur."}
          </p>
          {(editer.error || valider.error) && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{(editer.error ?? valider.error)!.message}</p>}
        </footer>
      )}
      {r.sha256_pdf && <p className="font-mono text-[11px] break-all text-texte-3">SHA-256 du PDF : {r.sha256_pdf}</p>}
    </article>
  );
}

export function PageRapports() {
  const { projetId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { data: tdb } = useTableauDeBord(projetId);
  const { data: rapports = [], isPending } = useRapports(projetId);
  const generer = useGenererRapport(projetId);
  const lectureSeule = tdb?.projet.lecture_seule ?? true;
  const peutDecider = tdb?.projet.peut_decider ?? false;
  const choisi = rapports.find((r) => r.id === params.get("version")) ?? rapports[0];
  const derniereValidee = rapports.find((r) => r.statut_validation === "valide");

  return (
    <Disposition>
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-end justify-between gap-4 lg:pt-2.5">
          <div className="flex flex-col gap-1.5">
            <span className="text-[13px] font-semibold text-texte-2">{tdb?.projet.nom ?? "Projet"}</span>
            <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Rapports</h1>
            <p className="text-[15px] text-texte-2">
              {rapports.length === 0 ? "Aucun état des lieux pour le moment" : `${rapports.length} version${rapports.length > 1 ? "s" : ""}`}
              {derniereValidee && ` · dernière validée : v${derniereValidee.version}`}
            </p>
          </div>
          {!lectureSeule && (
            <button type="button" disabled={generer.isPending}
              onClick={() => generer.mutate(undefined, { onSuccess: (r) => setParams({ version: r.id }) })}
              className="bouton-accent flex h-[50px] items-center gap-2 rounded-full px-[22px] text-[15px] font-semibold disabled:opacity-45">
              <IconeRapports taille={17} /> {generer.isPending ? "Préparation…" : "Générer un état des lieux"}
            </button>
          )}
        </div>
        {generer.data?.avertissement && <p className="text-[13px] font-medium text-partiel-texte">{generer.data.avertissement}</p>}
        {generer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{generer.error.message}</p>}

        {rapports.length > 1 && (
          <div role="radiogroup" aria-label="Affichage" className="flex self-start rounded-full bg-remplissage p-[3px]">
            {[{ cle: "", libelle: "Une version" }, { cle: "comparer", libelle: "Comparer deux versions" }].map((m) => (
              <button key={m.cle} type="button" role="radio" aria-checked={(params.get("mode") ?? "") === m.cle}
                onClick={() => setParams(m.cle ? { mode: m.cle } : choisi ? { version: choisi.id } : {})}
                className={`rounded-full px-4 py-1.5 text-[13px] ${(params.get("mode") ?? "") === m.cle ? "bg-groupe font-semibold shadow-groupe" : "font-medium text-texte-2"}`}>{m.libelle}</button>
            ))}
          </div>
        )}

        {params.get("mode") === "comparer" && rapports.length > 1 ? <Comparaison rapports={rapports} /> : <>
        {rapports.length > 1 && (
          <div role="tablist" aria-label="Versions du rapport" className="flex self-start overflow-x-auto rounded-full bg-remplissage p-[3px]">
            {rapports.map((r) => (
              <button key={r.id} type="button" role="tab" aria-selected={r.id === choisi?.id} onClick={() => setParams({ version: r.id })}
                className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[13px] whitespace-nowrap ${r.id === choisi?.id ? "bg-groupe font-semibold shadow-groupe" : "font-medium text-texte-2"}`}>
                v{r.version}
                <span className={`text-[11px] ${r.statut_validation === "valide" ? "text-conforme-texte" : "text-texte-3"}`}>
                  {r.statut_validation === "valide" ? "validée" : "brouillon"}
                </span>
              </button>
            ))}
          </div>
        )}

        {isPending ? (
          <div aria-busy="true" className="h-96 animate-pulse rounded-groupe bg-remplissage" />
        ) : choisi ? (
          <Detail key={choisi.id} r={choisi} lectureSeule={lectureSeule} peutDecider={peutDecider} projetId={projetId} />
        ) : (
          <p className="rounded-groupe bg-groupe px-4 py-8 text-center text-[15px] text-texte-2 shadow-groupe">
            L'état des lieux fige les données du projet à une date, en fait rédiger la synthèse par l'IA puis produit un PDF
            que vous relisez et validez.
          </p>
        )}
        </>}
      </div>
    </Disposition>
  );
}
