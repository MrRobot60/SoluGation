import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";

import { useComptes, useEnregistrerCompte, useEnregistrerIA, useEtatIA, useModifierOrganisation, useMoi, useRenvoyerInvitation, useTesterIA } from "../api/hooks";
import type { Compte, EtatIA, RoleCompte } from "../api/types";
import { Disposition } from "../composants/Disposition";
import { IconeEtincelle } from "../composants/Icones";
import { quand } from "../lib/format";

/** Raccourcis : préremplissent l'adresse (et un modèle courant) ; tout reste modifiable. */
const PRESELECTIONS = [
  { cle: "scaleway", nom: "Scaleway", url: "https://api.scaleway.ai/v1", modele: "mistral-small-3.2-24b-instruct-2506" },
  { cle: "mistral", nom: "Mistral", url: "https://api.mistral.ai/v1", modele: "mistral-small-latest" },
  { cle: "openai", nom: "OpenAI", url: "https://api.openai.com/v1", modele: "" },
  { cle: "ollama", nom: "Ollama (réseau local)", url: "http://ollama:11434/v1", modele: "" },
  { cle: "autre", nom: "", url: "", modele: "" },
];
const SOURCES: Record<EtatIA["source"], string> = {
  ecran: "Fournisseur configuré sur cet écran.",
  fichier: "Fournisseur défini dans le fichier de configuration (.env). Un fournisseur activé ici le remplacera.",
  aucune: "Aucune IA : SoluGation fonctionne entièrement sans, les fonctions IA sont masquées.",
};

const saisie = "w-full rounded-xl bg-remplissage px-3 py-2.5 text-[15px] outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)]";

function Champ({ libelle, aide, children }: { libelle: string; aide?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="flex flex-col">
        <span className="text-xs font-semibold text-texte-2">{libelle}</span>
        {aide && <span className="text-xs text-texte-3">{aide}</span>}
      </span>
      {children}
    </label>
  );
}

