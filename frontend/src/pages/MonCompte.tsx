import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";

import { ErreurApi } from "../api/client";
import { useChangerMotDePasse, useDeconnexion, useModifierProfil, useMoi } from "../api/hooks";
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

export function PageMonCompte() {
  const deconnexion = useDeconnexion();
  const naviguer = useNavigate();
  return (
    <Disposition>
      <div className="flex max-w-[760px] flex-col gap-5">
        <div className="flex flex-col gap-1.5 lg:pt-2.5">
          <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Mon compte</h1>
          <p className="text-[15px] text-texte-2">Vos informations et votre mot de passe.</p>
        </div>
        <SectionProfil />
        <SectionMotDePasse />
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
