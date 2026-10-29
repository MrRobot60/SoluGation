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
  est_admin_instance: boolean;
  lecture_seule: boolean;
  ia_disponible: boolean;
  visite_terminee: boolean;
}

export interface EtatIA {
  source: "ecran" | "fichier" | "aucune";
  disponible: boolean;
  ecran: {
    actif: boolean; nom: string; url: string; modele: string; a_une_cle: boolean; cle_fin: string;
    responsabilite_acceptee_par: string; responsabilite_acceptee_le: string | null; modifie_par: string; modifie_le: string | null;
  };
  fichier: { fournisseur: string; nom: string; url: string; modele: string };
  reseau_local_autorise: boolean;
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
  type: "tache" | "document" | "validation_ia" | "decision" | "reunion";
  lien?: string;
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
    peut_administrer: boolean;
    peut_prononcer: boolean;
    archive: boolean;
    exemple: boolean;
    decision: "" | "homologation" | "provisoire" | "refus";
    decision_libelle: string;
    decision_par: string;
    date_decision: string | null;
    date_fin_validite: string | null;
    periodicite_revue_mois: number;
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
  url_source: string;
  licence: string;
  licence_libelle: string;
  texte_embarque: boolean;
  date_publication: string | null;
  date_import: string | null;
  empreinte_source: string;
  prive: boolean;
  nb_mesures: number;
  nb_projets: number;
  nouvelle_version: string | null;
  nouvelle_version_libelle: string;
}

export interface FicheMesure extends Mesure {
  correspondances: { id: string; type: string; type_libelle: string; sens: "entrante" | "sortante"; origine: string; reference: string;
    modifiable: boolean; mesure: Mesure }[];
  projets: { projet: string; projet_nom: string; statut: StatutConformite; statut_libelle: string }[];
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
  referentiel_code?: string;
  referentiel_nom?: string;
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
  mesure_identifiant: string;
  mesure_intitule: string;
  referentiel_code: string;
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
  analyse: string;
  fournisseur: string;
  mesure: string;
  mesure_identifiant: string;
  mesure_intitule: string;
  referentiel_code: string;
  document: string | null;
  document_nom: string;
  couverture: Couverture;
  justification: string;
  extraits: { page: number | null; texte: string }[];
  confiance: string | null;
  cree_le: string;
  statut_validation: "a_valider" | "valide" | "rejete";
  valide_par_nom: string;
  valide_le: string | null;
}

export type EtatAnalyse = "en_attente" | "en_cours" | "terminee" | "echec";

export type TypeAnalyse = "analyse_documentaire" | "recommandation" | "suggestion_ebios";

export interface RecommandationIA {
  id: string;
  analyse: string;
  fournisseur: string;
  tache: string | null;
  mesure: string | null;
  mesure_identifiant: string;
  texte: string;
  etapes: string[];
  preuve_suggeree: string;
  effort: "" | "faible" | "moyen" | "eleve";
  statut_validation: "a_valider" | "valide" | "rejete";
  valide_par_nom: string;
  valide_le: string | null;
  cree_le: string;
}

export interface AnalyseIA {
  id: string;
  projet: string;
  type_analyse: TypeAnalyse;
  etat: EtatAnalyse;
  fournisseur: string;
  modele: string;
  erreur: string;
  demandee_par_nom: string;
  debut_le: string | null;
  fin_le: string | null;
  cree_le: string;
  nb_resultats: number;
  nb_a_valider: number;
  documents_analyses: { id: string; nom: string; analyse: boolean; raison?: string; tronque?: boolean; mesures?: number; conclusions?: number }[];
}

export type StatutTache = "a_faire" | "en_cours" | "en_revue" | "terminee" | "abandonnee";
export type PrioriteTache = "basse" | "moyenne" | "haute" | "critique";

export interface Tache {
  id: string;
  projet: string;
  titre: string;
  description: string;
  mesure: string | null;
  mesure_identifiant: string;
  mesure_intitule: string;
  referentiel_code: string;
  responsable: string | null;
  responsable_nom: string;
  responsable_utilisateur: string | null;
  echeance: string | null;
  preuve_attendue: string;
  statut: StatutTache;
  priorite: PrioriteTache;
  origine: "evaluation" | "analyse_ia" | "scan" | "ebios" | "manuelle";
  cloturee_par_nom: string;
  cloturee_le: string | null;
  nb_commentaires: number;
  en_retard: boolean;
  cree_le: string;
}

export interface Acteur {
  id: string;
  utilisateur: string | null;
  nom: string;
  email: string;
  organisme: string;
  role: string;
  affichage: string;
  role_libelle: string;
  role_code: string;
}

export interface Projet {
  id: string;
  nom: string;
  description: string;
  type_bien: TypeBien;
  niveau_vise: NiveauVise;
  statut: string;
  referentiels: string[];
  ebios_active: boolean;
  notifications_actives: boolean;
  calendrier_actif: boolean;
  periodicite_revue_mois: number;
  date_prochaine_revue: string | null;
}

