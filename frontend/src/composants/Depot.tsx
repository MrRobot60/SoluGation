import { useId, useState } from "react";

import { IconeCroix, IconeDepot } from "./Icones";

/* Liste blanche côté client (confort) ; le serveur contrôle le contenu réel du fichier. */
export const EXTENSIONS = [".pdf", ".docx", ".xlsx", ".odt", ".ods", ".txt", ".csv", ".xml", ".nessus", ".png", ".jpg", ".jpeg"];
export const TAILLE_MAX = 50 * 1024 * 1024;

export function taille(octets: number) {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`;
  return `${(octets / 1024 / 1024).toFixed(1).replace(".", ",")} Mo`;
}

export function erreurClient(fichier: File): string | null {
  const ext = fichier.name.includes(".") ? fichier.name.slice(fichier.name.lastIndexOf(".")).toLowerCase() : "";
  if (!EXTENSIONS.includes(ext)) return `Format non accepté (${ext || "sans extension"}).`;
  if (fichier.size > TAILLE_MAX) return "Fichier trop volumineux (50 Mo maximum).";
  if (fichier.size === 0) return "Fichier vide.";
  return null;
}

/** État d'un envoi en cours. */
export type Envoi = { progression: number; erreur?: string; nom: string };

/* ---- Zone de dépôt ----------------------------------------------------------------------- */

export function ZoneDepot({ surFichier, libelle, compacte = false, desactivee = false }: {
  surFichier: (f: File) => void; libelle: string; compacte?: boolean; desactivee?: boolean;
}) {
  const [survol, setSurvol] = useState(false);
  const id = useId();
  if (desactivee) return null;
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setSurvol(true); }}
      onDragLeave={() => setSurvol(false)}
      onDrop={(e) => { e.preventDefault(); setSurvol(false); const f = e.dataTransfer.files[0]; if (f) surFichier(f); }}
      className={`flex items-center gap-3 rounded-2xl border-[1.5px] border-dashed transition-colors duration-200 ease-ios ${compacte ? "px-3.5 py-3" : "flex-col px-6 py-8 text-center"} ${survol ? "border-accent-texte bg-accent-doux" : "border-texte-3"}`}
    >
      <IconeDepot taille={compacte ? 18 : 24} className="shrink-0 text-texte-2" />
      <p className="text-sm text-texte-2">
        {libelle}{" "}
        <label htmlFor={id} className="cursor-pointer font-semibold text-accent-texte">choisir un fichier</label>
      </p>
      <input id={id} type="file" className="sr-only" accept={EXTENSIONS.join(",")}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) surFichier(f); e.target.value = ""; }} />
    </div>
  );
}

export function Progression({ envoi, surFermer }: { envoi: Envoi; surFermer: () => void }) {
  if (envoi.erreur) {
    return (
      <div role="alert" className="flex items-center gap-2 text-[13px] font-medium text-manquant-texte">
        <span className="min-w-0 flex-1">« {envoi.nom} » : {envoi.erreur}</span>
        <button type="button" onClick={surFermer} aria-label="Fermer le message" className="flex size-8 items-center justify-center rounded-full hover:bg-remplissage">
          <IconeCroix taille={14} />
        </button>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1.5" aria-live="polite">
      <span className="text-[13px] text-texte-2">Envoi de « {envoi.nom} »… {Math.round(envoi.progression * 100)} %</span>
      <div className="h-1 overflow-hidden rounded-full bg-piste">
        <div className="h-1 rounded-full bg-accent transition-[width] duration-200" style={{ width: `${envoi.progression * 100}%` }} />
      </div>
    </div>
  );
}

