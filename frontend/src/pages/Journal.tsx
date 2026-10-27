import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";

import { api } from "../api/client";
import { useMoi, useTableauDeBord } from "../api/hooks";
import type { EntreeJournal, Pagine } from "../api/types";
import { Disposition } from "../composants/Disposition";
import { Chevron } from "../composants/Icones";

const ACTIONS = [
  { cle: "", libelle: "Toutes les actions" }, { cle: "creation", libelle: "Créations" }, { cle: "modification", libelle: "Modifications" },
  { cle: "suppression", libelle: "Suppressions" }, { cle: "decision", libelle: "Décisions" }, { cle: "validation_ia", libelle: "Validations IA" },
  { cle: "telechargement", libelle: "Téléchargements" }, { cle: "export", libelle: "Exports" }, { cle: "connexion", libelle: "Connexions" },
];
const TAILLE = 50;
const saisie = "rounded-full bg-groupe px-4 py-2 text-[14px] shadow-groupe outline-none";

/** Données de l'entrée, lisibles : « champ : avant → après » pour un diff, « clé : valeur » sinon. */
function Details({ donnees }: { donnees: Record<string, unknown> }) {
  const lignes = Object.entries(donnees);
  if (lignes.length === 0) return <p className="text-[13px] text-texte-3">Pas de détail.</p>;
  const texte = (v: unknown) => (v === null || v === undefined || v === "" ? "vide" : typeof v === "object" ? JSON.stringify(v) : String(v));
  return (
    <dl className="grid grid-cols-[minmax(110px,auto)_1fr] gap-x-3 gap-y-1 text-[13px]">
      {lignes.map(([cle, v]) => {
        const diff = v && typeof v === "object" && "avant" in (v as object) && "apres" in (v as object);
        return [
          <dt key={`${cle}-t`} className="font-semibold text-texte-2">{cle}</dt>,
          <dd key={`${cle}-d`} className="min-w-0 break-words">
            {diff ? <><span className="text-manquant-texte line-through">{texte((v as { avant: unknown }).avant).slice(0, 300)}</span> → <span className="text-conforme-texte">{texte((v as { apres: unknown }).apres).slice(0, 300)}</span></>
              : texte(v).slice(0, 600)}
          </dd>,
        ];
      })}
    </dl>
  );
}

