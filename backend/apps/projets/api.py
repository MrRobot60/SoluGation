from django.db import transaction
from django.http import HttpResponse
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.models import JournalAudit
from apps.comptes.models import Role, Utilisateur
from apps.core.api.acces import (est_archive, peut_administrer_projet, peut_decider_projet, peut_ecrire_projet,
                                 peut_prononcer_homologation, projets_accessibles)
from apps.core.api.base import JournaliseMixin, NomField, ProjetScopedSerializer, ProjetScopedViewSet
from apps.core.api.journal import journaliser
from apps.core.api.permissions import EcritureSelonRole, MembreOrganisation
from apps.referentiels.api import referentiels_accessibles
from apps.referentiels.models import Mesure

from .checklist import generer_checklist
from .reglages import STATUTS_MANUELS, DecisionHomologationSerializer, ajouter_mois, appliquer_decision, calendrier_ics
from .tableau_de_bord import tableau_de_bord as calculer_tableau_de_bord
from .models import (MAX_REFERENTIELS_PAR_PROJET, ActeurProjet, DocumentAttendu, Projet, ProjetReferentiel,
                     StatutMesure)

ROLE_CREATEUR = "chef-projet"


class ChampFiltre(serializers.PrimaryKeyRelatedField):
    """FK dont les choix dépendent de l'utilisateur (son organisation)."""

    def __init__(self, filtre, **kwargs):
        self.filtre = filtre
        super().__init__(**kwargs)

    def get_queryset(self):
        return self.filtre(self.context["request"].user)


def mesures_accessibles(u):
    return Mesure.objects.filter(referentiel__in=referentiels_accessibles(u))


def roles_projet(u):
    return Role.objects.filter(Q(organisation=None) | Q(organisation_id=u.organisation_id), portee=Role.Portee.PROJET)


def membres(u):
    return Utilisateur.objects.filter(organisation_id=u.organisation_id, is_active=True)


# --- Projets -----------------------------------------------------------------------------


class ActeurInitialSerializer(serializers.Serializer):
    """Acteur déclaré dans l'assistant de création : membre de l'organisation, ou contact externe (email)."""

    utilisateur = ChampFiltre(membres, required=False, allow_null=True)
    nom = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    organisme = serializers.CharField(max_length=150, required=False, allow_blank=True)
    role = ChampFiltre(roles_projet)

    def validate(self, attrs):
        if not attrs.get("utilisateur") and not attrs.get("email"):
            raise serializers.ValidationError("Un acteur sans compte doit avoir un email.")
        return attrs


class ProjetSerializer(serializers.ModelSerializer):
    referentiels = ChampFiltre(referentiels_accessibles, many=True)
    # Assistant de création : acteurs et checklist créés dans la même transaction que le projet.
    acteurs = ActeurInitialSerializer(many=True, write_only=True, required=False)
    generer_checklist = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Projet
        fields = ["id", "nom", "description", "type_bien", "niveau_vise", "statut", "referentiels", "ebios_active",
                  "notifications_actives", "calendrier_actif", "periodicite_revue_mois", "date_prochaine_revue",
                  "decision", "decision_par", "date_decision", "date_fin_validite", "cree_par", "cree_le", "modifie_le",
                  "acteurs", "generer_checklist"]
        # La décision d'homologation fera l'objet d'une action dédiée (autorité d'homologation), pas d'un PATCH.
        read_only_fields = ["decision", "decision_par", "date_decision", "date_fin_validite", "cree_par", "cree_le", "modifie_le"]

    def validate_referentiels(self, valeur):
        if not 1 <= len(valeur) <= MAX_REFERENTIELS_PAR_PROJET:
            raise serializers.ValidationError(f"Entre 1 et {MAX_REFERENTIELS_PAR_PROJET} référentiels.")
        return valeur

    def validate_statut(self, valeur):
        # Homologué / refusé : décision de l'autorité d'homologation ; archivé : action dédiée.
        if self.instance is not None and valeur != self.instance.statut and valeur not in STATUTS_MANUELS:
            raise serializers.ValidationError("Ce statut résulte d'une décision ou d'un archivage, pas d'une modification.")
        return valeur

    def validate_periodicite_revue_mois(self, valeur):
        if not 1 <= valeur <= 60:
            raise serializers.ValidationError("Entre 1 et 60 mois.")
        return valeur

    def validate_nom(self, valeur):
        qs = Projet.objects.filter(organisation_id=self.context["request"].user.organisation_id, nom=valeur)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Un projet porte déjà ce nom.")
        return valeur

    @transaction.atomic
    def create(self, validated_data):
        referentiels = validated_data.pop("referentiels")
        acteurs = validated_data.pop("acteurs", [])
        generer = validated_data.pop("generer_checklist", False)
        projet = Projet.objects.create(**validated_data)
        for ref in referentiels:
            ProjetReferentiel.objects.create(projet=projet, referentiel=ref)
        # Le créateur devient chef de projet : sans cela il ne verrait pas son propre projet.
        role = Role.objects.get(organisation=None, portee=Role.Portee.PROJET, code=ROLE_CREATEUR)
        ActeurProjet.objects.create(projet=projet, utilisateur=projet.cree_par, role=role)
        deja = {(projet.cree_par_id, role.id)}
        for a in acteurs:
            cle = (getattr(a.get("utilisateur"), "id", None), a["role"].id)
            if cle[0] is not None and cle in deja:
                continue  # même personne, même rôle : ignoré plutôt que refusé
            deja.add(cle)
            ActeurProjet.objects.create(projet=projet, **a)
        projet.checklist_creee = generer_checklist(projet) if generer else []
        return projet

    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.pop("acteurs", None)
        validated_data.pop("generer_checklist", None)
        referentiels = validated_data.pop("referentiels", None)
        projet = super().update(instance, validated_data)
        if referentiels is not None:
            ProjetReferentiel.objects.filter(projet=projet).exclude(referentiel__in=referentiels).delete()
            actuels = set(ProjetReferentiel.objects.filter(projet=projet).values_list("referentiel_id", flat=True))
            for ref in referentiels:
                if ref.id not in actuels:
                    ProjetReferentiel.objects.create(projet=projet, referentiel=ref)
        return projet


