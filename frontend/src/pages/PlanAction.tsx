import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import {
  useActeurs, useCommentaires, useCommenter, useEnregistrerTache, useGenererPlanAction, useHistorique, useMoi,
  useRecommandations, useTableauDeBord, useTaches,
} from "../api/hooks";
import type { Acteur, EntreeJournal, PrioriteTache, StatutTache, Tache } from "../api/types";
import { Disposition } from "../composants/Disposition";
import { Chevron, IconeCroix, IconeEtincelle, IconePlus } from "../composants/Icones";
import { BandeauRecommandations, CarteRecommandation, recommandationDe } from "../composants/RecommandationIA";
import { echeance, quand } from "../lib/format";

const STATUTS: { cle: StatutTache; libelle: string; texte: string }[] = [
  { cle: "a_faire", libelle: "À faire", texte: "text-texte-2" },
  { cle: "en_cours", libelle: "En cours", texte: "text-accent-texte" },
  { cle: "en_revue", libelle: "En revue", texte: "text-partiel-texte" },
  { cle: "terminee", libelle: "Terminée", texte: "text-conforme-texte" },
  { cle: "abandonnee", libelle: "Abandonnée", texte: "text-na-texte" },
];
const PRIORITES: { cle: PrioriteTache; libelle: string; marque: string }[] = [
  { cle: "critique", libelle: "Critique", marque: "bg-manquant" },
  { cle: "haute", libelle: "Haute", marque: "bg-manquant/60" },
  { cle: "moyenne", libelle: "Moyenne", marque: "bg-partiel" },
  { cle: "basse", libelle: "Basse", marque: "bg-na" },
];
const ORIGINES: Record<Tache["origine"], string> = {
  evaluation: "Manquement constaté à l'évaluation", analyse_ia: "Proposition de l'IA validée", scan: "Rapport de scan",
  ebios: "EBIOS RM", manuelle: "Créée à la main",
};
const CLOSES: StatutTache[] = ["terminee", "abandonnee"];
const statut = (s: StatutTache) => STATUTS.find((x) => x.cle === s)!;
const priorite = (p: PrioriteTache) => PRIORITES.find((x) => x.cle === p)!;

const FILTRES: { cle: string; libelle: string; garde: (t: Tache, moi?: string) => boolean }[] = [
  { cle: "ouvertes", libelle: "Ouvertes", garde: (t) => !CLOSES.includes(t.statut) },
  { cle: "retard", libelle: "En retard", garde: (t) => t.en_retard },
  { cle: "miennes", libelle: "Mes tâches", garde: (t, moi) => !CLOSES.includes(t.statut) && Boolean(moi) && t.responsable_utilisateur === moi },
  { cle: "closes", libelle: "Clôturées", garde: (t) => CLOSES.includes(t.statut) },
  { cle: "toutes", libelle: "Toutes", garde: () => true },
];

/* ---- Historique lisible ------------------------------------------------------------------- */

function valeurLisible(champ: string, v: unknown, acteurs: Acteur[]): string {
  if (v === null || v === undefined || v === "") return "vide";
  if (champ === "statut") return statut(v as StatutTache)?.libelle ?? String(v);
  if (champ === "priorite") return priorite(v as PrioriteTache)?.libelle ?? String(v);
  if (champ === "responsable") return acteurs.find((a) => a.id === v)?.affichage ?? "acteur retiré";
  if (champ === "echeance" && typeof v === "string") return new Date(`${v}T00:00:00`).toLocaleDateString("fr-FR");
  return String(v);
}

const CHAMPS: Record<string, string> = {
  titre: "Titre", statut: "Statut", priorite: "Priorité", responsable: "Responsable", echeance: "Échéance",
  preuve_attendue: "Preuve attendue", description: "Description",
};

function lignesHistorique(e: EntreeJournal, acteurs: Acteur[]): string[] {
  if (e.action === "creation") return [e.donnees.origine && e.donnees.origine !== "manuelle" ? "Tâche créée à partir d'un manquement" : "Tâche créée"];
  if (e.donnees.source === "recommandation IA acceptée") {
    const champs = (e.donnees.champs as string[]).map((c) => CHAMPS[c]?.toLowerCase() ?? c).join(", ");
    return [`Recommandation de l'IA acceptée (mis à jour : ${champs})`];
  }
  return Object.entries(e.donnees)
    .filter(([champ]) => CHAMPS[champ])
    .map(([champ, d]) => {
      const { avant, apres } = d as { avant: unknown; apres: unknown };
      return ["description", "preuve_attendue", "titre"].includes(champ)
        ? `${CHAMPS[champ]} modifié(e)`
        : `${CHAMPS[champ]} : ${valeurLisible(champ, avant, acteurs)} → ${valeurLisible(champ, apres, acteurs)}`;
    });
}