function SectionIA() {
  const { data: etat } = useEtatIA(true);
  const enregistrer = useEnregistrerIA();
  const tester = useTesterIA();
  const [b, setB] = useState({ nom: "", url: "", modele: "", cle: "" });
  const [accepte, setAccepte] = useState(false);
  useEffect(() => {
    if (etat) setB({ nom: etat.ecran.nom, url: etat.ecran.url, modele: etat.ecran.modele, cle: "" });
  }, [etat]);
  if (!etat) return <div aria-busy="true" className="h-80 animate-pulse rounded-groupe bg-remplissage" />;

  const e = etat.ecran;
  const modifie = b.nom !== e.nom || b.url !== e.url || b.modele !== e.modele || b.cle !== "";
  const changeFournisseur = b.url !== e.url || b.modele !== e.modele || b.cle !== "";
  const responsabiliteValide = Boolean(e.responsabilite_acceptee_le) && !changeFournisseur;
  const sauver = (actif?: boolean) => enregistrer.mutate(
    { nom: b.nom, url: b.url, modele: b.modele, ...(b.cle ? { cle: b.cle } : {}), ...(actif === undefined ? {} : { actif }),
      ...(accepte ? { accepter_responsabilite: true } : {}) },
    { onSuccess: () => { setAccepte(false); tester.reset(); } },
  );

  return (
    <section aria-labelledby="titre-ia" className="flex flex-col gap-4 rounded-groupe bg-groupe px-4 py-5 shadow-groupe sm:px-6">
      <div className="flex flex-col gap-1">
        <h2 id="titre-ia" className="flex items-center gap-2 text-[20px] font-bold"><IconeEtincelle taille={19} className="text-accent-texte" /> Intelligence artificielle</h2>
        <p className="text-[14px] leading-snug text-texte-2">
          Facultative. Branchez n'importe quel fournisseur proposant une API compatible OpenAI, dans le cloud ou sur votre réseau.
          L'IA propose (analyse des documents, recommandations, rédaction des rapports, EBIOS RM), un humain valide toujours.
        </p>
      </div>

      <p role="status" className={`rounded-2xl px-3.5 py-3 text-sm ${etat.disponible ? "bg-conforme/12 text-conforme-texte" : "bg-remplissage text-texte-2"}`}>
        <span className="font-semibold">{etat.disponible ? "IA active. " : "IA inactive. "}</span>{SOURCES[etat.source]}
        {etat.source === "fichier" && <> ({[etat.fichier.nom || etat.fichier.fournisseur, etat.fichier.modele].filter(Boolean).join(", ")})</>}
      </p>

      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-semibold text-texte-2">Préremplir</span>
        <div className="flex flex-wrap gap-1.5">
          {PRESELECTIONS.map((p) => (
            <button key={p.cle} type="button" onClick={() => setB({ ...b, nom: p.nom, url: p.url, modele: p.modele || b.modele })}
              className="rounded-full bg-remplissage px-3 py-1.5 text-[13px] font-medium">{p.nom || "Autre"}</button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Champ libelle="Nom affiché" aide="Visible dans l'appli et le journal.">
          <input className={saisie} value={b.nom} onChange={(ev) => setB({ ...b, nom: ev.target.value })} placeholder="ex. IA interne" />
        </Champ>
        <Champ libelle="Modèle" aide="Identifiant exact attendu par le fournisseur.">
          <input className={saisie} value={b.modele} onChange={(ev) => setB({ ...b, modele: ev.target.value })} placeholder="ex. mistral-small-latest" />
        </Champ>
        <div className="sm:col-span-2">
          <Champ libelle="Adresse de l'API" aide={etat.reseau_local_autorise ? "Réseau local autorisé par la configuration." : "HTTPS, adresse publique. Les adresses internes sont refusées sauf autorisation dans le fichier de configuration."}>
            <input className={saisie} value={b.url} inputMode="url" onChange={(ev) => setB({ ...b, url: ev.target.value })} placeholder="https://api.fournisseur.eu/v1" />
          </Champ>
        </div>
        <div className="sm:col-span-2">
          <Champ libelle="Clé d'API" aide={e.a_une_cle ? `Clé enregistrée se terminant par « ${e.cle_fin} ». Laissez vide pour la conserver.` : "Facultative pour un modèle local sans authentification."}>
            <input className={saisie} type="password" autoComplete="off" value={b.cle} onChange={(ev) => setB({ ...b, cle: ev.target.value })}
              placeholder={e.a_une_cle ? "••••••••" : ""} />
          </Champ>
        </div>
      </div>

      {(!responsabiliteValide || !e.actif) && (
        <label className="flex items-start gap-3 rounded-2xl bg-partiel/10 px-3.5 py-3 text-[13px] leading-snug">
          <input type="checkbox" checked={accepte} onChange={(ev) => setAccepte(ev.target.checked)} className="mt-0.5 size-5 shrink-0 accent-[var(--sg-accent)]" />
          <span>
            <span className="font-semibold">J'accepte la responsabilité de ce choix.</span> J'ai vérifié les conditions de ce fournisseur
            (conservation des données envoyées, usage pour l'entraînement, localisation) au regard des documents de mes organisations.
            Les extraits de documents, constats et données de projet lui seront transmis lors des analyses.
          </span>
        </label>
      )}
      {responsabiliteValide && (
        <p className="text-xs text-texte-2">Responsabilité acceptée par {e.responsabilite_acceptee_par} {quand(e.responsabilite_acceptee_le!)}.</p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" disabled={!modifie || enregistrer.isPending} onClick={() => sauver()}
          className="h-10 rounded-full bg-remplissage px-5 text-[14px] font-semibold disabled:opacity-45">Enregistrer</button>
        <button type="button" disabled={modifie || !e.url || tester.isPending} onClick={() => tester.mutate()}
          className="h-10 rounded-full bg-remplissage px-5 text-[14px] font-semibold disabled:opacity-45">
          {tester.isPending ? "Test en cours…" : "Tester la connexion"}
        </button>
        {e.actif && !changeFournisseur ? (
          <button type="button" disabled={enregistrer.isPending} onClick={() => sauver(false)}
            className="h-10 rounded-full px-4 text-[14px] font-semibold text-manquant-texte">Désactiver l'IA</button>
        ) : (
          <button type="button" disabled={!b.url || !b.modele || !(accepte || responsabiliteValide) || enregistrer.isPending} onClick={() => sauver(true)}
            className="bouton-accent h-10 rounded-full px-5 text-[14px] font-semibold disabled:opacity-45">Enregistrer et activer</button>
        )}
      </div>
      {modifie && <p className="-mt-2 text-xs text-texte-2">Enregistrez avant de tester : le test utilise la configuration enregistrée, sans aucune donnée de projet.</p>}
      {tester.data && (
        <p role="status" className={`text-[13px] font-medium ${tester.data.ok ? "text-conforme-texte" : "text-manquant-texte"}`}>
          {tester.data.ok ? `Connexion réussie (${tester.data.duree_ms} ms).` : `Échec : ${tester.data.detail}`}
        </p>
      )}
      {(enregistrer.error || tester.error) && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{(enregistrer.error ?? tester.error)!.message}</p>}
      {e.modifie_le && <p className="text-xs text-texte-3">Dernière modification par {e.modifie_par} {quand(e.modifie_le)}. Chaque changement est tracé au journal d'audit.</p>}
    </section>
  );
}

const ROLES: { cle: RoleCompte; libelle: string; aide: string }[] = [
  { cle: "membre", libelle: "Membre", aide: "Voit les projets dont il est acteur." },
  { cle: "admin", libelle: "Administrateur", aide: "Voit tous les projets, gère les comptes et l'organisation." },
  { cle: "auditeur", libelle: "Auditeur", aide: "Lecture seule partout." },
];
const ETATS: Record<Compte["etat"], { libelle: string; classe: string; symbole: string }> = {
  actif: { libelle: "Actif", classe: "bg-conforme/12 text-conforme-texte", symbole: "●" },
  invite: { libelle: "Invitation envoyée", classe: "bg-partiel/12 text-partiel-texte", symbole: "✉" },
  desactive: { libelle: "Désactivé", classe: "bg-remplissage text-texte-2", symbole: "○" },
};

function FormulaireInvitation({ fermer }: { fermer: () => void }) {
  const enregistrer = useEnregistrerCompte();
  const [c, setC] = useState({ email: "", first_name: "", last_name: "", fonction: "", role: "membre" as RoleCompte });
  const [envoye, setEnvoye] = useState("");
  const envoyer = (ev: FormEvent) => {
    ev.preventDefault();
    enregistrer.mutate(c, {
      onSuccess: () => { setEnvoye(c.email); setC({ email: "", first_name: "", last_name: "", fonction: "", role: c.role }); },
    });
  };
  return (
    <form onSubmit={envoyer} aria-label="Inviter une personne" className="flex flex-col gap-4 rounded-2xl bg-remplissage/60 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Champ libelle="Email professionnel">
            <input className={saisie} type="email" required autoFocus value={c.email} onChange={(ev) => setC({ ...c, email: ev.target.value })} />
          </Champ>
        </div>
        <Champ libelle="Prénom"><input className={saisie} value={c.first_name} onChange={(ev) => setC({ ...c, first_name: ev.target.value })} /></Champ>
        <Champ libelle="Nom"><input className={saisie} value={c.last_name} onChange={(ev) => setC({ ...c, last_name: ev.target.value })} /></Champ>
        <div className="sm:col-span-2">
          <Champ libelle="Fonction" aide="Facultatif, ex. RSSI, chef de projet, DSI.">
            <input className={saisie} value={c.fonction} onChange={(ev) => setC({ ...c, fonction: ev.target.value })} />
          </Champ>
        </div>
      </div>
      <fieldset className="flex flex-col gap-1.5">
        <legend className="mb-1.5 text-xs font-semibold text-texte-2">Rôle dans l'organisation</legend>
        {ROLES.map((r) => (
          <label key={r.cle} className="flex items-start gap-2.5 text-[14px]">
            <input type="radio" name="role" checked={c.role === r.cle} onChange={() => setC({ ...c, role: r.cle })} className="mt-1 accent-[var(--sg-accent)]" />
            <span><span className="font-medium">{r.libelle}</span> <span className="text-texte-2">· {r.aide}</span></span>
          </label>
        ))}
      </fieldset>
      <p className="text-[13px] text-texte-2">Un mail d'invitation est envoyé : la personne choisit elle-même son mot de passe (lien valable 7 jours). Les projets se partagent ensuite depuis leurs réglages.</p>
      {enregistrer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{enregistrer.error.message}</p>}
      {envoye && !enregistrer.error && <p role="status" className="text-[13px] font-medium text-conforme-texte">Invitation envoyée à {envoye}.</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={enregistrer.isPending} className="bouton-accent h-10 rounded-full px-5 text-[14px] font-semibold disabled:opacity-60">
          {enregistrer.isPending ? "Envoi…" : "Envoyer l'invitation"}
        </button>
        <button type="button" onClick={fermer} className="h-10 rounded-full px-4 text-[14px] font-semibold text-texte-2">Fermer</button>
      </div>
    </form>
  );
}

function LigneCompte({ c, moiInstallation }: { c: Compte; moiInstallation: boolean }) {
  const enregistrer = useEnregistrerCompte();
  const renvoyer = useRenvoyerInvitation();
  const [confirmer, setConfirmer] = useState(false);
  useEffect(() => {
    if (!confirmer) return;
    const t = setTimeout(() => setConfirmer(false), 5000);
    return () => clearTimeout(t);
  }, [confirmer]);
  const verrouille = c.est_moi || (c.is_superuser && !moiInstallation);
  const etat = ETATS[c.etat];
  const erreur = enregistrer.error ?? renvoyer.error;
  return (
    <li className="flex flex-col gap-2 border-b border-separateur py-3 last:border-b-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="flex min-w-0 basis-full flex-col sm:basis-0 sm:flex-1">
          <span className="truncate text-[15px] font-semibold">
            {c.first_name || c.last_name ? c.nom_complet : c.email}
            {c.est_moi && <span className="ml-1.5 text-xs font-medium text-texte-2">(vous)</span>}
            {c.is_superuser && <span className="ml-1.5 text-xs font-medium text-texte-2">· admin. de l'installation</span>}
          </span>
          <span className="truncate text-[13px] text-texte-2">
            {[c.first_name || c.last_name ? c.email : "", c.fonction].filter(Boolean).join(" · ")}
            {(c.first_name || c.last_name || c.fonction) && " · "}
            {c.last_login ? `connexion ${quand(c.last_login)}` : "jamais connecté"}
          </span>
        </span>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${etat.classe}`}><span aria-hidden="true">{etat.symbole} </span>{etat.libelle}</span>
        <select aria-label={`Rôle de ${c.email}`} value={c.role} disabled={verrouille || !c.is_active || enregistrer.isPending}
          onChange={(ev) => enregistrer.mutate({ id: c.id, role: ev.target.value as RoleCompte })}
          className="rounded-full bg-remplissage px-3 py-1.5 text-[13px] font-medium outline-none disabled:opacity-60">
          {ROLES.map((r) => <option key={r.cle} value={r.cle}>{r.libelle}</option>)}
        </select>
      </div>
      {!verrouille && (
        <div className="flex flex-wrap gap-3 text-[13px] font-semibold">
          {c.etat === "invite" && (
            <button type="button" disabled={renvoyer.isPending} onClick={() => renvoyer.mutate(c.id)} className="text-accent-texte disabled:opacity-60">
              {renvoyer.isSuccess ? "Invitation renvoyée" : "Renvoyer l'invitation"}
            </button>
          )}
          {c.is_active ? (
            <button type="button" disabled={enregistrer.isPending}
              onClick={() => (confirmer ? enregistrer.mutate({ id: c.id, is_active: false }, { onSettled: () => setConfirmer(false) }) : setConfirmer(true))}
              className="text-manquant-texte disabled:opacity-60">
              {confirmer ? "Confirmer : couper l'accès maintenant" : "Désactiver"}
            </button>
          ) : (
            <button type="button" disabled={enregistrer.isPending} onClick={() => enregistrer.mutate({ id: c.id, is_active: true })} className="text-accent-texte">
              Réactiver
            </button>
          )}
        </div>
      )}
      {erreur && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{erreur.message}</p>}
    </li>
  );
}

function SectionComptes() {
  const { data: moi } = useMoi();
  const { data: comptes } = useComptes();
  const [inviter, setInviter] = useState(false);
  const [q, setQ] = useState("");
  const [desactives, setDesactives] = useState(false);
  const t = q.trim().toLowerCase();
  const liste = (comptes ?? []).filter((c) => (desactives || c.is_active)
    && (!t || `${c.nom_complet} ${c.email} ${c.fonction}`.toLowerCase().includes(t)));
  const nbDesactives = (comptes ?? []).filter((c) => !c.is_active).length;
  return (
    <section aria-labelledby="titre-comptes" className="flex flex-col gap-4 rounded-groupe bg-groupe px-4 py-5 shadow-groupe sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 id="titre-comptes" className="text-[20px] font-bold">Comptes</h2>
          <p className="text-[14px] text-texte-2">
            Les personnes de votre organisation. Un compte désactivé ne peut plus se connecter ; son historique est conservé.
          </p>
        </div>
        {!inviter && (
          <button type="button" onClick={() => setInviter(true)} className="bouton-accent h-10 shrink-0 rounded-full px-5 text-[14px] font-semibold">
            Inviter une personne
          </button>
        )}
      </div>
      {inviter && <FormulaireInvitation fermer={() => setInviter(false)} />}
      {(comptes?.length ?? 0) > 6 && (
        <input type="search" aria-label="Rechercher un compte" value={q} onChange={(ev) => setQ(ev.target.value)} placeholder="Rechercher un nom, un email, une fonction"
          className={saisie} />
      )}
      {!comptes ? <div aria-busy="true" className="h-40 animate-pulse rounded-2xl bg-remplissage" /> : (
        <ul aria-label="Comptes de l'organisation">
          {liste.map((c) => <LigneCompte key={c.id} c={c} moiInstallation={!!moi?.est_admin_instance} />)}
          {liste.length === 0 && <li className="py-3 text-sm text-texte-2">Aucun compte.</li>}
        </ul>
      )}
      {nbDesactives > 0 && (
        <label className="flex items-center gap-2 text-[13px] text-texte-2">
          <input type="checkbox" checked={desactives} onChange={(ev) => setDesactives(ev.target.checked)} className="size-4 accent-[var(--sg-accent)]" />
          Afficher les comptes désactivés ({nbDesactives})
        </label>
      )}
    </section>
  );
}

function SectionOrganisation() {
  const { data: moi } = useMoi();
  const modifier = useModifierOrganisation();
  if (!moi) return null;
  const active = moi.organisation.ia_activee;
  return (
    <section aria-labelledby="titre-org" className="flex flex-col gap-3 rounded-groupe bg-groupe px-4 py-5 shadow-groupe sm:px-6">
      <h2 id="titre-org" className="text-[20px] font-bold">{moi.organisation.nom}</h2>
      <label className="flex items-start gap-3 text-[15px]">
        <input type="checkbox" checked={active} disabled={modifier.isPending} onChange={(ev) => modifier.mutate({ ia_activee: ev.target.checked })}
          className="mt-0.5 size-5 shrink-0 accent-[var(--sg-accent)]" />
        <span className="flex flex-col">
          <span className="font-medium">Autoriser l'IA pour cette organisation</span>
          <span className="text-[13px] text-texte-2">
            Décoché : aucune donnée de l'organisation n'est envoyée à un fournisseur, même si l'installation en a un.
          </span>
        </span>
      </label>
      {modifier.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{modifier.error.message}</p>}
    </section>
  );
}

export function PageAdministration() {
  const { data: moi } = useMoi();
  return (
    <Disposition>
      <div className="flex max-w-[860px] flex-col gap-5">
        <div className="flex flex-col gap-1.5 lg:pt-2.5">
          <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Administration</h1>
          <p className="text-[15px] text-texte-2">Comptes, réglages de votre organisation et de l'installation.</p>
        </div>
        {moi && !moi.est_admin && !moi.est_admin_instance && <p className="text-[15px] text-texte-2">Cette page est réservée aux administrateurs.</p>}
        {moi?.est_admin && <SectionComptes />}
        {moi?.est_admin && <SectionOrganisation />}
        {moi?.est_admin_instance && <SectionIA />}
        {moi?.est_admin && (
          <Link to="/journal" className="self-start rounded-full bg-remplissage px-4 py-2 text-[14px] font-semibold text-accent-texte">
            Journal d'audit de toute l'organisation
          </Link>
        )}
      </div>
    </Disposition>
  );
}
