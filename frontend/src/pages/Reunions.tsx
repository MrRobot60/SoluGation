import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { useActeurs, useActionReunion, useActionsDecidees, useEnregistrerReunion, useMoi, useReunions, useTableauDeBord } from "../api/hooks";
import type { Reunion } from "../api/types";
import { Disposition } from "../composants/Disposition";
import { Chevron, IconeCroix, IconePlus } from "../composants/Icones";
import { echeance, quand } from "../lib/format";

const saisie = "w-full rounded-xl bg-remplissage px-3 py-2.5 text-[15px] outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)] disabled:opacity-70";
const STATUTS: Record<Reunion["statut"], { libelle: string; classe: string }> = {
  planifiee: { libelle: "Planifiée", classe: "bg-accent-doux text-accent-texte" },
  tenue: { libelle: "Tenue", classe: "bg-conforme/15 text-conforme-texte" },
  annulee: { libelle: "Annulée", classe: "bg-remplissage text-texte-2 line-through" },
};

/** « 2026-10-30T14:00 » (heure locale) ⇄ ISO 8601 avec fuseau, pour <input type="datetime-local">. */
const versLocal = (iso: string) => { const d = new Date(iso); return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 16); };
const versIso = (local: string) => new Date(local).toISOString();
const horaire = (r: Reunion) => {
  const d = new Date(r.debut), f = new Date(r.fin);
  return `${d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })}, ${d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}–${f.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
};
function prochaineHeure() {
  const d = new Date(Date.now() + 2 * 86_400_000);
  d.setHours(10, 0, 0, 0);
  return d.toISOString();
}

function Champ({ libelle, children }: { libelle: string; children: ReactNode }) {
  return <label className="flex flex-col gap-1.5"><span className="text-xs font-semibold text-texte-2">{libelle}</span>{children}</label>;
}

function Fiche({ r, projetId, lectureSeule, peutAdministrer, fermer }: { r?: Reunion; projetId: string; lectureSeule: boolean; peutAdministrer: boolean; fermer: () => void }) {
  const { data: acteurs = [] } = useActeurs(projetId);
  const enregistrer = useEnregistrerReunion(projetId);
  const annuler = useActionReunion(projetId, "annuler");
  const valider = useActionReunion(projetId, "valider-compte-rendu");
  const { liste: actions, ajouter } = useActionsDecidees(projetId, r?.id);
  const [, setParams] = useSearchParams();
  const debut = r?.debut ?? prochaineHeure();
  const [b, setB] = useState({
    titre: r?.titre ?? "", debut: versLocal(debut), fin: versLocal(r?.fin ?? new Date(new Date(debut).getTime() + 3_600_000).toISOString()),
    lieu: r?.lieu ?? "", lien_visio: r?.lien_visio ?? "", ordre_du_jour: r?.ordre_du_jour ?? "",
    participants: r?.participants ?? acteurs.map((a) => a.id),
  });
  const [inviter, setInviter] = useState(true);
  const [cr, setCr] = useState(r?.compte_rendu ?? "");
  const [action, setAction] = useState({ titre: "", responsable: "", echeance: "" });
  const panneau = useRef<HTMLDivElement>(null);
  const fermerRef = useRef(fermer);
  fermerRef.current = fermer;
  useEffect(() => { if (!r && acteurs.length && b.participants.length === 0) setB((x) => ({ ...x, participants: acteurs.map((a) => a.id) })); }, [acteurs, r, b.participants.length]);
  useEffect(() => {
    panneau.current?.focus();
    const echap = (e: KeyboardEvent) => e.key === "Escape" && fermerRef.current();
    document.addEventListener("keydown", echap);
    return () => document.removeEventListener("keydown", echap);
  }, [r?.id]);
  useEffect(() => setCr(r?.compte_rendu ?? ""), [r?.compte_rendu]);

  const fige = Boolean(r?.compte_rendu_valide_le) || r?.statut === "annulee";
  const bloque = lectureSeule || fige;
  const { data: moi } = useMoi();
  // Annuler et valider le compte rendu : l'organisateur ou un administrateur du projet (le serveur le vérifie aussi).
  const organisateur = peutAdministrer || (r ? r.organisateur === moi?.id : true);
  const passee = r ? new Date(r.debut) < new Date() : false;
  const modifie = !r || b.titre !== r.titre || versIso(b.debut) !== new Date(r.debut).toISOString() || versIso(b.fin) !== new Date(r.fin).toISOString()
    || b.lieu !== r.lieu || b.lien_visio !== r.lien_visio || b.ordre_du_jour !== r.ordre_du_jour
    || b.participants.length !== r.participants.length || b.participants.some((p) => !r.participants.includes(p));
  const sauver = () => enregistrer.mutate(
    { id: r?.id, titre: b.titre, debut: versIso(b.debut), fin: versIso(b.fin), lieu: b.lieu, lien_visio: b.lien_visio, ordre_du_jour: b.ordre_du_jour,
      participants: b.participants, inviter },
    { onSuccess: (x) => { if (!r) setParams({ reunion: x.id }, { replace: true }); } },
  );
  const basculer = (id: string) => setB({ ...b, participants: b.participants.includes(id) ? b.participants.filter((p) => p !== id) : [...b.participants, id] });

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button type="button" aria-label="Fermer" onClick={fermer} className="absolute inset-0 bg-black/20 backdrop-blur-[2px]" />
      <div ref={panneau} tabIndex={-1} role="dialog" aria-modal="true" aria-label={r ? `Réunion : ${r.titre}` : "Nouvelle réunion"}
        className="verre relative flex h-full w-full flex-col gap-5 overflow-y-auto px-5 pt-4 pb-6 outline-none sm:m-3 sm:h-[calc(100%-24px)] sm:max-w-[600px] sm:rounded-verre">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[13px] font-semibold text-texte-2">{r ? `${STATUTS[r.statut].libelle} · organisée par ${r.organisateur_nom}` : "Nouvelle réunion"}</span>
          <button type="button" onClick={fermer} aria-label="Fermer" className="flex size-11 items-center justify-center rounded-full hover:bg-remplissage"><IconeCroix taille={18} /></button>
        </div>

        <div className="flex flex-col gap-4">
          <Champ libelle="Objet"><input className={saisie} disabled={bloque} value={b.titre} onChange={(e) => setB({ ...b, titre: e.target.value })} placeholder="ex. Comité de pilotage sécurité" /></Champ>
          <div className="grid gap-4 sm:grid-cols-2">
            <Champ libelle="Début"><input type="datetime-local" className={saisie} disabled={bloque} value={b.debut} onChange={(e) => setB({ ...b, debut: e.target.value })} /></Champ>
            <Champ libelle="Fin"><input type="datetime-local" className={saisie} disabled={bloque} value={b.fin} onChange={(e) => setB({ ...b, fin: e.target.value })} /></Champ>
            <Champ libelle="Lieu"><input className={saisie} disabled={bloque} value={b.lieu} onChange={(e) => setB({ ...b, lieu: e.target.value })} /></Champ>
            <Champ libelle="Lien de visio"><input className={saisie} disabled={bloque} inputMode="url" value={b.lien_visio} onChange={(e) => setB({ ...b, lien_visio: e.target.value })} placeholder="https://…" /></Champ>
          </div>
          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-1.5 text-xs font-semibold text-texte-2">Participants (acteurs du projet)</legend>
            <div className="flex flex-wrap gap-1.5">
              {acteurs.map((a) => {
                const actif = b.participants.includes(a.id);
                return (
                  <button key={a.id} type="button" aria-pressed={actif} disabled={bloque} onClick={() => basculer(a.id)}
                    className={`rounded-full px-3 py-1.5 text-[13px] font-medium ${actif ? "bg-accent-doux text-accent-texte shadow-[0_0_0_1.5px_var(--sg-accent)]" : "bg-remplissage text-texte-2"}`}>
                    {a.affichage} <span className="opacity-70">· {a.role_libelle}</span>
                  </button>
                );
              })}
            </div>
          </fieldset>
          <Champ libelle="Ordre du jour"><textarea rows={4} className={`${saisie} resize-y`} disabled={bloque} value={b.ordre_du_jour} onChange={(e) => setB({ ...b, ordre_du_jour: e.target.value })} /></Champ>
          {!bloque && (
            <div className="flex flex-wrap items-center gap-3">
              <button type="button" disabled={!modifie || !b.titre.trim() || !b.debut || !b.fin || enregistrer.isPending} onClick={sauver}
                className="bouton-accent h-11 rounded-full px-6 text-[15px] font-semibold disabled:opacity-45">{r ? "Enregistrer" : "Planifier"}</button>
              <label className="flex items-center gap-2 text-[13px] text-texte-2">
                <input type="checkbox" checked={inviter} onChange={(e) => setInviter(e.target.checked)} className="size-4 accent-[var(--sg-accent)]" />
                {r ? "Envoyer la mise à jour aux participants" : "Envoyer l'invitation (agenda .ics) aux participants"}
              </label>
            </div>
          )}
          {enregistrer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{enregistrer.error.message}</p>}
        </div>

        {r && r.statut !== "annulee" && (
          <section aria-labelledby="titre-cr" className="flex flex-col gap-2">
            <h2 id="titre-cr" className="text-[17px] font-bold">Compte rendu</h2>
            {r.compte_rendu_valide_le ? (
              <>
                <p className="text-[15px] leading-relaxed whitespace-pre-line">{r.compte_rendu}</p>
                <p className="text-xs text-texte-2">Validé par {r.compte_rendu_valide_par_nom} {quand(r.compte_rendu_valide_le)}, diffusé aux participants.</p>
              </>
            ) : (
              <>
                <textarea rows={6} className={`${saisie} resize-y`} disabled={lectureSeule} value={cr} onChange={(e) => setCr(e.target.value)}
                  placeholder={passee ? "Décisions, points d'attention, prochaines étapes…" : "À rédiger après la réunion."} />
                {!lectureSeule && (
                  <div className="flex flex-wrap gap-2">
                    <button type="button" disabled={cr === r.compte_rendu || enregistrer.isPending} onClick={() => enregistrer.mutate({ id: r.id, compte_rendu: cr })}
                      className="h-10 rounded-full bg-remplissage px-5 text-[14px] font-semibold disabled:opacity-45">Enregistrer le brouillon</button>
                    {organisateur && (
                      <button type="button" disabled={!r.compte_rendu.trim() || cr !== r.compte_rendu || valider.isPending} onClick={() => valider.mutate(r.id)}
                        className="bouton-accent h-10 rounded-full px-5 text-[14px] font-semibold disabled:opacity-45">Valider et diffuser</button>
                    )}
                  </div>
                )}
                <p className="text-xs text-texte-3">Une fois validé, le compte rendu est figé et envoyé aux participants (contacts externes compris).</p>
              </>
            )}
            {valider.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{valider.error.message}</p>}
          </section>
        )}

        {r && (
          <section aria-labelledby="titre-actions" className="flex flex-col gap-2">
            <h2 id="titre-actions" className="text-[17px] font-bold">Actions décidées</h2>
            {(actions.data ?? []).length === 0 && <p className="text-sm text-texte-2">Aucune action.</p>}
            <ul className="flex flex-col gap-1.5">
              {(actions.data ?? []).map((t) => (
                <li key={t.id}>
                  <Link to={`/projets/${projetId}/plan-action?tache=${t.id}`} className="flex flex-col rounded-2xl bg-groupe px-3.5 py-2.5 shadow-groupe">
                    <span className="text-sm font-medium">{t.titre}</span>
                    <span className="text-xs text-texte-2">{t.responsable_nom || "Sans responsable"} · {echeance(t.echeance, t.en_retard)}</span>
                  </Link>
                </li>
              ))}
            </ul>
            {!lectureSeule && r.statut !== "annulee" && (
              <form className="flex flex-col gap-2 rounded-2xl border border-separateur px-3.5 py-3"
                onSubmit={(e) => { e.preventDefault(); ajouter.mutate({ titre: action.titre, responsable: action.responsable || null, echeance: action.echeance || null }, { onSuccess: () => setAction({ titre: "", responsable: "", echeance: "" }) }); }}>
                <span className="text-xs font-semibold text-texte-2">Nouvelle action (crée une tâche du plan d'action)</span>
                <input aria-label="Action" placeholder="ex. Planifier l'audit de configuration" className={saisie} value={action.titre} onChange={(e) => setAction({ ...action, titre: e.target.value })} />
                <div className="grid gap-2 sm:grid-cols-2">
                  <select aria-label="Responsable" className={`${saisie} appearance-none`} value={action.responsable} onChange={(e) => setAction({ ...action, responsable: e.target.value })}>
                    <option value="">Responsable…</option>
                    {acteurs.map((a) => <option key={a.id} value={a.id}>{a.affichage}</option>)}
                  </select>
                  <input aria-label="Échéance" type="date" className={saisie} value={action.echeance} onChange={(e) => setAction({ ...action, echeance: e.target.value })} />
                </div>
                <button type="submit" disabled={!action.titre.trim() || ajouter.isPending} className="h-10 self-start rounded-full bg-remplissage px-5 text-[14px] font-semibold disabled:opacity-45">
                  <IconePlus taille={14} className="mr-1 inline" />Ajouter l'action
                </button>
                {ajouter.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{ajouter.error.message}</p>}
              </form>
            )}
          </section>
        )}

        {r?.statut === "planifiee" && !lectureSeule && organisateur && (
          <button type="button" disabled={annuler.isPending} onClick={() => annuler.mutate(r.id)} className="self-start px-1 text-[14px] font-semibold text-manquant-texte">
            Annuler la réunion (les participants sont prévenus)
          </button>
        )}
        {annuler.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{annuler.error.message}</p>}
      </div>
    </div>
  );
}

export function PageReunions() {
  const { projetId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { data: tdb } = useTableauDeBord(projetId);
  const { data: reunions = [], isPending } = useReunions(projetId);
  const lectureSeule = tdb?.projet.lecture_seule ?? true;
  const ouverte = params.get("reunion");
  const fiche = ouverte === "nouvelle" ? undefined : reunions.find((r) => r.id === ouverte);
  const maintenant = new Date();
  const aVenir = reunions.filter((r) => r.statut === "planifiee" && new Date(r.fin) >= maintenant).sort((a, b) => a.debut.localeCompare(b.debut));
  const passees = reunions.filter((r) => !aVenir.includes(r));

  const ligne = (r: Reunion) => (
    <li key={r.id}>
      <button type="button" onClick={() => setParams({ reunion: r.id })} className="flex min-h-[64px] w-full items-center gap-3.5 px-4 py-2.5 text-left hover:bg-remplissage">
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="text-[15px] leading-snug font-medium">{r.titre}
            <span className={`ml-2 rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUTS[r.statut].classe}`}>{STATUTS[r.statut].libelle}</span>
          </span>
          <span className="text-[13px] text-texte-2">
            {horaire(r)}{r.lieu ? ` · ${r.lieu}` : r.lien_visio ? " · visio" : ""} · {r.participants.length} participant(s)
            {r.nb_actions ? ` · ${r.nb_actions} action(s)` : ""}{r.statut === "tenue" && r.compte_rendu_valide_le ? " · compte rendu diffusé" : ""}
          </span>
        </span>
        <Chevron />
      </button>
    </li>
  );

  return (
    <Disposition>
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-end justify-between gap-4 lg:pt-2.5">
          <div className="flex flex-col gap-1.5">
            <span className="text-[13px] font-semibold text-texte-2">{tdb?.projet.nom ?? "Projet"}</span>
            <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Réunions</h1>
            <p className="text-[15px] text-texte-2">{aVenir.length} à venir · {passees.length} passée(s)</p>
          </div>
          {!lectureSeule && (
            <button type="button" onClick={() => setParams({ reunion: "nouvelle" })} className="bouton-accent flex h-[50px] items-center gap-2 rounded-full px-[22px] text-[15px] font-semibold">
              <IconePlus taille={17} /> Planifier une réunion
            </button>
          )}
        </div>
        {isPending ? <div aria-busy="true" className="h-72 animate-pulse rounded-groupe bg-remplissage" /> : (
          <>
            <section aria-label="À venir" className="flex flex-col gap-2">
              <h2 className="px-1 text-[13px] font-semibold text-texte-2">À venir</h2>
              {aVenir.length === 0 ? <p className="rounded-groupe bg-groupe px-4 py-5 text-[15px] text-texte-2 shadow-groupe">Aucune réunion planifiée.</p>
                : <ul className="divide-y divide-separateur overflow-hidden rounded-groupe bg-groupe shadow-groupe">{aVenir.map(ligne)}</ul>}
            </section>
            {passees.length > 0 && (
              <section aria-label="Passées et annulées" className="flex flex-col gap-2">
                <h2 className="px-1 text-[13px] font-semibold text-texte-2">Passées et annulées</h2>
                <ul className="divide-y divide-separateur overflow-hidden rounded-groupe bg-groupe shadow-groupe">{passees.map(ligne)}</ul>
              </section>
            )}
            <p className="px-1 text-xs text-texte-3">Les invitations arrivent par mail avec un fichier d'agenda (.ics) compatible Outlook, Google Agenda et Apple Calendrier. La synchronisation directe avec Outlook viendra plus tard.</p>
          </>
        )}
      </div>
      {ouverte && (ouverte === "nouvelle" || fiche) && (
        <Fiche key={ouverte} r={fiche} projetId={projetId} lectureSeule={lectureSeule} peutAdministrer={tdb?.projet.peut_administrer ?? false}
          fermer={() => setParams({}, { replace: true })} />
      )}
    </Disposition>
  );
}
