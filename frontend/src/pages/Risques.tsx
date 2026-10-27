import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { useActeurs, useDecider, useEvaluations, useObjets, useTableauDeBord } from "../api/hooks";
import type { ObjetEbios } from "../api/types";
import { Disposition } from "../composants/Disposition";
import { ECHELLE, ListeObjets, type Config } from "../composants/ebios/Objets";
import { quand } from "../lib/format";

const aujourdHui = () => new Date().toISOString().slice(0, 10);
const dateFr = (d: unknown) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString("fr-FR") : "");
const dans = (jours: number) => new Date(Date.now() + jours * 86_400_000).toISOString().slice(0, 10);

const STATUT_RISQUE: Record<string, { libelle: string; classe: string }> = {
  identifie: { libelle: "À statuer", classe: "bg-partiel/15 text-partiel-texte" },
  en_traitement: { libelle: "En traitement", classe: "bg-accent-doux text-accent-texte" },
  accepte: { libelle: "Accepté", classe: "bg-conforme/15 text-conforme-texte" },
  clos: { libelle: "Clos", classe: "bg-remplissage text-texte-2" },
};
const STATUT_DEROGATION: Record<string, { libelle: string; classe: string }> = {
  demandee: { libelle: "À décider", classe: "bg-partiel/15 text-partiel-texte" },
  acceptee: { libelle: "Acceptée", classe: "bg-conforme/15 text-conforme-texte" },
  refusee: { libelle: "Refusée", classe: "bg-manquant/15 text-manquant-texte" },
  expiree: { libelle: "Expirée", classe: "bg-remplissage text-texte-2" },
};
const NIVEAU = (n: number) => (n >= 9 ? "text-manquant-texte" : n >= 4 ? "text-partiel-texte" : "text-conforme-texte");

function Pastille({ statut, table }: { statut: unknown; table: Record<string, { libelle: string; classe: string }> }) {
  const s = table[statut as string];
  return s ? <span className={`ml-2 rounded-full px-2 py-0.5 text-[11px] font-semibold ${s.classe}`}>{s.libelle}</span> : null;
}

/** Zone de décision sous un élément : réservée aux décisionnaires, motif et date toujours demandés. */
function Decision({ o, chemin, projetId, peutDecider, lectureSeule }: { o: ObjetEbios; chemin: "risques-residuels" | "derogations"; projetId: string; peutDecider: boolean; lectureSeule: boolean }) {
  const decider = useDecider(projetId, chemin);
  const [mode, setMode] = useState<string | null>(null);
  const [texte, setTexte] = useState("");
  const [date, setDate] = useState(String(o.date_expiration ?? "") || dans(chemin === "risques-residuels" ? 365 : 180));
  const risque = chemin === "risques-residuels";
  const info = risque
    ? o.accepte_par_nom ? `Accepté par ${o.accepte_par_nom} ${quand(String(o.accepte_le))}${o.motif_acceptation ? ` : « ${o.motif_acceptation} »` : ""}` : ""
    : o.decidee_par_nom ? `${o.statut === "refusee" ? "Refusée" : "Décidée"} par ${o.decidee_par_nom} le ${dateFr(o.date_decision)}${o.commentaire_decision ? ` : « ${o.commentaire_decision} »` : ""}` : "";
  const possibles: { cle: string; libelle: string; principal?: boolean }[] = risque
    ? (o.statut === "accepte" || o.statut === "clos" ? [{ cle: "rouvrir", libelle: "Rouvrir" }] : [{ cle: "accepter", libelle: "Accepter le risque", principal: true }, { cle: "clore", libelle: "Clore" }])
    : o.statut === "demandee" ? [{ cle: "accepter", libelle: "Accepter", principal: true }, { cle: "refuser", libelle: "Refuser" }]
    : o.statut === "acceptee" ? [{ cle: "revoquer", libelle: "Révoquer" }] : [];
  const demandeDate = mode === "accepter";
  const texteRequis = (risque && mode === "accepter") || (!risque && mode === "refuser");
  if (!info && (!peutDecider || lectureSeule || possibles.length === 0)) return null;

  return (
    <div className="flex flex-col gap-2 border-t border-separateur px-4 py-2.5">
      {info && <p className="text-[13px] leading-snug text-texte-2">{info}</p>}
      {peutDecider && !lectureSeule && !mode && possibles.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {possibles.map((p) => (
            <button key={p.cle} type="button" onClick={() => { setMode(p.cle); setTexte(""); }}
              className={`h-8 rounded-full px-3.5 text-[13px] font-semibold ${p.principal ? "bouton-accent" : "bg-remplissage"}`}>{p.libelle}</button>
          ))}
        </div>
      )}
      {mode && (
        <form className="flex flex-col gap-2" onSubmit={(e) => {
          e.preventDefault();
          decider.mutate({ id: o.id, decision: mode, ...(risque ? { motif: texte } : { commentaire: texte }),
            ...(demandeDate ? (risque ? { date_revue: date } : { date_expiration: date }) : {}) }, { onSuccess: () => setMode(null) });
        }}>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold text-texte-2">{texteRequis ? "Motif (obligatoire)" : "Commentaire"}</span>
            <textarea rows={2} value={texte} onChange={(e) => setTexte(e.target.value)} className="resize-y rounded-xl bg-remplissage px-3 py-2 text-sm outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)]" />
          </label>
          {demandeDate && (
            <label className="flex items-center gap-2 text-[13px] text-texte-2">
              {risque ? "Date de revue" : "Valable jusqu'au"}
              <input type="date" min={dans(1)} value={date} onChange={(e) => setDate(e.target.value)} className="rounded-xl bg-remplissage px-2.5 py-1.5 text-[14px] text-texte outline-none" />
            </label>
          )}
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={decider.isPending || (texteRequis && !texte.trim()) || (demandeDate && date <= aujourdHui())}
              className="bouton-accent h-9 rounded-full px-4 text-[13px] font-semibold disabled:opacity-45">Confirmer la décision</button>
            <button type="button" onClick={() => setMode(null)} className="h-9 rounded-full px-3 text-[13px] font-medium text-texte-2">Annuler</button>
          </div>
          <p className="text-xs text-texte-3">Décision datée et nominative, tracée au journal d'audit.</p>
        </form>
      )}
      {decider.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{decider.error.message}</p>}
    </div>
  );
}

