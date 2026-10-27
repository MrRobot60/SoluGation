import { useEffect, useState, type ReactNode } from "react";
import { useParams } from "react-router";

import {
  useActeurs, useActionProjet, useEnregistrerObjet, useEvaluations, useMembres, useModifierProjet, useProjet, useReferentiels,
  useRolesProjet, useSupprimerObjet, useTableauDeBord, useTaches,
} from "../api/hooks";
import type { NiveauVise, Projet, TypeBien } from "../api/types";
import { Disposition } from "../composants/Disposition";
import { nomCourt } from "../composants/statuts";

const TYPES: { cle: TypeBien; libelle: string }[] = [
  { cle: "application", libelle: "Application" }, { cle: "poste_travail", libelle: "Poste de travail" },
  { cle: "si", libelle: "Système d'information" }, { cle: "autre", libelle: "Autre" },
];
const NIVEAUX: { cle: NiveauVise; libelle: string }[] = [
  { cle: "elementaire", libelle: "Élémentaire" }, { cle: "standard", libelle: "Standard" }, { cle: "renforce", libelle: "Renforcé" },
];
const STATUTS_MANUELS = [
  { cle: "brouillon", libelle: "Brouillon" }, { cle: "en_cours", libelle: "En cours" }, { cle: "en_attente_decision", libelle: "En attente de décision" },
];
const DECISIONS = [
  { cle: "homologation", libelle: "Homologation" }, { cle: "provisoire", libelle: "Homologation provisoire" }, { cle: "refus", libelle: "Refus" },
];
const saisie = "w-full rounded-xl bg-remplissage px-3 py-2.5 text-[15px] outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)] disabled:opacity-70";
const dateFr = (d: string | null | undefined) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString("fr-FR") : "");
const dans = (jours: number) => new Date(Date.now() + jours * 86_400_000).toISOString().slice(0, 10);

function Section({ id, titre, aide, children }: { id: string; titre: string; aide?: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4 rounded-groupe bg-groupe px-4 py-5 shadow-groupe sm:px-6">
      <div className="flex flex-col gap-1">
        <h2 id={id} className="text-[20px] font-bold">{titre}</h2>
        {aide && <p className="text-[14px] leading-snug text-texte-2">{aide}</p>}
      </div>
      {children}
    </section>
  );
}

function Champ({ libelle, aide, children }: { libelle: string; aide?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="flex flex-col"><span className="text-xs font-semibold text-texte-2">{libelle}</span>{aide && <span className="text-xs text-texte-3">{aide}</span>}</span>
      {children}
    </label>
  );
}

function Erreur({ e }: { e: Error | null }) {
  return e ? <p role="alert" className="text-[13px] font-medium text-manquant-texte">{e.message}</p> : null;
}

function Bascule({ libelle, aide, valeur, changer, desactive }: { libelle: string; aide: string; valeur: boolean; changer: (v: boolean) => void; desactive: boolean }) {
  return (
    <label className="flex items-start gap-3 text-[15px]">
      <input type="checkbox" checked={valeur} disabled={desactive} onChange={(e) => changer(e.target.checked)} className="mt-0.5 size-5 shrink-0 accent-[var(--sg-accent)]" />
      <span className="flex flex-col"><span className="font-medium">{libelle}</span><span className="text-[13px] text-texte-2">{aide}</span></span>
    </label>
  );
}

