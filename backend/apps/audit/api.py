"""Journal d'audit en lecture seule : consultation filtrée, export CSV (lui-même tracé) et vérification de
l'intégrité de la chaîne de hachage. Entrées hors projet (connexions, réglages) : administrateur uniquement."""

import csv
import io
import json

from django.db.models import Q
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.api.acces import est_admin_organisation, projets_accessibles
from apps.core.api.permissions import MembreOrganisation

from .models import JournalAudit

EXPORT_MAX = 50_000
TYPES = {  # libellés lisibles des objets tracés
    "projets.Projet": "Projet", "projets.DocumentAttendu": "Document attendu", "projets.StatutMesure": "Évaluation de mesure",
    "projets.ActeurProjet": "Acteur", "projets.ProjetReferentiel": "Référentiel du projet", "documents.DocumentDepose": "Document déposé",
    "documents.Preuve": "Preuve", "suivi.Tache": "Tâche", "suivi.Commentaire": "Commentaire", "suivi.Reunion": "Réunion",
    "ai.AnalyseIA": "Analyse IA", "ai.ResultatAnalyseMesure": "Conclusion IA", "ai.RecommandationIA": "Recommandation IA",
    "ai.ConfigurationIA": "Configuration de l'IA", "rapports.Rapport": "Rapport", "risques.RisqueResiduel": "Risque résiduel",
    "risques.Derogation": "Dérogation", "scans.ImportScan": "Rapport de scan", "scans.ConstatScan": "Constat de scan",
    "comptes.Organisation": "Organisation", "comptes.Utilisateur": "Utilisateur", "referentiels.CorrespondanceMesure": "Correspondance",
    "ebios.SuggestionEBIOS": "Proposition EBIOS RM",
}


def libelle_type(objet_type):
    if objet_type in TYPES:
        return TYPES[objet_type]
    return "EBIOS RM" if objet_type.startswith("ebios.") else objet_type.split(".")[-1]


class JournalAuditSerializer(serializers.ModelSerializer):
    action_libelle = serializers.CharField(source="get_action_display", read_only=True)
    objet_libelle = serializers.SerializerMethodField()
    projet_nom = serializers.CharField(source="projet.nom", read_only=True, default="")

    class Meta:
        model = JournalAudit
        fields = ["id", "horodatage", "acteur", "acteur_repr", "action", "action_libelle", "projet", "projet_nom", "objet_type",
                  "objet_libelle", "objet_id", "objet_repr", "donnees", "adresse_ip", "hash_precedent", "hash"]

    def get_objet_libelle(self, obj) -> str:
        return libelle_type(obj.objet_type)


def verifier_chaine(organisation):
    """Recalcule chaque empreinte et le chaînage. Une entrée modifiée ou supprimée (au milieu de la chaîne)
    est détectée ; la suppression des dernières entrées ne l'est que par comparaison avec une empreinte
    conservée ailleurs (celle renvoyée ici, à noter dans le rapport ou un registre externe)."""
    precedent, nb = "0" * 64, 0
    for entree in JournalAudit.objects.filter(organisation=organisation).order_by("id").iterator(chunk_size=2000):
        nb += 1
        if entree.hash_precedent != precedent:
            return {"integre": False, "entrees": nb, "anomalie": {"id": entree.id, "nature": "chaînage rompu (entrée supprimée ou insérée)"}}
        if entree.calculer_hash() != entree.hash:
            return {"integre": False, "entrees": nb, "anomalie": {"id": entree.id, "nature": "contenu modifié"}}
        precedent = entree.hash
    return {"integre": True, "entrees": nb, "derniere_empreinte": precedent}


