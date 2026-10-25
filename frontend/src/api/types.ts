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
