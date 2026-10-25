import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import {
  useDeposerPreuve, useDocumentsAttendus, useEvaluations, useEvaluer, useMesures, usePreuves, useResultatsIA,
  useStatuerIA, useTableauDeBord,
} from "../api/hooks";
import type { DocumentAttendu, EvaluationMesure, Mesure, Preuve, ResultatIA, StatutConformite } from "../api/types";
import { erreurClient, Progression, taille, ZoneDepot, type Envoi } from "../composants/Depot";
import { Disposition } from "../composants/Disposition";
import { Chevron, IconeEtincelle, IconeRecherche } from "../composants/Icones";
import { COUVERTURE, nomCourt, STATUTS } from "../composants/statuts";
import { quand } from "../lib/format";

const EVALUABLES: StatutConformite[] = ["conforme", "partiel", "manquant", "non_applicable"];
const STYLE: Record<StatutConformite, { texte: string; point: string }> = {
  conforme: { texte: "text-conforme-texte", point: "bg-conforme" },
  partiel: { texte: "text-partiel-texte", point: "bg-partiel" },
  manquant: { texte: "text-manquant-texte", point: "bg-manquant" },
  non_applicable: { texte: "text-na-texte", point: "bg-na" },
  non_evalue: { texte: "text-texte-2", point: "border-[1.5px] border-texte-3" },
};
const libelle = (s: StatutConformite) => STATUTS.find((x) => x.cle === s)!.libelle;

/* ---- Détail d'une mesure ------------------------------------------------------------------ */

function TexteOfficiel({ texte }: { texte: string }) {
  const [tout, setTout] = useState(false);
  const long = texte.length > 420;
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-semibold text-texte-2">Texte de la mesure</span>
      <p className="text-sm leading-relaxed whitespace-pre-line">{long && !tout ? `${texte.slice(0, 420).trimEnd()}…` : texte}</p>
      {long && (
        <button type="button" onClick={() => setTout(!tout)} className="self-start py-1 text-[13px] font-semibold text-accent-texte">
          {tout ? "Réduire" : "Afficher tout"}
        </button>
      )}
    </div>
  );
}

function Evaluation({ mesure, evaluation, projetId, lectureSeule }: {
  mesure: Mesure; evaluation?: EvaluationMesure; projetId: string; lectureSeule: boolean;
}) {
  const evaluer = useEvaluer(projetId);
  const [statut, setStatut] = useState<StatutConformite>(evaluation?.statut ?? "non_evalue");
  const [justification, setJustification] = useState(evaluation?.justification ?? "");
  useEffect(() => {
    setStatut(evaluation?.statut ?? "non_evalue");
    setJustification(evaluation?.justification ?? "");
  }, [evaluation?.statut, evaluation?.justification]);
  const modifie = statut !== (evaluation?.statut ?? "non_evalue") || justification !== (evaluation?.justification ?? "");
  const justificationRequise = (statut === "non_applicable" || statut === "partiel") && !justification.trim();

  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-xs font-semibold text-texte-2">Évaluation</span>
      <div role="radiogroup" aria-label="Statut de conformité" className="flex flex-wrap gap-1.5">
        {EVALUABLES.map((s) => (
          <button key={s} type="button" role="radio" aria-checked={statut === s} disabled={lectureSeule} onClick={() => setStatut(s)}
            className={`flex h-9 items-center gap-1.5 rounded-full px-3.5 text-[13px] font-semibold transition-colors duration-200 ease-ios disabled:cursor-default ${statut === s ? "bg-groupe shadow-[0_0_0_1.5px_var(--sg-accent)]" : "bg-remplissage text-texte-2"}`}>
            <span aria-hidden="true" className={`size-2 rounded-full ${STYLE[s].point}`} />
            {libelle(s)}
          </button>
        ))}
      </div>
      <label className="flex flex-col gap-1 rounded-2xl bg-remplissage px-3.5 pt-2 pb-2.5">
        <span className="text-xs font-medium text-texte-2">
          Justification{justificationRequise ? " (requise pour « partiel » ou « non applicable »)" : ""}
        </span>
        <textarea rows={2} value={justification} disabled={lectureSeule} onChange={(e) => setJustification(e.target.value)}
          placeholder="Constat, écart, référence de la preuve…"
          className="resize-y bg-transparent text-[15px] outline-none placeholder:text-texte-3" />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        {!lectureSeule && (
          <button type="button" disabled={!modifie || statut === "non_evalue" || justificationRequise || evaluer.isPending}
            onClick={() => evaluer.mutate({ existante: evaluation, mesure: mesure.id, statut, justification })}
            className="bouton-accent h-10 rounded-full px-5 text-[14px] font-semibold disabled:opacity-45">
            {evaluer.isPending ? "Enregistrement…" : "Enregistrer"}
          </button>
        )}
        {evaluation?.evalue_le && (
          <span className="text-xs text-texte-2">
            Évaluée par {evaluation.evalue_par_nom || "—"} · {quand(evaluation.evalue_le)}
            {evaluation.resultat_analyse ? " · d'après une proposition de l'IA validée" : ""}
          </span>
        )}
      </div>
      {evaluer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{evaluer.error.message}</p>}
    </div>
  );
}

