from datetime import date

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.models import JournalAudit
from apps.core.api.base import ProjetScopedSerializer, ProjetScopedViewSet
from apps.core.api.journal import journaliser
from apps.core.api.permissions import MembreOrganisation
from apps.projets.api import nom_acteur

from .models import Commentaire, Notification, Tache
from .notifications import acteurs_concernes, notifier
from .services import TACHES_CLOSES, plan_du_projet

LIBELLES_CHAMPS = {"titre": "Titre", "statut": "Statut", "priorite": "Priorité", "responsable": "Responsable",
                   "echeance": "Échéance", "preuve_attendue": "Preuve attendue", "description": "Description"}


def lien_tache(tache):
    return f"/projets/{tache.projet_id}/plan-action?tache={tache.pk}"


class TacheSerializer(ProjetScopedSerializer):
    mesure_identifiant = serializers.CharField(source="mesure.identifiant", read_only=True, default="")
    mesure_intitule = serializers.CharField(source="mesure.intitule", read_only=True, default="")
    referentiel_code = serializers.CharField(source="mesure.referentiel.code", read_only=True, default="")
    responsable_nom = serializers.SerializerMethodField()
    responsable_utilisateur = serializers.UUIDField(source="responsable.utilisateur_id", read_only=True, default=None)
    cloturee_par_nom = serializers.CharField(source="cloturee_par.__str__", read_only=True, default="")
    nb_commentaires = serializers.IntegerField(read_only=True, default=0)
    en_retard = serializers.SerializerMethodField()

    class Meta:
        model = Tache
        fields = ["id", "projet", "titre", "description", "mesure", "mesure_identifiant", "mesure_intitule",
                  "referentiel_code", "responsable", "responsable_nom", "responsable_utilisateur", "echeance", "preuve_attendue", "statut",
                  "priorite", "origine", "cloturee_par_nom", "cloturee_le", "nb_commentaires", "en_retard",
                  "cree_le", "modifie_le"]
        read_only_fields = ["origine", "cloturee_le"]

    def get_responsable_nom(self, obj) -> str:
        return nom_acteur(obj.responsable)

    def get_en_retard(self, obj) -> bool:
        return bool(obj.echeance and obj.echeance < date.today() and obj.statut not in TACHES_CLOSES)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        projet = attrs.get("projet") or self.instance.projet
        mesure = attrs.get("mesure")
        if mesure is not None and not projet.referentiels.filter(pk=mesure.referentiel_id).exists():
            raise serializers.ValidationError({"mesure": "Mesure hors des référentiels du projet."})
        return attrs


def resume_modifications(avant, apres, champs):
    lignes = []
    for champ in champs:
        if champ not in LIBELLES_CHAMPS:
            continue
        if champ == "responsable":
            a, b = nom_acteur(avant["responsable"]) or "personne", nom_acteur(apres.responsable) or "personne"
        elif champ in ("statut", "priorite"):
            a, b = avant[f"{champ}_libelle"], getattr(apres, f"get_{champ}_display")()
        elif champ == "echeance":
            a = avant["echeance"].strftime("%d/%m/%Y") if avant["echeance"] else "aucune"
            b = apres.echeance.strftime("%d/%m/%Y") if apres.echeance else "aucune"
        else:
            lignes.append(f"{LIBELLES_CHAMPS[champ]} modifié(e).")
            continue
        lignes.append(f"{LIBELLES_CHAMPS[champ]} : {a} → {b}")
    return "\n".join(lignes)


def signaler_nouvelle_tache(request, tache):
    """Journal + notification pour une tâche créée automatiquement (manquement)."""
    journaliser(request, JournalAudit.Action.CREATION, tache, tache.projet,
                {"titre": tache.titre, "origine": tache.origine, "mesure": tache.mesure.identifiant if tache.mesure else ""})
    notifier(tache.projet, auteur=request.user, type_evenement="tache.creee",
             titre=f"Nouvelle tâche ({tache.mesure.identifiant if tache.mesure else 'plan d’action'}) : {tache.titre}",
             message=f"Manquement constaté. Échéance : {tache.echeance:%d/%m/%Y}." if tache.echeance else "Manquement constaté.",
             lien=lien_tache(tache), destinataires=acteurs_concernes(tache.projet, responsable=tache.responsable, roles=()))


