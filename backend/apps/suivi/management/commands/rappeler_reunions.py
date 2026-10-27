from django.core.management.base import BaseCommand

from apps.suivi.reunions import rappeler_reunions


class Command(BaseCommand):
    help = "Rappel des réunions du lendemain (appli et mail). À planifier toutes les heures."

    def handle(self, *args, **options):
        self.stdout.write(f"{rappeler_reunions()} rappel(s) envoyé(s).")