function PropositionIA({ r, projetId, peutDecider }: { r: ResultatIA; projetId: string; peutDecider: boolean }) {
  const statuer = useStatuerIA(projetId);
  const c = COUVERTURE[r.couverture];
  return (
    <div className="flex flex-col gap-2.5 rounded-2xl bg-partiel/10 px-3.5 py-3">
      <span className="flex items-center gap-1.5 text-xs font-semibold text-partiel-texte">
        <IconeEtincelle taille={15} /> Proposition de l'IA, à valider
      </span>
      <p className="text-sm leading-relaxed">
        <span className={`font-semibold ${c.texte}`}>{c.libelle}</span>
        {r.document_nom ? ` d'après « ${r.document_nom} »` : ""} : {r.justification}
      </p>
      {peutDecider ? (
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={statuer.isPending} onClick={() => statuer.mutate({ id: r.id, decision: "valide" })}
            className="bouton-accent h-9 rounded-full px-4 text-[13px] font-semibold">Accepter</button>
          <button type="button" disabled={statuer.isPending} onClick={() => statuer.mutate({ id: r.id, decision: "rejete" })}
            className="h-9 rounded-full bg-remplissage px-4 text-[13px] font-semibold">Rejeter</button>
        </div>
      ) : (
        <p className="text-[13px] text-texte-2">En attente de décision du RSSI ou de l'autorité d'homologation.</p>
      )}
      {statuer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{statuer.error.message}</p>}
    </div>
  );
}