function Identite({ p, projetId, bloque }: { p: Projet; projetId: string; bloque: boolean }) {
  const modifier = useModifierProjet(projetId);
  const [b, setB] = useState({ nom: p.nom, description: p.description, type_bien: p.type_bien, niveau_vise: p.niveau_vise });
  useEffect(() => setB({ nom: p.nom, description: p.description, type_bien: p.type_bien, niveau_vise: p.niveau_vise }), [p]);
  const modifie = b.nom !== p.nom || b.description !== p.description || b.type_bien !== p.type_bien || b.niveau_vise !== p.niveau_vise;
  const manuel = STATUTS_MANUELS.some((s) => s.cle === p.statut);
  return (
    <Section id="r-identite" titre="Projet">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2"><Champ libelle="Nom"><input className={saisie} disabled={bloque} value={b.nom} onChange={(e) => setB({ ...b, nom: e.target.value })} /></Champ></div>
        <Champ libelle="Type de bien">
          <select className={`${saisie} appearance-none`} disabled={bloque} value={b.type_bien} onChange={(e) => setB({ ...b, type_bien: e.target.value as TypeBien })}>
            {TYPES.map((t) => <option key={t.cle} value={t.cle}>{t.libelle}</option>)}
          </select>
        </Champ>
        <Champ libelle="Niveau visé">
          <select className={`${saisie} appearance-none`} disabled={bloque} value={b.niveau_vise} onChange={(e) => setB({ ...b, niveau_vise: e.target.value as NiveauVise })}>
            {NIVEAUX.map((t) => <option key={t.cle} value={t.cle}>{t.libelle}</option>)}
          </select>
        </Champ>
        <div className="sm:col-span-2"><Champ libelle="Description"><textarea rows={3} className={`${saisie} resize-y`} disabled={bloque} value={b.description} onChange={(e) => setB({ ...b, description: e.target.value })} /></Champ></div>
      </div>
      {!bloque && (
        <button type="button" disabled={!modifie || !b.nom.trim() || modifier.isPending} onClick={() => modifier.mutate(b)}
          className="bouton-accent h-10 self-start rounded-full px-5 text-[14px] font-semibold disabled:opacity-45">Enregistrer</button>
      )}
      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-semibold text-texte-2">Avancement</span>
        {manuel ? (
          <div role="radiogroup" aria-label="Avancement du projet" className="flex flex-wrap self-start rounded-full bg-remplissage p-[3px]">
            {STATUTS_MANUELS.map((s) => (
              <button key={s.cle} type="button" role="radio" aria-checked={p.statut === s.cle} disabled={bloque || modifier.isPending} onClick={() => modifier.mutate({ statut: s.cle })}
                className={`rounded-full px-3.5 py-1.5 text-[13px] ${p.statut === s.cle ? "bg-groupe font-semibold shadow-groupe" : "font-medium text-texte-2"}`}>{s.libelle}</button>
            ))}
          </div>
        ) : <p className="text-[14px] text-texte-2">Fixé par la décision d'homologation ou l'archivage (voir plus bas).</p>}
      </div>
      <Erreur e={modifier.error} />
    </Section>
  );
}

