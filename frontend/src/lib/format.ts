import type { EntreeActivite } from "../api/types";

const jourMois = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });
const jourMoisAnnee = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric" });
const heure = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" });
const relatif = new Intl.RelativeTimeFormat("fr-FR", { numeric: "auto" });

function enDate(valeur: string): Date {
  // « 2026-11-01 » est une date sans heure : on la lit en heure locale, pas en UTC.
  return /^\d{4}-\d{2}-\d{2}$/.test(valeur) ? new Date(`${valeur}T00:00:00`) : new Date(valeur);
}

/** « 1er nov. », « 24 nov. », avec l'année si elle diffère de l'année en cours. */
export function dateCourte(valeur: string | null | undefined): string {
  if (!valeur) return "—";
  const d = enDate(valeur);
  const texte = (d.getFullYear() === new Date().getFullYear() ? jourMois : jourMoisAnnee).format(d);
  return d.getDate() === 1 ? texte.replace(/^1 /, "1er ") : texte;
}

export function echeance(valeur: string | null, enRetard: boolean): string {
  if (!valeur) return "Sans échéance";
  const aujourdHui = new Date();
  aujourdHui.setHours(0, 0, 0, 0);
  const jours = Math.round((enDate(valeur).getTime() - aujourdHui.getTime()) / 86_400_000);
  if (enRetard) return `En retard · ${dateCourte(valeur)}`;
  if (jours === 0) return "Aujourd’hui";
  if (jours === 1) return "Demain";
  return dateCourte(valeur);
}

export function quand(valeur: string): string {
  const d = new Date(valeur);
  const minutes = Math.round((d.getTime() - Date.now()) / 60_000);
  if (minutes > -60) return relatif.format(Math.min(minutes, 0), "minute");
  if (minutes > -60 * 12) return relatif.format(Math.round(minutes / 60), "hour");
  const hier = new Date();
  hier.setDate(hier.getDate() - 1);
  if (d.toDateString() === hier.toDateString()) return `Hier à ${heure.format(d)}`;
  return `${dateCourte(valeur)} à ${heure.format(d)}`;
}

export function pourcentage(part: number, total: number): string {
  return total ? `${Math.round((part / total) * 100)} %` : "—";
}

const OBJETS: Record<string, string> = {
  "documents.DocumentDepose": "le document",
  "projets.DocumentAttendu": "le document attendu",
  "projets.StatutMesure": "l'évaluation de",
  "projets.ActeurProjet": "l'acteur",
  "projets.Projet": "le projet",
  "projets.ProjetReferentiel": "le référentiel",
  "suivi.Tache": "la tâche",
};

/** Phrase lisible pour une entrée du journal d'audit. */
export function phraseActivite(e: EntreeActivite): string {
  const objet = `${OBJETS[e.objet_type] ?? ""} « ${e.objet} »`.trim();
  if (e.nb_checklist) return `${e.acteur} a généré la checklist : ${e.nb_checklist} documents attendus.`;
  switch (e.action) {
    case "creation":
      return e.objet_type === "documents.DocumentDepose"
        ? `${e.acteur} a déposé « ${e.objet} ».`
        : `${e.acteur} a créé ${objet}.`;
    case "modification":
      return `${e.acteur} a modifié ${objet}.`;
    case "suppression":
      return `${e.acteur} a retiré ${objet}.`;
    case "telechargement":
      return `${e.acteur} a téléchargé « ${e.objet} ».`;
    case "validation_ia":
      return `${e.acteur} a statué sur une conclusion de l'IA.`;
    case "decision":
      return `${e.acteur} a enregistré une décision : ${e.objet}.`;
    default:
      return `${e.acteur} : ${e.objet}`;
  }
}