function Preuves({ mesure, preuves, projetId, lectureSeule }: {
  mesure: Mesure; preuves: Preuve[]; projetId: string; lectureSeule: boolean;
}) {
  const deposer = useDeposerPreuve(projetId);
  const [envoi, setEnvoi] = useState<Envoi | null>(null);
  const series = useMemo(() => {
    const parSerie = new Map<string, Preuve[]>();
    for (const p of preuves) parSerie.set(p.serie, [...(parSerie.get(p.serie) ?? []), p]);
    return [...parSerie.values()].map((v) => v.sort((a, b) => b.version - a.version));
  }, [preuves]);

  const envoyer = (fichier: File, serie?: Preuve[]) => {
    const erreur = erreurClient(fichier);
    if (erreur) return setEnvoi({ progression: 0, erreur, nom: fichier.name });
    setEnvoi({ progression: 0, nom: fichier.name });
    deposer.mutate(
      {
        fichier,
        serie: serie?.[0].serie,
        titre: serie?.[0].titre ?? fichier.name.replace(/\.[^.]+$/, ""),
        mesures: serie?.[0].mesures ?? [mesure.id],
        surProgression: (p) => setEnvoi((e) => e && { ...e, progression: p }),
      },
      { onSuccess: () => setEnvoi(null), onError: (err) => setEnvoi({ progression: 0, erreur: err.message, nom: fichier.name }) },
    );
  };

  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-xs font-semibold text-texte-2">Preuves</span>
      {series.length === 0 && <p className="text-sm text-texte-2">Aucune preuve rattachée.</p>}
      <ul className="flex flex-col gap-2">
        {series.map((versions) => {
          const p = versions[0];
          return (
            <li key={p.serie} className="flex flex-col gap-2 rounded-2xl bg-remplissage px-3.5 py-3">
              <div className="flex items-center gap-3">
                <span className="flex min-w-0 flex-1 flex-col gap-px">
                  <span className="truncate text-sm font-semibold">{p.titre} <span className="font-medium text-texte-2">· v{p.version}</span></span>
                  <span className="text-xs text-texte-2">{p.nom_original} · {taille(p.taille)} · {p.depose_par_nom} · {quand(p.depose_le)}</span>
                  <span className="truncate font-mono text-[11px] text-texte-3" title={`SHA-256 : ${p.sha256}`}>SHA-256 {p.sha256.slice(0, 16)}…</span>
                </span>
                <a href={`/api/preuves/${p.id}/telecharger/`} download className="shrink-0 rounded-full bg-groupe px-3.5 py-2 text-[13px] font-semibold text-accent-texte shadow-groupe">
                  Télécharger
                </a>
              </div>
              {versions.length > 1 && (
                <details className="text-xs text-texte-2">
                  <summary className="cursor-pointer font-medium">Versions antérieures ({versions.length - 1})</summary>
                  <ul className="mt-1.5 flex flex-col gap-1">
                    {versions.slice(1).map((v) => (
                      <li key={v.id} className="flex items-center justify-between gap-2">
                        <span>v{v.version} · {v.nom_original} · {quand(v.depose_le)}</span>
                        <a href={`/api/preuves/${v.id}/telecharger/`} download className="font-semibold text-accent-texte">Télécharger</a>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {!lectureSeule && (
                <ZoneDepot compacte surFichier={(f) => envoyer(f, versions)} libelle={`Nouvelle version (v${p.version + 1}) : glissez un fichier ou`} />
              )}
            </li>
          );
        })}
      </ul>
      {envoi && <Progression envoi={envoi} surFermer={() => setEnvoi(null)} />}
      {!lectureSeule && <ZoneDepot compacte surFichier={(f) => envoyer(f)} libelle="Ajouter une preuve : glissez un fichier ou" />}
    </div>
  );
}

function LigneMesure({ m, evaluation, proposition, preuves, documents, ouvert, basculer, projetId, lectureSeule, peutDecider }: {
  m: Mesure; evaluation?: EvaluationMesure; proposition?: ResultatIA; preuves: Preuve[]; documents: DocumentAttendu[];
  ouvert: boolean; basculer: () => void; projetId: string; lectureSeule: boolean; peutDecider: boolean;
}) {
  const statut: StatutConformite = evaluation?.statut ?? "non_evalue";
  const nbSeries = new Set(preuves.map((p) => p.serie)).size;
  return (
    <li>
      <button type="button" onClick={basculer} aria-expanded={ouvert} aria-controls={`mesure-${m.id}`}
        className="flex min-h-[60px] w-full items-center gap-3.5 px-4 py-2.5 text-left hover:bg-remplissage">
        <span className="w-[74px] shrink-0 text-[13px] font-semibold text-texte-2 tabular-nums">{m.identifiant}</span>
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="line-clamp-2 text-[15px] leading-snug">{m.intitule}</span>
          <span className="flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-[13px]">
            <span className={`flex items-center gap-1.5 font-semibold ${STYLE[statut].texte}`}>
              <span aria-hidden="true" className={`size-2 rounded-full ${STYLE[statut].point}`} />{libelle(statut)}
            </span>
            {nbSeries > 0 && <span className="text-texte-2">{nbSeries} preuve{nbSeries > 1 ? "s" : ""}</span>}
            {proposition && <span className="flex items-center gap-1 font-semibold text-partiel-texte"><IconeEtincelle taille={13} />IA à valider</span>}
          </span>
        </span>
        <span className={`transition-transform duration-200 ease-ios ${ouvert ? "rotate-90" : ""}`}><Chevron /></span>
      </button>
      {ouvert && (
        <div id={`mesure-${m.id}`} className="flex flex-col gap-5 border-t border-separateur px-4 pt-4 pb-5 sm:pl-[106px]">
          {m.texte_officiel && <TexteOfficiel texte={m.texte_officiel} />}
          {proposition && <PropositionIA r={proposition} projetId={projetId} peutDecider={peutDecider} />}
          <Evaluation mesure={m} evaluation={evaluation} projetId={projetId} lectureSeule={lectureSeule} />
          <Preuves mesure={m} preuves={preuves} projetId={projetId} lectureSeule={lectureSeule} />
          {documents.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold text-texte-2">Documents de la checklist qui couvrent cette mesure</span>
              <ul className="flex flex-wrap gap-1.5">
                {documents.map((d) => (
                  <li key={d.id}>
                    <Link to={`/projets/${projetId}/documents`} className="block rounded-full bg-remplissage px-3 py-1.5 text-[13px] font-medium">
                      {d.intitule}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

/* ---- Page --------------------------------------------------------------------------------- */

const FILTRES: { cle: string; libelle: string; garde: (s: StatutConformite, ia: boolean) => boolean }[] = [
  { cle: "toutes", libelle: "Toutes", garde: () => true },
  { cle: "non_evalue", libelle: "Non évaluées", garde: (s) => s === "non_evalue" },
  { cle: "manquant", libelle: "Manquantes", garde: (s) => s === "manquant" },
  { cle: "partiel", libelle: "Partielles", garde: (s) => s === "partiel" },
  { cle: "conforme", libelle: "Conformes", garde: (s) => s === "conforme" },
  { cle: "non_applicable", libelle: "Non applicables", garde: (s) => s === "non_applicable" },
  { cle: "ia", libelle: "IA à valider", garde: (_, ia) => ia },
];

export function PageMesures() {
  const { projetId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { data: tdb } = useTableauDeBord(projetId);
  const referentiels = tdb?.referentiels ?? [];
  const refId = params.get("referentiel") ?? referentiels[0]?.id;
  const { data: mesures = [], isPending } = useMesures(refId);
  const { data: evaluations = [] } = useEvaluations(projetId);
  const { data: preuves = [] } = usePreuves(projetId);
  const { data: propositions = [] } = useResultatsIA(projetId);
  const { data: documents = [] } = useDocumentsAttendus(projetId);
  const [filtre, setFiltre] = useState(params.get("filtre") ?? "toutes");
  const [recherche, setRecherche] = useState("");
  const [ouvert, setOuvert] = useState<string | null>(null);
  const lectureSeule = tdb?.projet.lecture_seule ?? true;
  const peutDecider = tdb?.projet.peut_decider ?? false;

  const index = useMemo(() => ({
    evaluation: new Map(evaluations.map((e) => [e.mesure, e])),
    proposition: new Map(propositions.map((p) => [p.mesure, p])),
    preuves: (id: string) => preuves.filter((p) => p.mesures.includes(id)),
    documents: (id: string) => documents.filter((d) => d.mesures_couvertes.some((m) => m.id === id)),
  }), [evaluations, propositions, preuves, documents]);

  const statutDe = (m: Mesure): StatutConformite => index.evaluation.get(m.id)?.statut ?? "non_evalue";
  const q = recherche.trim().toLowerCase();
  const correspond = (m: Mesure) => !q || m.identifiant.toLowerCase().includes(q) || m.intitule.toLowerCase().includes(q);
  const garde = FILTRES.find((f) => f.cle === filtre)!.garde;
  const visibles = mesures.filter((m) => correspond(m) && garde(statutDe(m), index.proposition.has(m.id)));
  const categories = useMemo(() => {
    const groupes = new Map<string, Mesure[]>();
    for (const m of visibles) groupes.set(m.categorie || "Sans catégorie", [...(groupes.get(m.categorie || "Sans catégorie") ?? []), m]);
    return [...groupes.entries()];
  }, [visibles]);

  const ref = referentiels.find((r) => r.id === refId);
  const evaluees = mesures.filter((m) => statutDe(m) !== "non_evalue").length;
  const conformes = mesures.filter((m) => statutDe(m) === "conforme").length;
  const choisirRef = (id: string) => { setParams({ referentiel: id }); setOuvert(null); };

  return (
    <Disposition>
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5 lg:pt-2.5">
          <span className="text-[13px] font-semibold text-texte-2">{tdb?.projet.nom ?? "Projet"}</span>
          <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Mesures</h1>
          {ref && (
            <p className="text-[15px] text-texte-2">
              {ref.nom} · {evaluees} évaluées sur {mesures.length} · {conformes} conformes
            </p>
          )}
        </div>

        <div role="tablist" aria-label="Référentiel" className="flex self-start overflow-x-auto rounded-full bg-remplissage p-[3px]">
          {referentiels.map((r) => (
            <button key={r.id} type="button" role="tab" aria-selected={r.id === refId} onClick={() => choisirRef(r.id)}
              className={`rounded-full px-4 py-1.5 text-[13px] whitespace-nowrap transition-colors duration-200 ease-ios ${r.id === refId ? "bg-groupe font-semibold shadow-groupe" : "font-medium text-texte-2"}`}>
              {nomCourt(r)}
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-3">
          <label className="flex h-11 items-center gap-2.5 rounded-full bg-groupe px-4 shadow-groupe">
            <IconeRecherche taille={17} className="shrink-0 text-texte-2" />
            <span className="sr-only">Rechercher une mesure</span>
            <input type="search" value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder="Identifiant ou intitulé"
              className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-texte-3" />
          </label>
          <div role="radiogroup" aria-label="Filtrer par statut" className="flex flex-wrap gap-1.5">
            {FILTRES.map((f) => {
              const n = mesures.filter((m) => correspond(m) && f.garde(statutDe(m), index.proposition.has(m.id))).length;
              if (f.cle === "ia" && n === 0) return null;
              return (
                <button key={f.cle} type="button" role="radio" aria-checked={filtre === f.cle} onClick={() => setFiltre(f.cle)}
                  className={`h-8 rounded-full px-3 text-[13px] whitespace-nowrap transition-colors duration-200 ease-ios ${filtre === f.cle ? "bg-accent text-white font-semibold" : "bg-remplissage font-medium text-texte-2"}`}>
                  {f.libelle} {n}
                </button>
              );
            })}
          </div>
        </div>

        {isPending || !ref ? (
          <div aria-busy="true" className="h-96 animate-pulse rounded-groupe bg-remplissage" />
        ) : visibles.length === 0 ? (
          <p className="rounded-groupe bg-groupe px-4 py-6 text-center text-[15px] text-texte-2 shadow-groupe">Aucune mesure ne correspond.</p>
        ) : (
          <div className="flex flex-col gap-6">
            {categories.map(([categorie, liste]) => (
              <section key={categorie} aria-label={categorie} className="flex flex-col gap-2">
                <h2 className="px-1 text-[13px] font-semibold text-texte-2">{categorie} <span className="font-normal">· {liste.length}</span></h2>
                <ul className="divide-y divide-separateur overflow-hidden rounded-groupe bg-groupe shadow-groupe">
                  {liste.map((m) => (
                    <LigneMesure key={m.id} m={m} evaluation={index.evaluation.get(m.id)} proposition={index.proposition.get(m.id)}
                      preuves={index.preuves(m.id)} documents={index.documents(m.id)} ouvert={ouvert === m.id}
                      basculer={() => setOuvert(ouvert === m.id ? null : m.id)} projetId={projetId}
                      lectureSeule={lectureSeule} peutDecider={peutDecider} />
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </div>
    </Disposition>
  );
}
