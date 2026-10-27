"""Écran d'administration de l'IA, réservé à l'administrateur de l'installation (superutilisateur).

Le fournisseur saisi ici prime sur le fichier `.env`. Activer suppose d'accepter explicitement la
responsabilité des conditions du fournisseur (conservation des données, entraînement) ; toute modification de
l'adresse, du modèle ou de la clé redemande cette acceptation. La clé n'est jamais renvoyée."""

import logging
import time

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import JournalAudit

from .models import ConfigurationIA
from .provider import CompatibleOpenAI, IAIndisponible, depuis_ecran, ia_disponible
from .securite import UrlRefusee, chiffrer, dechiffrer, verifier_url

journal = logging.getLogger(__name__)


class AdminInstance(permissions.BasePermission):
    message = "Réservé à l'administrateur de l'installation."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class ConfigurationSerializer(serializers.Serializer):
    nom = serializers.CharField(max_length=60, allow_blank=True, required=False)
    url = serializers.CharField(max_length=300, allow_blank=True, required=False)
    modele = serializers.CharField(max_length=120, allow_blank=True, required=False)
    cle = serializers.CharField(max_length=500, allow_blank=True, required=False, write_only=True, trim_whitespace=True,
                                help_text="Vide ou absent : la clé enregistrée est conservée.")
    supprimer_cle = serializers.BooleanField(required=False, default=False)
    actif = serializers.BooleanField(required=False)
    accepter_responsabilite = serializers.BooleanField(required=False, default=False)

    def validate_url(self, valeur):
        valeur = valeur.strip().rstrip("/")
        if valeur:
            try:
                verifier_url(valeur)
            except UrlRefusee as e:
                raise serializers.ValidationError(str(e)) from None
        return valeur


def etat(config):
    c = config or ConfigurationIA()
    source = "ecran" if depuis_ecran() is not None else ("fichier" if settings.IA_FOURNISSEUR not in ("", "aucun") else "aucune")
    return {
        "source": source,
        "disponible": ia_disponible(),
        "ecran": {
            "actif": c.actif, "nom": c.nom, "url": c.url, "modele": c.modele, "a_une_cle": bool(c.cle_chiffree),
            "cle_fin": c.cle_fin, "responsabilite_acceptee_par": str(c.responsabilite_acceptee_par or ""),
            "responsabilite_acceptee_le": c.responsabilite_acceptee_le, "modifie_par": str(c.modifie_par or ""),
            "modifie_le": c.modifie_le if c.pk else None,
        },
        "fichier": {"fournisseur": settings.IA_FOURNISSEUR, "nom": settings.IA_NOM, "url": settings.IA_URL, "modele": settings.IA_MODELE},
        "reseau_local_autorise": settings.IA_AUTORISER_RESEAU_LOCAL,
    }


def _journaliser(request, config, donnees):
    """Configuration de l'installation : tracée dans le journal de l'organisation de l'administrateur."""
    journal.warning("Configuration IA modifiée par %s : %s", request.user, donnees)
    if request.user.organisation_id:
        JournalAudit.enregistrer(organisation=request.user.organisation, action=JournalAudit.Action.MODIFICATION, objet=config,
                                 acteur=request.user, donnees=donnees, ip=request.META.get("REMOTE_ADDR"),
                                 user_agent=request.META.get("HTTP_USER_AGENT", ""))


class ConfigurationIAView(APIView):
    permission_classes = [AdminInstance]
    serializer_class = ConfigurationSerializer

    def get(self, request):
        return Response(etat(ConfigurationIA.courante()))

    @transaction.atomic
    def put(self, request):
        demande = ConfigurationSerializer(data=request.data)
        demande.is_valid(raise_exception=True)
        v = demande.validated_data
        config = ConfigurationIA.objects.select_for_update().filter(instance=1).first() or ConfigurationIA()
        avant = {"nom": config.nom, "url": config.url, "modele": config.modele, "cle": config.cle_chiffree}
        for champ in ("nom", "url", "modele"):
            if champ in v:
                setattr(config, champ, v[champ])
        if v.get("supprimer_cle"):
            config.cle_chiffree, config.cle_fin = "", ""
        elif v.get("cle"):
            config.cle_chiffree, config.cle_fin = chiffrer(v["cle"]), v["cle"][-4:]
        change = {k for k in ("nom", "url", "modele") if getattr(config, k) != avant[k]} | ({"cle"} if config.cle_chiffree != avant["cle"] else set())
        if change - {"nom"}:  # autre adresse, autre modèle ou autre clé : la responsabilité est à réaccepter
            config.responsabilite_acceptee_par, config.responsabilite_acceptee_le = None, None
        if v.get("accepter_responsabilite"):
            config.responsabilite_acceptee_par, config.responsabilite_acceptee_le = request.user, timezone.now()
        if "actif" in v:
            if v["actif"] and not (config.url and config.modele):
                raise serializers.ValidationError({"actif": "Renseignez l'adresse et le modèle avant d'activer."})
            if v["actif"] and config.responsabilite_acceptee_le is None:
                raise serializers.ValidationError({"accepter_responsabilite": "Acceptez la responsabilité des conditions du fournisseur pour activer."})
            config.actif = v["actif"]
        elif change - {"nom"} and config.responsabilite_acceptee_le is None:
            config.actif = False  # fournisseur modifié sans nouvelle acceptation : l'IA s'arrête
        config.modifie_par = request.user
        config.save()
        _journaliser(request, config, {"champs": sorted(change), "actif": config.actif, "nom": config.nom, "url": config.url,
                                       "modele": config.modele, "responsabilite_acceptee": config.responsabilite_acceptee_le is not None})
        return Response(etat(config))


class TestIAView(APIView):
    """Appel minimal au fournisseur enregistré à l'écran (sans aucune donnée de projet) pour vérifier l'adresse,
    le modèle et la clé avant d'activer."""

    permission_classes = [AdminInstance]

    def post(self, request):
        config = ConfigurationIA.courante()
        if config is None or not (config.url and config.modele):
            return Response({"ok": False, "detail": "Enregistrez d'abord l'adresse et le modèle."}, status=400)
        fournisseur = CompatibleOpenAI(config.nom or "fournisseur", config.url, config.modele, dechiffrer(config.cle_chiffree),
                                       zdr_confirme=True, cle_requise=False, proteger_reseau=True, delai=30, essais=1)
        debut = time.monotonic()
        try:
            reponse = fournisseur.completer_json("Réponds uniquement en JSON.", 'Renvoie exactement {"ok": true}.')
        except IAIndisponible as e:
            return Response({"ok": False, "detail": str(e)})
        return Response({"ok": reponse.contenu.get("ok") is True, "duree_ms": round(1000 * (time.monotonic() - debut)),
                         "detail": "" if reponse.contenu.get("ok") is True else "Le modèle a répondu, mais pas au format JSON attendu."})
