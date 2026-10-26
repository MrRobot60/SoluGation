import { useState } from "react";

import type { SyntheseEbios } from "../../api/types";
import { ECHELLE } from "./Objets";

const TEINTE = (niveau: number) =>
  niveau >= 9 ? "bg-manquant/25 text-manquant-texte" : niveau >= 4 ? "bg-partiel/25 text-partiel-texte" : "bg-conforme/20 text-conforme-texte";

/** Matrice gravité × vraisemblance : nombre de risques par case, avant ou après traitement. */
export function Matrice({ matrice }: { matrice: SyntheseEbios["matrice"] }) {
  const [vue, setVue] = useState<"initiale" | "residuelle">("initiale");
  const cases = matrice[vue];
  return (
    <figure className="flex flex-col gap-3 rounded-2xl bg-groupe px-4 py-4 shadow-groupe">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <figcaption className="text-[15px] font-bold">Matrice des risques</figcaption>
        <div role="radiogroup" aria-label="Cotation affichée" className="flex rounded-full bg-remplissage p-[3px]">
          {(["initiale", "residuelle"] as const).map((v) => (
            <button key={v} type="button" role="radio" aria-checked={vue === v} onClick={() => setVue(v)}
              className={`rounded-full px-3 py-1 text-[13px] ${vue === v ? "bg-groupe font-semibold shadow-groupe" : "font-medium text-texte-2"}`}>
              {v === "initiale" ? "Avant traitement" : "Après traitement"}
            </button>
          ))}
        </div>
      </div>
      <table className="w-full table-fixed border-separate border-spacing-1 text-center text-[13px]">
        <caption className="sr-only">Nombre de risques par gravité (lignes) et vraisemblance (colonnes)</caption>
        <thead>
          <tr>
            <th scope="col" className="w-20 text-left text-xs font-medium text-texte-2">Gravité ↓</th>
            {[1, 2, 3, 4].map((v) => <th key={v} scope="col" className="text-xs font-medium text-texte-2">V{v}<span className="sr-only"> ({ECHELLE[v]})</span></th>)}
          </tr>
        </thead>
        <tbody>
          {[4, 3, 2, 1].map((g) => (
            <tr key={g}>
              <th scope="row" className="text-left text-xs font-medium text-texte-2">G{g} <span className="hidden sm:inline">{ECHELLE[g]}</span></th>
              {[1, 2, 3, 4].map((v) => {
                const liste = cases[`${g}-${v}`] ?? [];
                return (
                  <td key={v} title={liste.map((r) => r.intitule).join("\n")}
                    className={`h-12 rounded-lg font-bold tabular-nums ${liste.length ? TEINTE(g * v) : "bg-remplissage text-texte-3"}`}>
                    {liste.length || "·"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-texte-3">Vraisemblance → de V1 (minime) à V4 (quasi certaine). Survolez une case pour voir les risques.</p>
    </figure>
  );
}

const ZONES = { danger: { r: 52, libelle: "Danger", couleur: "var(--sg-manquant)" }, controle: { r: 104, libelle: "Contrôle", couleur: "var(--sg-partiel)" },
                veille: { r: 156, libelle: "Veille", couleur: "var(--sg-conforme)" } } as const;

/** Cartographie de la menace de l'écosystème : chaque partie prenante est placée dans sa zone. */
export function Cartographie({ carto }: { carto: SyntheseEbios["cartographie"] }) {
  const parZone = { danger: [] as typeof carto.parties, controle: [] as typeof carto.parties, veille: [] as typeof carto.parties };
  for (const p of carto.parties) parZone[p.zone].push(p);
  return (
    <figure className="flex flex-col gap-3 rounded-2xl bg-groupe px-4 py-4 shadow-groupe">
      <figcaption className="text-[15px] font-bold">Cartographie de la menace</figcaption>
      <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
        <svg viewBox="-170 -170 340 340" className="w-full max-w-[300px] shrink-0" role="img" aria-label="Parties prenantes par zone de menace">
          {(["veille", "controle", "danger"] as const).map((z) => (
            <circle key={z} r={ZONES[z].r} fill={ZONES[z].couleur} fillOpacity={0.1} stroke={ZONES[z].couleur} strokeOpacity={0.5} />
          ))}
          {(["danger", "controle", "veille"] as const).flatMap((z) => parZone[z].map((p, i, l) => {
            const rayon = z === "danger" ? 26 : ZONES[z].r - 26;
            const angle = (2 * Math.PI * i) / Math.max(l.length, 1) - Math.PI / 2;
            const x = rayon * Math.cos(angle), y = rayon * Math.sin(angle);
            return (
              <g key={p.id}>
                <circle cx={x} cy={y} r={p.critique ? 7 : 5} fill={ZONES[z].couleur} stroke="var(--sg-groupe)" strokeWidth={2} />
                <text x={x} y={y - 10} textAnchor="middle" fontSize="10" fill="currentColor">{p.nom.length > 16 ? `${p.nom.slice(0, 15)}…` : p.nom}</text>
              </g>
            );
          }))}
        </svg>
        <ul className="flex w-full flex-col gap-2 text-[13px]">
          {(["danger", "controle", "veille"] as const).map((z) => (
            <li key={z}>
              <span className="font-semibold">{ZONES[z].libelle}</span>
              <span className="text-texte-2"> · {z === "danger" ? `menace ≥ ${carto.seuils.danger}` : z === "controle" ? `menace ≥ ${carto.seuils.controle}` : "en dessous"}</span>
              <span className="block text-texte-2">{parZone[z].map((p) => `${p.nom} (${p.niveau_menace})${p.critique ? " · critique" : ""}`).join(", ") || "—"}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="text-xs text-texte-3">Menace = (dépendance × pénétration) / (maturité cyber × confiance). Seuils par défaut, ajustables plus tard.</p>
    </figure>
  );
}