function Referentiels({ p, projetId, bloque }: { p: Projet; projetId: string; bloque: boolean }) {
  const { data: referentiels = [] } = useReferentiels();
  const { data: evaluations = [] } = useEvaluations(projetId);
  const { data: taches = [] } = useTaches(projetId);
  const modifier = useModifierProjet(projetId);
  const [choix, setChoix] = useState<string[]>(p.referentiels);
  useEffect(() => setChoix(p.referentiels), [p.referentiels]);
  const retires = referentiels.filter((r) => p.referentiels.includes(r.id) && !choix.includes(r.id));
  const codes = new Set(retires.map((r) => r.code));
  const nbEval = evaluations.filter((e) => codes.has(e.referentiel_code)).length;
  const nbTaches = taches.filter((t) => codes.has(t.referentiel_code)).length;
  const modifie = choix.length !== p.referentiels.length || choix.some((c) => !p.referentiels.includes(c));
  return (
    <Section id="r-referentiels" titre="Référentiels" aide="De 1 à 3 référentiels. EBIOS RM est une méthode : elle ne compte pas dans cette limite.">
      <div className="flex flex-wrap gap-1.5">
        {referentiels.map((r) => {
          const actif = choix.includes(r.id);
          const plein = !actif && choix.length >= 3;
          return (
            <button key={r.id} type="button" aria-pressed={actif} disabled={bloque || plein}
              onClick={() => setChoix(actif ? choix.filter((c) => c !== r.id) : [...choix, r.id])}
              className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium disabled:opacity-45 ${actif ? "bg-accent-doux text-accent-texte shadow-[0_0_0_1.5px_var(--sg-accent)]" : "bg-remplissage text-texte-2"}`}>
              {nomCourt(r)}{r.prive ? " · privé" : ""}
            </button>
          );
        })}
      </div>
      {retires.length > 0 && (
        <p className="rounded-2xl bg-partiel/10 px-3.5 py-3 text-[13px] leading-snug text-partiel-texte">
          Retirer {retires.map((r) => nomCourt(r)).join(", ")} masque {nbEval} évaluation(s) et {nbTaches} tâche(s) liée(s). Rien n'est supprimé :
          remettre le référentiel les fait réapparaître.
        </p>
      )}
      {!bloque && (
        <button type="button" disabled={!modifie || choix.length === 0 || modifier.isPending} onClick={() => modifier.mutate({ referentiels: choix })}
          className="bouton-accent h-10 self-start rounded-full px-5 text-[14px] font-semibold disabled:opacity-45">Enregistrer les référentiels</button>
      )}
      <Erreur e={modifier.error} />
    </Section>
  );
}

function Acteurs({ projetId, bloque }: { projetId: string; bloque: boolean }) {
  const { data: acteurs = [] } = useActeurs(projetId);
  const { data: membres = [] } = useMembres();
  const { data: roles = [] } = useRolesProjet();
  const enregistrer = useEnregistrerObjet(projetId, "acteurs");
  const retirer = useSupprimerObjet(projetId, "acteurs");
  const [ajout, setAjout] = useState({ utilisateur: "", nom: "", email: "", organisme: "", role: "" });
  const externe = ajout.utilisateur === "externe";
  const pret = ajout.role && (externe ? ajout.email.includes("@") : ajout.utilisateur);
  const ajouter = () => enregistrer.mutate(
    externe ? { nom: ajout.nom, email: ajout.email, organisme: ajout.organisme, role: ajout.role } : { utilisateur: ajout.utilisateur, role: ajout.role },
    { onSuccess: () => setAjout({ utilisateur: "", nom: "", email: "", organisme: "", role: "" }) },
  );
  return (
    <Section id="r-acteurs" titre="Acteurs et rôles" aide="Le rôle fixe les droits : l'auditeur lit, le RSSI et l'autorité d'homologation décident, l'autorité d'homologation seule prononce l'homologation. Les contacts externes reçoivent les mails, sans compte.">
      <ul className="flex flex-col divide-y divide-separateur overflow-hidden rounded-2xl bg-remplissage">
        {acteurs.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center gap-3 px-3.5 py-2.5">
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-[15px] font-medium">{a.affichage}</span>
              <span className="truncate text-xs text-texte-2">{a.utilisateur ? "Compte de l'organisation" : `Contact externe${a.organisme ? ` · ${a.organisme}` : ""} · ${a.email}`}</span>
            </span>
            <select aria-label={`Rôle de ${a.affichage}`} value={a.role} disabled={bloque || enregistrer.isPending} onChange={(e) => enregistrer.mutate({ id: a.id, role: e.target.value })}
              className="rounded-xl bg-groupe px-2.5 py-1.5 text-[13px] outline-none">
              {roles.map((r) => <option key={r.id} value={r.id}>{r.libelle}</option>)}
            </select>
            {!bloque && (
              <button type="button" onClick={() => retirer.mutate(a.id)} className="px-2 py-1 text-[13px] font-semibold text-manquant-texte" aria-label={`Retirer ${a.affichage}`}>Retirer</button>
            )}
          </li>
        ))}
      </ul>
      {!bloque && (
        <div className="flex flex-col gap-3 rounded-2xl border border-separateur px-3.5 py-3">
          <span className="text-xs font-semibold text-texte-2">Ajouter un acteur</span>
          <div className="grid gap-3 sm:grid-cols-2">
            <select aria-label="Personne" className={`${saisie} appearance-none`} value={ajout.utilisateur} onChange={(e) => setAjout({ ...ajout, utilisateur: e.target.value })}>
              <option value="">Choisir une personne…</option>
              {membres.map((m) => <option key={m.id} value={m.id}>{m.nom_complet} — {m.email}</option>)}
              <option value="externe">Contact externe (sans compte)</option>
            </select>
            <select aria-label="Rôle" className={`${saisie} appearance-none`} value={ajout.role} onChange={(e) => setAjout({ ...ajout, role: e.target.value })}>
              <option value="">Choisir un rôle…</option>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.libelle}</option>)}
            </select>
            {externe && (
              <>
                <input aria-label="Nom" placeholder="Nom" className={saisie} value={ajout.nom} onChange={(e) => setAjout({ ...ajout, nom: e.target.value })} />
                <input aria-label="Email" type="email" placeholder="Email" className={saisie} value={ajout.email} onChange={(e) => setAjout({ ...ajout, email: e.target.value })} />
                <input aria-label="Organisme" placeholder="Organisme (facultatif)" className={`${saisie} sm:col-span-2`} value={ajout.organisme} onChange={(e) => setAjout({ ...ajout, organisme: e.target.value })} />
              </>
            )}
          </div>
          <button type="button" disabled={!pret || enregistrer.isPending} onClick={ajouter} className="bouton-accent h-10 self-start rounded-full px-5 text-[14px] font-semibold disabled:opacity-45">Ajouter</button>
        </div>
      )}
      <Erreur e={enregistrer.error ?? retirer.error} />
    </Section>
  );
}

function Options({ p, projetId, bloque }: { p: Projet; projetId: string; bloque: boolean }) {
  const modifier = useModifierProjet(projetId);
  return (
    <Section id="r-options" titre="Méthode et options">
      <Bascule libelle="EBIOS RM" aide="Analyse de risques guidée en cinq ateliers, facultative." valeur={p.ebios_active} desactive={bloque || modifier.isPending}
        changer={(v) => modifier.mutate({ ebios_active: v })} />
      <Bascule libelle="Notifications" aide="Mails et alertes dans l'appli à chaque modification (tâches, commentaires, décisions)." valeur={p.notifications_actives}
        desactive={bloque || modifier.isPending} changer={(v) => modifier.mutate({ notifications_actives: v })} />
      <Bascule libelle="Calendrier" aide="Export des échéances (tâches, documents, revues, dérogations, ateliers EBIOS) vers votre agenda." valeur={p.calendrier_actif}
        desactive={bloque || modifier.isPending} changer={(v) => modifier.mutate({ calendrier_actif: v })} />
      {p.calendrier_actif && (
        <a href={`/api/projets/${projetId}/calendrier/`} download className="self-start rounded-full bg-remplissage px-4 py-2 text-[14px] font-semibold text-accent-texte">
          Télécharger le calendrier (.ics)
        </a>
      )}
      <Erreur e={modifier.error} />
    </Section>
  );
}

function Revue({ p, projetId, bloque }: { p: Projet; projetId: string; bloque: boolean }) {
  const modifier = useModifierProjet(projetId);
  const faite = useActionProjet(projetId, "revue-faite");
  const [mois, setMois] = useState(String(p.periodicite_revue_mois));
  const [date, setDate] = useState(p.date_prochaine_revue ?? "");
  useEffect(() => { setMois(String(p.periodicite_revue_mois)); setDate(p.date_prochaine_revue ?? ""); }, [p.periodicite_revue_mois, p.date_prochaine_revue]);
  const retard = p.date_prochaine_revue && p.date_prochaine_revue < dans(0);
  const modifie = Number(mois) !== p.periodicite_revue_mois || date !== (p.date_prochaine_revue ?? "");
  return (
    <Section id="r-revue" titre="Revue périodique" aide="Un rappel part 30 jours avant la revue, puis en cas de retard, au chef de projet, au RSSI et à l'autorité d'homologation.">
      {p.date_prochaine_revue && (
        <p className={`text-[14px] ${retard ? "font-semibold text-manquant-texte" : "text-texte-2"}`}>
          Prochaine revue le {dateFr(p.date_prochaine_revue)}{retard ? " : en retard" : ""}.
        </p>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Champ libelle="Périodicité (mois)">
          <input type="number" min={1} max={60} className={saisie} disabled={bloque} value={mois} onChange={(e) => setMois(e.target.value)} />
        </Champ>
        <Champ libelle="Date de la prochaine revue">
          <input type="date" className={saisie} disabled={bloque} value={date} onChange={(e) => setDate(e.target.value)} />
        </Champ>
      </div>
      {!bloque && (
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={!modifie || modifier.isPending || Number(mois) < 1 || Number(mois) > 60}
            onClick={() => modifier.mutate({ periodicite_revue_mois: Number(mois), date_prochaine_revue: date || null })}
            className="bouton-accent h-10 rounded-full px-5 text-[14px] font-semibold disabled:opacity-45">Enregistrer</button>
          <button type="button" disabled={faite.isPending} onClick={() => faite.mutate({})} className="h-10 rounded-full bg-remplissage px-5 text-[14px] font-semibold">
            La revue a eu lieu
          </button>
        </div>
      )}
      {faite.data && <p className="text-[13px] text-conforme-texte">Revue enregistrée : la suivante est fixée au {dateFr(faite.data.date_prochaine_revue)}.</p>}
      <Erreur e={modifier.error ?? faite.error} />
    </Section>
  );
}

function Decision({ projetId }: { projetId: string }) {
  const { data: tdb } = useTableauDeBord(projetId);
  const prononcer = useActionProjet(projetId, "decision");
  const [b, setB] = useState({ decision: "homologation", date_fin_validite: dans(3 * 365), commentaire: "" });
  if (!tdb) return null;
  const pj = tdb.projet;
  const refus = b.decision === "refus";
  const pointsOuverts = [
    tdb.taches.ouvertes ? `${tdb.taches.ouvertes} tâche(s) ouverte(s)` : "",
    tdb.documents.attendus - tdb.documents.valides ? `${tdb.documents.attendus - tdb.documents.valides} document(s) non validé(s)` : "",
    tdb.evaluation.total - tdb.evaluation.evaluees ? `${tdb.evaluation.total - tdb.evaluation.evaluees} mesure(s) non évaluée(s)` : "",
  ].filter(Boolean);
  return (
    <Section id="r-decision" titre="Décision d'homologation" aide="Prononcée par l'autorité d'homologation du projet, et par elle seule. Aucune conclusion de l'IA ne vaut décision.">
      {pj.decision ? (
        <p className="rounded-2xl bg-remplissage px-3.5 py-3 text-[14px]">
          <span className="font-semibold">{pj.decision_libelle}</span> prononcée par {pj.decision_par} le {dateFr(pj.date_decision)}
          {pj.date_fin_validite ? `, valable jusqu'au ${dateFr(pj.date_fin_validite)}` : ""}.
        </p>
      ) : <p className="text-[14px] text-texte-2">Aucune décision prononcée.</p>}
      {pj.peut_prononcer ? (
        <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); prononcer.mutate(refus ? { decision: b.decision, commentaire: b.commentaire } : b); }}>
          {pointsOuverts.length > 0 && (
            <p className="rounded-2xl bg-partiel/10 px-3.5 py-3 text-[13px] text-partiel-texte">Points encore ouverts : {pointsOuverts.join(" · ")}.</p>
          )}
          <div role="radiogroup" aria-label="Décision" className="flex flex-wrap gap-1.5">
            {DECISIONS.map((d) => (
              <button key={d.cle} type="button" role="radio" aria-checked={b.decision === d.cle} onClick={() => setB({ ...b, decision: d.cle })}
                className={`h-9 rounded-full px-3.5 text-[13px] font-semibold ${b.decision === d.cle ? "bg-groupe shadow-[0_0_0_1.5px_var(--sg-accent)]" : "bg-remplissage text-texte-2"}`}>{d.libelle}</button>
            ))}
          </div>
          {!refus && (
            <Champ libelle="Fin de validité">
              <input type="date" min={dans(1)} className={saisie} value={b.date_fin_validite} onChange={(e) => setB({ ...b, date_fin_validite: e.target.value })} />
            </Champ>
          )}
          <Champ libelle={refus ? "Motif du refus (obligatoire)" : "Commentaire, réserves éventuelles"}>
            <textarea rows={3} className={`${saisie} resize-y`} value={b.commentaire} onChange={(e) => setB({ ...b, commentaire: e.target.value })} />
          </Champ>
          <button type="submit" disabled={prononcer.isPending || (refus ? !b.commentaire.trim() : !b.date_fin_validite || b.date_fin_validite <= dans(0))}
            className="bouton-accent h-11 self-start rounded-full px-6 text-[15px] font-semibold disabled:opacity-45">Prononcer la décision</button>
          <p className="text-xs text-texte-3">Décision datée et nominative, tracée au journal d'audit et notifiée au chef de projet et au RSSI.</p>
        </form>
      ) : <p className="text-[13px] text-texte-2">Seule l'autorité d'homologation désignée parmi les acteurs peut prononcer la décision.</p>}
      <Erreur e={prononcer.error} />
    </Section>
  );
}

