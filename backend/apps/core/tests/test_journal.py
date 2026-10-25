from django.db import DatabaseError, connection, transaction
from django.test import TestCase

from apps.audit.models import JournalAudit, JournalImmuable

from . import fabriques as f


class JournalAuditTests(f.DeuxOrganisationsMixin, TestCase):
    def _entree(self, org=None, projet=None):
        return JournalAudit.enregistrer(
            org or self.org_a, JournalAudit.Action.CREATION, projet or self.projet_a, acteur=self.user_a
        )

    def test_chainage(self):
        e1 = self._entree()
        e2 = self._entree()
        self.assertEqual(e1.hash_precedent, "0" * 64)
        self.assertEqual(e2.hash_precedent, e1.hash)
        self.assertEqual(e2.calculer_hash(), e2.hash)

    def test_chaines_separees_par_organisation(self):
        self._entree()
        e_b = self._entree(self.org_b, self.projet_b)
        self.assertEqual(e_b.hash_precedent, "0" * 64)

    def test_orm_refuse_modification_et_suppression(self):
        e = self._entree()
        e.objet_repr = "falsifié"
        with self.assertRaises(JournalImmuable):
            e.save()
        with self.assertRaises(JournalImmuable):
            e.delete()
        with self.assertRaises(JournalImmuable):
            JournalAudit.objects.all().delete()
        with self.assertRaises(JournalImmuable):
            JournalAudit.objects.update(objet_repr="x")

    def test_trigger_refuse_le_sql_brut(self):
        e = self._entree()
        for sql in (
            "UPDATE audit_journalaudit SET objet_repr = 'x' WHERE id = %s",
            "DELETE FROM audit_journalaudit WHERE id = %s",
        ):
            with self.subTest(sql=sql), self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(sql, [e.id])
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("TRUNCATE audit_journalaudit CASCADE")
