import json

from apps.referentiels.models import Licence

from .base import Importeur, MesureImportee


class NistCsf(Importeur):
    """Export JSON officiel du CPRT (NIST). Seules les sous-catégories actives sont importées :
    celles retirées par rapport à CSF 1.1 pointent vers un élément `WR-*`."""

    code = "nist-csf"
    nom = "NIST Cybersecurity Framework"
    version = "2.0"
    editeur = "NIST"
    licence = Licence.LIBRE
    url = "https://csrc.nist.gov/extensions/nudp/services/json/nudp/framework/version/csf_2_0_0/export/json?element=all"
    url_reference = "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf"
    nom_fichier = "csf-2.0.json"

    def lire(self, chemin):
        donnees = json.loads(chemin.read_text(encoding="utf-8"))["response"]["elements"]
        elements = {e["element_identifier"]: e for e in donnees["elements"]}
        relations = donnees["relationships"]
        retires = {
            r["source_element_identifier"]
            for r in relations
            if r["relationship_identifier"] == "projection" and r["dest_element_identifier"].startswith("WR-")
        }
        tri = {e["element_identifier"][2:]: e["title"] for e in donnees["elements"] if e["element_type"] == "sort"}

        mesures = []
        for ident, e in elements.items():
            if e["element_type"] != "subcategory" or ident in retires:
                continue
            code_categorie = ident.split("-")[0]
            categorie = elements[code_categorie]
            fonction = elements[code_categorie.split(".")[0]]
            mesures.append(
                MesureImportee(
                    identifiant=ident,
                    intitule=e["text"],
                    categorie=f"{fonction['title'].capitalize()} › {code_categorie} {categorie['title']}",
                    texte=e["text"],
                )
            )
        mesures.sort(key=lambda m: tri.get(m.identifiant, m.identifiant))
        return mesures
