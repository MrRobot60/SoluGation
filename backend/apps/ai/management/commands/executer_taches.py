"""Service de tâches de production : exécute les analyses IA en attente et les tâches planifiées.
Remplace le fil d'arrière-plan du serveur web (IA_EXECUTION=taches) et la crontab."""

import logging
import signal
import time
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import close_old_connections, connection
from django.utils import timezone

from apps.ai.analyse import DUREE_MAX_EN_COURS, analyses_en_attente, executer
from apps.ai.models import AnalyseIA

journal = logging.getLogger(__name__)

# Commandes idempotentes : les relancer au redémarrage du service est sans effet de bord.
PLANIFIEES = [
    ("rappeler_reunions", timedelta(hours=1)),
    ("rappeler_revues", timedelta(days=1)),
    ("expirer_derogations", timedelta(days=1)),
]


def liberer_interrompues():
    """Analyses restées « en cours » après un arrêt brutal : marquées en échec, l'utilisateur peut relancer."""
    return AnalyseIA.objects.filter(etat=AnalyseIA.Etat.EN_COURS, debut_le__lt=timezone.now() - DUREE_MAX_EN_COURS).update(
        etat=AnalyseIA.Etat.ECHEC, erreur="Analyse interrompue (arrêt du service). Relancez-la.", fin_le=timezone.now())


class Command(BaseCommand):
    help = "Service de tâches : analyses IA en attente et rappels planifiés (production)."

    def add_arguments(self, parser):
        parser.add_argument("--intervalle", type=float, default=3, help="Secondes entre deux consultations de la file.")
        parser.add_argument("--une-fois", action="store_true", help="Traite la file et les tâches dues, puis s'arrête.")

    def handle(self, intervalle, une_fois, **options):
        self.arret = False
        signal.signal(signal.SIGTERM, self._arreter)
        signal.signal(signal.SIGINT, self._arreter)
        derniers = {}
        self.stdout.write("Service de tâches démarré.")
        while not self.arret:
            if not connection.in_atomic_block:  # (tests : la transaction du test ne doit pas être fermée)
                close_old_connections()  # connexion perdue ou trop ancienne : rouverte proprement
            try:
                self._tour(derniers)
            except Exception:  # une erreur (base indisponible…) ne doit pas arrêter le service
                journal.exception("Erreur du service de tâches")
            if une_fois:
                break
            fin = time.monotonic() + intervalle
            while not self.arret and time.monotonic() < fin:
                time.sleep(0.2)
        self.stdout.write("Service de tâches arrêté.")

    def _tour(self, derniers):
        if n := liberer_interrompues():
            self.stdout.write(f"{n} analyse(s) interrompue(s) marquée(s) en échec.")
        for analyse_id in analyses_en_attente()[:10]:
            if self.arret:
                return
            executer(analyse_id)
        maintenant = timezone.now()
        for commande, periode in PLANIFIEES:
            if self.arret:
                return
            if maintenant - derniers.get(commande, maintenant - periode) >= periode:
                derniers[commande] = maintenant
                try:
                    call_command(commande, stdout=self.stdout)
                except Exception:
                    journal.exception("Échec de la tâche planifiée %s", commande)

    def _arreter(self, *_):
        self.arret = True
