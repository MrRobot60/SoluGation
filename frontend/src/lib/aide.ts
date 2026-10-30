// Léger (sans la documentation ni marked) : utilisé par la barre de navigation sur toutes les pages.

/** Texte brut d'un titre ou d'un paragraphe Markdown (balises, liens et emphase retirés). */
export function brut(md: string) {
  return md.replace(/<[^>]+>/g, "").replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/[*`]/g, "").trim();
}

/** Ancre au format GitHub, pour que les liens `page.md#section` marchent sur GitHub et dans l'appli. */
export function slug(titre: string) {
  return brut(titre).toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu, "").replace(/\s/g, "-");
}

// Aide contextuelle : rubrique de l'appli → section du guide de l'utilisateur (titres de docs/06-guide-utilisateur.md).
const SECTIONS_GUIDE: Record<string, string> = {
  "": "Tableau de bord", mesures: "Mesures", documents: "Documents", "plan-action": "Plan d'action", scans: "Scans de vulnérabilités",
  risques: "Risques et dérogations", ebios: "EBIOS RM", reunions: "Réunions", rapports: "Rapports", journal: "Journal d'audit",
  reglages: "Réglages du projet", bibliotheque: "Bibliothèque", administration: "Administration", nouveau: "Créer un projet",
  compte: "Mon compte",
};

export function lienAide(chemin: string) {
  const [, racine, , rubrique = ""] = chemin.split("/");
  const cle = racine === "projets" ? (chemin === "/projets/nouveau" ? "nouveau" : rubrique) : racine;
  const titre = SECTIONS_GUIDE[cle];
  return titre ? `/aide/06-guide-utilisateur#${slug(titre)}` : "/aide";
}
