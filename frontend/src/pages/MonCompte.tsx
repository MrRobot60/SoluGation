import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";

import { ErreurApi } from "../api/client";
import { useChangerMotDePasse, useDeconnexion, useDoubleAuth, useEtatDoubleAuth, useModifierProfil, useMoi } from "../api/hooks";
import { Disposition } from "../composants/Disposition";

const saisie = "w-full rounded-xl bg-remplissage px-3 py-2.5 text-[15px] outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)] read-only:text-texte-2";

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

function Section({ id, titre, description, children }: { id: string; titre: string; description?: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4 rounded-groupe bg-groupe px-4 py-5 shadow-groupe sm:px-6">
      <div className="flex flex-col gap-1">
        <h2 id={id} className="text-[20px] font-bold">{titre}</h2>
        {description && <p className="text-[14px] text-texte-2">{description}</p>}
      </div>
      {children}
    </section>
  );
}

/** Messages du serveur, champ par champ ({"nouveau": [...]}), sinon le message général. */
function erreursDe(erreur: Error | null): string[] {
  if (!erreur) return [];
  const donnees = erreur instanceof ErreurApi ? (erreur.donnees as Record<string, unknown> | null) : null;
  const liste = donnees ? Object.values(donnees).flatMap((v) => (Array.isArray(v) ? v : [])).filter((v): v is string => typeof v === "string") : [];
  return liste.length ? liste : [erreur.message];
}

function SectionProfil() {
  const { data: moi } = useMoi();
  const modifier = useModifierProfil();
  const [p, setP] = useState({ first_name: "", last_name: "", fonction: "" });
  useEffect(() => {
    if (moi) setP({ first_name: moi.first_name, last_name: moi.last_name, fonction: moi.fonction });
  }, [moi]);
  if (!moi) return null;
  const modifie = p.first_name !== moi.first_name || p.last_name !== moi.last_name || p.fonction !== moi.fonction;
  const enregistrer = (e: FormEvent) => {
    e.preventDefault();
    modifier.mutate({ first_name: p.first_name.trim(), last_name: p.last_name.trim(), fonction: p.fonction.trim() });
  };
  return (
    <Section id="titre-profil" titre="Profil" description="Votre nom et votre fonction apparaissent dans les projets, les mails et le journal d'audit.">
      <form onSubmit={enregistrer} className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Champ libelle="Prénom"><input className={saisie} autoComplete="given-name" value={p.first_name} onChange={(e) => setP({ ...p, first_name: e.target.value })} /></Champ>
          <Champ libelle="Nom"><input className={saisie} autoComplete="family-name" value={p.last_name} onChange={(e) => setP({ ...p, last_name: e.target.value })} /></Champ>
          <div className="sm:col-span-2">
            <Champ libelle="Fonction" aide="ex. RSSI, chef de projet, DSI.">
              <input className={saisie} autoComplete="organization-title" value={p.fonction} onChange={(e) => setP({ ...p, fonction: e.target.value })} />
            </Champ>
          </div>
          <Champ libelle="Email" aide="Identifiant de connexion : seul un administrateur peut en inviter un autre.">
            <input className={saisie} value={moi.email} readOnly />
          </Champ>
          <Champ libelle="Organisation et rôle" aide="Le rôle est attribué par un administrateur.">
            <input className={saisie} value={`${moi.organisation.nom} · ${moi.role?.libelle ?? "Membre"}`} readOnly />
          </Champ>
        </div>
        {modifier.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{erreursDe(modifier.error).join(" ")}</p>}
        {modifier.isSuccess && !modifie && <p role="status" className="text-[13px] font-medium text-conforme-texte">Profil enregistré.</p>}
        <button type="submit" disabled={!modifie || modifier.isPending}
          className="self-start rounded-full bg-remplissage px-5 py-2.5 text-[14px] font-semibold disabled:opacity-45">
          {modifier.isPending ? "Enregistrement…" : "Enregistrer"}
        </button>
      </form>
    </Section>
  );
}

