import { Link } from "react-router";

import type { TableauDeBord } from "../api/types";
import { echeance, phraseActivite, quand } from "../lib/format";
import { Chevron, IconeBouclier, IconeCalendrier, IconeCercle, IconeDocument, IconeEtincelle } from "./Icones";
import { COUVERTURE } from "./statuts";

function EnTeteBloc({ id, titre, lien, note }: { id: string; titre: string; lien?: { vers: string; texte: string }; note?: string }) {
  return (
    <div className="flex items-baseline justify-between px-1 lg:px-1.5">
      <h2 id={id} className="text-[22px] font-bold tracking-[-0.025em]">{titre}</h2>
      {lien && <Link to={lien.vers} className="py-2.5 text-[15px] text-accent-texte">{lien.texte}</Link>}
      {note && <span className="text-[13px] text-texte-2">{note}</span>}
    </div>
  );
}

const ICONES = { tache: IconeCercle, document: IconeDocument, validation_ia: IconeEtincelle, decision: IconeBouclier, reunion: IconeCalendrier };

export function PourVous({ d, base }: { d: TableauDeBord; base: string }) {
  return (
    <section aria-labelledby="titre-pour-vous" className="flex min-w-0 flex-col gap-2.5">
      <EnTeteBloc id="titre-pour-vous" titre="Pour vous" lien={{ vers: `${base}/plan-action`, texte: "Tout afficher" }} />
      {d.pour_vous.length === 0 ? (
        <p className="rounded-groupe bg-groupe px-4 py-5 text-[15px] text-texte-2 shadow-groupe">
          Rien ne vous est attribué pour le moment.
        </p>
      ) : (
        <ul className="overflow-hidden rounded-groupe bg-groupe shadow-groupe">
          {d.pour_vous.map((e, i) => {
            const Icone = ICONES[e.type];
            const vers = e.lien ? `${base}/${e.lien}` : e.type === "document" ? `${base}/documents` : e.type === "tache" ? `${base}/plan-action` : `${base}/mesures`;
            return (
              <li key={`${e.type}-${e.id ?? i}`}>
                <Link to={vers} className="flex min-h-[60px] items-center gap-3 px-3.5 py-2 transition-colors duration-200 ease-ios hover:bg-remplissage lg:min-h-[62px] lg:gap-3.5 lg:px-4">
                  <Icone taille={20} className="hidden shrink-0 text-texte-2 lg:block" />
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5 py-1">
                    <span className="text-[15px] leading-snug font-medium">{e.titre}</span>
                    {e.detail && <span className="hidden text-[13px] leading-snug text-texte-2 lg:block">{e.detail}</span>}
                    <span className={`text-[13px] lg:hidden ${e.en_retard ? "font-semibold text-manquant-texte" : "text-texte-2"}`}>
                      {echeance(e.echeance, e.en_retard)}
                    </span>
                  </span>
                  <span className={`hidden whitespace-nowrap text-sm lg:block ${e.en_retard ? "font-semibold text-manquant-texte" : "text-texte-2"}`}>
                    {echeance(e.echeance, e.en_retard).replace(/^En retard · /, "")}
                  </span>
                  <Chevron />
                </Link>
                {i < d.pour_vous.length - 1 && <div aria-hidden="true" className="ml-3.5 h-px bg-separateur lg:ml-[52px]" />}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export function AValider({ d, base }: { d: TableauDeBord; base: string }) {
  const v = d.a_valider;
  if (!v) return null;
  return (
    <section aria-labelledby="titre-a-valider" className="flex flex-col gap-2.5">
      <EnTeteBloc id="titre-a-valider" titre="À valider" note={`Analyse IA · ${quand(v.date)}`} />
      <div className="overflow-hidden rounded-groupe bg-groupe shadow-groupe">
        <p className="px-4 pt-3.5 pb-3 text-sm leading-relaxed text-texte-2">
          {v.documents.length ? `${v.documents.join(", ")}. ` : ""}
          Ces conclusions restent des propositions tant que vous ne les avez pas validées.
        </p>
        {v.conclusions.map((c) => {
          const s = COUVERTURE[c.couverture];
          return (
            <div key={c.id} className="flex min-h-[52px] items-center gap-3 border-t border-separateur px-4 py-1.5">
              <span className="w-11 shrink-0 text-[13px] font-semibold text-texte-2">{c.mesure}</span>
              <span className="min-w-0 flex-1 text-sm leading-snug">{c.intitule}</span>
              <span className={`flex items-center gap-1.5 whitespace-nowrap text-[13px] font-semibold ${s.texte}`}>
                <span aria-hidden="true" className={`size-2 rounded-full ${s.point}`} />
                {s.libelle}
              </span>
            </div>
          );
        })}
        <Link to={`${base}/mesures?filtre=ia`} className="flex min-h-[50px] items-center justify-center border-t border-separateur text-[15px] font-semibold text-accent-texte">
          {v.total > v.conclusions.length ? `Examiner les ${v.total} conclusions` : "Examiner et valider"}
        </Link>
      </div>
    </section>
  );
}

export function Activite({ d, base }: { d: TableauDeBord; base: string }) {
  return (
    <section aria-labelledby="titre-activite" className="flex flex-col gap-3 px-1 lg:px-1.5">
      <div className="flex items-baseline justify-between">
        <h2 id="titre-activite" className="text-[22px] font-bold tracking-[-0.025em]">Activité</h2>
        <Link to={`${base}/journal`} className="py-2.5 text-[15px] text-accent-texte">Journal</Link>
      </div>
      {d.activite.length === 0 ? (
        <p className="text-sm text-texte-2">Aucune activité enregistrée.</p>
      ) : (
        <ol className="flex flex-col gap-4">
          {d.activite.map((e) => (
            <li key={e.id} className="flex flex-col gap-0.5">
              <span className="text-sm leading-snug">{phraseActivite(e)}</span>
              <time dateTime={e.horodatage} className="text-xs text-texte-2">{quand(e.horodatage)}</time>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
