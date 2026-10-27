from django.core.management.base import BaseCommand

from apps.projets.reglages import rappeler_revues


class Command(BaseCommand):
    help = "Rappels de revue périodique (30 jours avant, puis en cas de retard). À planifier chaque jour."

    def handle(self, *args, **options):
        self.stdout.write(f"{rappeler_revues()} rappel(s) envoyé(s).")