/* ---- Fiche de tâche (panneau) -------------------------------------------------------------- */

type Brouillon = Pick<Tache, "titre" | "description" | "preuve_attendue" | "statut" | "priorite"> & {
  responsable: string; echeance: string;
};

const vierge: Brouillon = { titre: "", description: "", preuve_attendue: "", statut: "a_faire", priorite: "moyenne", responsable: "", echeance: "" };

function versBrouillon(t?: Tache): Brouillon {
  return t ? { titre: t.titre, description: t.description, preuve_attendue: t.preuve_attendue, statut: t.statut, priorite: t.priorite,
    responsable: t.responsable ?? "", echeance: t.echeance ?? "" } : vierge;
}

function Champ({ libelle, children }: { libelle: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-0.5 px-4 pt-2.5 pb-2">
      <span className="text-xs font-medium text-texte-2">{libelle}</span>
      {children}
    </label>
  );
}
const saisie = "w-full bg-transparent text-[15px] outline-none placeholder:text-texte-3 disabled:opacity-70";

function Fiche({ tache, projetId, lectureSeule, fermer }: { tache?: Tache; projetId: string; lectureSeule: boolean; fermer: () => void }) {
  const { data: acteurs = [] } = useActeurs(projetId);
  const { data: commentaires = [] } = useCommentaires(tache?.id);
  const { data: historique = [] } = useHistorique(tache?.id);
  const enregistrer = useEnregistrerTache(projetId);
  const commenter = useCommenter(projetId, tache?.id ?? "");
  const [b, setB] = useState<Brouillon>(versBrouillon(tache));
  const [texte, setTexte] = useState("");
  const titre = useRef<HTMLTextAreaElement>(null);
  const panneau = useRef<HTMLDivElement>(null);
  const [, setParams] = useSearchParams();

  useEffect(() => setB(versBrouillon(tache)), [tache]);
  useEffect(() => {
    const zone = titre.current;
    if (zone) { zone.style.height = "auto"; zone.style.height = `${zone.scrollHeight}px`; }
  }, [b.titre]);
  useEffect(() => {
    (tache ? panneau.current : titre.current)?.focus();
    const echap = (e: KeyboardEvent) => e.key === "Escape" && fermer();
    document.addEventListener("keydown", echap);
    return () => document.removeEventListener("keydown", echap);
  }, [tache?.id]);

  const initial = versBrouillon(tache);
  const modifies = (Object.keys(b) as (keyof Brouillon)[]).filter((k) => b[k] !== initial[k]);
  const sauver = () => {
    const champs = Object.fromEntries(modifies.map((k) => [k, (k === "responsable" || k === "echeance") && b[k] === "" ? null : b[k]]));
    enregistrer.mutate(tache ? { id: tache.id, ...champs } : champs, {
      onSuccess: (t) => { if (!tache) setParams({ tache: t.id }, { replace: true }); },
    });
  };

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button type="button" aria-label="Fermer la fiche" onClick={fermer} className="absolute inset-0 bg-black/20 backdrop-blur-[2px]" />
      <div ref={panneau} tabIndex={-1} role="dialog" aria-modal="true" aria-label={tache ? `Tâche : ${tache.titre}` : "Nouvelle tâche"}
        className="verre relative flex h-full w-full flex-col overflow-y-auto outline-none sm:m-3 sm:h-[calc(100%-24px)] sm:max-w-[560px] sm:rounded-verre">
        <div className="sticky top-0 z-10 flex items-center justify-between gap-3 px-5 pt-4 pb-2 backdrop-blur-xl">
          <span className="text-[13px] font-semibold text-texte-2">{tache ? ORIGINES[tache.origine] : "Nouvelle tâche"}</span>
          <button type="button" onClick={fermer} aria-label="Fermer" className="flex size-11 items-center justify-center rounded-full hover:bg-remplissage">
            <IconeCroix taille={18} />
          </button>
        </div>

        <div className="flex flex-col gap-5 px-5 pb-6">
          {/* Zone multiligne ajustée à son contenu : un titre long passe à la ligne au lieu d'être coupé. */}
          <textarea ref={titre} value={b.titre} rows={1} disabled={lectureSeule}
            onChange={(e) => setB({ ...b, titre: e.target.value.replace(/\n/g, " ") })}
            onKeyDown={(e) => { if (e.key === "Enter") e.preventDefault(); }}
            placeholder="Titre de la tâche" aria-label="Titre"
            className="w-full resize-none overflow-hidden bg-transparent text-[26px] leading-tight font-bold tracking-[-0.02em] outline-none [field-sizing:content] placeholder:text-texte-3" />
          {tache?.mesure_identifiant && (
            <Link to={`/projets/${projetId}/mesures`} className="-mt-3 self-start rounded-full bg-remplissage px-3 py-1.5 text-[13px] font-medium">
              {tache.mesure_identifiant} · {tache.mesure_intitule.slice(0, 70)}{tache.mesure_intitule.length > 70 ? "…" : ""}
            </Link>
          )}

          <div role="radiogroup" aria-label="Statut" className="flex flex-wrap gap-1.5">
            {STATUTS.filter((s) => s.cle !== "abandonnee" || b.statut === "abandonnee").map((s) => (
              <button key={s.cle} type="button" role="radio" aria-checked={b.statut === s.cle} disabled={lectureSeule}
                onClick={() => setB({ ...b, statut: s.cle })}
                className={`h-9 rounded-full px-3.5 text-[13px] font-semibold transition-colors duration-200 ease-ios ${b.statut === s.cle ? `bg-groupe shadow-[0_0_0_1.5px_var(--sg-accent)] ${s.texte}` : "bg-remplissage text-texte-2"}`}>
                {s.libelle}
              </button>
            ))}
          </div>

          <div className="overflow-hidden rounded-groupe bg-groupe shadow-groupe">
            <Champ libelle="Responsable">
              <select className={`${saisie} appearance-none`} value={b.responsable} disabled={lectureSeule} onChange={(e) => setB({ ...b, responsable: e.target.value })}>
                <option value="">Personne</option>
                {acteurs.map((a) => <option key={a.id} value={a.id}>{a.affichage} — {a.role_libelle}</option>)}
              </select>
            </Champ>
            <div aria-hidden="true" className="ml-4 h-px bg-separateur" />
            <div className="grid grid-cols-2">
              <Champ libelle="Échéance">
                <input type="date" className={saisie} value={b.echeance} disabled={lectureSeule} onChange={(e) => setB({ ...b, echeance: e.target.value })} />
              </Champ>
              <Champ libelle="Priorité">
                <select className={`${saisie} appearance-none`} value={b.priorite} disabled={lectureSeule} onChange={(e) => setB({ ...b, priorite: e.target.value as PrioriteTache })}>
                  {PRIORITES.map((p) => <option key={p.cle} value={p.cle}>{p.libelle}</option>)}
                </select>
              </Champ>
            </div>
            <div aria-hidden="true" className="ml-4 h-px bg-separateur" />
            <Champ libelle="Preuve attendue">
              <textarea rows={2} className={`${saisie} resize-y`} value={b.preuve_attendue} disabled={lectureSeule}
                placeholder="Ce qui permettra de clore la tâche" onChange={(e) => setB({ ...b, preuve_attendue: e.target.value })} />
            </Champ>
            <div aria-hidden="true" className="ml-4 h-px bg-separateur" />
            <Champ libelle="Description">
              <textarea rows={3} className={`${saisie} resize-y`} value={b.description} disabled={lectureSeule}
                onChange={(e) => setB({ ...b, description: e.target.value })} />
            </Champ>
          </div>

          {!lectureSeule && (
            <div className="flex flex-wrap items-center gap-3">
              <button type="button" onClick={sauver} disabled={!b.titre.trim() || modifies.length === 0 || enregistrer.isPending}
                className="bouton-accent h-11 rounded-full px-6 text-[15px] font-semibold disabled:opacity-45">
                {enregistrer.isPending ? "Enregistrement…" : tache ? "Enregistrer" : "Créer la tâche"}
              </button>
              {tache && !CLOSES.includes(tache.statut) && b.statut !== "abandonnee" && (
                <button type="button" onClick={() => setB({ ...b, statut: "abandonnee" })} className="h-11 px-2 text-[14px] font-medium text-texte-2">
                  Abandonner la tâche
                </button>
              )}
              {tache && <span className="text-xs text-texte-2">Chaque modification est notifiée au responsable et aux chefs de projet.</span>}
            </div>
          )}
          {enregistrer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{enregistrer.error.message}</p>}
          {tache?.cloturee_le && (
            <p className="text-[13px] text-texte-2">Clôturée par {tache.cloturee_par_nom} · {quand(tache.cloturee_le)}</p>
          )}

          {tache && <CarteRecommandation tache={tache} projetId={projetId} lectureSeule={lectureSeule} />}

          {tache && (
            <section aria-labelledby="titre-commentaires" className="flex flex-col gap-3">
              <h2 id="titre-commentaires" className="text-[17px] font-bold">Commentaires</h2>
              {commentaires.length === 0 && <p className="text-sm text-texte-2">Aucun commentaire.</p>}
              <ol className="flex flex-col gap-2.5">
                {commentaires.map((c) => (
                  <li key={c.id} className="rounded-2xl bg-groupe px-3.5 py-2.5 shadow-groupe">
                    <span className="text-xs text-texte-2"><span className="font-semibold text-texte">{c.auteur_nom}</span> · {quand(c.cree_le)}</span>
                    <p className="mt-0.5 text-[15px] leading-snug whitespace-pre-line">{c.texte}</p>
                  </li>
                ))}
              </ol>
              {!lectureSeule && (
                <form onSubmit={(e) => { e.preventDefault(); if (texte.trim()) commenter.mutate(texte, { onSuccess: () => setTexte("") }); }}
                  className="flex items-end gap-2 rounded-2xl bg-groupe p-2 pl-3.5 shadow-groupe">
                  <label className="sr-only" htmlFor="nouveau-commentaire">Votre commentaire</label>
                  <textarea id="nouveau-commentaire" rows={1} value={texte} onChange={(e) => setTexte(e.target.value)} placeholder="Écrire un commentaire…"
                    className="max-h-40 min-h-[40px] flex-1 resize-y bg-transparent py-2 text-[15px] outline-none placeholder:text-texte-3" />
                  <button type="submit" disabled={!texte.trim() || commenter.isPending} className="bouton-accent h-10 rounded-full px-4 text-[14px] font-semibold disabled:opacity-45">
                    Envoyer
                  </button>
                </form>
              )}
            </section>
          )}

          {tache && historique.length > 0 && (
            <section aria-labelledby="titre-historique" className="flex flex-col gap-3">
              <h2 id="titre-historique" className="text-[17px] font-bold">Historique</h2>
              <ol className="flex flex-col gap-3 border-l-2 border-separateur pl-4">
                {historique.map((e) => (
                  <li key={e.id} className="flex flex-col gap-0.5">
                    {lignesHistorique(e, acteurs).map((l) => <span key={l} className="text-sm leading-snug">{l}</span>)}
                    <span className="text-xs text-texte-2">{e.acteur_repr} · {quand(e.horodatage)}</span>
                  </li>
                ))}
              </ol>
              <p className="text-xs text-texte-3">Issu du journal d'audit, non modifiable.</p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---- Page --------------------------------------------------------------------------------- */

export function PagePlanAction() {
  const { projetId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { data: tdb } = useTableauDeBord(projetId);
  const { data: moi } = useMoi();
  const { data: taches = [], isPending } = useTaches(projetId);
  const { data: recos = [] } = useRecommandations(projetId);
  const generer = useGenererPlanAction(projetId);
  const [filtre, setFiltre] = useState("ouvertes");
  const lectureSeule = tdb?.projet.lecture_seule ?? true;
  const ouverte = params.get("tache");
  const fiche = ouverte === "nouvelle" ? undefined : taches.find((t) => t.id === ouverte);
  const derniereOuverte = useRef<string | null>(null);

  const fermer = () => {
    setParams({}, { replace: true });
    const id = derniereOuverte.current;
    setTimeout(() => document.querySelector<HTMLElement>(`[data-tache="${id}"]`)?.focus(), 0);
  };
  const ouvrir = (id: string) => { derniereOuverte.current = id; setParams({ tache: id }); };

  const moiNom = moi?.id;
  const garde = FILTRES.find((f) => f.cle === filtre)!.garde;
  const visibles = useMemo(() => taches.filter((t) => garde(t, moiNom)), [taches, garde, moiNom]);
  const ouvertes = taches.filter((t) => !CLOSES.includes(t.statut)).length;
  const retards = taches.filter((t) => t.en_retard).length;

  return (
    <Disposition>
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-end justify-between gap-4 lg:pt-2.5">
          <div className="flex flex-col gap-1.5">
            <span className="text-[13px] font-semibold text-texte-2">{tdb?.projet.nom ?? "Projet"}</span>
            <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Plan d'action</h1>
            <p className="text-[15px] text-texte-2">
              {ouvertes} ouverte{ouvertes > 1 ? "s" : ""}
              {retards > 0 && <span className="font-semibold text-manquant-texte"> · {retards} en retard</span>}
              {" · "}{taches.length - ouvertes} clôturée{taches.length - ouvertes > 1 ? "s" : ""}
            </p>
          </div>
          {!lectureSeule && (
            <button type="button" onClick={() => ouvrir("nouvelle")} className="bouton-accent flex h-[50px] items-center gap-2 rounded-full px-[22px] text-[15px] font-semibold">
              <IconePlus taille={17} /> Nouvelle tâche
            </button>
          )}
        </div>

        <BandeauRecommandations projetId={projetId} lectureSeule={lectureSeule}
          nbSansRecommandation={taches.filter((t) => !CLOSES.includes(t.statut) && !recommandationDe(recos, t.id)).length} />

        <div role="radiogroup" aria-label="Filtrer les tâches" className="flex flex-wrap gap-1.5">
          {FILTRES.map((f) => (
            <button key={f.cle} type="button" role="radio" aria-checked={filtre === f.cle} onClick={() => setFiltre(f.cle)}
              className={`h-8 rounded-full px-3 text-[13px] whitespace-nowrap transition-colors duration-200 ease-ios ${filtre === f.cle ? "bg-accent font-semibold text-white" : "bg-remplissage font-medium text-texte-2"}`}>
              {f.libelle} {taches.filter((t) => f.garde(t, moiNom)).length}
            </button>
          ))}
        </div>

        {isPending ? (
          <div aria-busy="true" className="h-80 animate-pulse rounded-groupe bg-remplissage" />
        ) : visibles.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-groupe bg-groupe px-4 py-8 text-center shadow-groupe">
            <p className="text-[15px] text-texte-2">
              {taches.length === 0 ? "Aucune tâche. Chaque mesure évaluée « manquant » ou « partiel » crée sa tâche automatiquement." : "Aucune tâche dans ce filtre."}
            </p>
            {!lectureSeule && taches.length === 0 && (
              <button type="button" onClick={() => generer.mutate()} disabled={generer.isPending} className="rounded-full bg-accent-doux px-4 py-2.5 text-[14px] font-semibold text-accent-texte">
                Créer les tâches des manquements déjà évalués
              </button>
            )}
            {generer.data && <p className="text-[13px] text-texte-2">{generer.data.crees} tâche(s) créée(s).</p>}
          </div>
        ) : (
          <ul className="divide-y divide-separateur overflow-hidden rounded-groupe bg-groupe shadow-groupe">
            {visibles.map((t) => {
              const s = statut(t.statut);
              const p = priorite(t.priorite);
              return (
                <li key={t.id}>
                  <button type="button" data-tache={t.id} onClick={() => ouvrir(t.id)}
                    className="flex min-h-[64px] w-full items-center gap-3.5 px-4 py-2.5 text-left hover:bg-remplissage">
                    <span aria-hidden="true" className={`h-9 w-1 shrink-0 rounded-full ${p.marque}`} />
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className={`text-[15px] leading-snug font-medium ${CLOSES.includes(t.statut) ? "text-texte-2 line-through decoration-texte-3" : ""}`}>{t.titre}</span>
                      <span className="text-[13px] leading-snug text-texte-2">
                        {t.mesure_identifiant && <>{t.mesure_identifiant} · </>}
                        {t.responsable_nom || "Sans responsable"} · priorité {p.libelle.toLowerCase()} ·{" "}
                        <span className={t.en_retard ? "font-semibold text-manquant-texte" : ""}>{echeance(t.echeance, t.en_retard)}</span>
                      </span>
                      {recommandationDe(recos, t.id)?.statut_validation === "a_valider" && (
                        <span className="flex items-center gap-1 text-xs font-semibold text-partiel-texte">
                          <IconeEtincelle taille={12} /> Recommandation à relire
                        </span>
                      )}
                    </span>
                    <span className="flex flex-col items-end gap-0.5">
                      <span className={`text-[13px] font-semibold whitespace-nowrap ${s.texte}`}>{s.libelle}</span>
                      {t.nb_commentaires > 0 && <span className="text-xs text-texte-2">{t.nb_commentaires} commentaire{t.nb_commentaires > 1 ? "s" : ""}</span>}
                    </span>
                    <Chevron />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      {ouverte && (ouverte === "nouvelle" || fiche) && (
        <Fiche key={ouverte} tache={fiche} projetId={projetId} lectureSeule={lectureSeule} fermer={fermer} />
      )}
    </Disposition>
  );
}