class JournalAuditViewSet(viewsets.ReadOnlyModelViewSet):
    """`?projet=`, `?objet_id=`, `?action=a,b`, `?acteur=<id>`, `?objet_type=`, `?du=AAAA-MM-JJ`, `?au=`, `?q=`
    (objet, auteur), `?hors_projet=1` (administrateur : connexions, réglages de l'organisation)."""

    serializer_class = JournalAuditSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        u = self.request.user
        filtre = Q(projet__in=projets_accessibles(u))
        if est_admin_organisation(u):
            filtre |= Q(projet=None)
        qs = JournalAudit.objects.filter(filtre, organisation_id=u.organisation_id).select_related("projet").order_by("-id")
        p = self.request.query_params
        if p.get("projet"):
            qs = qs.filter(projet_id=p["projet"])
        if p.get("hors_projet"):
            qs = qs.filter(projet=None)
        if p.get("objet_id"):  # historique d'un élément (tâche, document…)
            qs = qs.filter(objet_id=p["objet_id"])
        if p.get("action"):
            qs = qs.filter(action__in=p["action"].split(","))
        if p.get("acteur"):
            qs = qs.filter(acteur_id=p["acteur"])
        if p.get("objet_type"):
            qs = qs.filter(objet_type__startswith=p["objet_type"])
        if du := parse_date(p.get("du", "") or ""):
            qs = qs.filter(horodatage__date__gte=du)
        if au := parse_date(p.get("au", "") or ""):
            qs = qs.filter(horodatage__date__lte=au)
        if q := p.get("q", "").strip():
            qs = qs.filter(Q(objet_repr__icontains=q) | Q(acteur_repr__icontains=q))
        return qs

    @action(detail=False, methods=["get"])
    def acteurs(self, request):
        """Auteurs présents dans le périmètre visible (pour le filtre)."""
        lignes = self.get_queryset().exclude(acteur=None).values("acteur", "acteur_repr").distinct().order_by("acteur_repr")
        vus, resultat = set(), []
        for l in lignes:
            if l["acteur"] not in vus:
                vus.add(l["acteur"])
                resultat.append({"id": str(l["acteur"]), "nom": l["acteur_repr"]})
        return Response(resultat)

    @action(detail=False, methods=["get"])
    def exporter(self, request):
        """Export CSV des entrées filtrées (empreintes comprises), tracé au journal."""
        entrees = list(self.get_queryset()[:EXPORT_MAX])
        tampon = io.StringIO()
        ecrivain = csv.writer(tampon, delimiter=";")
        ecrivain.writerow(["id", "horodatage", "auteur", "action", "projet", "type", "objet", "donnees", "adresse_ip", "hash_precedent", "hash"])
        for e in entrees:
            ecrivain.writerow([e.id, e.horodatage.isoformat(), e.acteur_repr, e.get_action_display(), e.projet.nom if e.projet_id else "",
                               libelle_type(e.objet_type), e.objet_repr, json.dumps(e.donnees, ensure_ascii=False, default=str),
                               e.adresse_ip or "", e.hash_precedent, e.hash])
        JournalAudit.enregistrer(organisation=request.user.organisation, action=JournalAudit.Action.EXPORT, objet=request.user.organisation,
                                 acteur=request.user, projet=None, donnees={"export": "journal", "entrees": len(entrees),
                                                                             "filtres": dict(request.query_params.items())},
                                 ip=request.META.get("REMOTE_ADDR"), user_agent=request.META.get("HTTP_USER_AGENT", ""))
        reponse = HttpResponse("﻿" + tampon.getvalue(), content_type="text/csv; charset=utf-8")  # BOM : accents corrects dans Excel
        reponse["Content-Disposition"] = 'attachment; filename="journal-audit.csv"'
        return reponse

    @action(detail=False, methods=["get"])
    def integrite(self, request):
        """Vérification de toute la chaîne de l'organisation : administrateur uniquement (elle couvre tous les projets)."""
        if not est_admin_organisation(request.user):
            raise PermissionDenied("Réservé à l'administrateur de l'organisation.")
        return Response(verifier_chaine(request.user.organisation))
