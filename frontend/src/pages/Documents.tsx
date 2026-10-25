import { useEffect, useId, useRef, useState, type DragEvent, type ReactNode } from "react";
import { useParams } from "react-router";

import { useDeposer, useDepots, useDocumentsAttendus, useStatutDocument, useTableauDeBord } from "../api/hooks";
import type { DocumentAttendu, DocumentDepose, StatutDocument } from "../api/types";
import { Disposition } from "../composants/Disposition";
import { Chevron, IconeCoche, IconeCroix, IconeDepot, IconeDocument } from "../composants/Icones";
import { echeance, quand } from "../lib/format";

/* Liste blanche côté client (confort) ; le serveur contrôle le contenu réel du fichier. */
const EXTENSIONS = [".pdf", ".docx", ".xlsx", ".odt", ".ods", ".txt", ".csv", ".xml", ".nessus", ".png", ".jpg", ".jpeg"];
const TAILLE_MAX = 50 * 1024 * 1024;

const STATUTS: Record<StatutDocument, { libelle: string; texte: string; point: string }> = {
  attendu: { libelle: "À déposer", texte: "text-texte-2", point: "border-[1.5px] border-texte-3" },
  depose: { libelle: "En relecture", texte: "text-accent-texte", point: "bg-accent" },
  valide: { libelle: "Validé", texte: "text-conforme-texte", point: "bg-conforme" },
  refuse: { libelle: "Refusé", texte: "text-manquant-texte", point: "bg-manquant" },
  non_applicable: { libelle: "Non applicable", texte: "text-na-texte", point: "bg-na" },
};

const FILTRES: { cle: string; libelle: string; garde: (d: DocumentAttendu) => boolean }[] = [
  { cle: "tous", libelle: "Tous", garde: () => true },
  { cle: "a-deposer", libelle: "À déposer", garde: (d) => d.statut === "attendu" || d.statut === "refuse" },
  { cle: "relecture", libelle: "En relecture", garde: (d) => d.statut === "depose" },
  { cle: "valides", libelle: "Validés", garde: (d) => d.statut === "valide" || d.statut === "non_applicable" },
];