class ProjetViewSet(JournaliseMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                    mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Pas de suppression : un projet s'archive (statut), ses preuves et son journal restent."""

    serializer_class = ProjetSerializer
    permission_classes = [MembreOrganisation, EcritureSelonRole]

    def get_queryset(self):
        return projets_accessibles(self.request.user).prefetch_related("referentiels")

    def perform_update(self, serializer):
        if not peut_administrer_projet(self.request.user, serializer.instance):
            raise PermissionDenied("Les réglages reviennent au chef de projet, au RSSI, à l'autorité d'homologation ou à l'administrateur.")
        super().perform_update(serializer)

    def perform_create(self, serializer):
        u = self.request.user
        projet = serializer.save(organisation=u.organisation, cree_par=u)
        journaliser(self.request, JournalAudit.Action.CREATION, projet, projet, {
            "nom": projet.nom, "referentiels": [str(r.pk) for r in projet.referentiels.all()],
            "acteurs": ActeurProjet.objects.filter(projet=projet).count(),
            "checklist": [d.intitule for d in projet.checklist_creee],
        })

    @action(detail=True, methods=["post"], serializer_class=DecisionHomologationSerializer)
    @transaction.atomic
    def decision(self, request, pk=None):
        """Décision d'homologation : l'autorité d'homologation du projet, et elle seule (jamais l'IA)."""
        projet = self.get_object()
        if not peut_prononcer_homologation(request.user, projet):
            raise PermissionDenied("Seule l'autorité d'homologation du projet prononce la décision.")
        d = DecisionHomologationSerializer(data=request.data)
        d.is_valid(raise_exception=True)
        appliquer_decision(projet, request.user, d.validated_data)
        donnees = {"decision": projet.decision, "commentaire": d.validated_data.get("commentaire", ""),
                   "date_fin_validite": projet.date_fin_validite.isoformat() if projet.date_fin_validite else None}
        journaliser(request, JournalAudit.Action.DECISION, projet, projet, donnees)
        from apps.suivi.notifications import acteurs_concernes, notifier

        notifier(projet, auteur=request.user, type_evenement="homologation.decision",
                 titre=f"Décision d'homologation : {projet.get_decision_display().lower()}",
                 message=d.validated_data.get("commentaire", "") or (f"Valable jusqu'au {projet.date_fin_validite:%d/%m/%Y}." if projet.date_fin_validite else ""),
                 lien=f"/projets/{projet.pk}/reglages", destinataires=acteurs_concernes(projet, roles=("chef-projet", "rssi")))
        return Response(ProjetSerializer(projet, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="revue-faite")
    def revue_faite(self, request, pk=None):
        """La revue périodique a eu lieu : la suivante est fixée selon la périodicité."""
        projet = self.get_object()
        if not peut_administrer_projet(request.user, projet):
            raise PermissionDenied("Réglage réservé aux administrateurs du projet.")
        precedente = projet.date_prochaine_revue
        projet.date_prochaine_revue = ajouter_mois(timezone.localdate(), projet.periodicite_revue_mois)
        if projet.date_fin_validite:
            projet.date_prochaine_revue = min(projet.date_prochaine_revue, projet.date_fin_validite)
        projet.save(update_fields=["date_prochaine_revue", "modifie_le"])
        journaliser(request, JournalAudit.Action.MODIFICATION, projet, projet, {
            "revue_faite_le": timezone.localdate().isoformat(), "revue_prevue": precedente.isoformat() if precedente else None,
            "prochaine_revue": projet.date_prochaine_revue.isoformat()})
        return Response(ProjetSerializer(projet, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[MembreOrganisation])
    def archiver(self, request, pk=None):
        return self._archivage(request, archiver=True)

    @action(detail=True, methods=["post"], permission_classes=[MembreOrganisation])
    def desarchiver(self, request, pk=None):
        return self._archivage(request, archiver=False)

    def _archivage(self, request, archiver):
        projet = self.get_object()
        if not peut_administrer_projet(request.user, projet, meme_archive=True):
            raise PermissionDenied("Réservé aux administrateurs du projet.")
        if archiver == est_archive(projet):
            return Response({"detail": "Le projet est déjà dans cet état."}, status=status.HTTP_409_CONFLICT)
        # Au désarchivage : le statut d'avant (homologué, refusé…) est repris du journal, sinon « en cours ».
        avant = projet.statut
        if archiver:
            projet.statut = Projet.Statut.ARCHIVE
        else:
            derniere = (JournalAudit.objects.filter(projet=projet, objet_id=str(projet.pk), donnees__archivage="archive")
                        .order_by("-id").values_list("donnees", flat=True).first())
            projet.statut = (derniere or {}).get("statut_precedent") or Projet.Statut.EN_COURS
        projet.save(update_fields=["statut", "modifie_le"])
        journaliser(request, JournalAudit.Action.MODIFICATION, projet, projet,
                    {"archivage": "archive" if archiver else "desarchive", "statut_precedent": avant})
        return Response(ProjetSerializer(projet, context={"request": request}).data)

    @action(detail=True, methods=["get"], url_path="calendrier")
    def calendrier(self, request, pk=None):
        """Échéances du projet au format iCalendar, à importer dans un agenda (si le calendrier est activé)."""
        projet = self.get_object()
        if not projet.calendrier_actif:
            return Response({"detail": "Le calendrier est désactivé pour ce projet."}, status=status.HTTP_404_NOT_FOUND)
        journaliser(request, JournalAudit.Action.EXPORT, projet, projet, {"export": "calendrier"})
        reponse = HttpResponse(calendrier_ics(projet), content_type="text/calendar; charset=utf-8")
        reponse["Content-Disposition"] = f'attachment; filename="solugation-{projet.pk}.ics"'
        return reponse

    @action(detail=True, methods=["get"], url_path="tableau-de-bord")
    def tableau_de_bord(self, request, pk=None):
        """Agrégats du tableau de bord, vus par l'utilisateur connecté (« Pour vous » = ses tâches et documents)."""
        return Response(calculer_tableau_de_bord(self.get_object(), request.user))

    @action(detail=True, methods=["post"], url_path="generer-plan-action")
    def generer_plan_action(self, request, pk=None):
        """Rattrapage : une tâche pour chaque manquement évalué qui n'en a pas encore."""
        from apps.suivi.api import signaler_nouvelle_tache
        from apps.suivi.services import generer_plan_action

        projet = self.get_object()
        if not peut_ecrire_projet(request.user, projet):
            raise PermissionDenied("Écriture non autorisée sur ce projet.")
        crees = generer_plan_action(projet)
        for t in crees:
            signaler_nouvelle_tache(request, t)
        return Response({"crees": len(crees)}, status=status.HTTP_201_CREATED if crees else status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="generer-checklist")
    def generer_checklist(self, request, pk=None):
        projet = self.get_object()
        if not peut_ecrire_projet(request.user, projet):
            return Response({"detail": "Écriture non autorisée sur ce projet."}, status=status.HTTP_403_FORBIDDEN)
        crees = generer_checklist(projet)
        if crees:
            journaliser(request, JournalAudit.Action.CREATION, projet, projet,
                        {"checklist": [d.intitule for d in crees]})
        docs = DocumentAttendu.objects.filter(projet=projet)
        return Response({"crees": len(crees), "documents": DocumentAttenduSerializer(docs, many=True, context={"request": request}).data},
                        status=status.HTTP_201_CREATED if crees else status.HTTP_200_OK)


# --- Objets rattachés à un projet ---------------------------------------------------------


def nom_acteur(acteur):
    if acteur is None:
        return ""
    if acteur.utilisateur_id:
        return str(acteur.utilisateur)
    return acteur.nom or acteur.email



class ActeurProjetSerializer(ProjetScopedSerializer):
    utilisateur = ChampFiltre(membres, required=False, allow_null=True)
    role = ChampFiltre(roles_projet)
    affichage = serializers.SerializerMethodField()
    role_libelle = serializers.CharField(source="role.libelle", read_only=True)
    role_code = serializers.CharField(source="role.code", read_only=True)

    class Meta:
        model = ActeurProjet
        fields = ["id", "projet", "utilisateur", "nom", "email", "organisme", "role", "role_libelle", "role_code", "affichage"]
        # Le validateur d'unicité automatique rendrait « utilisateur » obligatoire : un contact externe n'en a pas.
        validators = []

    def get_affichage(self, obj) -> str:
        return nom_acteur(obj)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        utilisateur = attrs.get("utilisateur", getattr(self.instance, "utilisateur", None))
        email = attrs.get("email", getattr(self.instance, "email", ""))
        if utilisateur is None and not email:
            raise serializers.ValidationError("Un acteur sans compte doit avoir un email.")
        projet, role = attrs.get("projet") or self.instance.projet, attrs.get("role") or self.instance.role
        doublon = ActeurProjet.objects.filter(projet=projet, role=role)
        doublon = doublon.filter(utilisateur=utilisateur) if utilisateur else doublon.filter(utilisateur=None, email__iexact=email)
        if self.instance is not None:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError("Cette personne a déjà ce rôle dans le projet.")
        return attrs


class ActeurProjetViewSet(ProjetScopedViewSet):
    """Acteurs du projet. Ajout, changement de rôle et retrait : administrateurs du projet ; il reste toujours
    au moins un chef de projet (sinon plus personne ne pourrait régler le projet)."""

    queryset = ActeurProjet.objects.select_related("utilisateur", "role")
    serializer_class = ActeurProjetSerializer

    def _autoriser(self, projet):
        if not peut_administrer_projet(self.request.user, projet):
            raise PermissionDenied("La gestion des acteurs revient aux administrateurs du projet.")

    def _dernier_chef(self, acteur):
        return acteur.role.code == ROLE_CREATEUR and not ActeurProjet.objects.filter(
            projet=acteur.projet, role__code=ROLE_CREATEUR).exclude(pk=acteur.pk).exists()

    def perform_create(self, serializer):
        self._autoriser(serializer.validated_data["projet"])
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._autoriser(serializer.instance.projet)
        nouveau = serializer.validated_data.get("role")
        if nouveau is not None and nouveau.code != ROLE_CREATEUR and self._dernier_chef(serializer.instance):
            raise serializers.ValidationError({"role": "Le projet doit garder au moins un chef de projet."})
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._autoriser(instance.projet)
        if self._dernier_chef(instance):
            raise serializers.ValidationError("Le projet doit garder au moins un chef de projet.")
        super().perform_destroy(instance)


class ProjetReferentielSerializer(ProjetScopedSerializer):
    referentiel = ChampFiltre(referentiels_accessibles)

    class Meta:
        model = ProjetReferentiel
        fields = ["id", "projet", "referentiel"]


class ProjetReferentielViewSet(ProjetScopedViewSet):
    queryset = ProjetReferentiel.objects.select_related("referentiel")
    serializer_class = ProjetReferentielSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def perform_create(self, serializer):
        if not peut_administrer_projet(self.request.user, serializer.validated_data["projet"]):
            raise PermissionDenied("Les référentiels se règlent par les administrateurs du projet.")
        super().perform_create(serializer)

    def perform_destroy(self, instance):
        if not peut_administrer_projet(self.request.user, instance.projet):
            raise PermissionDenied("Les référentiels se règlent par les administrateurs du projet.")
        if ProjetReferentiel.objects.filter(projet=instance.projet).count() <= 1:
            raise serializers.ValidationError("Un projet garde au moins un référentiel.")
        super().perform_destroy(instance)


class StatutMesureSerializer(ProjetScopedSerializer):
    mesure = ChampFiltre(mesures_accessibles)
    evalue_par_nom = NomField(source="evalue_par")
    mesure_identifiant = serializers.CharField(source="mesure.identifiant", read_only=True)
    mesure_intitule = serializers.CharField(source="mesure.intitule", read_only=True)
    referentiel_code = serializers.CharField(source="mesure.referentiel.code", read_only=True)

    class Meta:
        model = StatutMesure
        fields = ["id", "projet", "mesure", "mesure_identifiant", "mesure_intitule", "referentiel_code", "statut", "justification",
                  "resultat_analyse", "evalue_par", "evalue_par_nom", "evalue_le"]
        read_only_fields = ["resultat_analyse", "evalue_par", "evalue_le"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        projet = attrs.get("projet") or self.instance.projet
        mesure = attrs.get("mesure") or self.instance.mesure
        if not projet.referentiels.filter(pk=mesure.referentiel_id).exists():
            raise serializers.ValidationError({"mesure": "Mesure hors des référentiels du projet."})
        return attrs


class StatutMesureViewSet(ProjetScopedViewSet):
    queryset = StatutMesure.objects.select_related("mesure__referentiel", "evalue_par")
    serializer_class = StatutMesureSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_create(self, serializer):
        serializer.validated_data.update(evalue_par=self.request.user, evalue_le=timezone.now())
        super().perform_create(serializer)
        self._manquement(serializer.instance)

    def perform_update(self, serializer):
        # Une évaluation reprise à la main n'est plus « d'après une proposition de l'IA ».
        serializer.validated_data.update(evalue_par=self.request.user, evalue_le=timezone.now(), resultat_analyse=None)
        super().perform_update(serializer)
        self._manquement(serializer.instance)

    def _manquement(self, evaluation):
        from apps.suivi.api import signaler_nouvelle_tache
        from apps.suivi.services import tache_pour_manquement

        if tache := tache_pour_manquement(evaluation):
            signaler_nouvelle_tache(self.request, tache)


class DocumentAttenduSerializer(ProjetScopedSerializer):
    mesures = ChampFiltre(mesures_accessibles, many=True, required=False)
    nb_versions = serializers.IntegerField(source="versions.count", read_only=True)
    responsable_nom = serializers.SerializerMethodField()
    responsable_role = serializers.CharField(source="responsable.role.libelle", read_only=True, default="")
    mesures_couvertes = serializers.SerializerMethodField()

    class Meta:
        model = DocumentAttendu
        fields = ["id", "projet", "intitule", "description", "type_document", "mesures", "mesures_couvertes",
                  "responsable", "responsable_nom", "responsable_role", "echeance", "statut", "obligatoire", "origine",
                  "nb_versions"]
        read_only_fields = ["origine"]

    def get_responsable_nom(self, obj) -> str:
        return nom_acteur(obj.responsable)

    def get_mesures_couvertes(self, obj) -> list[dict]:
        return [{"id": m.id, "identifiant": m.identifiant, "intitule": m.intitule, "referentiel": m.referentiel.code}
                for m in obj.mesures.all()]

    def validate_statut(self, valeur):
        # Toute décision sur une pièce (valider, refuser, rouvrir, non applicable) est réservée aux décisionnaires.
        # Le passage automatique en « déposé » se fait au dépôt, pas par cette voie.
        if self.instance is not None and valeur != self.instance.statut:
            if not peut_decider_projet(self.context["request"].user, self.instance.projet):
                raise PermissionDenied("Seuls le RSSI, l'autorité d'homologation ou l'administrateur peuvent statuer sur une pièce.")
        decisions = (DocumentAttendu.Statut.VALIDE, DocumentAttendu.Statut.REFUSE)
        if valeur in decisions and (self.instance is None or not self.instance.versions.exists()):
            raise serializers.ValidationError("Aucune version déposée : rien à valider ni à refuser.")
        return valeur

    def create(self, validated_data):
        validated_data["origine"] = DocumentAttendu.Origine.MANUELLE
        return super().create(validated_data)


class DocumentAttenduViewSet(ProjetScopedViewSet):
    queryset = DocumentAttendu.objects.select_related("responsable__utilisateur", "responsable__role").prefetch_related(
        "mesures__referentiel")
    serializer_class = DocumentAttenduSerializer
