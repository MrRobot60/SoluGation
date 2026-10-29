from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.ai import administration as administration_ia
from apps.ai.api import AnalyseViewSet, RecommandationViewSet, ResultatViewSet
from apps.ebios.api import ROUTES as ROUTES_EBIOS
from apps.rapports.api import RapportViewSet
from apps.risques.api import DerogationViewSet, RisqueViewSet
from apps.scans.api import ConstatViewSet, ImportViewSet
from apps.audit.api import JournalAuditViewSet
from apps.comptes import api as comptes
from apps.comptes import gestion as gestion_comptes
from apps.comptes import mots_de_passe
from apps.documents.api import DocumentDeposeViewSet, PreuveViewSet
from apps.projets import api as projets
from apps.referentiels.api import CorrespondanceViewSet, MesureViewSet, ReferentielViewSet
from apps.suivi.api import CommentaireViewSet, NotificationViewSet, ReunionViewSet, TacheViewSet

routeur = DefaultRouter()
routeur.register("utilisateurs", comptes.UtilisateurViewSet, basename="utilisateur")
routeur.register("roles", comptes.RoleViewSet, basename="role")
routeur.register("administration/comptes", gestion_comptes.CompteViewSet, basename="compte")
routeur.register("referentiels", ReferentielViewSet, basename="referentiel")
routeur.register("mesures", MesureViewSet, basename="mesure")
routeur.register("correspondances", CorrespondanceViewSet, basename="correspondance")
routeur.register("projets", projets.ProjetViewSet, basename="projet")
routeur.register("acteurs", projets.ActeurProjetViewSet, basename="acteur")
routeur.register("projet-referentiels", projets.ProjetReferentielViewSet, basename="projet-referentiel")
routeur.register("statuts-mesures", projets.StatutMesureViewSet, basename="statut-mesure")
routeur.register("documents-attendus", projets.DocumentAttenduViewSet, basename="document-attendu")
routeur.register("documents-deposes", DocumentDeposeViewSet, basename="document-depose")
routeur.register("preuves", PreuveViewSet, basename="preuve")
routeur.register("resultats-ia", ResultatViewSet, basename="resultat-ia")
routeur.register("analyses-ia", AnalyseViewSet, basename="analyse-ia")
routeur.register("recommandations-ia", RecommandationViewSet, basename="recommandation-ia")
routeur.register("rapports", RapportViewSet, basename="rapport")
routeur.register("risques-residuels", RisqueViewSet, basename="risque-residuel")
routeur.register("derogations", DerogationViewSet, basename="derogation")
routeur.register("imports-scans", ImportViewSet, basename="import-scan")
routeur.register("reunions", ReunionViewSet, basename="reunion")
routeur.register("constats-scans", ConstatViewSet, basename="constat-scan")
for prefixe, vue, nom in ROUTES_EBIOS:
    routeur.register(prefixe, vue, basename=nom)
routeur.register("taches", TacheViewSet, basename="tache")
routeur.register("commentaires", CommentaireViewSet, basename="commentaire")
routeur.register("notifications", NotificationViewSet, basename="notification")
routeur.register("journal", JournalAuditViewSet, basename="journal")

urlpatterns = [
    path("auth/csrf/", comptes.CsrfView.as_view()),
    path("auth/connexion/", comptes.ConnexionView.as_view()),
    path("auth/deconnexion/", comptes.DeconnexionView.as_view()),
    path("auth/moi/", comptes.MoiView.as_view()),
    path("auth/moi/visite/", comptes.VisiteView.as_view()),
    path("auth/mot-de-passe-oublie/", mots_de_passe.MotDePasseOublieView.as_view()),
    path("auth/lien/", mots_de_passe.LienView.as_view()),
    path("organisation/", comptes.OrganisationView.as_view()),
    path("administration/ia/", administration_ia.ConfigurationIAView.as_view()),
    path("administration/ia/tester/", administration_ia.TestIAView.as_view()),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    *routeur.urls,
]
