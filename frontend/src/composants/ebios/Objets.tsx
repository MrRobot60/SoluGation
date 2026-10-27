import { useId, useState, type ReactNode } from "react";

import { useEnregistrerObjet, useSupprimerObjet } from "../../api/hooks";
import type { ObjetEbios } from "../../api/types";
import { IconePlus } from "../Icones";

export type Option = { valeur: string; libelle: string };

export type Champ = { cle: string; libelle: string; aide?: string; requis?: boolean } & (
  | { type: "texte" | "zone" | "date" | "booleen" | "echelle" }
  | { type: "choix" | "lien" | "liens"; options: Option[] }
);

export interface Config {
  ressource: string;
  /** Chemin d'API ; par défaut `ebios/<ressource>`. */
  api?: string;
  /** Objet non modifiable (ex. dérogation déjà décidée). */
  verrou?: (o: ObjetEbios) => boolean;
  /** Actions affichées sous l'objet (ex. décisions). */
  actions?: (o: ObjetEbios) => ReactNode;
  titre: string;
  aide?: string;
  champs: Champ[];
  resume: (o: ObjetEbios) => ReactNode;
  detail?: (o: ObjetEbios) => ReactNode;
  vide: string;
  ajout: string;
}

export const ECHELLE = ["", "Faible", "Modéré", "Important", "Très élevé"];

const saisie = "w-full rounded-xl bg-remplissage px-3 py-2 text-[15px] outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)] disabled:opacity-70";

function Echelle({ valeur, changer, libelle }: { valeur: number | null; changer: (v: number) => void; libelle: string }) {
  return (
    <div role="radiogroup" aria-label={libelle} className="flex gap-1">
      {[1, 2, 3, 4].map((n) => (
        <button key={n} type="button" role="radio" aria-checked={valeur === n} title={ECHELLE[n]} onClick={() => changer(n)}
          className={`h-9 min-w-9 rounded-full px-3 text-[13px] font-semibold tabular-nums transition-colors duration-200 ease-ios ${valeur === n ? "bg-accent text-white" : "bg-remplissage text-texte-2"}`}>
          {n}<span className="sr-only"> : {ECHELLE[n]}</span>
        </button>
      ))}
    </div>
  );
}

function ChampSaisi({ c, valeur, changer }: { c: Champ; valeur: unknown; changer: (v: unknown) => void }) {
  const id = `${useId()}-${c.cle}`; // unique même si plusieurs formulaires sont ouverts
  const entete = (
    <span className="flex flex-col">
      <span className="text-xs font-semibold text-texte-2">{c.libelle}{c.requis ? " *" : ""}</span>
      {c.aide && <span className="text-xs text-texte-3">{c.aide}</span>}
    </span>
  );
  if (c.type === "echelle") return <div className="flex flex-col gap-1.5">{entete}<Echelle valeur={(valeur as number) ?? null} changer={changer} libelle={c.libelle} /></div>;
  if (c.type === "booleen") {
    return (
      <label className="flex items-center gap-2.5 text-[15px]">
        <input type="checkbox" checked={Boolean(valeur)} onChange={(e) => changer(e.target.checked)} className="size-5 accent-[var(--sg-accent)]" />
        <span className="flex flex-col"><span className="font-medium">{c.libelle}</span>{c.aide && <span className="text-xs text-texte-3">{c.aide}</span>}</span>
      </label>
    );
  }
  if (c.type === "liens") {
    const choisis = new Set((valeur as string[]) ?? []);
    return (
      <fieldset className="flex flex-col gap-1.5">
        <legend className="mb-1.5">{entete}</legend>
        {c.options.length === 0 ? <p className="text-[13px] text-texte-3">Rien à relier pour l'instant.</p> : (
          <div className="flex flex-wrap gap-1.5">
            {c.options.map((o) => {
              const actif = choisis.has(o.valeur);
              return (
                <button key={o.valeur} type="button" aria-pressed={actif}
                  onClick={() => { const n = new Set(choisis); if (actif) n.delete(o.valeur); else n.add(o.valeur); changer([...n]); }}
                  className={`max-w-full truncate rounded-full px-3 py-1.5 text-[13px] font-medium ${actif ? "bg-accent-doux text-accent-texte shadow-[0_0_0_1.5px_var(--sg-accent)]" : "bg-remplissage text-texte-2"}`}>
                  {o.libelle}
                </button>
              );
            })}
          </div>
        )}
      </fieldset>
    );
  }
  return (
    <label htmlFor={id} className="flex flex-col gap-1.5">
      {entete}
      {c.type === "zone" ? (
        <textarea id={id} rows={3} value={(valeur as string) ?? ""} onChange={(e) => changer(e.target.value)} className={`${saisie} resize-y`} />
      ) : c.type === "choix" || c.type === "lien" ? (
        <select id={id} value={(valeur as string) ?? ""} onChange={(e) => changer(e.target.value || null)} className={`${saisie} appearance-none`}>
          <option value="">{c.type === "lien" ? "Choisir…" : "—"}</option>
          {c.options.map((o) => <option key={o.valeur} value={o.valeur}>{o.libelle}</option>)}
        </select>
      ) : (
        <input id={id} type={c.type === "date" ? "date" : "text"} value={(valeur as string) ?? ""} onChange={(e) => changer(e.target.value || (c.type === "date" ? null : ""))} className={saisie} />
      )}
    </label>
  );
}

