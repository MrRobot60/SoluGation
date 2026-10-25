import { useEffect, useRef, useState, type ComponentType, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";

import { useCreerProjet, useMembres, useMoi, useReferentiels, useRolesProjet } from "../api/hooks";
import type { ActeurInitial, NiveauVise, NouveauProjet, TypeBien } from "../api/types";
import { Logo } from "../composants/Disposition";
import {
  IconeCoche, IconeCouches, IconeCroix, IconeFenetre, IconePlus, IconePoints, IconePortable, IconeReseau,
} from "../composants/Icones";
import { nomCourt } from "../composants/statuts";

const MAX_REFERENTIELS = 3;

const TYPES: { valeur: TypeBien; libelle: string; detail: string; Icone: ComponentType<{ taille?: number }> }[] = [
  { valeur: "application", libelle: "Application", detail: "Service web, mobile ou métier", Icone: IconeFenetre },
  { valeur: "poste_travail", libelle: "Poste de travail", detail: "Configuration type, parc de postes", Icone: IconePortable },
  { valeur: "si", libelle: "Système d'information", detail: "Ensemble d'applications et d'infrastructures", Icone: IconeReseau },
  { valeur: "autre", libelle: "Autre", detail: "Objet connecté, service externalisé…", Icone: IconePoints },
];

const NIVEAUX: { valeur: NiveauVise; libelle: string; detail: string }[] = [
  { valeur: "elementaire", libelle: "Élémentaire", detail: "Bien peu exposé : dossier allégé, sans audit ni test d'intrusion." },
  { valeur: "standard", libelle: "Standard", detail: "Cas courant : dossier complet, audit de sécurité et test d'intrusion." },
  { valeur: "renforce", libelle: "Renforcé", detail: "Bien sensible ou très exposé : mêmes pièces, contrôles approfondis (prestataire qualifié conseillé)." },
];

const ETAPES = ["Le bien", "Référentiels", "Niveau visé", "Acteurs", "Récapitulatif"];

type ActeurBrouillon = ActeurInitial & { cle: string; affichage: string; libelleRole: string };

const VIDE: NouveauProjet = {
  nom: "", description: "", type_bien: "application", niveau_vise: "standard", ebios_active: false,
  referentiels: [], acteurs: [], generer_checklist: true,
};

/* ---- Petits composants de formulaire ----------------------------------------------------- */

function Groupe({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`overflow-hidden rounded-groupe bg-groupe shadow-groupe ${className}`}>{children}</div>;
}

function Separateur({ retrait = "ml-4" }: { retrait?: string }) {
  return <div aria-hidden="true" className={`h-px bg-separateur ${retrait}`} />;
}

function Champ({ libelle, children }: { libelle: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-0.5 px-4 pt-2.5 pb-2">
      <span className="text-xs font-medium text-texte-2">{libelle}</span>
      {children}
    </label>
  );
}

const classeSaisie = "w-full bg-transparent text-[16px] outline-none placeholder:text-texte-3";
const classeSelect = "w-full appearance-none bg-transparent text-[16px] outline-none";

function Pastille({ actif }: { actif: boolean }) {
  return (
    <span aria-hidden="true" className={`flex size-[22px] shrink-0 items-center justify-center rounded-full border-[1.5px] transition-colors duration-200 ease-ios ${actif ? "border-accent bg-accent text-white" : "border-texte-3"}`}>
      {actif && <IconeCoche taille={13} />}
    </span>
  );
}

/* ---- Étapes ------------------------------------------------------------------------------ */

function EtapeBien({ p, maj }: { p: NouveauProjet; maj: (v: Partial<NouveauProjet>) => void }) {
  return (
    <div className="flex flex-col gap-6">
      <Groupe>
        <Champ libelle="Nom du projet">
          <input className={classeSaisie} value={p.nom} required maxLength={200} autoFocus
            placeholder="Portail usagers" onChange={(e) => maj({ nom: e.target.value })} />
        </Champ>
        <Separateur />
        <Champ libelle="Description (facultatif)">
          <textarea className={`${classeSaisie} min-h-[72px] resize-none`} value={p.description} rows={3}
            placeholder="Périmètre, finalité, utilisateurs…" onChange={(e) => maj({ description: e.target.value })} />
        </Champ>
      </Groupe>

      <fieldset className="flex flex-col gap-2.5">
        <legend className="mb-2.5 px-1 text-[15px] font-semibold">Type de bien</legend>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {TYPES.map(({ valeur, libelle, detail, Icone }) => {
            const actif = p.type_bien === valeur;
            return (
              <label key={valeur} className={`flex cursor-pointer items-center gap-3 rounded-[18px] bg-groupe p-3.5 shadow-groupe ring-2 transition-shadow duration-200 ease-ios has-focus-visible:ring-accent-texte ${actif ? "ring-accent" : "ring-transparent"}`}>
                <input type="radio" name="type_bien" value={valeur} checked={actif} className="sr-only"
                  onChange={() => maj({ type_bien: valeur })} />
                <span className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${actif ? "bg-accent-doux text-accent-texte" : "bg-remplissage text-texte-2"}`}>
                  <Icone taille={21} />
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-px">
                  <span className="text-[15px] font-semibold">{libelle}</span>
                  <span className="text-[13px] leading-snug text-texte-2">{detail}</span>
                </span>
                <Pastille actif={actif} />
              </label>
            );
          })}
        </div>
      </fieldset>
    </div>
  );
}

function EtapeReferentiels({ p, maj }: { p: NouveauProjet; maj: (v: Partial<NouveauProjet>) => void }) {
  const { data: referentiels = [], isPending } = useReferentiels();
  const plein = p.referentiels.length >= MAX_REFERENTIELS;
  const basculer = (id: string) =>
    maj({ referentiels: p.referentiels.includes(id) ? p.referentiels.filter((r) => r !== id) : [...p.referentiels, id] });

  return (
    <div className="flex flex-col gap-6">
      <fieldset className="flex flex-col">
        <legend className="mb-2.5 flex w-full items-baseline justify-between px-1">
          <span className="text-[15px] font-semibold">Référentiels applicables</span>
          <span aria-live="polite" className={`text-[13px] ${plein ? "font-semibold text-accent-texte" : "text-texte-2"}`}>
            {p.referentiels.length} / {MAX_REFERENTIELS}
          </span>
        </legend>
        <Groupe>
          {isPending && <p className="px-4 py-4 text-sm text-texte-2">Chargement de la bibliothèque…</p>}
          {referentiels.map((r, i) => {
            const actif = p.referentiels.includes(r.id);
            const bloque = plein && !actif;
            return (
              <div key={r.id}>
                {i > 0 && <Separateur retrait="ml-[52px]" />}
                <label className={`flex items-center gap-3.5 px-4 py-3 ${bloque ? "cursor-not-allowed opacity-45" : "cursor-pointer"}`}>
                  <input type="checkbox" className="sr-only peer" checked={actif} disabled={bloque} onChange={() => basculer(r.id)} />
                  <span className="rounded-full peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent-texte"><Pastille actif={actif} /></span>
                  <span className="flex min-w-0 flex-1 flex-col gap-px">
                    <span className="text-[15px] font-medium">{r.nom}</span>
                    <span className="text-[13px] text-texte-2">
                      {r.editeur} · version {r.version} · {r.nb_mesures} mesures{r.prive ? " · copie de votre organisation" : ""}
                    </span>
                  </span>
                </label>
              </div>
            );
          })}
        </Groupe>
        <p className="mt-2 px-1 text-[13px] text-texte-2">Entre 1 et 3 référentiels. Une même preuve peut couvrir des exigences équivalentes.</p>
      </fieldset>

      <Groupe>
        <label className="flex cursor-pointer items-center gap-3.5 px-4 py-3.5">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-remplissage text-texte-2"><IconeCouches taille={21} /></span>
          <span className="flex min-w-0 flex-1 flex-col gap-px">
            <span className="text-[15px] font-semibold">Analyse de risques EBIOS RM</span>
            <span className="text-[13px] leading-snug text-texte-2">Méthode de l'ANSSI, ateliers 1 à 5 guidés. Ne compte pas dans les 3 référentiels.</span>
          </span>
          <input type="checkbox" role="switch" checked={p.ebios_active} onChange={(e) => maj({ ebios_active: e.target.checked })} className="peer sr-only" />
          <span aria-hidden="true" className="relative h-[31px] w-[51px] shrink-0 rounded-full bg-remplissage transition-colors duration-200 ease-ios peer-checked:bg-conforme peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent-texte after:absolute after:top-[2px] after:left-[2px] after:size-[27px] after:rounded-full after:bg-white after:shadow-[0_3px_8px_rgb(0_0_0/0.15)] after:transition-transform after:duration-200 after:ease-ios peer-checked:after:translate-x-5" />
        </label>
      </Groupe>
    </div>
  );
}

function EtapeNiveau({ p, maj }: { p: NouveauProjet; maj: (v: Partial<NouveauProjet>) => void }) {
  return (
    <fieldset>
      <legend className="sr-only">Niveau visé</legend>
      <Groupe>
        {NIVEAUX.map(({ valeur, libelle, detail }, i) => {
          const actif = p.niveau_vise === valeur;
          return (
            <div key={valeur}>
              {i > 0 && <Separateur retrait="ml-[52px]" />}
              <label className="flex cursor-pointer items-center gap-3.5 px-4 py-3.5">
                <input type="radio" name="niveau" value={valeur} checked={actif} className="peer sr-only" onChange={() => maj({ niveau_vise: valeur })} />
                <span className="rounded-full peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent-texte"><Pastille actif={actif} /></span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-[15px] font-semibold">{libelle}</span>
                  <span className="text-[13px] leading-snug text-texte-2">{detail}</span>
                </span>
              </label>
            </div>
          );
        })}
      </Groupe>
      <p className="mt-2 px-1 text-[13px] text-texte-2">Le niveau détermine les pièces attendues dans la checklist.</p>
    </fieldset>
  );
}

function EtapeActeurs({ acteurs, setActeurs }: { acteurs: ActeurBrouillon[]; setActeurs: (a: ActeurBrouillon[]) => void }) {
  const { data: moi } = useMoi();
  const { data: membres = [] } = useMembres();
  const { data: roles = [] } = useRolesProjet();
  const [mode, setMode] = useState<"membre" | "externe">("membre");
  const [utilisateur, setUtilisateur] = useState("");
  const [nom, setNom] = useState("");
  const [email, setEmail] = useState("");
  const [organisme, setOrganisme] = useState("");
  const [role, setRole] = useState("");
  const roleChef = roles.find((r) => r.code === "chef-projet");
  const sansAutorite = !acteurs.some((a) => roles.find((r) => r.id === a.role)?.code === "autorite-homologation");

  const ajouter = (e: FormEvent) => {
    e.preventDefault();
    const libelleRole = roles.find((r) => r.id === role)?.libelle ?? "";
    if (mode === "membre") {
      const m = membres.find((u) => u.id === utilisateur);
      if (!m || !role) return;
      if (acteurs.some((a) => a.utilisateur === m.id && a.role === role)) return;
      setActeurs([...acteurs, { cle: `${m.id}-${role}`, utilisateur: m.id, role, affichage: m.nom_complet || m.email, libelleRole }]);
      setUtilisateur("");
    } else {
      if (!email || !role) return;
      setActeurs([...acteurs, { cle: `${email}-${role}`, nom, email, organisme, role, affichage: nom ? `${nom} · ${email}` : email, libelleRole }]);
      setNom(""); setEmail(""); setOrganisme("");
    }
    setRole("");
  };

  return (
    <div className="flex flex-col gap-6">
      <section aria-label="Acteurs du projet">
        <Groupe>
          <div className="flex items-center gap-3 px-4 py-3">
            <span className="flex min-w-0 flex-1 flex-col gap-px">
              <span className="text-[15px] font-medium">{moi?.nom_complet} <span className="text-texte-2">(vous)</span></span>
              <span className="text-[13px] text-texte-2">{roleChef?.libelle ?? "Chef de projet"} · ajouté automatiquement</span>
            </span>
          </div>
          {acteurs.map((a) => (
            <div key={a.cle}>
              <Separateur />
              <div className="flex items-center gap-3 px-4 py-2.5">
                <span className="flex min-w-0 flex-1 flex-col gap-px">
                  <span className="truncate text-[15px] font-medium">{a.affichage}</span>
                  <span className="text-[13px] text-texte-2">{a.libelleRole}{a.utilisateur ? "" : " · sans compte"}</span>
                </span>
                <button type="button" aria-label={`Retirer ${a.affichage}`} onClick={() => setActeurs(acteurs.filter((x) => x.cle !== a.cle))}
                  className="flex size-11 items-center justify-center rounded-full text-texte-2 hover:bg-remplissage">
                  <IconeCroix taille={17} />
                </button>
              </div>
            </div>
          ))}
        </Groupe>
        {sansAutorite && (
          <p className="mt-2 px-1 text-[13px] text-partiel-texte">
            Aucune autorité d'homologation pour l'instant : vous pourrez la désigner plus tard.
          </p>
        )}
      </section>

      <form onSubmit={ajouter} aria-label="Ajouter un acteur" className="flex flex-col gap-3">
        <div role="radiogroup" aria-label="Type d'acteur" className="flex self-start rounded-full bg-remplissage p-[3px]">
          {(["membre", "externe"] as const).map((m) => (
            <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => setMode(m)}
              className={`rounded-full px-4 py-1.5 text-[13px] transition-colors duration-200 ease-ios ${mode === m ? "bg-groupe font-semibold shadow-groupe" : "font-medium text-texte-2"}`}>
              {m === "membre" ? "Membre de l'organisation" : "Contact externe"}
            </button>
          ))}
        </div>
        <Groupe>
          {mode === "membre" ? (
            <Champ libelle="Personne">
              <select className={classeSelect} value={utilisateur} onChange={(e) => setUtilisateur(e.target.value)}>
                <option value="">Choisir…</option>
                {membres.map((u) => (
                  <option key={u.id} value={u.id}>{u.nom_complet || u.email}{u.fonction ? ` — ${u.fonction}` : ""}</option>
                ))}
              </select>
            </Champ>
          ) : (
            <>
              <Champ libelle="Nom">
                <input className={classeSaisie} value={nom} onChange={(e) => setNom(e.target.value)} placeholder="Direction générale" />
              </Champ>
              <Separateur />
              <Champ libelle="Email">
                <input type="email" className={classeSaisie} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="prenom.nom@exemple.fr" />
              </Champ>
              <Separateur />
              <Champ libelle="Organisme (facultatif)">
                <input className={classeSaisie} value={organisme} onChange={(e) => setOrganisme(e.target.value)} />
              </Champ>
            </>
          )}
          <Separateur />
          <Champ libelle="Rôle dans le projet">
            <select className={classeSelect} value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="">Choisir…</option>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.libelle}</option>)}
            </select>
          </Champ>
        </Groupe>
        <button type="submit" disabled={!role || (mode === "membre" ? !utilisateur : !email)}
          className="flex h-11 items-center gap-2 self-start rounded-full bg-accent-doux px-4 text-[15px] font-semibold text-accent-texte disabled:opacity-45">
          <IconePlus taille={17} /> Ajouter l'acteur
        </button>
      </form>
    </div>
  );
}

function EtapeRecap({ p, acteurs, maj }: { p: NouveauProjet; acteurs: ActeurBrouillon[]; maj: (v: Partial<NouveauProjet>) => void }) {
  const { data: referentiels = [] } = useReferentiels();
  const lignes: [string, ReactNode][] = [
    ["Projet", p.nom],
    ["Type de bien", TYPES.find((t) => t.valeur === p.type_bien)?.libelle],
    ["Référentiels", referentiels.filter((r) => p.referentiels.includes(r.id)).map(nomCourt).join(" · ")],
    ["EBIOS RM", p.ebios_active ? "Activé" : "Non"],
    ["Niveau visé", NIVEAUX.find((n) => n.valeur === p.niveau_vise)?.libelle],
    ["Acteurs", `${acteurs.length + 1} (dont vous, chef de projet)`],
  ];
  return (
    <div className="flex flex-col gap-6">
      <Groupe>
        <dl>
          {lignes.map(([cle, valeur], i) => (
            <div key={cle}>
              {i > 0 && <Separateur />}
              <div className="flex items-baseline justify-between gap-4 px-4 py-3">
                <dt className="shrink-0 text-[15px] text-texte-2">{cle}</dt>
                <dd className="min-w-0 text-right text-[15px] font-medium">{valeur}</dd>
              </div>
            </div>
          ))}
        </dl>
      </Groupe>
      <Groupe>
        <label className="flex cursor-pointer items-center gap-3.5 px-4 py-3.5">
          <input type="checkbox" className="peer sr-only" checked={p.generer_checklist} onChange={(e) => maj({ generer_checklist: e.target.checked })} />
          <span className="rounded-full peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent-texte"><Pastille actif={p.generer_checklist} /></span>
          <span className="flex min-w-0 flex-1 flex-col gap-px">
            <span className="text-[15px] font-semibold">Générer la checklist des documents attendus</span>
            <span className="text-[13px] leading-snug text-texte-2">Selon le type de bien, le niveau et EBIOS RM, avec un responsable et une échéance pour chaque pièce.</span>
          </span>
        </label>
      </Groupe>
      <p className="px-1 text-[13px] text-texte-2">Les notifications et le calendrier sont activés par défaut ; vous pourrez les régler dans les paramètres du projet.</p>
    </div>
  );
}

/* ---- Assistant ---------------------------------------------------------------------------- */

export function PageNouveauProjet() {
  const naviguer = useNavigate();
  const creer = useCreerProjet();
  const [etape, setEtape] = useState(0);
  const [p, setP] = useState<NouveauProjet>(VIDE);
  const [acteurs, setActeurs] = useState<ActeurBrouillon[]>([]);
  const titre = useRef<HTMLHeadingElement>(null);
  const maj = (v: Partial<NouveauProjet>) => setP((avant) => ({ ...avant, ...v }));

  useEffect(() => {
    if (etape > 0) titre.current?.focus();
  }, [etape]);

  const valide = [p.nom.trim().length > 0, p.referentiels.length >= 1 && p.referentiels.length <= MAX_REFERENTIELS, true, true, true][etape];
  const derniere = etape === ETAPES.length - 1;

  const suivant = () => {
    if (!valide) return;
    if (!derniere) return setEtape(etape + 1);
    const corps: NouveauProjet = {
      ...p,
      nom: p.nom.trim(),
      acteurs: acteurs.map(({ utilisateur, nom, email, organisme, role }) => ({ utilisateur, nom, email, organisme, role })),
    };
    creer.mutate(corps, { onSuccess: (projet) => naviguer(`/projets/${projet.id}`, { replace: true }) });
  };

  return (
    <div className="flex min-h-dvh justify-center px-4 pt-4 pb-10 sm:pt-8">
      <div className="flex w-full max-w-[640px] flex-col">
        <div className="flex items-center justify-between">
          <Link to="/" className="py-2.5 text-[15px] text-accent-texte">Annuler</Link>
          <Logo taille={28} />
          <span className="w-[60px] text-right text-[13px] text-texte-2">{etape + 1} sur {ETAPES.length}</span>
        </div>

        <ol aria-label="Étapes" className="mt-4 flex gap-1.5">
          {ETAPES.map((nom, i) => (
            <li key={nom} className="flex-1" aria-current={i === etape ? "step" : undefined}>
              <span className={`block h-1 rounded-full transition-colors duration-300 ease-ios ${i <= etape ? "bg-accent" : "bg-piste"}`} />
              <span className="sr-only">{nom}{i < etape ? " (fait)" : ""}</span>
            </li>
          ))}
        </ol>

        <form onSubmit={(e) => { e.preventDefault(); suivant(); }} className="mt-7 flex flex-col gap-7" noValidate>
          <div className="flex flex-col gap-1.5 px-1">
            <span className="text-[13px] font-semibold text-texte-2">Nouveau projet d'homologation</span>
            <h1 ref={titre} tabIndex={-1} className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] outline-none">
              {ETAPES[etape]}
            </h1>
          </div>

          {etape === 0 && <EtapeBien p={p} maj={maj} />}
          {etape === 1 && <EtapeReferentiels p={p} maj={maj} />}
          {etape === 2 && <EtapeNiveau p={p} maj={maj} />}
          {etape === 4 && <EtapeRecap p={p} acteurs={acteurs} maj={maj} />}
          {etape !== 3 && <BarreActions etape={etape} setEtape={setEtape} valide={valide} derniere={derniere} enCours={creer.isPending} />}
        </form>

        {/* Étape acteurs hors du formulaire principal : elle contient son propre formulaire d'ajout. */}
        {etape === 3 && (
          <div className="mt-7 flex flex-col gap-7">
            <EtapeActeurs acteurs={acteurs} setActeurs={setActeurs} />
            <form onSubmit={(e) => { e.preventDefault(); suivant(); }}>
              <BarreActions etape={etape} setEtape={setEtape} valide derniere={false} enCours={false} />
            </form>
          </div>
        )}

        {creer.error && (
          <p role="alert" className="mt-4 rounded-groupe bg-groupe px-4 py-3 text-sm font-medium text-manquant-texte shadow-groupe">
            {creer.error.message}
          </p>
        )}
      </div>
    </div>
  );
}

function BarreActions({ etape, setEtape, valide, derniere, enCours }: {
  etape: number; setEtape: (e: number) => void; valide: boolean; derniere: boolean; enCours: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3 pt-2">
      {etape > 0 ? (
        <button type="button" onClick={() => setEtape(etape - 1)} className="h-[50px] rounded-full px-4 text-[15px] font-medium text-accent-texte">
          Retour
        </button>
      ) : <span />}
      <button type="submit" disabled={!valide || enCours}
        className="bouton-accent h-[50px] min-w-[180px] rounded-full px-6 text-[15px] font-semibold disabled:opacity-45">
        {derniere ? (enCours ? "Création…" : "Créer le projet") : "Continuer"}
      </button>
    </div>
  );
}
