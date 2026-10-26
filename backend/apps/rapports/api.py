"""Rapports d'état des lieux : génération (instantané + rédaction IA en arrière-plan, texte automatique à défaut),
relecture des sections, validation (PDF figé et empreinté SHA-256) et téléchargement tracé."""

import hashlib

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.ai.analyse import preparer
from apps.ai.models import AnalyseIA
from apps.ai.provider import IAIndisponible
from apps.audit.models import JournalAudit
from apps.core.api.acces import peut_decider_projet, peut_ecrire_projet, projets_accessibles
from apps.core.api.journal import journaliser
from apps.core.api.permissions import MembreOrganisation
from apps.core.models import StatutValidation
from apps.projets.models import Projet

from .donnees import evolution, instantane
from .models import Rapport
from .pdf import rendre
from .redaction import SECTIONS, TEXTE_MAX, VERSION_PROMPT, chiffres_non_verifies, texte_automatique


def redaction_en_cours(rapport):
    a = rapport.analyse_ia
    return bool(a and a.etat in (AnalyseIA.Etat.EN_ATTENTE, AnalyseIA.Etat.EN_COURS))


class RapportSerializer(serializers.ModelSerializer):
    genere_par_nom = serializers.CharField(source="genere_par.__str__", read_only=True)
    valide_par_nom = serializers.CharField(source="valide_par.__str__", read_only=True, default="")
    redaction = serializers.SerializerMethodField()
    chiffres = serializers.SerializerMethodField()

    class Meta:
        model = Rapport
        fields = ["id", "projet", "version", "titre", "sections", "statut_validation", "valide_par_nom", "valide_le",
                  "genere_par_nom", "cree_le", "modifie_le", "pdf_genere_le", "sha256_pdf", "rapport_precedent",
                  "redaction", "chiffres"]
        read_only_fields = fields

    def get_redaction(self, obj) -> dict:
        a = obj.analyse_ia
        if a is None:
            return {"etat": "sans_ia", "erreur": "", "fournisseur": "", "modele": ""}
        return {"etat": a.etat, "erreur": a.erreur, "fournisseur": a.fournisseur, "modele": a.modele}

    def get_chiffres(self, obj) -> dict:
        d = obj.donnees
        return {"conformite": d["conformite"], "nb_manquements": d["nb_manquements"],
                "taches_ouvertes": d["plan_action"]["ouvertes"], "documents_valides": d["documents"]["par_statut"]["valide"],
                "documents_total": d["documents"]["total"], "evolution": d.get("evolution")}


