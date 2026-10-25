"""Fabriques minimales pour les tests : deux organisations étanches A et B."""

from apps.comptes.models import Organisation, Role, Utilisateur
from apps.projets.models import ActeurProjet, Projet
from apps.referentiels.models import Licence, Referentiel


def organisation(nom, **kwargs):
    return Organisation.objects.create(nom=nom, secteur=Organisation.Secteur.PRIVE, **kwargs)


def utilisateur(org, email):
    return Utilisateur.objects.create_user(email=email, password="mot-de-passe-de-test-1", organisation=org)


def role_projet(code="rssi"):
    role, _ = Role.objects.get_or_create(code=code, portee=Role.Portee.PROJET, organisation=None, defaults={"libelle": code})
    return role


def projet(org, createur, nom="Projet"):
    return Projet.objects.create(
        organisation=org, nom=nom, type_bien=Projet.TypeBien.APPLICATION,
        niveau_vise=Projet.NiveauVise.STANDARD, cree_par=createur,
    )


def acteur(p, user):
    return ActeurProjet.objects.create(projet=p, utilisateur=user, role=role_projet())


def referentiel(code, org=None, version="1"):
    return Referentiel.objects.create(organisation=org, code=code, nom=code, version=version, licence=Licence.LIBRE)


class DeuxOrganisationsMixin:
    @classmethod
    def setUpTestData(cls):
        cls.org_a = organisation("Org A")
        cls.org_b = organisation("Org B")
        cls.user_a = utilisateur(cls.org_a, "a@a.test")
        cls.user_b = utilisateur(cls.org_b, "b@b.test")
        cls.projet_a = projet(cls.org_a, cls.user_a, "Projet A")
        cls.projet_b = projet(cls.org_b, cls.user_b, "Projet B")
