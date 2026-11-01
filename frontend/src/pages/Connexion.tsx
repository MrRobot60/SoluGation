import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";

import { useConnexion, useConnexionCode, useMoi } from "../api/hooks";
import { Logo } from "../composants/Disposition";
import { MentionLicence } from "../composants/MentionLicence";

const champ = "flex flex-col gap-0.5 px-4 pt-2.5 pb-2";

/** Second temps : code à 6 chiffres de l'application, ou code de secours. */
function EtapeCode({ retour, annuler }: { retour: string; annuler: () => void }) {
  const code = useConnexionCode();
  const naviguer = useNavigate();
  const [valeur, setValeur] = useState("");
  const [secours, setSecours] = useState(false);
  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    code.mutate(valeur.trim(), { onSuccess: () => naviguer(retour, { replace: true }) });
  };
  return (
    <form onSubmit={soumettre} className="flex flex-col gap-5">
      <p className="text-center text-[15px] text-texte-2">
        {secours ? "Saisissez l'un de vos codes de secours (il ne servira qu'une fois)." : "Saisissez le code à 6 chiffres affiché par votre application d'authentification."}
      </p>
      <div className="overflow-hidden rounded-groupe bg-groupe shadow-groupe">
        <label className={champ}>
          <span className="text-xs font-medium text-texte-2">{secours ? "Code de secours" : "Code"}</span>
          <input key={String(secours)} required autoFocus value={valeur} onChange={(e) => setValeur(e.target.value)}
            {...(secours
              ? { autoComplete: "off", placeholder: "xxxxx-xxxxx", spellCheck: false }
              : { autoComplete: "one-time-code", inputMode: "numeric" as const, pattern: "[0-9 ]{6,7}", maxLength: 7, placeholder: "123 456" })}
            className="bg-transparent text-[20px] tracking-[0.12em] tabular-nums outline-none placeholder:text-texte-3" />
        </label>
      </div>
      {code.error && <p role="alert" className="text-center text-sm font-medium text-manquant-texte">{code.error.message}</p>}
      <button type="submit" disabled={code.isPending} className="bouton-accent h-[50px] rounded-full text-[15px] font-semibold disabled:opacity-60">
        {code.isPending ? "Vérification…" : "Valider"}
      </button>
      <div className="flex justify-between text-sm font-semibold">
        <button type="button" onClick={() => { setSecours(!secours); setValeur(""); code.reset(); }} className="text-accent-texte">
          {secours ? "Utiliser l'application" : "Utiliser un code de secours"}
        </button>
        <button type="button" onClick={annuler} className="text-texte-2">Annuler</button>
      </div>
      <p className="text-center text-[13px] text-texte-2">Téléphone perdu et plus de code de secours ? L'administrateur de votre organisation peut réinitialiser votre double authentification.</p>
    </form>
  );
}

export function PageConnexion() {
  const { data: moi } = useMoi();
  const connexion = useConnexion();
  const naviguer = useNavigate();
  const etat = useLocation().state as { depuis?: string; email?: string } | null;
  const retour = etat?.depuis ?? "/";
  const [email, setEmail] = useState(etat?.email ?? "");
  const [motDePasse, setMotDePasse] = useState("");
  const [codeAttendu, setCodeAttendu] = useState(false);

  if (moi) return <Navigate to={retour} replace />;

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    connexion.mutate({ email, password: motDePasse }, {
      onSuccess: (r) => {
        setMotDePasse("");
        if ("double_authentification" in r) setCodeAttendu(true);
        else naviguer(retour, { replace: true });
      },
    });
  };

  return (
    <main className="relative flex min-h-dvh items-center justify-center px-4 pt-10 pb-16">
      <div className="verre flex w-full max-w-[400px] flex-col gap-5 rounded-verre px-6 pt-8 pb-6 sm:px-8">
        <div className="flex flex-col items-center gap-3 text-center">
          <Logo taille={64} decoratif />
          <h1 className="text-[28px] font-bold tracking-[-0.03em]">{codeAttendu ? "Vérification" : "SoluGation"}</h1>
          {!codeAttendu && <p className="text-[15px] text-texte-2">Connectez-vous pour suivre vos homologations.</p>}
        </div>

        {codeAttendu ? <EtapeCode retour={retour} annuler={() => { setCodeAttendu(false); connexion.reset(); }} /> : (
          <form onSubmit={soumettre} className="flex flex-col gap-5">
            <div className="flex flex-col overflow-hidden rounded-groupe bg-groupe shadow-groupe">
              <label className={champ}>
                <span className="text-xs font-medium text-texte-2">Email</span>
                <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)}
                  className="bg-transparent text-[16px] outline-none" />
              </label>
              <div aria-hidden="true" className="ml-4 h-px bg-separateur" />
              <label className={champ}>
                <span className="text-xs font-medium text-texte-2">Mot de passe</span>
                <input type="password" autoComplete="current-password" required value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)}
                  className="bg-transparent text-[16px] outline-none" />
              </label>
            </div>

            {connexion.error && <p role="alert" className="text-center text-sm font-medium text-manquant-texte">{connexion.error.message}</p>}

            <button type="submit" disabled={connexion.isPending} className="bouton-accent h-[50px] rounded-full text-[15px] font-semibold disabled:opacity-60">
              {connexion.isPending ? "Connexion…" : "Se connecter"}
            </button>
            <Link to="/mot-de-passe-oublie" className="text-center text-sm font-semibold text-accent-texte">Mot de passe oublié ?</Link>
          </form>
        )}
      </div>
      <MentionLicence className="absolute inset-x-4 bottom-4" />
    </main>
  );
}