function taille(octets: number) {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`;
  return `${(octets / 1024 / 1024).toFixed(1).replace(".", ",")} Mo`;
}

function erreurClient(fichier: File): string | null {
  const ext = fichier.name.includes(".") ? fichier.name.slice(fichier.name.lastIndexOf(".")).toLowerCase() : "";
  if (!EXTENSIONS.includes(ext)) return `Format non accepté (${ext || "sans extension"}).`;
  if (fichier.size > TAILLE_MAX) return "Fichier trop volumineux (50 Mo maximum).";
  if (fichier.size === 0) return "Fichier vide.";
  return null;
}

function enRetard(d: DocumentAttendu) {
  if (!d.echeance || !["attendu", "refuse"].includes(d.statut)) return false;
  return new Date(`${d.echeance}T23:59:59`) < new Date();
}

/** État d'un dépôt en cours, par cible (id du document attendu, ou « libre »). */
type Envoi = { progression: number; erreur?: string; nom: string };

function useEnvois(projetId: string) {
  const deposer = useDeposer(projetId);
  const [envois, setEnvois] = useState<Record<string, Envoi>>({});
  const envoyer = (fichier: File, cible?: string) => {
    const cle = cible ?? "libre";
    const erreur = erreurClient(fichier);
    if (erreur) return setEnvois((e) => ({ ...e, [cle]: { progression: 0, erreur, nom: fichier.name } }));
    setEnvois((e) => ({ ...e, [cle]: { progression: 0, nom: fichier.name } }));
    deposer.mutate(
      { fichier, documentAttendu: cible, surProgression: (p) => setEnvois((e) => ({ ...e, [cle]: { ...e[cle], progression: p } })) },
      {
        onSuccess: () => setEnvois(({ [cle]: _, ...reste }) => reste),
        onError: (err) => setEnvois((e) => ({ ...e, [cle]: { progression: 0, erreur: err.message, nom: fichier.name } })),
      },
    );
  };
  const oublier = (cle: string) => setEnvois(({ [cle]: _, ...reste }) => reste);
  return { envois, envoyer, oublier };
}

/* ---- Zone de dépôt ----------------------------------------------------------------------- */

function ZoneDepot({ surFichier, libelle, compacte = false, desactivee = false }: {
  surFichier: (f: File) => void; libelle: string; compacte?: boolean; desactivee?: boolean;
}) {
  const champ = useRef<HTMLInputElement>(null);
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
      <input id={id} ref={champ} type="file" className="sr-only" accept={EXTENSIONS.join(",")}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) surFichier(f); e.target.value = ""; }} />
    </div>
  );
}

function Progression({ envoi, surFermer }: { envoi: Envoi; surFermer: () => void }) {
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

/* ---- Versions ---------------------------------------------------------------------------- */

function ListeVersions({ versions }: { versions: DocumentDepose[] }) {
  if (versions.length === 0) return <p className="text-sm text-texte-2">Aucune version déposée.</p>;
  return (
    <ol className="flex flex-col">
      {versions.map((v, i) => (
        <li key={v.id} className={`flex items-center gap-3 py-2.5 ${i > 0 ? "border-t border-separateur" : ""}`}>
          <span className="w-9 shrink-0 text-[13px] font-semibold text-texte-2">v{v.version}</span>
          <span className="flex min-w-0 flex-1 flex-col gap-px">
            <span className="truncate text-sm font-medium">{v.nom_original}</span>
            <span className="text-xs text-texte-2">
              {taille(v.taille)} · {v.depose_par_nom} · {quand(v.depose_le)}
            </span>
            <span className="truncate font-mono text-[11px] text-texte-3" title={`SHA-256 : ${v.sha256}`}>SHA-256 {v.sha256.slice(0, 16)}…</span>
          </span>
          <a href={`/api/documents-deposes/${v.id}/telecharger/`} download
            className="shrink-0 rounded-full bg-accent-doux px-3.5 py-2 text-[13px] font-semibold text-accent-texte">
            Télécharger
          </a>
        </li>
      ))}
    </ol>
  );
}

/* ---- Ligne de la checklist ---------------------------------------------------------------- */

function LigneDocument({ d, versions, ouvert, basculer, envoi, envoyer, oublier, lectureSeule, projetId }: {
  d: DocumentAttendu; versions: DocumentDepose[]; ouvert: boolean; basculer: () => void; envoi?: Envoi;
  envoyer: (f: File, cible?: string) => void; oublier: (cle: string) => void; lectureSeule: boolean; projetId: string;
}) {
  const [survol, setSurvol] = useState(false);
  const statut = useStatutDocument(projetId);
  const s = STATUTS[d.statut];
  const retard = enRetard(d);
  const idDetail = `detail-${d.id}`;
  const deposerIci = (e: DragEvent) => {
    e.preventDefault();
    setSurvol(false);
    const f = e.dataTransfer.files[0];
    if (f && !lectureSeule) envoyer(f, d.id);
  };

  return (
    <li
      onDragOver={(e) => { if (!lectureSeule) { e.preventDefault(); setSurvol(true); } }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setSurvol(false); }}
      onDrop={deposerIci}
      className={`relative transition-colors duration-200 ease-ios ${survol ? "bg-accent-doux" : ""}`}
    >
      <button type="button" onClick={basculer} aria-expanded={ouvert} aria-controls={idDetail}
        className="flex min-h-[64px] w-full items-center gap-3.5 px-4 py-2.5 text-left hover:bg-remplissage">
        <span aria-hidden="true" className={`size-2.5 shrink-0 rounded-full ${s.point}`} />
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="text-[15px] leading-snug font-medium">
            {d.intitule}
            {!d.obligatoire && <span className="text-texte-2"> · facultatif</span>}
          </span>
          <span className="text-[13px] leading-snug text-texte-2">
            {d.responsable_nom ? `${d.responsable_nom}${d.responsable_role ? ` · ${d.responsable_role}` : ""}` : "Sans responsable"}
            {" · "}
            <span className={retard ? "font-semibold text-manquant-texte" : ""}>{echeance(d.echeance, retard)}</span>
          </span>
          {/* Mobile : le statut est écrit, jamais porté par la seule couleur du point. */}
          <span className={`text-[13px] font-semibold sm:hidden ${s.texte}`}>
            {s.libelle}{d.nb_versions > 0 ? ` · ${d.nb_versions} version${d.nb_versions > 1 ? "s" : ""}` : ""}
          </span>
        </span>
        <span className="hidden flex-col items-end gap-0.5 sm:flex">
          <span className={`text-[13px] font-semibold whitespace-nowrap ${s.texte}`}>{s.libelle}</span>
          {d.nb_versions > 0 && <span className="text-xs text-texte-2">{d.nb_versions} version{d.nb_versions > 1 ? "s" : ""}</span>}
        </span>
        <span className={`transition-transform duration-200 ease-ios ${ouvert ? "rotate-90" : ""}`}><Chevron /></span>
      </button>
      {survol && (
        <div aria-hidden="true" className="pointer-events-none absolute inset-1 flex items-center justify-center rounded-2xl border-[1.5px] border-dashed border-accent-texte text-sm font-semibold text-accent-texte">
          Déposer comme version {d.nb_versions + 1}
        </div>
      )}
      {envoi && <div className="px-4 pb-3 pl-10"><Progression envoi={envoi} surFermer={() => oublier(d.id)} /></div>}

      {ouvert && (
        <div id={idDetail} className="flex flex-col gap-5 border-t border-separateur px-4 pt-4 pb-5 sm:pl-10">
          {d.description && <p className="text-sm leading-relaxed text-texte-2">{d.description}</p>}
          {d.mesures_couvertes.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-texte-2">Mesures couvertes</span>
              <ul className="flex flex-wrap gap-1.5">
                {d.mesures_couvertes.map((m) => (
                  <li key={m.id} title={m.intitule} className="rounded-full bg-remplissage px-2.5 py-1 text-xs font-medium">
                    {m.identifiant}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold text-texte-2">Versions</span>
            <ListeVersions versions={versions} />
          </div>
          <ZoneDepot compacte desactivee={lectureSeule} surFichier={(f) => envoyer(f, d.id)}
            libelle={d.nb_versions ? `Nouvelle version (v${d.nb_versions + 1}) : glissez un fichier ici ou` : "Glissez un fichier ici ou"} />
          {!lectureSeule && (
            <div className="flex flex-wrap gap-2">
              {d.statut === "depose" && (
                <>
                  <ActionStatut onClick={() => statut.mutate({ id: d.id, statut: "valide" })} principal>
                    <IconeCoche taille={15} /> Valider la version {versions[0]?.version}
                  </ActionStatut>
                  <ActionStatut onClick={() => statut.mutate({ id: d.id, statut: "refuse" })}>Refuser</ActionStatut>
                </>
              )}
              {d.statut === "valide" && <ActionStatut onClick={() => statut.mutate({ id: d.id, statut: "depose" })}>Remettre en relecture</ActionStatut>}
              {d.statut === "attendu" && !d.obligatoire && <ActionStatut onClick={() => statut.mutate({ id: d.id, statut: "non_applicable" })}>Non applicable</ActionStatut>}
              {d.statut === "non_applicable" && <ActionStatut onClick={() => statut.mutate({ id: d.id, statut: "attendu" })}>Rétablir</ActionStatut>}
            </div>
          )}
          {statut.error && <p role="alert" className="text-[13px] font-medium text-manquant-texte">{statut.error.message}</p>}
        </div>
      )}
    </li>
  );
}

function ActionStatut({ children, onClick, principal }: { children: ReactNode; onClick: () => void; principal?: boolean }) {
  return (
    <button type="button" onClick={onClick}
      className={`flex h-10 items-center gap-1.5 rounded-full px-4 text-[14px] font-semibold ${principal ? "bouton-accent" : "bg-remplissage"}`}>
      {children}
    </button>
  );
}

/* ---- Page --------------------------------------------------------------------------------- */

export function PageDocuments() {
  const { projetId = "" } = useParams();
  const { data: tdb } = useTableauDeBord(projetId);
  const { data: attendus = [], isPending } = useDocumentsAttendus(projetId);
  const { data: depots = [] } = useDepots(projetId);
  const { envois, envoyer, oublier } = useEnvois(projetId);
  const [filtre, setFiltre] = useState("tous");
  const [ouvert, setOuvert] = useState<string | null>(null);
  const lectureSeule = tdb?.projet.lecture_seule ?? true;

  // Un fichier lâché hors d'une zone prévue ne doit pas être ouvert par le navigateur.
  useEffect(() => {
    const bloquer = (e: Event) => e.preventDefault();
    window.addEventListener("dragover", bloquer);
    window.addEventListener("drop", bloquer);
    return () => {
      window.removeEventListener("dragover", bloquer);
      window.removeEventListener("drop", bloquer);
    };
  }, []);

  const versionsDe = (id: string | null) =>
    depots.filter((v) => v.document_attendu === id).sort((a, b) => b.version - a.version || b.depose_le.localeCompare(a.depose_le));
  const visibles = attendus.filter(FILTRES.find((f) => f.cle === filtre)!.garde);
  const deposes = attendus.filter((d) => d.nb_versions > 0 || d.statut === "valide").length;
  const valides = attendus.filter((d) => d.statut === "valide").length;
  const retards = attendus.filter(enRetard).length;
  const libres = versionsDe(null);

  return (
    <Disposition>
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-end justify-between gap-4 lg:pt-2.5">
          <div className="flex flex-col gap-1.5">
            <span className="text-[13px] font-semibold text-texte-2">{tdb?.projet.nom ?? "Projet"}</span>
            <h1 className="text-[34px] leading-[1.06] font-bold tracking-[-0.03em] lg:text-[44px]">Documents</h1>
            <p className="text-[15px] text-texte-2">
              {deposes} sur {attendus.length} déposés · {valides} validés
              {retards > 0 && <span className="font-semibold text-manquant-texte"> · {retards} en retard</span>}
            </p>
          </div>
        </div>

        <div role="radiogroup" aria-label="Filtrer les documents" className="flex self-start overflow-x-auto rounded-full bg-remplissage p-[3px]">
          {FILTRES.map((f) => {
            const n = attendus.filter(f.garde).length;
            return (
              <button key={f.cle} type="button" role="radio" aria-checked={filtre === f.cle} onClick={() => setFiltre(f.cle)}
                className={`rounded-full px-3.5 py-1.5 text-[13px] whitespace-nowrap transition-colors duration-200 ease-ios ${filtre === f.cle ? "bg-groupe font-semibold shadow-groupe" : "font-medium text-texte-2"}`}>
                {f.libelle} <span className="text-texte-2">{n}</span>
              </button>
            );
          })}
        </div>

        <section aria-label="Checklist des documents attendus">
          {isPending ? (
            <div aria-busy="true" className="h-72 animate-pulse rounded-groupe bg-remplissage" />
          ) : visibles.length === 0 ? (
            <p className="rounded-groupe bg-groupe px-4 py-6 text-center text-[15px] text-texte-2 shadow-groupe">
              {attendus.length === 0 ? "Aucun document attendu : générez la checklist depuis la création du projet." : "Aucun document dans ce filtre."}
            </p>
          ) : (
            <ul className="divide-y divide-separateur overflow-hidden rounded-groupe bg-groupe shadow-groupe">
              {visibles.map((d) => (
                <LigneDocument key={d.id} d={d} versions={versionsDe(d.id)} ouvert={ouvert === d.id}
                  basculer={() => setOuvert(ouvert === d.id ? null : d.id)} envoi={envois[d.id]}
                  envoyer={envoyer} oublier={oublier} lectureSeule={lectureSeule} projetId={projetId} />
              ))}
            </ul>
          )}
          {!lectureSeule && attendus.length > 0 && (
            <p className="mt-2 px-1 text-[13px] text-texte-2">Glissez un fichier sur une ligne pour en déposer une nouvelle version.</p>
          )}
        </section>

        <section aria-labelledby="titre-autres" className="flex flex-col gap-2.5">
          <div className="flex items-baseline justify-between px-1">
            <h2 id="titre-autres" className="flex items-center gap-2 text-[22px] font-bold tracking-[-0.025em]">
              <IconeDocument taille={20} className="text-texte-2" /> Autres pièces
            </h2>
            <span className="text-[13px] text-texte-2">hors checklist</span>
          </div>
          <div className="flex flex-col gap-4 rounded-groupe bg-groupe px-4 py-4 shadow-groupe">
            {libres.length > 0 && <ListeVersions versions={libres} />}
            {envois.libre && <Progression envoi={envois.libre} surFermer={() => oublier("libre")} />}
            <ZoneDepot desactivee={lectureSeule} surFichier={(f) => envoyer(f)}
              libelle="Glissez ici une pièce qui ne correspond à aucun document attendu, ou" />
            {lectureSeule && libres.length === 0 && <p className="text-sm text-texte-2">Aucune pièce.</p>}
          </div>
          <p className="px-1 text-xs text-texte-3">
            PDF, Word, Excel, OpenDocument, texte, CSV, XML (rapports de scan), PNG ou JPEG, 50 Mo maximum.
            Chaque fichier est contrôlé, horodaté et empreinté (SHA-256) ; une version déposée n'est jamais modifiée.
          </p>
        </section>
      </div>
    </Disposition>
  );
}
