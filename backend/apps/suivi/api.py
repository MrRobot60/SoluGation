from datetime import date

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.models import JournalAudit
from apps.core.api.acces import peut_administrer_projet, peut_ecrire_projet
from apps.core.api.base import NomField, ProjetScopedSerializer, ProjetScopedViewSet
from apps.core.api.journal import journaliser
from apps.core.api.permissions import MembreOrganisation
from apps.projets.api import nom_acteur
from apps.projets.models import ActeurProjet

from .models import Commentaire, Notification, Reunion, Tache
from .notifications import acteurs_concernes, notifier
from .reunions import inviter, lien
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
    cloturee_par_nom = NomField(source="cloturee_par")
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
    auteur_nom = NomField(source="auteur")

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


# --- Réunions -------------------------------------------------------------------------------

CHAMPS_INVITATION = ("titre", "debut", "fin", "lieu", "lien_visio", "ordre_du_jour")


def peut_organiser(utilisateur, reunion):
    return reunion.organisateur_id == utilisateur.pk or peut_administrer_projet(utilisateur, reunion.projet)


class ReunionSerializer(ProjetScopedSerializer):
    organisateur_nom = NomField(source="organisateur")
    compte_rendu_valide_par_nom = NomField(source="compte_rendu_valide_par")
    participants_detail = serializers.SerializerMethodField()
    nb_actions = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Reunion
        fields = ["id", "projet", "titre", "debut", "fin", "lieu", "lien_visio", "participants", "participants_detail", "ordre_du_jour",
                  "compte_rendu", "statut", "organisateur", "organisateur_nom", "compte_rendu_valide_par_nom", "compte_rendu_valide_le",
                  "nb_actions", "cree_le"]
        read_only_fields = ["statut", "organisateur", "compte_rendu_valide_le"]

    def get_participants_detail(self, obj) -> list:
        return [{"id": str(a.pk), "nom": nom_acteur(a), "role": a.role.libelle, "externe": a.utilisateur_id is None}
                for a in obj.participants.select_related("utilisateur", "role")]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is not None:
            if self.instance.compte_rendu_valide_le:
                raise serializers.ValidationError("Compte rendu validé : la réunion ne se modifie plus.")
            if self.instance.statut == Reunion.Statut.ANNULEE:
                raise serializers.ValidationError("Réunion annulée : planifiez-en une nouvelle.")
        debut = attrs.get("debut", getattr(self.instance, "debut", None))
        fin = attrs.get("fin", getattr(self.instance, "fin", None))
        if debut and fin and fin <= debut:
            raise serializers.ValidationError({"fin": "La fin doit suivre le début."})
        return attrs


class ActionReunionSerializer(serializers.Serializer):
    titre = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    responsable = serializers.UUIDField(required=False, allow_null=True)
    echeance = serializers.DateField(required=False, allow_null=True)


