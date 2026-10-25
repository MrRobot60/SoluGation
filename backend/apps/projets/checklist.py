"""Checklist des documents attendus, générée selon le contexte du projet.

Chaque entrée : conditions (type de bien, niveau visé, EBIOS RM), rôle responsable, échéance relative,
et mesures couvertes par référentiel. Seules les mesures des référentiels du projet sont rattachées.
La génération est idempotente : un document déjà présent (même intitulé) n'est pas recréé."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from apps.referentiels.models import Mesure

from .models import ActeurProjet, DocumentAttendu, Projet

TB = Projet.TypeBien
NV = Projet.NiveauVise
TOUS_BIENS = frozenset(TB.values)
TOUS_NIVEAUX = frozenset(NV.values)


@dataclass(frozen=True)
class Modele:
    intitule: str
    type_document: str
    description: str
    role: str
    delai_jours: int
    mesures: dict[str, tuple[str, ...]] = field(default_factory=dict)
    biens: frozenset = TOUS_BIENS
    niveaux: frozenset = TOUS_NIVEAUX
    obligatoire: bool = True
    si_ebios: bool | None = None  # None : quel que soit le choix EBIOS RM


CATALOGUE = (
    Modele(
        "Stratégie d'homologation", "Cadrage",
        "Périmètre, niveau visé, acteurs (dont l'autorité d'homologation), contenu du dossier et planning.",
        "chef-projet", 7,
        {"rgs": ("§2.4",), "ii901": ("INT-HOMOLOG-SSI",)},
    ),
    Modele(
        "Analyse de risques EBIOS RM (ateliers 1 à 5)", "Analyse de risques",
        "Livrables des cinq ateliers : socle, sources de risque, scénarios stratégiques et opérationnels, traitement.",
        "rssi", 45,
        {"rgs": ("§2.1",), "hygiene-anssi": ("M41",), "nist-csf": ("ID.RA-05",)},
        si_ebios=True,
    ),
    Modele(
        "Analyse de risques", "Analyse de risques",
        "Besoins de sécurité, menaces, risques et mesures de traitement retenues.",
        "rssi", 30,
        {"rgs": ("§2.1",), "hygiene-anssi": ("M41",), "nist-csf": ("ID.RA-05",)},
        si_ebios=False,
    ),
    Modele(
        "Politique de sécurité applicable (PSSI)", "Politique",
        "PSSI de l'organisme et, le cas échéant, déclinaison propre au système.",
        "rssi", 14,
        {"ii901": ("ORG-PIL-PSSI",), "nist-csf": ("GV.PO-01",)},
    ),
    Modele(
        "Dossier d'architecture technique", "Architecture",
        "Schémas d'architecture, flux, interconnexions, zones de confiance et composants.",
        "chef-projet", 21,
        {"rgs": ("§2.3",), "hygiene-anssi": ("M04",), "ii901": ("RES-CARTO", "GDB-CARTO"),
         "nist-csf": ("ID.AM-03",), "owasp-asvs": ("V13.1.1",)},
        biens=frozenset({TB.APPLICATION, TB.SYSTEME_INFORMATION, TB.AUTRE}),
    ),
    Modele(
        "Configuration de référence du poste de travail", "Architecture",
        "Image (master), durcissement, comptes, mises à jour et outils de sécurité du poste.",
        "chef-projet", 21,
        {"hygiene-anssi": ("M14",), "ii901": ("PDT-CONFIG",), "nist-csf": ("PR.PS-01",)},
        biens=frozenset({TB.POSTE_TRAVAIL}),
    ),
    Modele(
        "Matrice de conformité aux référentiels", "Conformité",
        "Applicabilité et état de chaque mesure des référentiels retenus, avec justification des écarts.",
        "rssi", 45,
        {"rgs": ("§2.3",)},
    ),
    Modele(
        "Procédures d'exploitation sécurisée", "Exploitation",
        "Maintien en condition de sécurité : mises à jour, sauvegardes, journalisation, gestion des comptes.",
        "chef-projet", 45,
        {"rgs": ("§2.5",), "hygiene-anssi": ("M34", "M36", "M37"), "ii901": ("EXP-CONFIG", "EXP-POL-JOUR"),
         "owasp-asvs": ("V16.1.1",)},
        biens=frozenset({TB.APPLICATION, TB.SYSTEME_INFORMATION, TB.AUTRE}),
    ),
    Modele(
        "Procédure de gestion des incidents de sécurité", "Exploitation",
        "Détection, qualification, escalade, traitement et retour d'expérience.",
        "rssi", 30,
        {"rgs": ("§7.10",), "hygiene-anssi": ("M40",), "ii901": ("TI-OPS-SSI",), "nist-csf": ("RS.MA-01",)},
    ),
    Modele(
        "Plan de continuité et de reprise d'activité (PCA/PRA)", "Continuité",
        "Besoins de disponibilité, scénarios de sinistre, sauvegardes, procédures et tests de reprise.",
        "chef-projet", 60,
        {"rgs": ("§7.10",), "ii901": ("PCA-LOCAL", "PCA-PROC"), "nist-csf": ("RC.RP-01",)},
        biens=frozenset({TB.APPLICATION, TB.SYSTEME_INFORMATION, TB.AUTRE}),
        niveaux=frozenset({NV.STANDARD, NV.RENFORCE}),
    ),
    Modele(
        "Clauses de sécurité des contrats et plan d'assurance sécurité (PAS)", "Contrats",
        "Exigences de sécurité imposées aux prestataires, PAS et modalités de contrôle (si recours à des tiers).",
        "chef-projet", 30,
        {"rgs": ("§7.6",), "hygiene-anssi": ("M03",), "ii901": ("ORG-TIERS",), "nist-csf": ("GV.SC-05",)},
        obligatoire=False,
    ),
    Modele(
        "Inventaire des composants logiciels (SBOM)", "Exploitation",
        "Composants tiers et versions, pour le suivi des vulnérabilités.",
        "chef-projet", 30,
        {"owasp-asvs": ("V15.1.2",), "nist-csf": ("ID.AM-01",)},
        biens=frozenset({TB.APPLICATION}),
    ),
    Modele(
        "Rapport d'audit de sécurité", "Audit",
        "Audit d'architecture, de configuration et organisationnel (prestataire qualifié PASSI conseillé au niveau renforcé).",
        "rssi", 60,
        {"rgs": ("§7.11",), "hygiene-anssi": ("M38",), "ii901": ("CONTR-SSI",), "nist-csf": ("ID.IM-02",)},
        niveaux=frozenset({NV.STANDARD, NV.RENFORCE}),
    ),
    Modele(
        "Rapport de test d'intrusion", "Audit",
        "Tests techniques sur le périmètre exposé, avec plan de correction des vulnérabilités.",
        "rssi", 60,
        {"hygiene-anssi": ("M38",), "nist-csf": ("ID.RA-01",)},
        biens=frozenset({TB.APPLICATION, TB.SYSTEME_INFORMATION}),
        niveaux=frozenset({NV.STANDARD, NV.RENFORCE}),
    ),
    Modele(
        "Charte d'utilisation et actions de sensibilisation", "Organisation",
        "Règles d'usage opposables aux utilisateurs et preuves de sensibilisation.",
        "rssi", 30,
        {"rgs": ("§7.5",), "hygiene-anssi": ("M02",), "ii901": ("RH-SSI",)},
        biens=frozenset({TB.POSTE_TRAVAIL, TB.SYSTEME_INFORMATION}),
    ),
    Modele(
        "Décision d'homologation signée", "Décision",
        "Décision de l'autorité d'homologation : périmètre, durée de validité, conditions et risques résiduels acceptés.",
        "autorite-homologation", 90,
        {"rgs": ("§2.4",), "ii901": ("INT-HOMOLOG-SSI",)},
    ),
)


def modeles_applicables(projet):
    return [
        m for m in CATALOGUE
        if projet.type_bien in m.biens and projet.niveau_vise in m.niveaux
        and (m.si_ebios is None or m.si_ebios == projet.ebios_active)
    ]


def generer_checklist(projet, aujourd_hui=None):
    aujourd_hui = aujourd_hui or date.today()
    existants = set(DocumentAttendu.objects.filter(projet=projet).values_list("intitule", flat=True))
    referentiels = {r.code: r for r in projet.referentiels.all()}
    acteurs = {}
    for a in ActeurProjet.objects.filter(projet=projet).select_related("role").order_by("cree_le"):
        acteurs.setdefault(a.role.code, a)

    crees = []
    for modele in modeles_applicables(projet):
        if modele.intitule in existants:
            continue
        doc = DocumentAttendu.objects.create(
            projet=projet, intitule=modele.intitule, description=modele.description,
            type_document=modele.type_document, responsable=acteurs.get(modele.role),
            echeance=aujourd_hui + timedelta(days=modele.delai_jours), obligatoire=modele.obligatoire,
            origine=DocumentAttendu.Origine.GENEREE,
        )
        mesures = [
            m for code, ids in modele.mesures.items() if code in referentiels
            for m in Mesure.objects.filter(referentiel=referentiels[code], identifiant__in=ids)
        ]
        doc.mesures.set(mesures)
        crees.append(doc)
    return crees
