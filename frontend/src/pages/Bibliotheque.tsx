import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { useCategories, useCorrespondance, useFicheMesure, useMesures, useMoi, useRechercheMesures, useReferentiels } from "../api/hooks";
import type { Mesure, Referentiel } from "../api/types";
import { Disposition } from "../composants/Disposition";
import { IconeCroix, IconeRecherche } from "../composants/Icones";
import { nomCourt } from "../composants/statuts";
import { quand } from "../lib/format";

const TYPES = [
  { cle: "equivalente", libelle: "Équivalente" }, { cle: "partielle", libelle: "Partielle" }, { cle: "inclut", libelle: "Inclut" },
];

function Fiche({ id, fermer, lectureSeule }: { id: string; fermer: () => void; lectureSeule: boolean }) {
  const { data: m } = useFicheMesure(id);
  const { ajouter, retirer } = useCorrespondance(id);
  const [q, setQ] = useState("");
  const [type, setType] = useState("equivalente");
  const [reference, setReference] = useState("");
  const { data: resultats = [] } = useRechercheMesures(q);
  const panneau = useRef<HTMLDivElement>(null);
  const fermerRef = useRef(fermer);
  fermerRef.current = fermer;
  useEffect(() => {
    panneau.current?.focus(); // à l'ouverture d'une fiche seulement, pas à chaque rendu
    const echap = (e: KeyboardEvent) => e.key === "Escape" && fermerRef.current();
    document.addEventListener("keydown", echap);
    return () => document.removeEventListener("keydown", echap);
  }, [id]);
  const candidats = resultats.filter((r) => m && r.referentiel !== m.referentiel && !m.correspondances.some((c) => c.mesure.id === r.id));

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button type="button" aria-label="Fermer la fiche" onClick={fermer} className="absolute inset-0 bg-black/20 backdrop-blur-[2px]" />
      <div ref={panneau} tabIndex={-1} role="dialog" aria-modal="true" aria-label={m ? `Mesure ${m.identifiant}` : "Mesure"}
        className="verre relative flex h-full w-full flex-col gap-5 overflow-y-auto px-5 pt-4 pb-6 outline-none sm:m-3 sm:h-[calc(100%-24px)] sm:max-w-[600px] sm:rounded-verre">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[13px] font-semibold text-texte-2">{m?.referentiel_nom}</span>
          <button type="button" onClick={fermer} aria-label="Fermer" className="flex size-11 items-center justify-center rounded-full hover:bg-remplissage"><IconeCroix taille={18} /></button>
        </div>
        {!m ? <div aria-busy="true" className="h-64 animate-pulse rounded-groupe bg-remplissage" /> : (
          <>
            <div className="flex flex-col gap-1">
              <span className="text-[15px] font-bold text-texte-2 tabular-nums">{m.identifiant}</span>
              <h2 className="text-[24px] leading-tight font-bold tracking-[-0.02em]">{m.intitule}</h2>
              {m.categorie && <span className="text-[13px] text-texte-2">{m.categorie}{m.niveaux.length ? ` · niveaux ${m.niveaux.join(", ")}` : ""}</span>}
            </div>
            {m.texte_officiel ? (
              <section aria-label="Texte de la mesure" className="rounded-2xl bg-groupe px-4 py-3 shadow-groupe">
                <p className="text-[15px] leading-relaxed whitespace-pre-line">{m.texte_officiel}</p>
              </section>
            ) : <p className="text-[13px] text-texte-2">Texte officiel non embarqué (norme sous licence) : consultez votre copie licenciée.</p>}

            <section aria-labelledby="f-projets" className="flex flex-col gap-2">
              <h3 id="f-projets" className="text-[17px] font-bold">Dans mes projets</h3>
              {m.projets.length === 0 ? <p className="text-sm text-texte-2">Pas encore évaluée dans vos projets.</p> : (
                <ul className="flex flex-col gap-1.5">
                  {m.projets.map((p) => (
                    <li key={p.projet}>
                      <Link to={`/projets/${p.projet}/mesures`} className="flex items-center justify-between rounded-2xl bg-groupe px-3.5 py-2.5 text-sm shadow-groupe">
                        <span className="font-medium">{p.projet_nom}</span><span className="text-texte-2">{p.statut_libelle}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section aria-labelledby="f-corresp" className="flex flex-col gap-2">
              <h3 id="f-corresp" className="text-[17px] font-bold">Correspondances</h3>
              <p className="text-[13px] text-texte-2">Mesures équivalentes dans d'autres référentiels : une même preuve peut couvrir plusieurs exigences.</p>
              {m.correspondances.length === 0 && <p className="text-sm text-texte-2">Aucune correspondance.</p>}
              <ul className="flex flex-col gap-1.5">
                {m.correspondances.map((c) => (
                  <li key={c.id} className="flex items-center gap-3 rounded-2xl bg-groupe px-3.5 py-2.5 shadow-groupe">
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-sm font-medium">{c.mesure.referentiel_code} {c.mesure.identifiant} — {c.mesure.intitule}</span>
                      <span className="text-xs text-texte-2">{c.type_libelle} · {c.origine}{c.reference ? ` · ${c.reference}` : ""}</span>
                    </span>
                    {c.modifiable && !lectureSeule && (
                      <button type="button" onClick={() => retirer.mutate(c.id)} className="text-[13px] font-semibold text-manquant-texte">Retirer</button>
                    )}
                  </li>
                ))}
              </ul>
              {!lectureSeule && (
                <div className="flex flex-col gap-2 rounded-2xl border border-separateur px-3.5 py-3">
                  <span className="text-xs font-semibold text-texte-2">Ajouter une correspondance (propre à votre organisation)</span>
                  <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Chercher une mesure d'un autre référentiel…" aria-label="Chercher une mesure"
                    className="rounded-xl bg-remplissage px-3 py-2 text-sm outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)]" />
                  <div className="flex flex-wrap gap-2">
                    <select aria-label="Type de correspondance" value={type} onChange={(e) => setType(e.target.value)} className="rounded-xl bg-remplissage px-2.5 py-1.5 text-[13px] outline-none">
                      {TYPES.map((t) => <option key={t.cle} value={t.cle}>{t.libelle}</option>)}
                    </select>
                    <input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="Source (facultatif)" aria-label="Source de la correspondance"
                      className="min-w-0 flex-1 rounded-xl bg-remplissage px-3 py-1.5 text-[13px] outline-none" />
                  </div>
                  {candidats.length > 0 && (
                    <ul className="flex max-h-56 flex-col gap-1 overflow-y-auto">
                      {candidats.map((r) => (
                        <li key={r.id}>
                          <button type="button" disabled={ajouter.isPending} onClick={() => ajouter.mutate({ mesure_cible: r.id, type_correspondance: type, reference }, { onSuccess: () => setQ("") })}
                            className="w-full truncate rounded-xl px-2.5 py-1.5 text-left text-[13px] hover:bg-remplissage">
                            <span className="font-semibold">{r.referentiel_code} {r.identifiant}</span> — {r.intitule}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  {(ajouter.error || retirer.error) && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{(ajouter.error ?? retirer.error)!.message}</p>}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

function EnTete({ r }: { r: Referentiel }) {
  return (
    <section aria-labelledby="titre-ref" className="flex flex-col gap-2 rounded-groupe bg-groupe px-4 py-4 shadow-groupe sm:px-6">
      <h2 id="titre-ref" className="text-[22px] font-bold tracking-[-0.02em]">{r.nom} <span className="font-medium text-texte-2">{r.version}</span></h2>
      <p className="text-[13px] leading-snug text-texte-2">
        {[r.editeur, `${r.nb_mesures} mesures`, r.licence_libelle, r.prive ? "copie privée de votre organisation" : "bibliothèque commune",
          r.nb_projets ? `utilisé dans ${r.nb_projets} projet(s)` : "utilisé dans aucun projet"].filter(Boolean).join(" · ")}
      </p>
      <p className="text-xs text-texte-3">
        {r.url_source && <><a href={r.url_source} target="_blank" rel="noreferrer noopener" className="font-semibold text-accent-texte">Source officielle</a> · </>}
        {r.date_import ? `importé ${quand(r.date_import)}` : ""}{r.empreinte_source ? ` · SHA-256 ${r.empreinte_source.slice(0, 12)}…` : ""}
      </p>
      {r.nouvelle_version && (
        <p role="status" className="rounded-2xl bg-partiel/10 px-3.5 py-2.5 text-[13px] font-medium text-partiel-texte">
          Nouvelle version disponible : {r.nouvelle_version_libelle}. Les projets restent sur la version choisie à leur création.
        </p>
      )}
    </section>
  );
}

export function PageBibliotheque() {
  const [params, setParams] = useSearchParams();
  const { data: moi } = useMoi();
  const { data: referentiels = [] } = useReferentiels();
  const refId = params.get("referentiel") ?? referentiels[0]?.id;
  const ref = referentiels.find((r) => r.id === refId);
  const { data: mesures = [], isPending } = useMesures(refId);
  const { data: categories = [] } = useCategories(refId);
  const [categorie, setCategorie] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [partout, setPartout] = useState(false);
  const { data: trouvees = [] } = useRechercheMesures(partout ? q : "");
  const fiche = params.get("mesure");
  const lectureSeule = moi?.lecture_seule ?? true;

  const locales = useMemo(() => {
    const t = q.trim().toLowerCase();
    return mesures.filter((m) => (!categorie || (m.categorie || "Sans catégorie") === categorie)
      && (!t || m.identifiant.toLowerCase().includes(t) || m.intitule.toLowerCase().includes(t) || (m.texte_officiel ?? "").toLowerCase().includes(t)));
  }, [mesures, categorie, q]);
  const liste: Mesure[] = partout && q.trim().length >= 2 ? trouvees : locales;
  const ouvrir = (id: string) => setParams({ ...(refId ? { referentiel: refId } : {}), mesure: id });
  const fermer = () => setParams(refId ? { referentiel: refId } : {});

  return (
    <Disposition>
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5 lg:pt-2.5">
          <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Bibliothèque</h1>
          <p className="max-w-[720px] text-[15px] text-texte-2">
            Les référentiels disponibles sur l'installation, et les copies licenciées propres à votre organisation. Les sources libres sont
            importées depuis les sites officiels, avec leur version et leur empreinte.
          </p>
        </div>

        <div role="tablist" aria-label="Référentiels" className="flex flex-wrap gap-1.5">
          {referentiels.map((r) => (
            <button key={r.id} type="button" role="tab" aria-selected={r.id === refId}
              onClick={() => { setParams({ referentiel: r.id }); setCategorie(null); }}
              className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[13px] ${r.id === refId ? "bg-groupe font-semibold shadow-[0_0_0_1.5px_var(--sg-accent)]" : "bg-remplissage font-medium text-texte-2"}`}>
              {nomCourt(r)}
              {r.prive && <span className="text-[11px] text-texte-3">privé</span>}
              {r.nouvelle_version && <span aria-label="nouvelle version disponible" className="size-2 rounded-full bg-partiel" />}
            </button>
          ))}
        </div>

        {ref && <EnTete r={ref} />}

        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex h-11 min-w-0 flex-1 items-center gap-2.5 rounded-full bg-groupe px-4 shadow-groupe">
              <IconeRecherche taille={17} className="shrink-0 text-texte-2" />
              <span className="sr-only">Rechercher une mesure</span>
              <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Identifiant, intitulé ou texte"
                className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-texte-3" />
            </label>
            <label className="flex items-center gap-2 text-[13px] text-texte-2">
              <input type="checkbox" checked={partout} onChange={(e) => setPartout(e.target.checked)} className="size-4 accent-[var(--sg-accent)]" />
              Tous les référentiels
            </label>
          </div>
          {!partout && categories.length > 8 && (
            <select aria-label="Catégorie" value={categorie ?? ""} onChange={(e) => setCategorie(e.target.value || null)}
              className="max-w-full self-start rounded-full bg-groupe px-4 py-2 text-[14px] shadow-groupe outline-none">
              <option value="">Toutes les catégories ({mesures.length})</option>
              {categories.map((c) => <option key={c.categorie} value={c.categorie}>{c.categorie} ({c.nb_mesures})</option>)}
            </select>
          )}
          {!partout && categories.length > 1 && categories.length <= 8 && (
            <div role="radiogroup" aria-label="Catégorie" className="flex flex-wrap gap-1.5">
              <button type="button" role="radio" aria-checked={categorie === null} onClick={() => setCategorie(null)}
                className={`h-8 rounded-full px-3 text-[13px] ${categorie === null ? "bg-accent font-semibold text-white" : "bg-remplissage font-medium text-texte-2"}`}>Toutes</button>
              {categories.map((c) => (
                <button key={c.categorie} type="button" role="radio" aria-checked={categorie === c.categorie} onClick={() => setCategorie(c.categorie)}
                  className={`h-8 max-w-[280px] truncate rounded-full px-3 text-[13px] ${categorie === c.categorie ? "bg-accent font-semibold text-white" : "bg-remplissage font-medium text-texte-2"}`}>
                  {c.categorie} <span className="opacity-70">{c.nb_mesures}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {isPending && !partout ? <div aria-busy="true" className="h-96 animate-pulse rounded-groupe bg-remplissage" /> : liste.length === 0 ? (
          <p className="rounded-groupe bg-groupe px-4 py-6 text-center text-[15px] text-texte-2 shadow-groupe">
            {partout && q.trim().length < 2 ? "Tapez au moins deux caractères pour chercher dans tous les référentiels." : "Aucune mesure ne correspond."}
          </p>
        ) : (
          <ul className="divide-y divide-separateur overflow-hidden rounded-groupe bg-groupe shadow-groupe">
            {liste.map((m) => (
              <li key={m.id}>
                <button type="button" onClick={() => ouvrir(m.id)} className="flex min-h-[56px] w-full items-center gap-3.5 px-4 py-2.5 text-left hover:bg-remplissage">
                  <span className="w-[96px] shrink-0 text-[13px] font-semibold text-texte-2 tabular-nums">{partout ? `${m.referentiel_code} ` : ""}{m.identifiant}</span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="line-clamp-2 text-[15px] leading-snug">{m.intitule}</span>
                    {m.categorie && <span className="truncate text-xs text-texte-3">{m.categorie}</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {fiche && <Fiche id={fiche} fermer={fermer} lectureSeule={lectureSeule} />}
    </Disposition>
  );
}
