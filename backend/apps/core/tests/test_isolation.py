"""Une organisation ne doit jamais pouvoir lire ni lier les données d'une autre."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.ai.models import AnalyseIA
from apps.core.models import StatutValidation
from apps.projets.models import ActeurProjet, DocumentAttendu, Projet, ProjetReferentiel
from apps.suivi.models import ActionPlan, Tache

from . import fabriques as f


class IsolationTests(f.DeuxOrganisationsMixin, TestCase):
    def test_filtrage_par_organisation(self):
        self.assertQuerySetEqual(Projet.objects.pour_organisation(self.org_a), [self.projet_a])
        self.assertQuerySetEqual(Projet.objects.pour_organisation(self.org_b), [self.projet_b])

    def test_organisation_recopiee_depuis_le_projet(self):
        doc = DocumentAttendu(projet=self.projet_a, intitule="PSSI")
        doc.organisation_id = self.org_b.id  # tentative de forçage
        doc.save()
        doc.refresh_from_db()
        self.assertEqual(doc.organisation_id, self.org_a.id)
        self.assertFalse(DocumentAttendu.objects.pour_organisation(self.org_b).exists())

    def test_fk_vers_un_autre_projet_refusee(self):
        acteur_b = f.acteur(self.projet_b, self.user_b)
        with self.assertRaises(ValidationError):
            DocumentAttendu.objects.create(projet=self.projet_a, intitule="PSSI", responsable=acteur_b)

    def test_tache_ne_peut_pas_viser_le_plan_d_une_autre_organisation(self):
        plan_b = ActionPlan.objects.create(projet=self.projet_b)
        with self.assertRaises(ValidationError):
            Tache.objects.create(projet=self.projet_a, plan=plan_b, titre="x")

    def test_acteur_d_une_autre_organisation_refuse(self):
        with self.assertRaises(ValidationError):
            ActeurProjet.objects.create(projet=self.projet_a, utilisateur=self.user_b, role=f.role_projet())

    def test_referentiel_prive_d_une_autre_organisation_refuse(self):
        prive_b = f.referentiel("iso27001", org=self.org_b)
        with self.assertRaises(ValidationError):
            ProjetReferentiel.objects.create(projet=self.projet_a, referentiel=prive_b)

    def test_referentiel_commun_et_prive_propre_acceptes(self):
        ProjetReferentiel.objects.create(projet=self.projet_a, referentiel=f.referentiel("rgs"))
        ProjetReferentiel.objects.create(projet=self.projet_a, referentiel=f.referentiel("iso27001", org=self.org_a))
        self.assertEqual(self.projet_a.referentiels.count(), 2)


class RegleMetierTests(f.DeuxOrganisationsMixin, TestCase):
    def test_trois_referentiels_maximum(self):
        for code in ("a", "b", "c"):
            ProjetReferentiel.objects.create(projet=self.projet_a, referentiel=f.referentiel(code))
        with self.assertRaises(ValidationError):
            ProjetReferentiel.objects.create(projet=self.projet_a, referentiel=f.referentiel("d"))

    def _analyse(self, **kwargs):
        return AnalyseIA.objects.create(
            projet=self.projet_a, type_analyse=AnalyseIA.Type.ANALYSE_DOCUMENTAIRE, fournisseur="test",
            modele="test", version_prompt="1", demandee_par=self.user_a, **kwargs,
        )

    def test_conclusion_ia_nait_a_valider(self):
        self.assertEqual(self._analyse().statut_validation, StatutValidation.A_VALIDER)

    def test_validation_sans_valideur_refusee_par_la_base(self):
        with self.assertRaises(IntegrityError):
            self._analyse(statut_validation=StatutValidation.VALIDE)

    def test_validation_tracee(self):
        analyse = self._analyse()
        analyse.valider(self.user_a)
        analyse.refresh_from_db()
        self.assertEqual(analyse.valide_par, self.user_a)
        self.assertIsNotNone(analyse.valide_le)

    def test_ia_desactivee(self):
        self.org_a.ia_activee = False
        self.org_a.save()
        self.projet_a.refresh_from_db()
        with self.assertRaises(ValidationError):
            self._analyse()