function Integrite() {
  const [lancer, setLancer] = useState(false);
  const { data, isFetching, error } = useQuery({
    queryKey: ["journal", "integrite"], queryFn: () => api<{ integre: boolean; entrees: number; derniere_empreinte?: string; anomalie?: { id: number; nature: string } }>("/api/journal/integrite/"),
    enabled: lancer, staleTime: 0,
  });
  return (
    <section aria-label="Intégrité du journal" className="flex flex-wrap items-center gap-3 rounded-groupe bg-groupe px-4 py-3.5 shadow-groupe">
      <p role="status" className="min-w-0 flex-1 text-[13px] leading-snug text-texte-2">
        {!data && !isFetching && "Chaque entrée contient l'empreinte de la précédente : toute modification ou suppression faite en base casse la chaîne."}
        {isFetching && "Vérification de toute la chaîne de l'organisation…"}
        {data?.integre && <><span className="font-semibold text-conforme-texte">Chaîne intègre</span> : {data.entrees} entrées vérifiées. Dernière empreinte <span className="font-mono text-[11px]">{data.derniere_empreinte}</span> (à conserver hors de l'application pour détecter une troncature).</>}
        {data && !data.integre && <span className="font-semibold text-manquant-texte">Anomalie à l'entrée n° {data.anomalie!.id} : {data.anomalie!.nature}. Conservez cette preuve et alertez le RSSI.</span>}
        {error && <span className="text-manquant-texte">{error.message}</span>}
      </p>
      <button type="button" disabled={isFetching} onClick={() => setLancer(true)} className="h-9 shrink-0 rounded-full bg-accent-doux px-4 text-[13px] font-semibold text-accent-texte">
        Vérifier l'intégrité
      </button>
    </section>
  );
}

export function PageJournal() {
  const { projetId = "" } = useParams();
  const { data: moi } = useMoi();
  const { data: tdb } = useTableauDeBord(projetId || undefined);
  const [filtres, setFiltres] = useState({ action: "", acteur: "", du: "", au: "", q: "", hors_projet: false });
  const [page, setPage] = useState(1);
  const [ouverte, setOuverte] = useState<number | null>(null);
  const requete = new URLSearchParams({
    ...(projetId ? { projet: projetId } : {}), ...(filtres.action ? { action: filtres.action } : {}), ...(filtres.acteur ? { acteur: filtres.acteur } : {}),
    ...(filtres.du ? { du: filtres.du } : {}), ...(filtres.au ? { au: filtres.au } : {}), ...(filtres.q.trim() ? { q: filtres.q.trim() } : {}),
    ...(filtres.hors_projet ? { hors_projet: "1" } : {}),
  }).toString();
  const { data, isPending } = useQuery({
    queryKey: ["journal", requete, page], queryFn: () => api<Pagine<EntreeJournal>>(`/api/journal/?${requete}&taille=${TAILLE}&page=${page}`),
    placeholderData: keepPreviousData,
  });
  const { data: acteurs = [] } = useQuery({ queryKey: ["journal", "acteurs", projetId], queryFn: () => api<{ id: string; nom: string }[]>(`/api/journal/acteurs/?${projetId ? `projet=${projetId}` : ""}`) });
  const changer = (champ: string, valeur: string | boolean) => { setFiltres({ ...filtres, [champ]: valeur }); setPage(1); };
  const pages = data ? Math.max(1, Math.ceil(data.count / TAILLE)) : 1;

  return (
    <Disposition>
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5 lg:pt-2.5">
          <span className="text-[13px] font-semibold text-texte-2">{projetId ? tdb?.projet.nom ?? "Projet" : moi?.organisation.nom}</span>
          <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Journal d'audit</h1>
          <p className="max-w-[720px] text-[15px] text-texte-2">
            Toutes les actions tracées, en ajout seul : rien ne peut y être modifié ni supprimé, y compris par un administrateur.
            {data ? ` ${data.count} entrée(s) dans ce filtre.` : ""}
          </p>
        </div>

        {moi?.est_admin && <Integrite />}

        <div className="flex flex-wrap items-center gap-2">
          <select aria-label="Action" className={saisie} value={filtres.action} onChange={(e) => changer("action", e.target.value)}>
            {ACTIONS.map((a) => <option key={a.cle} value={a.cle}>{a.libelle}</option>)}
          </select>
          <select aria-label="Auteur" className={saisie} value={filtres.acteur} onChange={(e) => changer("acteur", e.target.value)}>
            <option value="">Tous les auteurs</option>
            {acteurs.map((a) => <option key={a.id} value={a.id}>{a.nom}</option>)}
          </select>
          <label className="flex items-center gap-1.5 text-[13px] text-texte-2">Du <input type="date" className={saisie} value={filtres.du} onChange={(e) => changer("du", e.target.value)} /></label>
          <label className="flex items-center gap-1.5 text-[13px] text-texte-2">au <input type="date" className={saisie} value={filtres.au} onChange={(e) => changer("au", e.target.value)} /></label>
          <input type="search" aria-label="Rechercher" placeholder="Objet ou auteur" className={`${saisie} min-w-[180px] flex-1`} value={filtres.q} onChange={(e) => changer("q", e.target.value)} />
          {!projetId && moi?.est_admin && (
            <label className="flex items-center gap-2 text-[13px] text-texte-2">
              <input type="checkbox" checked={filtres.hors_projet} onChange={(e) => changer("hors_projet", e.target.checked)} className="size-4 accent-[var(--sg-accent)]" />
              Hors projet (connexions, réglages)
            </label>
          )}
          <a href={`/api/journal/exporter/?${requete}`} download className="ml-auto rounded-full bg-remplissage px-4 py-2 text-[13px] font-semibold text-accent-texte">Exporter (CSV)</a>
        </div>

        {isPending ? <div aria-busy="true" className="h-96 animate-pulse rounded-groupe bg-remplissage" /> : (data?.results.length ?? 0) === 0 ? (
          <p className="rounded-groupe bg-groupe px-4 py-6 text-center text-[15px] text-texte-2 shadow-groupe">Aucune entrée dans ce filtre.</p>
        ) : (
          <ol className="divide-y divide-separateur overflow-hidden rounded-groupe bg-groupe shadow-groupe">
            {data!.results.map((e) => (
              <li key={e.id}>
                <button type="button" aria-expanded={ouverte === e.id} onClick={() => setOuverte(ouverte === e.id ? null : e.id)}
                  className="flex w-full items-start gap-3 px-4 py-2.5 text-left hover:bg-remplissage">
                  <span className="w-[118px] shrink-0 text-[12px] text-texte-2 tabular-nums">
                    {new Date(e.horodatage).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="text-[14px] leading-snug"><span className="font-semibold">{e.action_libelle}</span> · {e.objet_libelle}{e.objet_repr ? ` « ${e.objet_repr} »` : ""}</span>
                    <span className="text-xs text-texte-2">{e.acteur_repr}{!projetId && e.projet_nom ? ` · ${e.projet_nom}` : ""}</span>
                  </span>
                  <span className={`mt-1 transition-transform duration-200 ease-ios ${ouverte === e.id ? "rotate-90" : ""}`}><Chevron /></span>
                </button>
                {ouverte === e.id && (
                  <div className="flex flex-col gap-2 border-t border-separateur px-4 py-3 sm:pl-[146px]">
                    <Details donnees={e.donnees} />
                    <p className="font-mono text-[11px] break-all text-texte-3">n° {e.id}{e.adresse_ip ? ` · IP ${e.adresse_ip}` : ""} · empreinte {e.hash} · précédente {e.hash_precedent}</p>
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}
        {pages > 1 && (
          <nav aria-label="Pages" className="flex items-center justify-center gap-3 text-[14px]">
            <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-full bg-remplissage px-4 py-2 font-semibold disabled:opacity-40">Précédentes</button>
            <span className="text-texte-2">Page {page} / {pages}</span>
            <button type="button" disabled={page >= pages} onClick={() => setPage(page + 1)} className="rounded-full bg-remplissage px-4 py-2 font-semibold disabled:opacity-40">Suivantes</button>
          </nav>
        )}
      </div>
    </Disposition>
  );
}