function Archivage({ projetId, archive }: { projetId: string; archive: boolean }) {
  const archiver = useActionProjet(projetId, archive ? "desarchiver" : "archiver");
  const [confirmer, setConfirmer] = useState(false);
  return (
    <Section id="r-archivage" titre="Archivage" aide={archive ? "Ce projet est archivé : tout est en lecture seule." : "Un projet archivé passe en lecture seule pour tous. Rien n'est supprimé : preuves et journal restent consultables."}>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" disabled={archiver.isPending} onClick={() => (archive || confirmer ? archiver.mutate({}, { onSuccess: () => setConfirmer(false) }) : setConfirmer(true))}
          className={`h-10 rounded-full px-5 text-[14px] font-semibold ${archive ? "bouton-accent" : "bg-remplissage text-manquant-texte"}`}>
          {archive ? "Désarchiver le projet" : confirmer ? "Confirmer l'archivage" : "Archiver le projet"}
        </button>
        {confirmer && <button type="button" onClick={() => setConfirmer(false)} className="h-10 px-3 text-[14px] text-texte-2">Annuler</button>}
      </div>
      <Erreur e={archiver.error} />
    </Section>
  );
}

export function PageReglages() {
  const { projetId = "" } = useParams();
  const { data: tdb } = useTableauDeBord(projetId);
  const { data: p } = useProjet(projetId);
  const administrer = tdb?.projet.peut_administrer ?? false;
  const archive = tdb?.projet.archive ?? false;
  const bloque = !administrer || archive;

  return (
    <Disposition>
      <div className="flex max-w-[860px] flex-col gap-5">
        <div className="flex flex-col gap-1.5 lg:pt-2.5">
          <span className="text-[13px] font-semibold text-texte-2">{tdb?.projet.nom ?? "Projet"}</span>
          <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Réglages</h1>
          {tdb && !administrer && <p className="text-[15px] text-texte-2">Consultation seule : les réglages reviennent au chef de projet, au RSSI, à l'autorité d'homologation ou à l'administrateur.</p>}
        </div>
        {!p ? <div aria-busy="true" className="h-96 animate-pulse rounded-groupe bg-remplissage" /> : (
          <>
            <Identite p={p} projetId={projetId} bloque={bloque} />
            <Referentiels p={p} projetId={projetId} bloque={bloque} />
            <Acteurs projetId={projetId} bloque={bloque} />
            <Options p={p} projetId={projetId} bloque={bloque} />
            <Revue p={p} projetId={projetId} bloque={bloque} />
            <Decision projetId={projetId} />
            {administrer && <Archivage projetId={projetId} archive={archive} />}
          </>
        )}
      </div>
    </Disposition>
  );
}