export interface Commentaire {
  id: string;
  texte: string;
  auteur: string;
  auteur_nom: string;
  cree_le: string;
}

export interface EntreeJournal {
  id: number;
  horodatage: string;
  acteur_repr: string;
  action: string;
  objet_type: string;
  donnees: Record<string, unknown>;
  action_libelle?: string;
  objet_libelle?: string;
  objet_repr?: string;
  projet?: string | null;
  projet_nom?: string;
  adresse_ip?: string | null;
  hash?: string;
  hash_precedent?: string;
}

export interface NotificationApp {
  id: string;
  projet: string | null;
  type_evenement: string;
  titre: string;
  message: string;
  lien: string;
  lue_le: string | null;
  cree_le: string;
}

export interface SectionRapport {
  cle: string;
  titre: string;
  texte: string;
  source: "ia" | "automatique" | "modifie";
  alertes: string[];
}

export interface Rapport {
  id: string;
  projet: string;
  version: number;
  titre: string;
  sections: SectionRapport[];
  statut_validation: "a_valider" | "valide" | "rejete";
  valide_par_nom: string;
  valide_le: string | null;
  genere_par_nom: string;
  cree_le: string;
  modifie_le: string;
  pdf_genere_le: string | null;
  sha256_pdf: string;
  rapport_precedent: string | null;
  redaction: { etat: EtatAnalyse | "sans_ia"; erreur: string; fournisseur: string; modele: string };
  chiffres: {
    conformite: Record<StatutConformite | "total", number>;
    nb_manquements: number;
    taches_ouvertes: number;
    documents_valides: number;
    documents_total: number;
    evolution: { conforme: number; manquant: number; partiel: number; non_evalue: number; taches_ouvertes: number; documents_valides: number } | null;
  };
  avertissement?: string;
}

/** Objet EBIOS RM générique (les champs dépendent de la ressource). */
export type ObjetEbios = { id: string; projet: string; [champ: string]: unknown };

export interface SyntheseEbios {
  ateliers: { numero: number; libelle: string; statut: "non_commence" | "en_cours" | "termine"; date_atelier: string | null; id: string }[];
  comptes: Record<string, number>;
  alertes: { atelier: number; texte: string }[];
  matrice: { initiale: Record<string, { id: string; intitule: string }[]>; residuelle: Record<string, { id: string; intitule: string }[]> };
  cartographie: {
    seuils: { danger: number; controle: number };
    parties: { id: string; nom: string; categorie: string; niveau_menace: number; zone: "danger" | "controle" | "veille"; critique: boolean }[];
  };
}

export interface SuggestionEbios {
  id: string;
  analyse: string;
  fournisseur: string;
  atelier: number;
  type_objet: "evenement_redoute" | "bien_support" | "couple" | "scenario_strategique" | "scenario_operationnel";
  type_libelle: string;
  parent_id: string | null;
  contenu: Record<string, unknown>;
  statut_validation: "a_valider" | "valide" | "rejete";
  cree_le: string;
}

export type Severite = "info" | "faible" | "moyenne" | "haute" | "critique";

export interface ImportScan {
  id: string;
  outil: "nessus" | "openvas" | "cyberwatch";
  outil_libelle: string;
  nom_original: string;
  sha256: string;
  date_scan: string | null;
  etat: "en_attente" | "traite" | "echec";
  erreur: string;
  bilan: { total?: number; par_severite?: Record<Severite, number>; nouveaux?: number; deja_vus?: number; disparus?: number; precedent?: string | null };
  depose_par_nom: string;
  depose_le: string;
}

export interface ConstatScan {
  id: string;
  import_scan: string;
  identifiant_outil: string;
  titre: string;
  severite: Severite;
  cvss: string | null;
  cve: string[];
  hote: string;
  port: number | null;
  protocole: string;
  description: string;
  solution: string;
  statut: "ouvert" | "traite" | "faux_positif" | "accepte";
  commentaire_statut: string;
  statut_par_nom: string;
  a_une_tache: boolean;
}

export interface Reunion {
  id: string;
  projet: string;
  titre: string;
  debut: string;
  fin: string;
  lieu: string;
  lien_visio: string;
  participants: string[];
  participants_detail: { id: string; nom: string; role: string; externe: boolean }[];
  ordre_du_jour: string;
  compte_rendu: string;
  statut: "planifiee" | "tenue" | "annulee";
  organisateur: string;
  organisateur_nom: string;
  compte_rendu_valide_par_nom: string;
  compte_rendu_valide_le: string | null;
  nb_actions: number;
}

export type RoleCompte = "admin" | "membre" | "auditeur";

export interface Compte {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  nom_complet: string;
  fonction: string;
  role: RoleCompte;
  role_libelle: string;
  is_active: boolean;
  etat: "actif" | "invite" | "desactive";
  est_moi: boolean;
  last_login: string | null;
  date_joined: string;
  is_superuser: boolean;
}

export type NatureLien = "invitation" | "reinitialisation";
