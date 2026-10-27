from django.core.management.base import BaseCommand

from apps.risques.api import expirer_derogations


class Command(BaseCommand):
    help = "Passe « expirées » les dérogations acceptées dont la date d'expiration est dépassée (à planifier chaque jour)."

    def handle(self, *args, **options):
        self.stdout.write(f"{len(expirer_derogations())} dérogation(s) expirée(s).")
