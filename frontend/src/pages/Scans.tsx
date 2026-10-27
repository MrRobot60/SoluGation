import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { useConstatsScan, useCreerTachesScan, useImporterScan, useImportsScans, useStatuerConstat, useTableauDeBord } from "../api/hooks";
import type { ConstatScan, Severite } from "../api/types";
import { erreurClient, Progression, ZoneDepot, type Envoi } from "../composants/Depot";
import { Disposition } from "../composants/Disposition";
import { Chevron } from "../composants/Icones";
import { quand } from "../lib/format";

const SEVERITES: { cle: Severite; libelle: string; classe: string }[] = [
  { cle: "critique", libelle: "Critique", classe: "bg-manquant text-white" },
  { cle: "haute", libelle: "Haute", classe: "bg-manquant/20 text-manquant-texte" },
  { cle: "moyenne", libelle: "Moyenne", classe: "bg-partiel/20 text-partiel-texte" },
  { cle: "faible", libelle: "Faible", classe: "bg-conforme/15 text-conforme-texte" },
  { cle: "info", libelle: "Info", classe: "bg-remplissage text-texte-2" },
];
const STATUTS: Record<ConstatScan["statut"], string> = { ouvert: "Ouvert", traite: "Traité", faux_positif: "Faux positif", accepte: "Risque accepté" };
const sev = (s: Severite) => SEVERITES.find((x) => x.cle === s)!;

type Groupe = { id: string; tete: ConstatScan; constats: ConstatScan[] };