class ReunionViewSet(ProjetScopedViewSet):
    """Réunions d'un projet (`?projet=`, `?a_venir=1`). Pas de suppression : une réunion s'annule. Les participants
    reçoivent une invitation iCalendar (`inviter=false` pour ne pas l'envoyer), mise à jour à chaque changement."""

    serializer_class = ReunionSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        self.queryset = (Reunion.objects.select_related("organisateur", "compte_rendu_valide_par")
                         .annotate(nb_actions=Count("actions", distinct=True)))
        qs = super().get_queryset()
        if self.request.query_params.get("a_venir"):
            qs = qs.filter(debut__gte=timezone.now(), statut=Reunion.Statut.PLANIFIEE)
        return qs.order_by("-debut")

    def _inviter(self):
        return str(self.request.data.get("inviter", "true")).lower() not in ("false", "0", "non")

    def _prevenir(self, reunion, titre):
        destinataires = [a.utilisateur for a in reunion.participants.select_related("utilisateur") if a.utilisateur_id]
        notifier(reunion.projet, auteur=self.request.user, type_evenement="reunion.invitation", titre=titre,
                 message=f"{timezone.localtime(reunion.debut):%d/%m/%Y à %H:%M}{' · ' + reunion.lieu if reunion.lieu else ''}",
                 lien=lien(reunion), destinataires=destinataires)
        if self._inviter():
            inviter(reunion)

    def perform_create(self, serializer):
        serializer.validated_data["organisateur"] = self.request.user
        super().perform_create(serializer)
        self._prevenir(serializer.instance, f"Invitation : {serializer.instance.titre}")

    def perform_update(self, serializer):
        r = serializer.instance
        avant = {c: getattr(r, c) for c in CHAMPS_INVITATION} | {"participants": set(r.participants.values_list("pk", flat=True))}
        super().perform_update(serializer)
        r.refresh_from_db()
        apres = {c: getattr(r, c) for c in CHAMPS_INVITATION} | {"participants": set(r.participants.values_list("pk", flat=True))}
        if avant != apres and r.statut == Reunion.Statut.PLANIFIEE:
            r.sequence += 1  # les agendas remplacent l'invitation précédente
            r.save(update_fields=["sequence"])
            self._prevenir(r, f"Réunion modifiée : {r.titre}")

    def _organisateur_ou_refus(self, reunion):
        if not peut_organiser(self.request.user, reunion):
            raise PermissionDenied("Réservé à l'organisateur ou aux administrateurs du projet.")

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        r = self.get_object()
        self._organisateur_ou_refus(r)
        if r.statut != Reunion.Statut.PLANIFIEE:
            return Response({"detail": "Seule une réunion planifiée s'annule."}, status=status.HTTP_409_CONFLICT)
        r.statut, r.sequence = Reunion.Statut.ANNULEE, r.sequence + 1
        r.save(update_fields=["statut", "sequence", "modifie_le"])
        journaliser(request, JournalAudit.Action.MODIFICATION, r, r.projet, {"statut": "annulee"})
        inviter(r, annulation=True)
        return Response(ReunionSerializer(r, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="valider-compte-rendu")
    def valider_compte_rendu(self, request, pk=None):
        """Compte rendu validé : figé, réunion « tenue », diffusé aux participants (appli et mail)."""
        r = self.get_object()
        self._organisateur_ou_refus(r)
        if r.compte_rendu_valide_le or r.statut == Reunion.Statut.ANNULEE:
            return Response({"detail": "Compte rendu déjà validé, ou réunion annulée."}, status=status.HTTP_409_CONFLICT)
        if not r.compte_rendu.strip():
            raise serializers.ValidationError({"compte_rendu": "Rédigez le compte rendu avant de le valider."})
        r.statut, r.compte_rendu_valide_par, r.compte_rendu_valide_le = Reunion.Statut.TENUE, request.user, timezone.now()
        r.save(update_fields=["statut", "compte_rendu_valide_par", "compte_rendu_valide_le", "modifie_le"])
        journaliser(request, JournalAudit.Action.MODIFICATION, r, r.projet, {"compte_rendu": "validé", "longueur": len(r.compte_rendu)})
        destinataires = [a.utilisateur if a.utilisateur_id else a.email for a in r.participants.select_related("utilisateur")]
        notifier(r.projet, auteur=request.user, type_evenement="reunion.compte_rendu", titre=f"Compte rendu : {r.titre}",
                 message=r.compte_rendu[:3000], lien=lien(r), destinataires=[d for d in destinataires if d])
        return Response(ReunionSerializer(r, context={"request": request}).data)

    @action(detail=True, methods=["get", "post"], serializer_class=ActionReunionSerializer)
    def actions(self, request, pk=None):
        """Actions décidées en séance : des tâches du plan d'action rattachées à la réunion."""
        r = self.get_object()
        if request.method == "GET":
            taches = Tache.objects.filter(reunion=r).select_related("mesure__referentiel", "responsable__utilisateur", "cloturee_par")
            return Response(TacheSerializer(taches.order_by("echeance", "cree_le"), many=True, context={"request": request}).data)
        if not peut_ecrire_projet(request.user, r.projet):
            raise PermissionDenied("Écriture non autorisée sur ce projet.")
        d = ActionReunionSerializer(data=request.data)
        d.is_valid(raise_exception=True)
        responsable = None
        if d.validated_data.get("responsable"):
            responsable = ActeurProjet.objects.filter(projet=r.projet, pk=d.validated_data["responsable"]).first()
            if responsable is None:
                raise serializers.ValidationError({"responsable": "Acteur inexistant."})
        tache = Tache.objects.create(projet=r.projet, plan=plan_du_projet(r.projet), reunion=r, origine=Tache.Origine.REUNION,
                                     titre=d.validated_data["titre"], description=d.validated_data.get("description", ""),
                                     responsable=responsable, echeance=d.validated_data.get("echeance"))
        journaliser(request, JournalAudit.Action.CREATION, tache, r.projet, {"titre": tache.titre, "reunion": str(r.pk)})
        notifier(r.projet, auteur=request.user, type_evenement="tache.creee", titre=f"Action décidée en réunion : {tache.titre}",
                 message=f"Réunion « {r.titre} »", lien=lien_tache(tache),
                 destinataires=acteurs_concernes(r.projet, responsable=responsable, roles=()))
        return Response(TacheSerializer(tache, context={"request": request}).data, status=status.HTTP_201_CREATED)