function SectionMotDePasse() {
  const { data: moi } = useMoi();
  const changer = useChangerMotDePasse();
  const [m, setM] = useState({ actuel: "", nouveau: "", confirmation: "" });
  const differents = m.confirmation.length > 0 && m.confirmation !== m.nouveau;
  const pret = m.actuel && m.nouveau.length >= 12 && m.nouveau === m.confirmation;
  const envoyer = (e: FormEvent) => {
    e.preventDefault();
    if (pret) changer.mutate({ actuel: m.actuel, nouveau: m.nouveau }, { onSuccess: () => setM({ actuel: "", nouveau: "", confirmation: "" }) });
  };
  return (
    <Section id="titre-mdp" titre="Mot de passe" description="Après le changement, vos autres sessions ouvertes (autres navigateurs, autres appareils) sont fermées et un mail de confirmation vous est envoyé.">
      <form onSubmit={envoyer} className="flex flex-col gap-4">
        <input type="email" autoComplete="username" value={moi?.email ?? ""} readOnly hidden />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Champ libelle="Mot de passe actuel">
              <input className={saisie} type="password" autoComplete="current-password" required value={m.actuel} onChange={(e) => setM({ ...m, actuel: e.target.value })} />
            </Champ>
          </div>
          <Champ libelle="Nouveau mot de passe" aide={`12 caractères minimum (${m.nouveau.length}). Une phrase de passe est idéale.`}>
            <input className={saisie} type="password" autoComplete="new-password" required minLength={12} value={m.nouveau} onChange={(e) => setM({ ...m, nouveau: e.target.value })} />
          </Champ>
          <Champ libelle="Confirmation" aide={differents ? "Les deux saisies sont différentes." : " "}>
            <input className={saisie} type="password" autoComplete="new-password" required value={m.confirmation} onChange={(e) => setM({ ...m, confirmation: e.target.value })}
              aria-invalid={differents} />
          </Champ>
        </div>
        {changer.error && (
          <div role="alert" className="flex flex-col gap-1 text-[13px] font-medium text-manquant-texte">
            {erreursDe(changer.error).map((t) => <p key={t}>{t}</p>)}
          </div>
        )}
        {changer.isSuccess && <p role="status" className="text-[13px] font-medium text-conforme-texte">Mot de passe modifié. Vos autres sessions ont été fermées.</p>}
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" disabled={!pret || changer.isPending}
            className="bouton-accent h-10 rounded-full px-5 text-[14px] font-semibold disabled:opacity-45">
            {changer.isPending ? "Modification…" : "Changer le mot de passe"}
          </button>
          <Link to="/mot-de-passe-oublie" className="text-[13px] font-semibold text-accent-texte">Mot de passe actuel oublié ?</Link>
        </div>
      </form>
    </Section>
  );
}