class TacheViewSet(ProjetScopedViewSet):
    """Plan d'action. Pas de suppression : une tâche s'abandonne (statut), son historique reste.
    `?projet=`, `?statut=`, `?mesure=`, `?moi=1` (tâches dont je suis responsable)."""

    serializer_class = TacheSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        self.queryset = (Tache.objects.select_related("mesure__referentiel", "responsable__utilisateur", "cloturee_par")
                         .annotate(nb_commentaires=Count("commentaires")))
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("statut"):
            qs = qs.filter(statut__in=p["statut"].split(","))
        if p.get("mesure"):
            qs = qs.filter(mesure_id=p["mesure"])
        if p.get("moi"):
            qs = qs.filter(responsable__utilisateur=self.request.user)
        return qs.order_by("echeance", "cree_le")

    def perform_create(self, serializer):
        projet = serializer.validated_data["projet"]
        tache = serializer.save(plan=plan_du_projet(projet), origine=Tache.Origine.MANUELLE)
        journaliser(self.request, JournalAudit.Action.CREATION, tache, projet, {"titre": tache.titre})
        notifier(projet, auteur=self.request.user, type_evenement="tache.creee", titre=f"Nouvelle tâche : {tache.titre}",
                 message=f"Échéance : {tache.echeance:%d/%m/%Y}" if tache.echeance else "Sans échéance.",
                 lien=lien_tache(tache), destinataires=acteurs_concernes(projet, responsable=tache.responsable))

    def perform_update(self, serializer):
        t = serializer.instance
        avant = {"responsable": t.responsable, "echeance": t.echeance, "statut_libelle": t.get_statut_display(),
                 "priorite_libelle": t.get_priorite_display()}
        nouveau_statut = serializer.validated_data.get("statut")
        if nouveau_statut and nouveau_statut != t.statut:
            clos = nouveau_statut in TACHES_CLOSES
            serializer.validated_data.update(cloturee_par=self.request.user if clos else None,
                                             cloturee_le=timezone.now() if clos else None)
        champs = [c for c, v in serializer.validated_data.items() if getattr(t, c, None) != v]
        super().perform_update(serializer)  # journal avec avant/après
        resume = resume_modifications(avant, serializer.instance, champs)
        if resume:
            destinataires = acteurs_concernes(t.projet, responsable=serializer.instance.responsable)
            if avant["responsable"] and avant["responsable"] != serializer.instance.responsable:
                destinataires += acteurs_concernes(t.projet, responsable=avant["responsable"], roles=())
            notifier(t.projet, auteur=self.request.user, type_evenement="tache.modifiee",
                     titre=f"Tâche modifiée : {t.titre}", message=resume, lien=lien_tache(t), destinataires=destinataires)


class CommentaireSerializer(ProjetScopedSerializer):
    auteur_nom = serializers.CharField(source="auteur.__str__", read_only=True)

    class Meta:
        model = Commentaire
        fields = ["id", "projet", "tache", "document_attendu", "statut_mesure", "texte", "auteur", "auteur_nom",
                  "cree_le", "edite_le"]
        read_only_fields = ["auteur", "edite_le"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if sum(attrs.get(c) is not None for c in ("tache", "document_attendu", "statut_mesure")) != 1:
            raise serializers.ValidationError("Un commentaire porte sur exactement un élément.")
        if not attrs["texte"].strip():
            raise serializers.ValidationError({"texte": "Commentaire vide."})
        return attrs


class CommentaireViewSet(ProjetScopedViewSet):
    """Fil de discussion. Ni modification ni suppression : il fait partie de l'historique.
    `?tache=`, `?document_attendu=`, `?statut_mesure=`."""

    serializer_class = CommentaireSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        self.queryset = Commentaire.objects.select_related("auteur")
        qs = super().get_queryset()
        for champ in ("tache", "document_attendu", "statut_mesure"):
            if self.request.query_params.get(champ):
                qs = qs.filter(**{f"{champ}_id": self.request.query_params[champ]})
        return qs.order_by("cree_le")

    def perform_create(self, serializer):
        c = serializer.save(auteur=self.request.user)
        journaliser(self.request, JournalAudit.Action.CREATION, c, c.projet, {"texte": c.texte[:500]})
        if c.tache_id:
            participants = [x.auteur for x in Commentaire.objects.filter(tache=c.tache).select_related("auteur")]
            notifier(c.projet, auteur=self.request.user, type_evenement="commentaire",
                     titre=f"Nouveau commentaire : {c.tache.titre}", message=f"{self.request.user} : {c.texte[:1000]}",
                     lien=lien_tache(c.tache),
                     destinataires=acteurs_concernes(c.projet, responsable=c.tache.responsable, en_plus=participants))


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "projet", "type_evenement", "titre", "message", "lien", "lue_le", "cree_le"]
        read_only_fields = fields


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Mes notifications uniquement. `?non_lues=1`."""

    serializer_class = NotificationSerializer
    permission_classes = [MembreOrganisation]

    def get_queryset(self):
        u = self.request.user
        qs = Notification.objects.filter(destinataire=u, organisation_id=u.organisation_id).order_by("-cree_le")
        if self.request.query_params.get("non_lues"):
            qs = qs.filter(lue_le__isnull=True)
        return qs

    @action(detail=False, methods=["get"])
    def compteur(self, request):
        return Response({"non_lues": self.get_queryset().filter(lue_le__isnull=True).count()})

    @action(detail=False, methods=["post"], url_path="tout-lu")
    def tout_lu(self, request):
        n = self.get_queryset().filter(lue_le__isnull=True).update(lue_le=timezone.now())
        return Response({"marquees": n}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def lue(self, request, pk=None):
        self.get_queryset().filter(Q(pk=pk), lue_le__isnull=True).update(lue_le=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)
