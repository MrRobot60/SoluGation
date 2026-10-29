import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation } from "react-router";

import { ErreurApi } from "../api/client";
import { useDefinirMotDePasse, useMotDePasseOublie, useVerifierLien } from "../api/hooks";
import type { NatureLien } from "../api/types";
import { Logo } from "../composants/Disposition";

function Carte({ titre, sousTitre, children }: { titre: string; sousTitre?: ReactNode; children: ReactNode }) {
  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="verre flex w-full max-w-[420px] flex-col gap-5 rounded-verre px-6 pt-8 pb-6 sm:px-8">
        <div className="flex flex-col items-center gap-3 text-center">
          <Logo taille={56} decoratif />
          <h1 className="text-[26px] font-bold tracking-[-0.03em]">{titre}</h1>
          {sousTitre && <p className="text-[15px] text-texte-2">{sousTitre}</p>}
        </div>
        {children}
      </div>
    </main>
  );
}

const champ = "flex flex-col gap-0.5 px-4 pt-2.5 pb-2";
const lienRetour = <Link to="/connexion" className="text-center text-sm font-semibold text-accent-texte">Retour à la connexion</Link>;

export function PageMotDePasseOublie() {
  const demande = useMotDePasseOublie();
  const [email, setEmail] = useState("");
  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    demande.mutate(email);
  };
  if (demande.isSuccess) {
    return (
      <Carte titre="Vérifiez vos mails">
        <p role="status" className="text-center text-[15px] leading-relaxed">
          Si un compte actif correspond à <span className="font-semibold">{email}</span>, un lien pour choisir un nouveau mot de passe
          vient de lui être envoyé. Il est valable 1 heure.
        </p>
        <p className="text-center text-[13px] text-texte-2">Rien reçu après quelques minutes ? Vérifiez les indésirables, ou contactez l'administrateur de votre organisation.</p>
        {lienRetour}
      </Carte>
    );
  }
  return (
    <Carte titre="Mot de passe oublié" sousTitre="Indiquez votre email : vous recevrez un lien pour en choisir un nouveau.">
      <form onSubmit={soumettre} className="flex flex-col gap-5">
        <div className="overflow-hidden rounded-groupe bg-groupe shadow-groupe">
          <label className={champ}>
            <span className="text-xs font-medium text-texte-2">Email</span>
            <input type="email" autoComplete="username" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)}
              className="bg-transparent text-[16px] outline-none" />
          </label>
        </div>
        {demande.error && <p role="alert" className="text-center text-sm font-medium text-manquant-texte">{demande.error.message}</p>}
        <button type="submit" disabled={demande.isPending} className="bouton-accent h-[50px] rounded-full text-[15px] font-semibold disabled:opacity-60">
          {demande.isPending ? "Envoi…" : "Recevoir le lien"}
        </button>
        {lienRetour}
      </form>
    </Carte>
  );
}

