import { useEffect, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router";

import { api } from "../api/client";
import { useActeurs, useEnregistrerObjet, usePreremplirSocle, useSyntheseEbios, useTableauDeBord, useToutEbios } from "../api/hooks";
import type { ObjetEbios } from "../api/types";
import { Disposition } from "../composants/Disposition";
import { ECHELLE, ListeObjets, type Config, type Option } from "../composants/ebios/Objets";
import { PanneauPropositions } from "../composants/ebios/Propositions";
import { Cartographie, Matrice } from "../composants/ebios/Visuels";

const STATUTS = [
  { cle: "non_commence", libelle: "Non commencé" },
  { cle: "en_cours", libelle: "En cours" },
  { cle: "termine", libelle: "Terminé" },
] as const;
const ATELIERS = [
  { n: 1, titre: "Cadrage et socle", but: "Délimiter l'objet étudié : ses valeurs métier, les biens qui les supportent, les événements redoutés et l'état du socle de sécurité." },
  { n: 2, titre: "Sources de risque", but: "Identifier qui pourrait attaquer et dans quel but, puis retenir les couples source / objectif les plus pertinents." },
  { n: 3, titre: "Scénarios stratégiques", but: "Évaluer la menace venant de l'écosystème et décrire, à haut niveau, comment chaque couple retenu atteindrait ses fins." },
  { n: 4, titre: "Scénarios opérationnels", but: "Détailler les modes opératoires techniques des chemins d'attaque et en estimer la vraisemblance." },
  { n: 5, titre: "Traitement du risque", but: "Coter les risques, choisir leur traitement, définir les mesures (PACS) et mesurer le risque résiduel." },
];

const RESSOURCES = [
  "ateliers", "valeurs-metier", "biens-supports", "evenements-redoutes", "ecarts-socle", "sources-risque", "objectifs-vises", "couples",
  "parties-prenantes", "scenarios-strategiques", "chemins", "mesures-ecosysteme", "scenarios-operationnels", "risques", "mesures-traitement",
] as const;

const court = (t: unknown, n = 70) => { const s = String(t ?? ""); return s.length > n ? `${s.slice(0, n - 1)}…` : s; };
const opts = (liste: ObjetEbios[], libelle: (o: ObjetEbios) => string): Option[] => liste.map((o) => ({ valeur: o.id, libelle: libelle(o) }));
const cote = (libelle: string, v: unknown) => (v ? `${libelle} ${v} (${ECHELLE[v as number].toLowerCase()})` : "");

function MetaAtelier({ atelier, projetId, lectureSeule, acteurs }: { atelier?: ObjetEbios; projetId: string; lectureSeule: boolean; acteurs: Option[] }) {
  const enregistrer = useEnregistrerObjet(projetId, "ebios/ateliers");
  const [notes, setNotes] = useState("");
  const [date, setDate] = useState("");
  useEffect(() => { setNotes(String(atelier?.notes ?? "")); setDate(String(atelier?.date_atelier ?? "")); }, [atelier?.id, atelier?.notes, atelier?.date_atelier]);
  if (!atelier) return null;
  const participants = new Set((atelier.participants as string[]) ?? []);
  const maj = (champs: Record<string, unknown>) => enregistrer.mutate({ id: atelier.id, ...champs });

  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-groupe px-4 py-4 shadow-groupe">
      <div className="flex flex-wrap items-center gap-3">
        <div role="radiogroup" aria-label="Avancement de l'atelier" className="flex rounded-full bg-remplissage p-[3px]">
          {STATUTS.map((s) => (
            <button key={s.cle} type="button" role="radio" aria-checked={atelier.statut === s.cle} disabled={lectureSeule} onClick={() => maj({ statut: s.cle })}
              className={`rounded-full px-3 py-1.5 text-[13px] ${atelier.statut === s.cle ? "bg-groupe font-semibold shadow-groupe" : "font-medium text-texte-2"}`}>{s.libelle}</button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-[13px] text-texte-2">
          Date de l'atelier
          <input type="date" value={date} disabled={lectureSeule} onChange={(e) => setDate(e.target.value)} onBlur={() => date !== String(atelier.date_atelier ?? "") && maj({ date_atelier: date || null })}
            className="rounded-xl bg-remplissage px-2.5 py-1.5 text-[14px] text-texte outline-none" />
        </label>
      </div>
      {acteurs.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[13px] text-texte-2">Participants</span>
          {acteurs.map((a) => {
            const actif = participants.has(a.valeur);
            return (
              <button key={a.valeur} type="button" aria-pressed={actif} disabled={lectureSeule}
                onClick={() => { const n = new Set(participants); if (actif) n.delete(a.valeur); else n.add(a.valeur); maj({ participants: [...n] }); }}
                className={`rounded-full px-3 py-1 text-[13px] font-medium ${actif ? "bg-accent-doux text-accent-texte" : "bg-remplissage text-texte-2"}`}>{a.libelle}</button>
            );
          })}
        </div>
      )}
      <label className="flex flex-col gap-1">
        <span className="text-xs font-semibold text-texte-2">Notes de l'atelier{atelier.numero === 1 ? " (missions, périmètre, hypothèses)" : ""}</span>
        <textarea rows={2} value={notes} disabled={lectureSeule} onChange={(e) => setNotes(e.target.value)} onBlur={() => notes !== String(atelier.notes ?? "") && maj({ notes })}
          className="resize-y rounded-xl bg-remplissage px-3 py-2 text-[15px] outline-none focus:shadow-[0_0_0_2px_var(--sg-accent)]" />
      </label>
      {enregistrer.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{enregistrer.error.message}</p>}
    </div>
  );
}

function Activation({ projetId, lectureSeule }: { projetId: string; lectureSeule: boolean }) {
  const client = useQueryClient();
  const [erreur, setErreur] = useState("");
  const activer = () => api(`/api/projets/${projetId}/`, { methode: "PATCH", corps: { ebios_active: true } })
    .then(() => client.invalidateQueries({ queryKey: ["tableau-de-bord", projetId] }))
    .catch((e: Error) => setErreur(e.message));
  return (
    <div className="flex flex-col items-start gap-3 rounded-groupe bg-groupe px-5 py-6 shadow-groupe">
      <p className="text-[15px] text-texte-2">
        EBIOS RM n'est pas activé pour ce projet. La méthode est facultative et ne compte pas dans la limite des trois référentiels.
      </p>
      {!lectureSeule && <button type="button" onClick={activer} className="bouton-accent h-11 rounded-full px-5 text-[15px] font-semibold">Activer EBIOS RM</button>}
      {erreur && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{erreur}</p>}
    </div>
  );
}

export function PageEbios() {
  const { projetId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { data: tdb } = useTableauDeBord(projetId);
  const actif = tdb?.projet.ebios_active ?? false;
  const lectureSeule = tdb?.projet.lecture_seule ?? true;
  const id = actif ? projetId : "";
  const { data: synthese } = useSyntheseEbios(id);
  const { data: acteurs = [] } = useActeurs(projetId);
  const socle = usePreremplirSocle(projetId);
  const o = useToutEbios(id, RESSOURCES);
  const n = Number(params.get("atelier") ?? 1);

  const nom = (r: string, champ: string) => Object.fromEntries(o[r].map((x) => [x.id, String(x[champ] ?? "")]));
  const vm = nom("valeurs-metier", "nom"), sr = nom("sources-risque", "libelle"), ov = nom("objectifs-vises", "libelle"), pp = nom("parties-prenantes", "nom");
  const ss = nom("scenarios-strategiques", "intitule"), ch = nom("chemins", "description");
  const couple = (c: ObjetEbios) => `${sr[c.source as string] ?? "?"} → ${ov[c.objectif as string] ?? "?"}`;
  const coupleNom = Object.fromEntries(o.couples.map((c) => [c.id, couple(c)]));
  const optActeurs = acteurs.map((a) => ({ valeur: a.id, libelle: `${a.affichage} — ${a.role_libelle}` }));
  const liste = (cles: unknown, table: Record<string, string>) => ((cles as string[]) ?? []).map((k) => court(table[k], 40)).join(", ");

  const C: Record<string, Config> = {
    vm: { ressource: "valeurs-metier", titre: "Valeurs métier", ajout: "Ajouter une valeur métier", vide: "Aucune valeur métier.",
      aide: "Processus ou informations essentiels à la mission, que l'on veut protéger.",
      champs: [{ cle: "nom", libelle: "Nom", type: "texte", requis: true },
        { cle: "nature", libelle: "Nature", type: "choix", requis: true, options: [{ valeur: "processus", libelle: "Processus" }, { valeur: "information", libelle: "Information" }] },
        { cle: "description", libelle: "Description", type: "zone" }, { cle: "entite_responsable", libelle: "Entité responsable", type: "texte" }],
      resume: (x) => String(x.nom), detail: (x) => [x.nature === "processus" ? "Processus" : "Information", court(x.description, 120)].filter(Boolean).join(" · ") },
    er: { ressource: "evenements-redoutes", titre: "Événements redoutés", ajout: "Ajouter un événement redouté", vide: "Aucun événement redouté.",
      aide: "Ce qu'il ne faut pas qu'il arrive à une valeur métier (indisponibilité, altération, divulgation…), avec sa gravité.",
      champs: [{ cle: "valeur_metier", libelle: "Valeur métier", type: "lien", requis: true, options: opts(o["valeurs-metier"], (x) => String(x.nom)) },
        { cle: "description", libelle: "Événement redouté", type: "zone", requis: true }, { cle: "impacts", libelle: "Impacts", type: "zone" },
        { cle: "gravite", libelle: "Gravité", type: "echelle", requis: true }],
      resume: (x) => court(x.description, 110), detail: (x) => [vm[x.valeur_metier as string], cote("gravité", x.gravite)].filter(Boolean).join(" · ") },
    bs: { ressource: "biens-supports", titre: "Biens supports", ajout: "Ajouter un bien support", vide: "Aucun bien support.",
      aide: "Composants sur lesquels reposent les valeurs métier : serveurs, applications, réseaux, personnes, locaux, prestataires.",
      champs: [{ cle: "nom", libelle: "Nom", type: "texte", requis: true }, { cle: "type_bien", libelle: "Type", type: "texte" },
        { cle: "valeurs_metier", libelle: "Valeurs métier supportées", type: "liens", options: opts(o["valeurs-metier"], (x) => String(x.nom)) },
        { cle: "description", libelle: "Description", type: "zone" }],
      resume: (x) => String(x.nom), detail: (x) => [x.type_bien, liste(x.valeurs_metier, vm)].filter(Boolean).join(" · ") },
    socle: { ressource: "ecarts-socle", titre: "Socle de sécurité", ajout: "Ajouter un écart", vide: "Aucun écart au socle enregistré.",
      aide: "Écarts aux référentiels applicables. Ils se déduisent des évaluations de conformité du projet.",
      champs: [{ cle: "intitule", libelle: "Mesure ou exigence", type: "texte", requis: true },
        { cle: "etat", libelle: "État", type: "choix", requis: true, options: [{ valeur: "applique", libelle: "Appliqué sans restriction" },
          { valeur: "restrictions", libelle: "Appliqué avec restrictions" }, { valeur: "non_applique", libelle: "Non appliqué" }] },
        { cle: "justification", libelle: "Justification", type: "zone" }],
      resume: (x) => court(x.intitule, 110), detail: (x) => ({ applique: "Appliqué", restrictions: "Avec restrictions", non_applique: "Non appliqué" } as Record<string, string>)[x.etat as string] },
    sr: { ressource: "sources-risque", titre: "Sources de risque", ajout: "Ajouter une source de risque", vide: "Aucune source de risque.",
      aide: "Qui pourrait porter atteinte au projet : État, crime organisé, hacktiviste, concurrent, personne interne…",
      champs: [{ cle: "libelle", libelle: "Source de risque", type: "texte", requis: true }, { cle: "categorie", libelle: "Catégorie", type: "texte" },
        { cle: "description", libelle: "Description", type: "zone" }],
      resume: (x) => String(x.libelle), detail: (x) => String(x.categorie ?? "") },
    ov: { ressource: "objectifs-vises", titre: "Objectifs visés", ajout: "Ajouter un objectif visé", vide: "Aucun objectif visé.",
      aide: "Ce que la source de risque cherche à obtenir : gain financier, espionnage, sabotage, revendication…",
      champs: [{ cle: "libelle", libelle: "Objectif visé", type: "texte", requis: true }, { cle: "description", libelle: "Description", type: "zone" }],
      resume: (x) => String(x.libelle) },
    couples: { ressource: "couples", titre: "Couples SR/OV", ajout: "Ajouter un couple", vide: "Aucun couple SR/OV.",
      aide: "Évaluez chaque couple puis retenez les plus pertinents : seuls les couples retenus alimentent l'atelier 3.",
      champs: [{ cle: "source", libelle: "Source de risque", type: "lien", requis: true, options: opts(o["sources-risque"], (x) => String(x.libelle)) },
        { cle: "objectif", libelle: "Objectif visé", type: "lien", requis: true, options: opts(o["objectifs-vises"], (x) => String(x.libelle)) },
        { cle: "motivation", libelle: "Motivation", type: "echelle", requis: true }, { cle: "ressources", libelle: "Ressources", type: "echelle", requis: true },
        { cle: "activite", libelle: "Activité", type: "echelle", requis: true }, { cle: "pertinence", libelle: "Pertinence", type: "echelle", requis: true },
        { cle: "retenu", libelle: "Couple retenu", type: "booleen", aide: "À étudier dans les scénarios stratégiques." },
        { cle: "justification", libelle: "Justification", type: "zone" }],
      resume: (x) => <>{couple(x)} {x.retenu ? <span className="ml-1 rounded-full bg-accent-doux px-2 py-0.5 text-[11px] font-semibold text-accent-texte">retenu</span> : null}</>,
      detail: (x) => cote("pertinence", x.pertinence) },
    pp: { ressource: "parties-prenantes", titre: "Parties prenantes de l'écosystème", ajout: "Ajouter une partie prenante", vide: "Aucune partie prenante.",
      aide: "Fournisseurs, prestataires, partenaires ou clients en lien avec l'objet étudié. Leur cotation donne leur niveau de menace.",
      champs: [{ cle: "nom", libelle: "Nom", type: "texte", requis: true }, { cle: "categorie", libelle: "Catégorie", type: "texte" },
        { cle: "dependance", libelle: "Dépendance", type: "echelle", requis: true }, { cle: "penetration", libelle: "Pénétration", type: "echelle", requis: true },
        { cle: "maturite", libelle: "Maturité cyber", type: "echelle", requis: true }, { cle: "confiance", libelle: "Confiance", type: "echelle", requis: true },
        { cle: "critique", libelle: "Partie prenante critique", type: "booleen" }],
      resume: (x) => String(x.nom), detail: (x) => [x.categorie, `menace ${x.niveau_menace} (${({ danger: "danger", controle: "contrôle", veille: "veille" } as Record<string, string>)[x.zone as string]})`].filter(Boolean).join(" · ") },
    ss: { ressource: "scenarios-strategiques", titre: "Scénarios stratégiques", ajout: "Ajouter un scénario stratégique", vide: "Aucun scénario stratégique.",
      aide: "Comment un couple retenu provoquerait un ou plusieurs événements redoutés, directement ou via l'écosystème.",
      champs: [{ cle: "couple", libelle: "Couple SR/OV retenu", type: "lien", requis: true, options: opts(o.couples.filter((c) => c.retenu), couple) },
        { cle: "intitule", libelle: "Intitulé", type: "texte", requis: true }, { cle: "description", libelle: "Description", type: "zone" },
        { cle: "evenements_redoutes", libelle: "Événements redoutés provoqués", type: "liens", options: opts(o["evenements-redoutes"], (x) => court(x.description, 50)) },
        { cle: "gravite", libelle: "Gravité", type: "echelle", requis: true }],
      resume: (x) => String(x.intitule), detail: (x) => [coupleNom[x.couple as string], cote("gravité", x.gravite)].filter(Boolean).join(" · ") },
    ch: { ressource: "chemins", titre: "Chemins d'attaque", ajout: "Ajouter un chemin d'attaque", vide: "Aucun chemin d'attaque.",
      champs: [{ cle: "scenario", libelle: "Scénario stratégique", type: "lien", requis: true, options: opts(o["scenarios-strategiques"], (x) => String(x.intitule)) },
        { cle: "description", libelle: "Chemin d'attaque", type: "zone", requis: true },
        { cle: "parties_prenantes", libelle: "Parties prenantes empruntées", type: "liens", options: opts(o["parties-prenantes"], (x) => String(x.nom)) }],
      resume: (x) => court(x.description, 110), detail: (x) => [ss[x.scenario as string], liste(x.parties_prenantes, pp)].filter(Boolean).join(" · ") },
    me: { ressource: "mesures-ecosysteme", titre: "Mesures sur l'écosystème", ajout: "Ajouter une mesure", vide: "Aucune mesure sur l'écosystème.",
      aide: "Exigences à imposer aux parties prenantes les plus menaçantes pour réduire leur niveau de menace.",
      champs: [{ cle: "partie_prenante", libelle: "Partie prenante", type: "lien", requis: true, options: opts(o["parties-prenantes"], (x) => String(x.nom)) },
        { cle: "intitule", libelle: "Mesure", type: "texte", requis: true }, { cle: "description", libelle: "Description", type: "zone" }],
      resume: (x) => String(x.intitule), detail: (x) => pp[x.partie_prenante as string] },
    so: { ressource: "scenarios-operationnels", titre: "Scénarios opérationnels", ajout: "Ajouter un scénario opérationnel", vide: "Aucun scénario opérationnel.",
      aide: "Mode opératoire technique d'un chemin d'attaque : reconnaissance, intrusion, déplacement, exploitation.",
      champs: [{ cle: "chemin", libelle: "Chemin d'attaque", type: "lien", requis: true, options: opts(o.chemins, (x) => court(x.description, 60)) },
        { cle: "intitule", libelle: "Intitulé", type: "texte", requis: true }, { cle: "mode_operatoire", libelle: "Mode opératoire", type: "zone" },
        { cle: "biens_supports", libelle: "Biens supports visés", type: "liens", options: opts(o["biens-supports"], (x) => String(x.nom)) },
        { cle: "vraisemblance", libelle: "Vraisemblance", type: "echelle", requis: true }],
      resume: (x) => String(x.intitule), detail: (x) => [court(ch[x.chemin as string], 60), cote("vraisemblance", x.vraisemblance)].filter(Boolean).join(" · ") },
    risques: { ressource: "risques", titre: "Risques", ajout: "Ajouter un risque", vide: "Aucun risque.",
      aide: "Un risque par scénario. Gravité et vraisemblance sont reprises des scénarios si vous ne les saisissez pas. « Accepter » inscrit le risque au registre des risques résiduels.",
      champs: [{ cle: "scenario_strategique", libelle: "Scénario stratégique", type: "lien", requis: true, options: opts(o["scenarios-strategiques"], (x) => String(x.intitule)) },
        { cle: "scenario_operationnel", libelle: "Scénario opérationnel", type: "lien", options: opts(o["scenarios-operationnels"], (x) => String(x.intitule)) },
        { cle: "intitule", libelle: "Intitulé du risque", type: "texte", requis: true },
        { cle: "gravite", libelle: "Gravité initiale", type: "echelle" }, { cle: "vraisemblance", libelle: "Vraisemblance initiale", type: "echelle" },
        { cle: "option_traitement", libelle: "Option de traitement", type: "choix", options: [{ valeur: "reduire", libelle: "Réduire" },
          { valeur: "transferer", libelle: "Transférer" }, { valeur: "eviter", libelle: "Éviter" }, { valeur: "accepter", libelle: "Accepter" }] },
        { cle: "gravite_residuelle", libelle: "Gravité résiduelle", type: "echelle" }, { cle: "vraisemblance_residuelle", libelle: "Vraisemblance résiduelle", type: "echelle" }],
      resume: (x) => String(x.intitule),
      detail: (x) => [`G${x.gravite} × V${x.vraisemblance}`, x.niveau_residuel ? `résiduel G${x.gravite_residuelle} × V${x.vraisemblance_residuelle}` : "",
        ({ reduire: "à réduire", transferer: "à transférer", eviter: "à éviter", accepter: "accepté" } as Record<string, string>)[x.option_traitement as string] ?? "sans traitement"].filter(Boolean).join(" · ") },
    mt: { ressource: "mesures-traitement", titre: "Mesures de traitement (PACS)", ajout: "Ajouter une mesure", vide: "Aucune mesure de traitement.",
      aide: "Chaque mesure crée une tâche dans le plan d'action, suivie comme les autres.",
      champs: [{ cle: "intitule", libelle: "Mesure", type: "texte", requis: true }, { cle: "description", libelle: "Description", type: "zone" },
        { cle: "risques", libelle: "Risques traités", type: "liens", options: opts(o.risques, (x) => String(x.intitule)) },
        { cle: "responsable", libelle: "Responsable", type: "lien", options: optActeurs }, { cle: "echeance", libelle: "Échéance", type: "date" },
        { cle: "cout_complexite", libelle: "Coût / complexité", type: "echelle" }, { cle: "freins", libelle: "Freins et difficultés", type: "zone" }],
      resume: (x) => String(x.intitule), detail: (x) => [liste(x.risques, Object.fromEntries(o.risques.map((r) => [r.id, String(r.intitule)]))),
        x.tache_statut ? `tâche : ${String(x.tache_statut).toLowerCase()}` : ""].filter(Boolean).join(" · ") },
  };
  const parents = { ...vm, ...coupleNom, ...Object.fromEntries(o.chemins.map((c) => [c.id, court(c.description, 50)])) };
  const atelier = o.ateliers.find((a) => a.numero === n);
  const alertes = synthese?.alertes.filter((a) => a.atelier === n) ?? [];
  const liste_ = (k: string, enTete?: ReactNode) => <ListeObjets key={k} config={C[k]} objets={o[C[k].ressource]} projetId={projetId} lectureSeule={lectureSeule} enTete={enTete} />;

  return (
    <Disposition>
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5 lg:pt-2.5">
          <span className="text-[13px] font-semibold text-texte-2">{tdb?.projet.nom ?? "Projet"}</span>
          <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">EBIOS RM</h1>
          <p className="text-[15px] text-texte-2">Analyse de risques en cinq ateliers, dans l'ordre que vous voulez : les incohérences sont signalées au fil de l'eau.</p>
        </div>

        {tdb && !actif ? <Activation projetId={projetId} lectureSeule={lectureSeule} /> : (
          <>
            <nav aria-label="Ateliers" className="grid grid-cols-5 gap-1.5">
              {ATELIERS.map((a) => {
                const statut = synthese?.ateliers.find((x) => x.numero === a.n)?.statut ?? "non_commence";
                const nb = synthese?.alertes.filter((x) => x.atelier === a.n).length ?? 0;
                return (
                  <button key={a.n} type="button" aria-current={n === a.n ? "step" : undefined} onClick={() => setParams({ atelier: String(a.n) })}
                    className={`flex flex-col items-start gap-1 rounded-2xl px-3 py-2.5 text-left transition-colors duration-200 ease-ios ${n === a.n ? "bg-groupe shadow-[0_0_0_1.5px_var(--sg-accent)]" : "bg-remplissage"}`}>
                    <span className="flex w-full items-center justify-between text-[13px] font-bold">
                      {a.n}
                      <span aria-hidden="true" className={`size-2.5 rounded-full ${statut === "termine" ? "bg-conforme" : statut === "en_cours" ? "bg-accent" : "border-[1.5px] border-texte-3"}`} />
                    </span>
                    <span className="hidden text-[12px] leading-tight font-semibold sm:block">{a.titre}</span>
                    <span className="sr-only">{a.titre}, {STATUTS.find((s) => s.cle === statut)?.libelle}</span>
                    {nb > 0 && <span className="text-[11px] font-semibold text-partiel-texte">{nb} alerte{nb > 1 ? "s" : ""}</span>}
                  </button>
                );
              })}
            </nav>

            <section aria-labelledby="titre-atelier" className="flex flex-col gap-5">
              <div className="flex flex-col gap-1">
                <h2 id="titre-atelier" className="text-[24px] font-bold tracking-[-0.02em]">Atelier {n} — {ATELIERS[n - 1].titre}</h2>
                <p className="max-w-[720px] text-[15px] leading-snug text-texte-2">{ATELIERS[n - 1].but}</p>
              </div>
              <MetaAtelier atelier={atelier} projetId={projetId} lectureSeule={lectureSeule} acteurs={optActeurs} />
              {alertes.length > 0 && (
                <ul aria-label="Points à compléter" className="flex flex-col gap-1 rounded-2xl bg-partiel/10 px-4 py-3 text-[13px] text-partiel-texte">
                  {alertes.map((a) => <li key={a.texte}>• {a.texte}</li>)}
                </ul>
              )}
              <PanneauPropositions atelier={n} projetId={projetId} lectureSeule={lectureSeule} parents={parents} />

              {n === 1 && <>{liste_("vm")}{liste_("er")}{liste_("bs")}
                {liste_("socle", !lectureSeule && (
                  <button type="button" disabled={socle.isPending} onClick={() => socle.mutate()} className="rounded-full bg-accent-doux px-3.5 py-1.5 text-[13px] font-semibold text-accent-texte">
                    {socle.isPending ? "Pré-remplissage…" : "Pré-remplir depuis la conformité"}
                  </button>
                ))}
                {socle.data && <p className="-mt-3 px-1 text-[13px] text-texte-2">{socle.data.crees ? `${socle.data.crees} écart(s) ajouté(s) depuis les mesures manquantes ou partielles.` : "Aucun nouvel écart : le socle est à jour."}</p>}
                <p className="px-1 text-[13px] text-texte-2">Le détail des mesures se gère dans <Link to={`/projets/${projetId}/mesures`} className="font-semibold text-accent-texte">Mesures</Link>.</p>
              </>}
              {n === 2 && <>{liste_("sr")}{liste_("ov")}{liste_("couples")}</>}
              {n === 3 && <>{liste_("pp")}{synthese && synthese.cartographie.parties.length > 0 && <Cartographie carto={synthese.cartographie} />}
                {liste_("me")}{liste_("ss")}{liste_("ch")}</>}
              {n === 4 && <>{liste_("so")}</>}
              {n === 5 && <>{synthese && <Matrice matrice={synthese.matrice} />}{liste_("risques")}{liste_("mt")}
                <p className="px-1 text-[13px] text-texte-2">Les tâches créées se suivent dans le <Link to={`/projets/${projetId}/plan-action`} className="font-semibold text-accent-texte">plan d'action</Link>.</p>
              </>}
            </section>
          </>
        )}
      </div>
    </Disposition>
  );
}
