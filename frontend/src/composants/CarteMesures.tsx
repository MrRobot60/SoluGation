import type { ReferentielTdb } from "../api/types";
import { nomCourt, STATUTS } from "./statuts";

/**
 * Une case par mesure, regroupées par référentiel et rangées par statut (colonne par colonne).
 * C'est le contenu que le verre de la synthèse vient flouter : la légende de chaque groupe est donc au-dessus,
 * pour ne jamais passer sous le verre.
 */
export function CarteMesures({ referentiels }: { referentiels: ReferentielTdb[] }) {
  const total = referentiels.reduce((s, r) => s + r.total, 0);
  return (
    <section aria-labelledby="titre-carte" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline gap-x-[18px] gap-y-1.5">
        <h2 id="titre-carte" className="text-[15px] font-semibold">
          {total} mesures, une case chacune
        </h2>
        <ul aria-label="Légende" className="flex flex-wrap gap-x-3.5 gap-y-1">
          {STATUTS.map((s) => (
            <li key={s.cle} className="flex items-center gap-1.5 text-xs text-texte-2">
              <span aria-hidden="true" className={`size-2.5 rounded-[3px] ${s.legende}`} />
              {s.libelle}
            </li>
          ))}
        </ul>
      </div>
      <div className="overflow-x-auto pb-[92px] lg:pb-[104px]">
        <div className="flex w-max gap-2 [--case:7px] [--ecart:3px] [--lignes:20] lg:gap-[22px] lg:[--case:16px] lg:[--ecart:5px] lg:[--lignes:14]">
          {[...referentiels].sort((a, b) => b.total - a.total).map((r) => (
            <figure
              key={r.id}
              role="img"
              aria-label={`${r.nom} : ${STATUTS.map((s) => `${r.statuts[s.cle]} ${s.pluriel}`).join(", ")}`}
              className="m-0 flex w-min flex-col justify-end gap-2 lg:w-auto"
            >
              <figcaption className="text-[11px] leading-tight font-medium text-texte-2 lg:text-xs lg:whitespace-nowrap">
                {nomCourt(r)} · {r.total}
                {r.nouvelle_version && <span className="text-accent-texte"> · nouvelle version disponible</span>}
              </figcaption>
              <div className="grid grid-flow-col [grid-auto-columns:var(--case)] [grid-template-rows:repeat(var(--lignes),var(--case))] gap-(--ecart)">
                {STATUTS.flatMap((s) =>
                  Array.from({ length: r.statuts[s.cle] }, (_, i) => (
                    <div key={`${s.cle}-${i}`} className={`rounded-[2px] lg:rounded-case ${s.fond}`} />
                  )),
                )}
              </div>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}
