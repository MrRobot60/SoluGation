"""Protection en base du journal d'audit : UPDATE, DELETE et TRUNCATE refusés par trigger,
quel que soit le chemin (ORM, SQL brut, admin). En prod, l'appli doit en plus se connecter avec
un rôle non propriétaire de la table (un propriétaire peut désactiver un trigger)."""

from django.db import migrations

TABLE = "audit_journalaudit"

SQL = f"""
CREATE OR REPLACE FUNCTION solugation_journal_immuable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Journal d''audit en ajout seul : % interdit', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER journal_audit_pas_de_modification
    BEFORE UPDATE OR DELETE ON {TABLE}
    FOR EACH ROW EXECUTE FUNCTION solugation_journal_immuable();

CREATE TRIGGER journal_audit_pas_de_truncate
    BEFORE TRUNCATE ON {TABLE}
    FOR EACH STATEMENT EXECUTE FUNCTION solugation_journal_immuable();

REVOKE UPDATE, DELETE, TRUNCATE ON {TABLE} FROM PUBLIC;
"""

SQL_INVERSE = f"""
DROP TRIGGER IF EXISTS journal_audit_pas_de_truncate ON {TABLE};
DROP TRIGGER IF EXISTS journal_audit_pas_de_modification ON {TABLE};
DROP FUNCTION IF EXISTS solugation_journal_immuable();
"""


class Migration(migrations.Migration):
    dependencies = [("audit", "0002_initial")]

    operations = [migrations.RunSQL(SQL, SQL_INVERSE)]
