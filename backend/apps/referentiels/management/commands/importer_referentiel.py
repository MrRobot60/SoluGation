from django.core.management.base import BaseCommand, CommandError

from apps.comptes.models import Organisation
from apps.referentiels.importeurs import IMPORTEURS, ErreurImport


class Command(BaseCommand):
    help = (
        "Importe un référentiel depuis sa source officielle (idempotent). « libres » = toutes les sources libres : "
        "téléchargées automatiquement, ou déposées à la main dans data/sources/<code>/<version>/ (II 901, RGS)."
    )

    def add_arguments(self, parser):
        parser.add_argument("code", choices=sorted(IMPORTEURS) + ["libres"])
        parser.add_argument("--fichier", help="Fichier local (obligatoire sans téléchargement automatique).")
        parser.add_argument("--organisation", help="Slug de l'organisation (import privé).")

    def handle(self, code, fichier, organisation, **options):
        org = None
        if organisation:
            org = Organisation.objects.filter(slug=organisation).first()
            if org is None:
                raise CommandError(f"Organisation inconnue : {organisation}")
        codes = [c for c, i in IMPORTEURS.items() if not i.prive] if code == "libres" else [code]
        for c in codes:
            try:
                resultat = IMPORTEURS[c](fichier=fichier, organisation=org).importer()
            except ErreurImport as e:
                raise CommandError(f"{c} : {e}") from e
            ref = resultat.referentiel
            self.stdout.write(self.style.SUCCESS(
                f"{ref} : {ref.mesures.count()} mesures ({resultat.crees} créées, {resultat.mis_a_jour} mises à jour), "
                f"sha256 {ref.empreinte_source[:12]}…"
            ))