export function PageRisques() {
  const { projetId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const onglet = params.get("onglet") === "derogations" ? "derogations" : "risques";
  const { data: tdb } = useTableauDeBord(projetId);
  const { data: risques = [] } = useObjets(projetId, "risques-residuels");
  const { data: derogations = [] } = useObjets(projetId, "derogations");
  const { data: acteurs = [] } = useActeurs(projetId);
  const { data: evaluations = [] } = useEvaluations(projetId);
  const lectureSeule = tdb?.projet.lecture_seule ?? true;
  const peutDecider = tdb?.projet.peut_decider ?? false;
  const acteursOpt = acteurs.map((a) => ({ valeur: a.id, libelle: `${a.affichage} — ${a.role_libelle}` }));
  const ecarts = evaluations.filter((e) => e.statut === "manquant" || e.statut === "partiel")
    .map((e) => ({ valeur: e.mesure, libelle: `${e.referentiel_code} ${e.mesure_identifiant} — ${e.mesure_intitule.slice(0, 70)}` }));

  const configRisques: Config = {
    ressource: "risques-residuels", api: "risques-residuels", titre: "Registre des risques résiduels", ajout: "Ajouter un risque", vide: "Aucun risque résiduel.",
    aide: "Risques qui subsistent après traitement. Les risques acceptés dans EBIOS RM s'y inscrivent. Les accepter formellement revient au RSSI ou à l'autorité d'homologation.",
    champs: [{ cle: "intitule", libelle: "Risque", type: "texte", requis: true }, { cle: "description", libelle: "Description", type: "zone" },
      { cle: "gravite", libelle: "Gravité", type: "echelle", requis: true }, { cle: "vraisemblance", libelle: "Vraisemblance", type: "echelle", requis: true },
      { cle: "proprietaire", libelle: "Propriétaire du risque", type: "lien", options: acteursOpt },
      { cle: "statut", libelle: "Avancement", type: "choix", options: [{ valeur: "identifie", libelle: "À statuer" }, { valeur: "en_traitement", libelle: "En traitement" }] },
      { cle: "date_revue", libelle: "Date de revue", type: "date" }],
    verrou: (o) => o.statut === "clos",
    resume: (o) => <>{String(o.intitule)}<Pastille statut={o.statut} table={STATUT_RISQUE} /></>,
    detail: (o) => (
      <>
        <span className={`font-semibold ${NIVEAU(Number(o.niveau))}`}>G{String(o.gravite)} × V{String(o.vraisemblance)}</span>
        {` · ${o.origine === "ebios" ? "EBIOS RM" : o.origine === "manuelle" ? "saisie manuelle" : String(o.origine)}`}
        {o.proprietaire_nom ? ` · ${o.proprietaire_nom}` : ""}
        {o.date_revue ? <span className={o.revue_depassee ? "font-semibold text-manquant-texte" : ""}> · revue {dateFr(o.date_revue)}{o.revue_depassee ? " (dépassée)" : ""}</span> : null}
        {Number(o.nb_derogations) > 0 ? ` · ${o.nb_derogations} dérogation(s)` : ""}
      </>
    ),
    actions: (o) => <Decision o={o} chemin="risques-residuels" projetId={projetId} peutDecider={peutDecider} lectureSeule={lectureSeule} />,
  };

  const configDerogations: Config = {
    ressource: "derogations", api: "derogations", titre: "Dérogations", ajout: "Demander une dérogation", vide: "Aucune dérogation.",
    aide: "Écart assumé à une mesure ou à un risque, pour une durée limitée, avec des mesures compensatoires. Une dérogation décidée ne se modifie plus.",
    champs: [{ cle: "mesure", libelle: "Mesure concernée", type: "lien", options: ecarts, aide: "Mesures évaluées manquantes ou partielles." },
      { cle: "risque", libelle: "Ou risque concerné", type: "lien", options: risques.map((r) => ({ valeur: r.id, libelle: String(r.intitule) })) },
      { cle: "motif", libelle: "Motif", type: "zone", requis: true }, { cle: "mesures_compensatoires", libelle: "Mesures compensatoires", type: "zone" },
      { cle: "date_expiration", libelle: "Échéance proposée", type: "date" }],
    verrou: (o) => o.statut !== "demandee",
    resume: (o) => <>{String(o.cible)}<Pastille statut={o.statut} table={STATUT_DEROGATION} /></>,
    detail: (o) => (
      <>
        {String(o.motif).slice(0, 160)}
        {o.date_expiration ? <span className={o.statut === "acceptee" && String(o.date_expiration) < dans(30) ? "font-semibold text-partiel-texte" : ""}>
          {` · ${o.statut === "demandee" ? "proposée jusqu'au" : "jusqu'au"} ${dateFr(o.date_expiration)}`}</span> : null}
        {` · demandée par ${o.demandee_par_nom}`}
      </>
    ),
    actions: (o) => <Decision o={o} chemin="derogations" projetId={projetId} peutDecider={peutDecider} lectureSeule={lectureSeule} />,
  };

  const aStatuer = risques.filter((r) => r.statut === "identifie").length;
  const aDecider = derogations.filter((d) => d.statut === "demandee").length;
  const onglets = [
    { cle: "risques", libelle: "Risques résiduels", n: risques.length, alerte: aStatuer },
    { cle: "derogations", libelle: "Dérogations", n: derogations.length, alerte: aDecider },
  ];

  return (
    <Disposition>
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5 lg:pt-2.5">
          <span className="text-[13px] font-semibold text-texte-2">{tdb?.projet.nom ?? "Projet"}</span>
          <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Risques et dérogations</h1>
          <p className="text-[15px] text-texte-2">
            {risques.filter((r) => r.statut === "accepte").length} risque(s) accepté(s) · {aStatuer} à statuer ·{" "}
            {derogations.filter((d) => d.statut === "acceptee").length} dérogation(s) en cours{aDecider ? ` · ${aDecider} à décider` : ""}
          </p>
        </div>

        <div role="tablist" aria-label="Registre" className="flex self-start rounded-full bg-remplissage p-[3px]">
          {onglets.map((o) => (
            <button key={o.cle} type="button" role="tab" aria-selected={onglet === o.cle} onClick={() => setParams({ onglet: o.cle })}
              className={`flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[13px] ${onglet === o.cle ? "bg-groupe font-semibold shadow-groupe" : "font-medium text-texte-2"}`}>
              {o.libelle} <span className="text-texte-2">{o.n}</span>
              {o.alerte > 0 && <span className="rounded-full bg-partiel/20 px-1.5 text-[11px] font-semibold text-partiel-texte">{o.alerte}<span className="sr-only"> à décider</span></span>}
            </button>
          ))}
        </div>

        {!peutDecider && !lectureSeule && (
          <p className="text-[13px] text-texte-2">Les décisions (accepter, refuser, clore) reviennent au RSSI, à l'autorité d'homologation ou à l'administrateur.</p>
        )}

        {onglet === "risques" ? (
          <>
            <ListeObjets config={configRisques} objets={risques} projetId={projetId} lectureSeule={lectureSeule} />
            {tdb?.projet.ebios_active && <p className="px-1 text-[13px] text-texte-2">Les risques à accepter se préparent dans <Link to={`/projets/${projetId}/ebios?atelier=5`} className="font-semibold text-accent-texte">EBIOS RM, atelier 5</Link>.</p>}
          </>
        ) : (
          <ListeObjets config={configDerogations} objets={derogations} projetId={projetId} lectureSeule={lectureSeule} />
        )}
        <p className="px-1 text-xs text-texte-3">Échelles : gravité et vraisemblance de 1 ({ECHELLE[1].toLowerCase()}) à 4 ({ECHELLE[4].toLowerCase()}).</p>
      </div>
    </Disposition>
  );
}
