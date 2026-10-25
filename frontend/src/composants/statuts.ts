import type { Couverture, StatutConformite } from "../api/types";

/** Ordre d'affichage et classes du thème pour chaque statut (libellé toujours affiché à côté de la couleur). */
export const STATUTS: { cle: StatutConformite; libelle: string; pluriel: string; fond: string; legende: string }[] = [
  { cle: "conforme", libelle: "Conforme", pluriel: "conformes", fond: "bg-conforme", legende: "bg-conforme" },
  { cle: "partiel", libelle: "Partiel", pluriel: "partielles", fond: "bg-partiel", legende: "bg-partiel" },
  { cle: "manquant", libelle: "Manquant", pluriel: "manquantes", fond: "bg-manquant", legende: "bg-manquant" },
  { cle: "non_applicable", libelle: "Non applicable", pluriel: "non applicables", fond: "bg-na", legende: "bg-na" },
  { cle: "non_evalue", libelle: "Non évaluée", pluriel: "non évaluées", fond: "bg-non-evalue", legende: "bg-non-evalue-legende" },
];

export const COUVERTURE: Record<Couverture, { libelle: string; texte: string; point: string }> = {
  couvert: { libelle: "Couvert", texte: "text-conforme-texte", point: "bg-conforme" },
  partiel: { libelle: "Partiel", texte: "text-partiel-texte", point: "bg-partiel" },
  absent: { libelle: "Absent", texte: "text-manquant-texte", point: "bg-manquant" },
};

const NOMS_COURTS: Record<string, string> = {
  rgs: "RGS",
  "hygiene-anssi": "Hygiène ANSSI",
  "owasp-asvs": "OWASP ASVS",
  "nist-csf": "NIST CSF",
  ii901: "II 901",
  iso27001: "ISO 27001",
};

/** Nom court pour les légendes ; le nom complet reste dans les libellés accessibles. */
export function nomCourt(r: { code: string; nom: string; version: string }) {
  return NOMS_COURTS[r.code] ? `${NOMS_COURTS[r.code]} ${r.version}` : r.nom;
}
