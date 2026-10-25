import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";

import { useConnexion, useMoi } from "../api/hooks";
import { Logo } from "../composants/Disposition";

export function PageConnexion() {
  const { data: moi } = useMoi();
  const connexion = useConnexion();
  const naviguer = useNavigate();
  const retour = (useLocation().state as { depuis?: string } | null)?.depuis ?? "/";
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");

  if (moi) return <Navigate to={retour} replace />;

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    connexion.mutate({ email, password: motDePasse }, { onSuccess: () => naviguer(retour, { replace: true }) });
  };

  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <form onSubmit={soumettre} className="verre flex w-full max-w-[400px] flex-col gap-5 rounded-verre px-6 pt-8 pb-6 sm:px-8">
        <div className="flex flex-col items-center gap-3 text-center">
          <Logo taille={64} decoratif />
          <h1 className="text-[28px] font-bold tracking-[-0.03em]">SoluGation</h1>
          <p className="text-[15px] text-texte-2">Connectez-vous pour suivre vos homologations.</p>
        </div>

        <div className="flex flex-col overflow-hidden rounded-groupe bg-groupe shadow-groupe">
          <label className="flex flex-col gap-0.5 px-4 pt-2.5 pb-2">
            <span className="text-xs font-medium text-texte-2">Email</span>
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-transparent text-[16px] outline-none"
            />
          </label>
          <div aria-hidden="true" className="ml-4 h-px bg-separateur" />
          <label className="flex flex-col gap-0.5 px-4 pt-2.5 pb-2">
            <span className="text-xs font-medium text-texte-2">Mot de passe</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={motDePasse}
              onChange={(e) => setMotDePasse(e.target.value)}
              className="bg-transparent text-[16px] outline-none"
            />
          </label>
        </div>

        {connexion.error && (
          <p role="alert" className="text-center text-sm font-medium text-manquant-texte">
            {connexion.error.message}
          </p>
        )}

        <button
          type="submit"
          disabled={connexion.isPending}
          className="bouton-accent h-[50px] rounded-full text-[15px] font-semibold disabled:opacity-60"
        >
          {connexion.isPending ? "Connexion…" : "Se connecter"}
        </button>
      </form>
    </main>
  );
}
