from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.ai.api import ResultatViewSet
from apps.audit.api import JournalAuditViewSet
from apps.comptes import api as comptes
from apps.documents.api import DocumentDeposeViewSet, PreuveViewSet
from apps.projets import api as projets
from apps.referentiels.api import MesureViewSet, ReferentielViewSet
from apps.suivi.api import CommentaireViewSet, NotificationViewSet, TacheViewSet

routeur = DefaultRouter()
routeur.register("utilisateurs", comptes.UtilisateurViewSet, basename="utilisateur")
routeur.register("roles", comptes.RoleViewSet, basename="role")
routeur.register("referentiels", ReferentielViewSet, basename="referentiel")
routeur.register("mesures", MesureViewSet, basename="mesure")
routeur.register("projets", projets.ProjetViewSet, basename="projet")
routeur.register("acteurs", projets.ActeurProjetViewSet, basename="acteur")
routeur.register("projet-referentiels", projets.ProjetReferentielViewSet, basename="projet-referentiel")
routeur.register("statuts-mesures", projets.StatutMesureViewSet, basename="statut-mesure")
routeur.register("documents-attendus", projets.DocumentAttenduViewSet, basename="document-attendu")
routeur.register("documents-deposes", DocumentDeposeViewSet, basename="document-depose")
routeur.register("preuves", PreuveViewSet, basename="preuve")
routeur.register("resultats-ia", ResultatViewSet, basename="resultat-ia")
routeur.register("taches", TacheViewSet, basename="tache")
routeur.register("commentaires", CommentaireViewSet, basename="commentaire")
routeur.register("notifications", NotificationViewSet, basename="notification")
routeur.register("journal", JournalAuditViewSet, basename="journal")

urlpatterns = [
    path("auth/csrf/", comptes.CsrfView.as_view()),
    path("auth/connexion/", comptes.ConnexionView.as_view()),
    path("auth/deconnexion/", comptes.DeconnexionView.as_view()),
    path("auth/moi/", comptes.MoiView.as_view()),
    path("organisation/", comptes.OrganisationView.as_view()),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    *routeur.urls,
]