/** Lien reçu par mail : invitation (activer le compte) ou réinitialisation. Le jeton est dans le fragment (#uid=…&jeton=…). */
export function PageDefinirMotDePasse({ nature }: { nature: NatureLien }) {
  const { hash } = useLocation();
  const lien = useMemo(() => {
    const p = new URLSearchParams(hash.slice(1));
    const uid = p.get("uid"), jeton = p.get("jeton");
    return uid && jeton ? { nature, uid, jeton } : null;
  }, [hash, nature]);
  const verification = useVerifierLien(lien);
  const definir = useDefinirMotDePasse();
  const [mdp, setMdp] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const invitation = nature === "invitation";

  if (!lien || verification.isError) {
    return (
      <Carte titre="Lien non valable">
        <p role="alert" className="text-center text-[15px] leading-relaxed">
          {verification.error instanceof ErreurApi ? verification.error.message : "Ce lien est incomplet. Ouvrez-le directement depuis le mail reçu."}
        </p>
        {invitation
          ? <p className="text-center text-[13px] text-texte-2">Demandez à l'administrateur de votre organisation de vous renvoyer l'invitation.</p>
          : <Link to="/mot-de-passe-oublie" className="bouton-accent flex h-[50px] items-center justify-center rounded-full text-[15px] font-semibold">Demander un nouveau lien</Link>}
        {lienRetour}
      </Carte>
    );
  }
  if (!verification.data) return <main aria-busy="true" className="min-h-dvh" />;
  const compte = verification.data;

  if (definir.isSuccess) {
    return (
      <Carte titre={invitation ? "Compte activé" : "Mot de passe modifié"}>
        <p role="status" className="text-center text-[15px] leading-relaxed">
          {invitation ? "Votre compte est prêt. Connectez-vous avec votre email et le mot de passe choisi." : "Connectez-vous avec votre nouveau mot de passe. Vos autres sessions ont été fermées."}
        </p>
        <Link to="/connexion" state={{ email: compte.email }} className="bouton-accent flex h-[50px] items-center justify-center rounded-full text-[15px] font-semibold">Se connecter</Link>
      </Carte>
    );
  }

  const tropCourt = mdp.length > 0 && mdp.length < 12;
  const differents = confirmation.length > 0 && confirmation !== mdp;
  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    if (mdp.length >= 12 && mdp === confirmation) definir.mutate({ ...lien, password: mdp });
  };
  const erreurs = definir.error instanceof ErreurApi
    ? ((definir.error.donnees as { password?: string[] } | null)?.password ?? [definir.error.message])
    : definir.error ? [definir.error.message] : [];

  return (
    <Carte
      titre={invitation ? `Bienvenue${compte.prenom ? `, ${compte.prenom}` : ""}` : "Nouveau mot de passe"}
      sousTitre={invitation ? <>Choisissez votre mot de passe pour rejoindre <span className="font-semibold text-texte">{compte.organisation}</span>.</> : compte.email}
    >
      <form onSubmit={soumettre} className="flex flex-col gap-4">
        {/* Champ identifiant (masqué) : les gestionnaires de mots de passe associent le nouveau mot de passe au bon compte. */}
        <input type="email" autoComplete="username" value={compte.email} readOnly hidden />
        <div className="overflow-hidden rounded-groupe bg-groupe shadow-groupe">
          <label className={champ}>
            <span className="text-xs font-medium text-texte-2">Mot de passe</span>
            <input type="password" autoComplete="new-password" required autoFocus minLength={12} value={mdp} onChange={(e) => setMdp(e.target.value)}
              aria-describedby="regles-mdp" className="bg-transparent text-[16px] outline-none" />
          </label>
          <div aria-hidden="true" className="ml-4 h-px bg-separateur" />
          <label className={champ}>
            <span className="text-xs font-medium text-texte-2">Confirmation</span>
            <input type="password" autoComplete="new-password" required value={confirmation} onChange={(e) => setConfirmation(e.target.value)}
              className="bg-transparent text-[16px] outline-none" />
          </label>
        </div>
        <ul id="regles-mdp" className="flex flex-col gap-1 text-[13px] text-texte-2">
          <li className={tropCourt ? "font-medium text-manquant-texte" : mdp.length >= 12 ? "text-conforme-texte" : ""}>
            <span aria-hidden="true">{mdp.length >= 12 ? "✓ " : "· "}</span>12 caractères minimum ({mdp.length})
          </li>
          <li><span aria-hidden="true">· </span>Ni trop courant, ni proche de votre nom ou de votre email. Une phrase de passe est idéale.</li>
          {differents && <li className="font-medium text-manquant-texte">Les deux saisies sont différentes.</li>}
        </ul>
        {erreurs.length > 0 && (
          <div role="alert" className="flex flex-col gap-1 text-sm font-medium text-manquant-texte">
            {erreurs.map((m) => <p key={m}>{m}</p>)}
          </div>
        )}
        <button type="submit" disabled={definir.isPending || mdp.length < 12 || mdp !== confirmation}
          className="bouton-accent h-[50px] rounded-full text-[15px] font-semibold disabled:opacity-60">
          {definir.isPending ? "Enregistrement…" : invitation ? "Activer mon compte" : "Enregistrer le mot de passe"}
        </button>
        {lienRetour}
      </form>
    </Carte>
  );
}