class CreationSerializer(serializers.Serializer):
    projet = serializers.PrimaryKeyRelatedField(queryset=Projet.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["projet"].queryset = projets_accessibles(self.context["request"].user)


class SectionSerializer(serializers.Serializer):
    cle = serializers.ChoiceField(choices=[c for c, _ in SECTIONS])
    texte = serializers.CharField(max_length=TEXTE_MAX, allow_blank=False, trim_whitespace=True)


class EditionSerializer(serializers.Serializer):
    sections = SectionSerializer(many=True, allow_empty=False)


def _telechargement(contenu, nom):
    reponse = HttpResponse(contenu, content_type="application/pdf")
    reponse["Content-Disposition"] = f'attachment; filename="{nom}"'
    reponse["X-Content-Type-Options"] = "nosniff"
    reponse["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return reponse


class RapportViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """`?projet=`. POST {projet} : nouvelle version (instantané figé, rédaction IA en arrière-plan si l'IA est
    activée). PATCH {sections: [{cle, texte}]} tant que le rapport n'est pas validé. `valider` fige le PDF."""

    serializer_class = RapportSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        qs = (Rapport.objects.filter(projet__in=projets_accessibles(self.request.user))
              .select_related("projet__organisation", "genere_par", "valide_par", "analyse_ia", "rapport_precedent")
              .order_by("-version"))
        if self.request.query_params.get("projet"):
            qs = qs.filter(projet_id=self.request.query_params["projet"])
        return qs

    def create(self, request, *args, **kwargs):
        demande = CreationSerializer(data=request.data, context={"request": request})
        demande.is_valid(raise_exception=True)
        projet = demande.validated_data["projet"]
        if not peut_ecrire_projet(request.user, projet):
            raise PermissionDenied("Lecture seule sur ce projet.")
        precedent = (Rapport.objects.filter(projet=projet, statut_validation=StatutValidation.VALIDE).order_by("-version").first()
                     or Rapport.objects.filter(projet=projet).order_by("-version").first())
        donnees = instantane(projet)
        donnees["evolution"] = evolution(donnees, precedent.donnees if precedent else None)
        avertissement = ""
        for _ in range(2):  # deux créations simultanées : la contrainte d'unicité tranche, on retente une fois
            try:
                with transaction.atomic():
                    version = (Rapport.objects.filter(projet=projet).aggregate(m=Max("version"))["m"] or 0) + 1
                    rapport = Rapport.objects.create(
                        projet=projet, version=version, titre=f"État des lieux — {projet.nom}", donnees=donnees,
                        sections=texte_automatique(donnees), rapport_precedent=precedent, genere_par=request.user,
                    )
                    if projet.organisation.ia_activee:
                        try:
                            with transaction.atomic():
                                rapport.analyse_ia = preparer(request.user, projet, AnalyseIA.Type.REDACTION_RAPPORT,
                                                              VERSION_PROMPT, {"rapport": str(rapport.pk)})
                                rapport.save(update_fields=["analyse_ia"])
                        except IAIndisponible as e:
                            avertissement = f"{e} Texte rédigé automatiquement à partir des données."
                    journaliser(request, JournalAudit.Action.CREATION, rapport, projet,
                                {"version": version, "redaction_ia": rapport.analyse_ia_id is not None})
                break
            except IntegrityError:
                continue
        else:
            return Response({"detail": "Création simultanée d'un autre rapport : réessayez."}, status=status.HTTP_409_CONFLICT)
        donnees_reponse = RapportSerializer(self.get_queryset().get(pk=rapport.pk)).data
        return Response({**donnees_reponse, "avertissement": avertissement}, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        rapport = self.get_object()
        if not peut_ecrire_projet(request.user, rapport.projet):
            raise PermissionDenied("Lecture seule sur ce projet.")
        if rapport.statut_validation != StatutValidation.A_VALIDER:
            return Response({"detail": "Un rapport validé ne se modifie plus : générez une nouvelle version."},
                            status=status.HTTP_409_CONFLICT)
        if redaction_en_cours(rapport):
            return Response({"detail": "Rédaction par l'IA en cours : patientez avant de modifier."}, status=status.HTTP_409_CONFLICT)
        edition = EditionSerializer(data=request.data)
        edition.is_valid(raise_exception=True)
        nouveaux = {s["cle"]: s["texte"] for s in edition.validated_data["sections"]}
        modifiees = []
        for section in rapport.sections:
            if section["cle"] in nouveaux and nouveaux[section["cle"]] != section["texte"]:
                section.update(texte=nouveaux[section["cle"]], source="modifie",
                               alertes=chiffres_non_verifies(nouveaux[section["cle"]], rapport.donnees))
                modifiees.append(section["cle"])
        if modifiees:
            rapport.save(update_fields=["sections", "modifie_le"])
            journaliser(request, JournalAudit.Action.MODIFICATION, rapport, rapport.projet, {"sections": modifiees})
        return Response(RapportSerializer(rapport).data)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        rapport = self.get_object()
        if not peut_decider_projet(request.user, rapport.projet):
            raise PermissionDenied("Seuls le RSSI, l'autorité d'homologation ou l'administrateur valident un rapport.")
        if redaction_en_cours(rapport):
            return Response({"detail": "Rédaction par l'IA en cours : patientez avant de valider."}, status=status.HTTP_409_CONFLICT)
        with transaction.atomic():
            rapport = Rapport.objects.select_for_update().get(pk=rapport.pk)
            if rapport.statut_validation != StatutValidation.A_VALIDER:
                return Response({"detail": "Ce rapport a déjà été validé."}, status=status.HTTP_409_CONFLICT)
            rapport.statut_validation, rapport.valide_par, rapport.valide_le = StatutValidation.VALIDE, request.user, timezone.now()
            pdf = rendre(rapport, self._analyse_terminee(rapport))
            rapport.sha256_pdf = hashlib.sha256(pdf).hexdigest()
            rapport.fichier_pdf.save(f"rapport-v{rapport.version}.pdf", ContentFile(pdf), save=False)
            rapport.pdf_genere_le = timezone.now()
            rapport.save()
            journaliser(request, JournalAudit.Action.DECISION, rapport, rapport.projet,
                        {"decision": "rapport validé", "version": rapport.version, "sha256": rapport.sha256_pdf})
        return Response(RapportSerializer(rapport).data)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """Rapport validé : le PDF figé à la validation. Sinon : aperçu « Brouillon » calculé, jamais stocké."""
        rapport = self.get_object()
        nom = f"etat-des-lieux-v{rapport.version}{'' if rapport.statut_validation == StatutValidation.VALIDE else '-brouillon'}.pdf"
        if rapport.statut_validation == StatutValidation.VALIDE and rapport.fichier_pdf:
            with rapport.fichier_pdf.open("rb") as f:
                contenu = f.read()
        else:
            contenu = rendre(rapport, self._analyse_terminee(rapport))
        journaliser(request, JournalAudit.Action.EXPORT, rapport, rapport.projet,
                    {"version": rapport.version, "brouillon": rapport.statut_validation != StatutValidation.VALIDE})
        return _telechargement(contenu, nom)

    @staticmethod
    def _analyse_terminee(rapport):
        a = rapport.analyse_ia
        return a if a and a.etat == AnalyseIA.Etat.TERMINEE else None