/** Mot de passe redemandé avant une action sensible sur la double authentification. */
function ConfirmerMotDePasse({ libelle, enCours, erreur, valider, annuler, danger }: {
  libelle: string; enCours: boolean; erreur: Error | null; valider: (mdp: string) => void; annuler: () => void; danger?: boolean;
}) {
  const [mdp, setMdp] = useState("");
  return (
    <form onSubmit={(e) => { e.preventDefault(); valider(mdp); }} className="flex flex-col gap-3 rounded-2xl bg-remplissage/60 p-4">
      <Champ libelle="Mot de passe" aide="Redemandé pour toute modification de la double authentification.">
        <input className={saisie} type="password" autoComplete="current-password" required autoFocus value={mdp} onChange={(e) => setMdp(e.target.value)} />
      </Champ>
      {erreur && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{erreursDe(erreur).join(" ")}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={enCours || !mdp}
          className={`h-10 rounded-full px-5 text-[14px] font-semibold disabled:opacity-45 ${danger ? "bg-manquant/15 text-manquant-texte" : "bouton-accent"}`}>
          {enCours ? "Vérification…" : libelle}
        </button>
        <button type="button" onClick={annuler} className="h-10 rounded-full px-4 text-[14px] font-semibold text-texte-2">Annuler</button>
      </div>
    </form>
  );
}

function CodesSecours({ codes, fermer }: { codes: string[]; fermer: () => void }) {
  const [copie, setCopie] = useState(false);
  const texte = `Codes de secours SoluGation (chacun ne sert qu'une fois)\n\n${codes.join("\n")}\n`;
  const telecharger = () => {
    const url = URL.createObjectURL(new Blob([texte], { type: "text/plain" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "solugation-codes-de-secours.txt" });
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-partiel/10 p-4">
      <p className="text-[14px] font-semibold">Vos codes de secours</p>
      <p className="text-[13px] text-texte-2">
        Chacun permet de se connecter une fois si vous n'avez plus votre téléphone. Conservez-les hors de l'ordinateur (gestionnaire de mots de passe,
        papier dans un lieu sûr). <span className="font-semibold text-texte">Ils ne seront plus affichés.</span>
      </p>
      <ul aria-label="Codes de secours" className="grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-[15px] tabular-nums sm:grid-cols-3">
        {codes.map((c) => <li key={c}>{c}</li>)}
      </ul>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => void navigator.clipboard?.writeText(texte).then(() => setCopie(true))}
          className="h-9 rounded-full bg-remplissage px-4 text-[13px] font-semibold">{copie ? "Copiés" : "Copier"}</button>
        <button type="button" onClick={telecharger} className="h-9 rounded-full bg-remplissage px-4 text-[13px] font-semibold">Télécharger (.txt)</button>
        <button type="button" onClick={fermer} className="bouton-accent h-9 rounded-full px-4 text-[13px] font-semibold">Je les ai mis en lieu sûr</button>
      </div>
    </div>
  );
}

const POLITIQUES = {
  desactivee: "La double authentification est désactivée sur cette installation.",
  facultative: "Facultative : vous choisissez de l'activer.",
  administrateurs: "Obligatoire pour les administrateurs sur cette installation.",
  tous: "Obligatoire pour tous les comptes sur cette installation.",
};

function SectionDoubleAuth() {
  const { data: etat } = useEtatDoubleAuth();
  const { preparer, activer, desactiver, codes } = useDoubleAuth();
  const [etape, setEtape] = useState<"" | "mdp-activer" | "scanner" | "mdp-codes" | "mdp-desactiver">("");
  const [code, setCode] = useState("");
  const [nouveauxCodes, setNouveauxCodes] = useState<string[] | null>(null);
  if (!etat) return null;
  if (etat.politique === "desactivee" && !etat.active) return null;
  const qr = preparer.data;

  return (
    <Section id="titre-2fa" titre="Double authentification"
      description="En plus du mot de passe, un code à 6 chiffres donné par une application de votre téléphone (Aegis, FreeOTP, Google Authenticator, 1Password…). Un mot de passe volé ne suffit plus.">
      <p role="status" className={`rounded-2xl px-3.5 py-3 text-sm ${etat.active ? "bg-conforme/12 text-conforme-texte" : etat.requise ? "bg-manquant/12 text-manquant-texte" : "bg-remplissage text-texte-2"}`}>
        <span className="font-semibold">{etat.active ? "✓ Active. " : etat.requise ? "À activer pour continuer. " : "Inactive. "}</span>
        {POLITIQUES[etat.politique]}
        {etat.active && ` ${etat.codes_secours_restants} code${etat.codes_secours_restants > 1 ? "s" : ""} de secours restant${etat.codes_secours_restants > 1 ? "s" : ""}.`}
      </p>

      {nouveauxCodes && <CodesSecours codes={nouveauxCodes} fermer={() => setNouveauxCodes(null)} />}

      {!etat.active && etape === "" && (
        <button type="button" onClick={() => setEtape("mdp-activer")} className="bouton-accent h-10 self-start rounded-full px-5 text-[14px] font-semibold">
          Activer la double authentification
        </button>
      )}
      {etape === "mdp-activer" && (
        <ConfirmerMotDePasse libelle="Continuer" enCours={preparer.isPending} erreur={preparer.error} annuler={() => { setEtape(""); preparer.reset(); }}
          valider={(mdp) => preparer.mutate(mdp, { onSuccess: () => setEtape("scanner") })} />
      )}
      {etape === "scanner" && qr && (
        <form onSubmit={(e) => { e.preventDefault(); activer.mutate(code, { onSuccess: (r) => { setNouveauxCodes(r.codes_secours); setEtape(""); setCode(""); preparer.reset(); } }); }}
          className="flex flex-col gap-4 rounded-2xl bg-remplissage/60 p-4">
          <ol className="flex list-decimal flex-col gap-1 pl-5 text-[14px]">
            <li>Dans votre application, ajoutez un compte en scannant ce QR code.</li>
            <li>Saisissez le code à 6 chiffres qu'elle affiche.</li>
          </ol>
          <div className="flex flex-wrap items-start gap-5">
            {/* QR code généré par le serveur (SVG, sans ressource externe) ; fond blanc pour la lecture en mode sombre. */}
            <div className="size-[164px] shrink-0 overflow-hidden rounded-xl bg-white p-1 [&>svg]:size-full" dangerouslySetInnerHTML={{ __html: qr.qr_svg }} />
            <div className="flex min-w-0 flex-1 basis-56 flex-col gap-3">
              <div className="flex flex-col gap-1">
                <span className="text-xs font-semibold text-texte-2">Pas d'appareil photo ? Saisissez cette clé :</span>
                <code className="rounded-lg bg-groupe px-2.5 py-1.5 font-mono text-[13px] break-all select-all">{qr.secret.match(/.{1,4}/g)?.join(" ")}</code>
              </div>
              <Champ libelle="Code à 6 chiffres">
                <input className={`${saisie} text-[18px] tracking-[0.12em] tabular-nums`} required autoFocus inputMode="numeric" autoComplete="one-time-code"
                  pattern="[0-9 ]{6,7}" maxLength={7} value={code} onChange={(e) => setCode(e.target.value)} placeholder="123 456" />
              </Champ>
            </div>
          </div>
          {activer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{activer.error.message}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={activer.isPending} className="bouton-accent h-10 rounded-full px-5 text-[14px] font-semibold disabled:opacity-45">
              {activer.isPending ? "Vérification…" : "Activer"}
            </button>
            <button type="button" onClick={() => { setEtape(""); preparer.reset(); activer.reset(); }} className="h-10 rounded-full px-4 text-[14px] font-semibold text-texte-2">Annuler</button>
          </div>
        </form>
      )}

      {etat.active && etape === "" && !nouveauxCodes && (
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => setEtape("mdp-codes")} className="h-10 rounded-full bg-remplissage px-5 text-[14px] font-semibold">Nouveaux codes de secours</button>
          {!etat.requise && (
            <button type="button" onClick={() => setEtape("mdp-desactiver")} className="h-10 rounded-full px-4 text-[14px] font-semibold text-manquant-texte">Désactiver</button>
          )}
        </div>
      )}
      {etape === "mdp-codes" && (
        <ConfirmerMotDePasse libelle="Générer de nouveaux codes" enCours={codes.isPending} erreur={codes.error} annuler={() => { setEtape(""); codes.reset(); }}
          valider={(mdp) => codes.mutate(mdp, { onSuccess: (r) => { setNouveauxCodes(r.codes_secours); setEtape(""); } })} />
      )}
      {etape === "mdp-desactiver" && (
        <ConfirmerMotDePasse libelle="Désactiver" danger enCours={desactiver.isPending} erreur={desactiver.error} annuler={() => { setEtape(""); desactiver.reset(); }}
          valider={(mdp) => desactiver.mutate(mdp, { onSuccess: () => setEtape("") })} />
      )}
    </Section>
  );
}

export function PageMonCompte() {
  const { data: moi } = useMoi();
  const aConfigurer = !!moi && moi.double_auth.requise && !moi.double_auth.active;
  const deconnexion = useDeconnexion();
  const naviguer = useNavigate();
  return (
    <Disposition>
      <div className="flex max-w-[760px] flex-col gap-5">
        <div className="flex flex-col gap-1.5 lg:pt-2.5">
          <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Mon compte</h1>
          <p className="text-[15px] text-texte-2">Vos informations et votre mot de passe.</p>
        </div>
        {aConfigurer && (
          <p role="alert" className="rounded-2xl bg-manquant/12 px-4 py-3 text-[15px] text-manquant-texte">
            <span className="font-semibold">Double authentification obligatoire.</span> Activez-la ci-dessous pour accéder à SoluGation.
          </p>
        )}
        {aConfigurer && <SectionDoubleAuth />}
        <SectionProfil />
        <SectionMotDePasse />
        {!aConfigurer && <SectionDoubleAuth />}
        <Section id="titre-session" titre="Session">
          <button type="button" disabled={deconnexion.isPending}
            onClick={() => deconnexion.mutate(undefined, { onSettled: () => naviguer("/connexion") })}
            className="self-start rounded-full bg-remplissage px-5 py-2.5 text-[14px] font-semibold text-manquant-texte">
            Se déconnecter
          </button>
        </Section>
      </div>
    </Disposition>
  );
}
