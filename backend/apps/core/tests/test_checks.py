"""Contrôles de production : une valeur d'exemple bloque le démarrage."""

from django.test import SimpleTestCase, override_settings

from apps.core.checks import configuration_production

SURS = dict(SECRET_KEY="x" * 50, AWS_SECRET_ACCESS_KEY="s3-secret-solide", ALLOWED_HOSTS=["solugation.exemple.fr"],
            FRONTEND_URL="https://solugation.exemple.fr", EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
            AWS_S3_OBJECT_PARAMETERS={"ServerSideEncryption": "AES256"}, IA_EXECUTION="taches")


class ControlesProductionTests(SimpleTestCase):
    def ids(self):
        return {p.id for p in configuration_production(None)}

    def test_configuration_saine(self):
        with override_settings(**SURS, DATABASES={"default": {"PASSWORD": "mot-de-passe-solide"}}):
            self.assertEqual(self.ids(), set())

    def test_valeurs_d_exemple_bloquantes(self):
        with override_settings(**{**SURS, "SECRET_KEY": "a-remplacer-par-une-longue-valeur-aleatoire", "ALLOWED_HOSTS": []},
                               DATABASES={"default": {"PASSWORD": "a-remplacer"}}):
            self.assertEqual(self.ids(), {"solugation.E001", "solugation.E003"})

    def test_avertissements(self):
        with override_settings(**{**SURS, "FRONTEND_URL": "http://x", "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend",
                                  "AWS_S3_OBJECT_PARAMETERS": {}, "IA_EXECUTION": "fil"},
                               DATABASES={"default": {"PASSWORD": "solide"}}):
            self.assertEqual(self.ids(), {"solugation.W001", "solugation.W002", "solugation.W003", "solugation.W004"})


class AdresseClientTests(SimpleTestCase):
    def adresse(self, **meta):
        from django.test import RequestFactory

        from apps.core.middleware import AdresseClientMiddleware

        vue = AdresseClientMiddleware(lambda r: r.META["REMOTE_ADDR"])
        return vue(RequestFactory().get("/", REMOTE_ADDR="172.18.0.2", **meta))

    def test_sans_proxy_l_en_tete_est_ignore(self):
        self.assertEqual(self.adresse(HTTP_X_FORWARDED_FOR="6.6.6.6"), "172.18.0.2")

    @override_settings(SOLUGATION_PROXY_DE_CONFIANCE=True)
    def test_derriere_le_proxy(self):
        self.assertEqual(self.adresse(HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.7"), "203.0.113.7")
        self.assertEqual(self.adresse(), "172.18.0.2")
