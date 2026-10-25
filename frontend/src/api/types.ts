export type StatutConformite = "conforme" | "partiel" | "manquant" | "non_applicable" | "non_evalue";
export type Couverture = "couvert" | "partiel" | "absent";

export interface Moi {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  nom_complet: string;
  fonction: string;
  role: { code: string; libelle: string; lecture_seule: boolean } | null;
  organisation: { id: string; nom: string; ia_activee: boolean };
  est_admin: boolean;
  lecture_seule: boolean;
}

export interface Pagine<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ProjetResume {
  id: string;
  nom: string;
  statut: string;
  type_bien: string;
  niveau_vise: string;
}

export interface ReferentielTdb {
  id: string;
  code: string;
  nom: string;
  version: string;
  total: number;
  statuts: Record<StatutConformite, number>;
  nouvelle_version: boolean;
}

export interface ElementPourVous {
  type: "tache" | "document" | "validation_ia";
  id: string | null;
  titre: string;
  detail: string;
  echeance: string | null;
  en_retard: boolean;
}

export interface TableauDeBord {
  projet: {
    id: string;
    nom: string;
    statut: string;
    statut_libelle: string;
    type_bien_libelle: string;
    niveau_vise_libelle: string;
    ebios_active: boolean;
    date_prochaine_revue: string | null;
    lecture_seule: boolean;
    peut_decider: boolean;
  };
  referentiels: ReferentielTdb[];
  evaluation: { evaluees: number; total: number };
  conformite: { conformes: number; applicables: number };
  documents: { attendus: number; deposes: number; valides: number };
  taches: { ouvertes: number; en_retard: number };
  echeances: { prochain_document: { intitule: string; echeance: string } | null; decision: string | null };
  pour_vous: ElementPourVous[];
  a_valider: {
    analyse: string;
    date: string;
    documents: string[];
    total: number;
    conclusions: { id: string; mesure: string; intitule: string; couverture: Couverture }[];
  } | null;
  activite: EntreeActivite[];
}

export interface EntreeActivite {
  id: number;
  horodatage: string;
  acteur: string;
  action: string;
  objet_type: string;
  objet: string;
  champs: string[];
  nb_checklist: number;
}

export interface Referentiel {
  id: string;
  code: string;
  nom: string;
  version: string;
  editeur: string;
  licence: string;
  prive: boolean;
  nb_mesures: number;
  nouvelle_version: string | null;
}

export interface Utilisateur {
  id: string;
  email: string;
  nom_complet: string;
  fonction: string;
  is_active: boolean;
}

export interface Role {
  id: string;
  code: string;
  libelle: string;
  portee: "organisation" | "projet";
  lecture_seule: boolean;
}

export type TypeBien = "application" | "poste_travail" | "si" | "autre";
export type NiveauVise = "elementaire" | "standard" | "renforce";

export interface ActeurInitial {
  utilisateur?: string;
  nom?: string;
  email?: string;
  organisme?: string;
  role: string;
}

export interface NouveauProjet {
  nom: string;
  description: string;
  type_bien: TypeBien;
  niveau_vise: NiveauVise;
  ebios_active: boolean;
  referentiels: string[];
  acteurs: ActeurInitial[];
  generer_checklist: boolean;
}

export type StatutDocument = "attendu" | "depose" | "valide" | "refuse" | "non_applicable";

export interface DocumentAttendu {
  id: string;
  projet: string;
  intitule: string;
  description: string;
  type_document: string;
  mesures_couvertes: { id: string; identifiant: string; intitule: string; referentiel: string }[];
  responsable: string | null;
  responsable_nom: string;
  responsable_role: string;
  echeance: string | null;
  statut: StatutDocument;
  obligatoire: boolean;
  origine: "generee" | "manuelle";
  nb_versions: number;
}

export interface DocumentDepose {
  id: string;
  projet: string;
  document_attendu: string | null;
  version: number;
  nom_original: string;
  type_mime: string;
  taille: number;
  sha256: string;
  depose_par: string;
  depose_par_nom: string;
  depose_le: string;
  commentaire: string;
}

export interface Mesure {
  id: string;
  referentiel: string;
  identifiant: string;
  intitule: string;
  categorie: string;
  niveaux: string[];
  texte_officiel: string | null;
  ordre: number;
}

export interface EvaluationMesure {
  id: string;
  projet: string;
  mesure: string;
  statut: StatutConformite;
  justification: string;
  resultat_analyse: string | null;
  evalue_par: string | null;
  evalue_par_nom: string;
  evalue_le: string | null;
}

export interface Preuve {
  id: string;
  projet: string;
  serie: string;
  version: number;
  titre: string;
  description: string;
  mesures: string[];
  nom_original: string;
  type_mime: string;
  taille: number;
  sha256: string;
  depose_par_nom: string;
  depose_le: string;
}

export interface ResultatIA {
  id: string;
  mesure: string;
  mesure_identifiant: string;
  document_nom: string;
  couverture: Couverture;
  justification: string;
  statut_validation: "a_valider" | "valide" | "rejete";
  valide_par_nom: string;
  valide_le: string | null;
}