function Vulnerabilite({ g, projetId, choisi, basculer, peutEcrire, peutDecider }: {
  g: Groupe; projetId: string; choisi: boolean; basculer: () => void; peutEcrire: boolean; peutDecider: boolean;
}) {
  const statuer = useStatuerConstat(projetId);
  const [ouvert, setOuvert] = useState(false);
  const [mode, setMode] = useState<"faux_positif" | "accepte" | null>(null);
  const [commentaire, setCommentaire] = useState("");
  const t = g.tete;
  const s = sev(t.severite);
  const hotes = g.constats.map((c) => `${c.hote}${c.port ? `:${c.port}` : ""}`);
  const ouverts = g.constats.filter((c) => c.statut === "ouvert").length;
  const selectionnable = peutEcrire && ouverts > 0 && !t.a_une_tache && t.severite !== "info";

  return (
    <li className="flex flex-col">
      <div className="flex items-start gap-3 px-4 py-3">
        {peutEcrire && (
          <input type="checkbox" aria-label={`Sélectionner ${t.titre}`} checked={choisi} disabled={!selectionnable} onChange={basculer}
            className="mt-1 size-5 shrink-0 accent-[var(--sg-accent)] disabled:opacity-30" />
        )}
        <button type="button" onClick={() => setOuvert(!ouvert)} aria-expanded={ouvert} className="flex min-w-0 flex-1 items-start gap-3 text-left">
          <span className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold ${s.classe}`}>{s.libelle}</span>
          <span className="flex min-w-0 flex-1 flex-col gap-0.5">
            <span className="text-[15px] leading-snug font-medium">{t.titre}</span>
            <span className="text-[13px] text-texte-2">
              {t.cvss ? `CVSS ${t.cvss} · ` : ""}{g.constats.length} hôte(s){t.cve.length ? ` · ${t.cve.length} CVE` : ""}
              {ouverts < g.constats.length ? ` · ${g.constats.length - ouverts} qualifié(s)` : ""}
              {t.a_une_tache && <span className="font-semibold text-accent-texte"> · tâche en cours</span>}
              {t.statut !== "ouvert" && <span className="font-semibold"> · {STATUTS[t.statut]}</span>}
            </span>
          </span>
          <span className={`mt-1 transition-transform duration-200 ease-ios ${ouvert ? "rotate-90" : ""}`}><Chevron /></span>
        </button>
      </div>
      {ouvert && (
        <div className="flex flex-col gap-3 border-t border-separateur px-4 pt-3 pb-4 sm:pl-12">
          <p className="text-[13px] text-texte-2"><span className="font-semibold text-texte">Hôtes : </span>{hotes.join(", ")}</p>
          {t.cve.length > 0 && <p className="text-[13px] text-texte-2"><span className="font-semibold text-texte">CVE : </span>{t.cve.join(", ")}</p>}
          {t.description && <p className="text-sm leading-relaxed whitespace-pre-line">{t.description.slice(0, 1200)}</p>}
          {t.solution && <p className="text-sm leading-relaxed whitespace-pre-line"><span className="font-semibold">Solution : </span>{t.solution.slice(0, 1200)}</p>}
          {t.commentaire_statut && <p className="text-[13px] text-texte-2">{STATUTS[t.statut]} par {t.statut_par_nom} : « {t.commentaire_statut} »</p>}
          {peutEcrire && !mode && (
            <div className="flex flex-wrap gap-2">
              {t.statut !== "faux_positif" && <button type="button" onClick={() => setMode("faux_positif")} className="h-8 rounded-full bg-remplissage px-3.5 text-[13px] font-semibold">Faux positif</button>}
              {peutDecider && t.statut !== "accepte" && <button type="button" onClick={() => setMode("accepte")} className="h-8 rounded-full bg-remplissage px-3.5 text-[13px] font-semibold">Accepter le risque</button>}
              {t.statut !== "ouvert" && (
                <button type="button" onClick={() => statuer.mutate({ id: t.id, statut: "ouvert", tous_les_hotes: true })} className="h-8 rounded-full bg-remplissage px-3.5 text-[13px] font-semibold">Rouvrir</button>
              )}
            </div>
          )}
          {mode && (
            <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); statuer.mutate({ id: t.id, statut: mode, commentaire, tous_les_hotes: true }, { onSuccess: () => setMode(null) }); }}>
              <label className="flex flex-col gap-1">
                <span className="text-xs font-semibold text-texte-2">Justification (obligatoire, pour les {g.constats.length} hôte(s))</span>
                <textarea rows={2} value={commentaire} onChange={(e) => setCommentaire(e.target.value)} className="resize-y rounded-xl bg-remplissage px-3 py-2 text-sm outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)]" />
              </label>
              <div className="flex gap-2">
                <button type="submit" disabled={!commentaire.trim() || statuer.isPending} className="bouton-accent h-9 rounded-full px-4 text-[13px] font-semibold disabled:opacity-45">Confirmer</button>
                <button type="button" onClick={() => setMode(null)} className="h-9 px-3 text-[13px] text-texte-2">Annuler</button>
              </div>
            </form>
          )}
          {statuer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{statuer.error.message}</p>}
        </div>
      )}
    </li>
  );
}

export function PageScans() {
  const { projetId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { data: tdb } = useTableauDeBord(projetId);
  const { data: imports = [] } = useImportsScans(projetId);
  const importer = useImporterScan(projetId);
  const creer = useCreerTachesScan(projetId);
  const [envoi, setEnvoi] = useState<Envoi | null>(null);
  const [filtre, setFiltre] = useState<Severite | "tous">("tous");
  const [masquerQualifies, setMasquerQualifies] = useState(true);
  const [choix, setChoix] = useState<Set<string>>(new Set());
  const lectureSeule = tdb?.projet.lecture_seule ?? true;
  const courant = imports.find((i) => i.id === params.get("import")) ?? imports.find((i) => i.etat === "traite");
  const { data: constats = [], isPending } = useConstatsScan(projetId, courant?.id);

  const groupes = useMemo(() => {
    const parId = new Map<string, ConstatScan[]>();
    for (const c of constats) parId.set(c.identifiant_outil, [...(parId.get(c.identifiant_outil) ?? []), c]);
    const ordre = SEVERITES.map((s) => s.cle);
    return [...parId.entries()].map(([id, liste]) => ({ id, tete: liste[0], constats: liste }))
      .sort((a, b) => ordre.indexOf(a.tete.severite) - ordre.indexOf(b.tete.severite) || Number(b.tete.cvss ?? 0) - Number(a.tete.cvss ?? 0));
  }, [constats]);
  const visibles = groupes.filter((g) => (filtre === "tous" || g.tete.severite === filtre) && (!masquerQualifies || g.constats.some((c) => c.statut === "ouvert")));

  const envoyer = (fichier: File) => {
    const erreur = erreurClient(fichier);
    if (erreur) return setEnvoi({ progression: 0, erreur, nom: fichier.name });
    setEnvoi({ progression: 0, nom: fichier.name });
    importer.mutate({ fichier, surProgression: (p) => setEnvoi((e) => e && { ...e, progression: p }) }, {
      onSuccess: (i) => { setEnvoi(null); setParams({ import: i.id }); setChoix(new Set()); },
      onError: (e) => setEnvoi({ progression: 0, erreur: e.message, nom: fichier.name }),
    });
  };
  const b = courant?.bilan;

  return (
    <Disposition>
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5 lg:pt-2.5">
          <span className="text-[13px] font-semibold text-texte-2">{tdb?.projet.nom ?? "Projet"}</span>
          <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Scans de vulnérabilités</h1>
          <p className="max-w-[720px] text-[15px] text-texte-2">
            Importez un rapport Nessus (.nessus), OpenVAS (.xml) ou un export CSV (Cyberwatch…). Les constats sont comparés au scan précédent ;
            vous choisissez ensuite ceux qui deviennent des tâches du plan d'action.
          </p>
        </div>

        {!lectureSeule && (
          <div className="flex flex-col gap-2 rounded-groupe bg-groupe px-4 py-4 shadow-groupe">
            <ZoneDepot surFichier={envoyer} libelle="Glissez ici un rapport de scan, ou" />
            {envoi && <Progression envoi={envoi} surFermer={() => setEnvoi(null)} />}
            <p className="text-xs text-texte-3">Le rapport est conservé dans le coffre, empreinté (SHA-256). Les XML sont lus sans entités externes.</p>
          </div>
        )}

        {imports.length > 0 && (
          <div role="tablist" aria-label="Rapports importés" className="flex flex-wrap gap-1.5">
            {imports.map((i) => (
              <button key={i.id} type="button" role="tab" aria-selected={i.id === courant?.id} disabled={i.etat !== "traite"}
                onClick={() => { setParams({ import: i.id }); setChoix(new Set()); }}
                className={`flex flex-col items-start rounded-2xl px-3.5 py-2 text-left text-[13px] disabled:opacity-60 ${i.id === courant?.id ? "bg-groupe shadow-[0_0_0_1.5px_var(--sg-accent)]" : "bg-remplissage"}`}>
                <span className="font-semibold">{i.outil_libelle} · {i.date_scan ? new Date(i.date_scan).toLocaleDateString("fr-FR") : quand(i.depose_le)}</span>
                <span className="max-w-[220px] truncate text-xs text-texte-2">{i.etat === "echec" ? `Échec : ${i.erreur}` : i.nom_original}</span>
              </button>
            ))}
          </div>
        )}

        {courant && b && (
          <section aria-label="Bilan du rapport" className="flex flex-col gap-3 rounded-groupe bg-groupe px-4 py-4 shadow-groupe">
            <div className="flex flex-wrap gap-2">
              {SEVERITES.filter((s) => (b.par_severite?.[s.cle] ?? 0) > 0).map((s) => (
                <span key={s.cle} className={`rounded-full px-2.5 py-1 text-[13px] font-semibold ${s.classe}`}>{b.par_severite?.[s.cle]} {s.libelle.toLowerCase()}</span>
              ))}
            </div>
            <p className="text-[13px] text-texte-2">
              {b.total} constat(s){b.precedent ? ` · ${b.nouveaux} nouveau(x), ${b.deja_vus} déjà vu(s), ${b.disparus} disparu(s) depuis le scan précédent` : " · premier scan de cet outil"}
              {" · "}<a href={`/api/imports-scans/${courant.id}/telecharger/`} download className="font-semibold text-accent-texte">rapport d'origine</a>
              <span className="font-mono text-[11px] text-texte-3"> · SHA-256 {courant.sha256.slice(0, 12)}…</span>
            </p>
          </section>
        )}

        {courant && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <div role="radiogroup" aria-label="Filtrer par sévérité" className="flex flex-wrap gap-1.5">
                {[{ cle: "tous" as const, libelle: "Toutes" }, ...SEVERITES].map((s) => (
                  <button key={s.cle} type="button" role="radio" aria-checked={filtre === s.cle} onClick={() => setFiltre(s.cle)}
                    className={`h-8 rounded-full px-3 text-[13px] ${filtre === s.cle ? "bg-accent font-semibold text-white" : "bg-remplissage font-medium text-texte-2"}`}>{s.libelle}</button>
                ))}
              </div>
              <label className="ml-auto flex items-center gap-2 text-[13px] text-texte-2">
                <input type="checkbox" checked={masquerQualifies} onChange={(e) => setMasquerQualifies(e.target.checked)} className="size-4 accent-[var(--sg-accent)]" />
                Masquer les faux positifs et risques acceptés
              </label>
            </div>

            {!lectureSeule && (
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" disabled={choix.size === 0 || creer.isPending} onClick={() => creer.mutate({ id: courant.id, identifiants: [...choix] }, { onSuccess: () => setChoix(new Set()) })}
                  className="bouton-accent h-10 rounded-full px-5 text-[14px] font-semibold disabled:opacity-45">
                  Créer {choix.size || ""} tâche{choix.size > 1 ? "s" : ""}
                </button>
                <button type="button" disabled={creer.isPending} onClick={() => creer.mutate({ id: courant.id, severite_min: "haute" })}
                  className="h-10 rounded-full bg-remplissage px-4 text-[14px] font-semibold">Toutes les hautes et critiques</button>
                {creer.data && (
                  <span role="status" className="text-[13px] text-texte-2">
                    {creer.data.crees ? <>{creer.data.crees} tâche(s) créée(s) dans le <Link to={`/projets/${projetId}/plan-action`} className="font-semibold text-accent-texte">plan d'action</Link>.</> : "Aucune nouvelle tâche : ces vulnérabilités sont déjà suivies."}
                  </span>
                )}
                {creer.error && <span role="alert" className="text-[13px] font-medium text-manquant-texte">{creer.error.message}</span>}
              </div>
            )}

            {isPending ? <div aria-busy="true" className="h-72 animate-pulse rounded-groupe bg-remplissage" /> : visibles.length === 0 ? (
              <p className="rounded-groupe bg-groupe px-4 py-6 text-center text-[15px] text-texte-2 shadow-groupe">Aucun constat dans ce filtre.</p>
            ) : (
              <ul className="divide-y divide-separateur overflow-hidden rounded-groupe bg-groupe shadow-groupe">
                {visibles.map((g) => (
                  <Vulnerabilite key={g.id} g={g} projetId={projetId} choisi={choix.has(g.id)} peutEcrire={!lectureSeule} peutDecider={tdb?.projet.peut_decider ?? false}
                    basculer={() => { const n = new Set(choix); if (n.has(g.id)) n.delete(g.id); else n.add(g.id); setChoix(n); }} />
                ))}
              </ul>
            )}
          </>
        )}
        {imports.length === 0 && lectureSeule && <p className="text-[15px] text-texte-2">Aucun rapport de scan importé.</p>}
      </div>
    </Disposition>
  );
}