function Formulaire({ config, objet, projetId, fermer }: { config: Config; objet?: ObjetEbios; projetId: string; fermer: () => void }) {
  const chemin = config.api ?? `ebios/${config.ressource}`;
  const enregistrer = useEnregistrerObjet(projetId, chemin);
  const supprimer = useSupprimerObjet(projetId, chemin);
  const [b, setB] = useState<Record<string, unknown>>(() => Object.fromEntries(config.champs.map((c) => [c.cle, objet?.[c.cle] ?? (c.type === "liens" ? [] : c.type === "booleen" ? false : c.type === "echelle" ? null : "")])));
  const [confirmer, setConfirmer] = useState(false);
  const manquant = config.champs.some((c) => c.requis && (b[c.cle] === null || b[c.cle] === "" || b[c.cle] === undefined));
  const erreur = enregistrer.error ?? supprimer.error;

  return (
    <form onSubmit={(e) => { e.preventDefault(); enregistrer.mutate({ id: objet?.id, ...b }, { onSuccess: fermer }); }}
      className="flex flex-col gap-4 rounded-2xl bg-groupe px-4 py-4 shadow-[0_0_0_1.5px_var(--sg-accent)]">
      {config.champs.map((c) => <ChampSaisi key={c.cle} c={c} valeur={b[c.cle]} changer={(v) => setB({ ...b, [c.cle]: v })} />)}
      <div className="flex flex-wrap items-center gap-2">
        <button type="submit" disabled={manquant || enregistrer.isPending} className="bouton-accent h-10 rounded-full px-5 text-[14px] font-semibold disabled:opacity-45">
          {enregistrer.isPending ? "Enregistrement…" : objet ? "Enregistrer" : "Ajouter"}
        </button>
        <button type="button" onClick={fermer} className="h-10 rounded-full px-4 text-[14px] font-medium text-texte-2">Annuler</button>
        {objet && (
          <button type="button" onClick={() => (confirmer ? supprimer.mutate(objet.id, { onSuccess: fermer }) : setConfirmer(true))}
            className="ml-auto h-10 rounded-full px-4 text-[14px] font-semibold text-manquant-texte">
            {confirmer ? "Confirmer la suppression" : "Supprimer"}
          </button>
        )}
      </div>
      {confirmer && <p className="text-xs text-texte-2">La suppression retire aussi les éléments qui en dépendent dans les ateliers suivants.</p>}
      {erreur && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{erreur.message}</p>}
    </form>
  );
}

export function ListeObjets({ config, objets, projetId, lectureSeule, enTete }: {
  config: Config; objets: ObjetEbios[]; projetId: string; lectureSeule: boolean; enTete?: ReactNode;
}) {
  const [edition, setEdition] = useState<string | null>(null);
  return (
    <section aria-labelledby={`liste-${config.ressource}`} className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-end justify-between gap-2 px-1">
        <div className="flex flex-col gap-0.5">
          <h3 id={`liste-${config.ressource}`} className="text-[17px] font-bold">{config.titre} <span className="font-normal text-texte-2">· {objets.length}</span></h3>
          {config.aide && <p className="max-w-[640px] text-[13px] leading-snug text-texte-2">{config.aide}</p>}
        </div>
        {enTete}
      </div>
      <ul className="flex flex-col gap-2">
        {objets.length === 0 && edition !== "nouveau" && (
          <li className="rounded-2xl bg-groupe px-4 py-4 text-sm text-texte-2 shadow-groupe">{config.vide}</li>
        )}
        {objets.map((o) => (
          <li key={o.id}>
            {edition === o.id ? (
              <Formulaire config={config} objet={o} projetId={projetId} fermer={() => setEdition(null)} />
            ) : (
              <div className="flex flex-col overflow-hidden rounded-2xl bg-groupe shadow-groupe">
                <button type="button" disabled={lectureSeule || config.verrou?.(o)} onClick={() => setEdition(o.id)}
                  className="flex w-full flex-col gap-1 px-4 py-3 text-left enabled:hover:bg-remplissage disabled:cursor-default">
                  <span className="text-[15px] leading-snug font-medium">{config.resume(o)}</span>
                  {config.detail && <span className="text-[13px] leading-snug text-texte-2">{config.detail(o)}</span>}
                </button>
                {config.actions?.(o)}
              </div>
            )}
          </li>
        ))}
        {edition === "nouveau" && <li><Formulaire config={config} projetId={projetId} fermer={() => setEdition(null)} /></li>}
      </ul>
      {!lectureSeule && edition !== "nouveau" && (
        <button type="button" onClick={() => setEdition("nouveau")} className="flex items-center gap-1.5 self-start rounded-full px-2 py-1.5 text-[14px] font-semibold text-accent-texte">
          <IconePlus taille={15} /> {config.ajout}
        </button>
      )}
    </section>
  );
}
