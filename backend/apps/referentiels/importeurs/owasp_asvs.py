import json

from apps.referentiels.models import Licence

from .base import Importeur, MesureImportee

NIVEAUX = ["L1", "L2", "L3"]


def tronquer(texte, n=500):
    return texte if len(texte) <= n else texte[: n - 1].rstrip() + "…"


class OwaspAsvs(Importeur):
    code = "owasp-asvs"
    nom = "OWASP Application Security Verification Standard"
    version = "5.0.0"
    editeur = "OWASP Foundation"
    licence = Licence.CC_BY_SA
    url = (
        "https://github.com/OWASP/ASVS/releases/download/v5.0.0_release/"
        "OWASP_Application_Security_Verification_Standard_5.0.0_en.json"
    )
    nom_fichier = "asvs-5.0.0-en.json"

    def lire(self, chemin):
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
        mesures = []
        for chapitre in donnees["Requirements"]:
            for section in chapitre["Items"]:
                categorie = f"{chapitre['Shortcode']} {chapitre['Name']} › {section['Shortcode']} {section['Name']}"
                for exigence in section["Items"]:
                    # Le niveau indiqué est le niveau minimal : l'exigence s'applique aussi aux niveaux supérieurs.
                    niveau_min = int(exigence["L"])
                    mesures.append(
                        MesureImportee(
                            identifiant=exigence["Shortcode"],
                            intitule=tronquer(exigence["Description"]),
                            categorie=categorie,
                            texte=exigence["Description"],
                            niveaux=NIVEAUX[niveau_min - 1 :],
                        )
                    )
        return mesures
