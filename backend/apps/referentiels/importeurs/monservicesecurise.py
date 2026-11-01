"""Référentiel de mesures de MonServiceSécurisé (ANSSI, homologation des services publics en ligne).

Source : dépôt public betagouv/mon-service-securise, licence Apache-2.0, figé sur un commit (reproductible) :
`donneesReferentielMesuresV2.ts` (intitulé, description, catégorie, origine ANSSI ou CNIL) et
`donneesComplementairesReferentielMesuresV2.ts` (thématique, porteurs suggérés).

Les fichiers sont du TypeScript : ils ne sont jamais exécutés. Seul l'objet littéral exporté est lu, par un
analyseur restreint (chaînes, objets, tableaux) qui refuse toute autre construction.
"""

import html
import re
import urllib.request

from apps.referentiels.models import Licence

from .base import ErreurImport, Importeur, MesureImportee

COMMIT = "b9897f1ef3c9483b9d57814275f3b9d8eecc846f"  # 30/10/2026
DEPOT = "https://github.com/betagouv/mon-service-securise"
BRUT = f"https://raw.githubusercontent.com/betagouv/mon-service-securise/{COMMIT}"
MESURES = "donneesReferentielMesuresV2.ts"
COMPLEMENTS = "donneesComplementairesReferentielMesuresV2.ts"

CATEGORIES = {"gouvernance": "Gouvernance", "protection": "Protection", "defense": "Défense", "resilience": "Résilience"}

JETON = re.compile(r"""
    (?P<espace>\s+|//[^\n]*|/\*.*?\*/)
  | (?P<chaine>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")
  | (?P<nom>[A-Za-z_$][\w$]*)
  | (?P<signe>[{}\[\]:,])
""", re.S | re.X)
ECHAPPEMENTS = {"n": "\n", "t": "\t", "r": "\r", "'": "'", '"': '"', "\\": "\\", "`": "`"}


def _jetons(texte, debut):
    i = debut
    while i < len(texte):
        m = JETON.match(texte, i)
        if not m:
            raise ErreurImport(f"Construction inattendue dans la source TypeScript : {texte[i:i + 40]!r}")
        i = m.end()
        if m.lastgroup != "espace":
            yield m.lastgroup, m.group(), i


def objet_exporte(texte, nom):
    """Valeur de `export const <nom>… = { … }` : objets, tableaux et chaînes uniquement."""
    m = re.search(rf"export const {re.escape(nom)}\b[^=]*=\s*", texte)
    if not m:
        raise ErreurImport(f"Export « {nom} » introuvable : format de la source modifié ?")
    flux = _jetons(texte, m.end())

    def valeur(jeton=None):
        genre, brut, _ = jeton or next(flux)
        if genre == "chaine":
            return re.sub(r"\\(.)", lambda e: ECHAPPEMENTS.get(e.group(1), e.group(1)), brut[1:-1])
        if brut == "{":
            resultat = {}
            while True:
                genre, cle, _ = next(flux)
                if cle == "}":
                    return resultat
                if genre not in ("chaine", "nom") or next(flux)[1] != ":":
                    raise ErreurImport(f"Clé inattendue : {cle!r}")
                resultat[valeur((genre, cle, 0)) if genre == "chaine" else cle] = valeur()
                fin = next(flux)[1]
                if fin == "}":
                    return resultat
                if fin != ",":
                    raise ErreurImport(f"Séparateur inattendu : {fin!r}")
        if brut == "[":
            resultat = []
            while True:
                jeton = next(flux)
                if jeton[1] == "]":
                    return resultat
                resultat.append(valeur(jeton))
                fin = next(flux)[1]
                if fin == "]":
                    return resultat
                if fin != ",":
                    raise ErreurImport(f"Séparateur inattendu : {fin!r}")
        raise ErreurImport(f"Valeur inattendue : {brut!r}")

    try:
        return valeur()
    except StopIteration:
        raise ErreurImport("Source TypeScript tronquée.") from None


def texte_brut(fragment):
    """Description longue : `<br>` en sauts de ligne, autres balises retirées, entités décodées."""
    fragment = re.sub(r"<br\s*/?>", "\n", fragment)
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


class MonServiceSecurise(Importeur):
    code = "monservicesecurise"
    nom = "MonServiceSécurisé : référentiel de mesures"
    version = f"V2 ({COMMIT[:7]})"
    editeur = "ANSSI (MonServiceSécurisé)"
    licence = Licence.APACHE_2
    url_reference = DEPOT
    fichiers_attendus = (MESURES, COMPLEMENTS)

    def obtenir_fichier(self):
        if not self.fichier:  # téléchargement depuis le commit figé, une seule fois
            dossier = self.dossier_sources()
            dossier.mkdir(parents=True, exist_ok=True)
            for nom in self.fichiers_attendus:
                if not (dossier / nom).is_file():
                    requete = urllib.request.Request(f"{BRUT}/{nom}", headers={"User-Agent": "SoluGation-import/1.0"})
                    with urllib.request.urlopen(requete, timeout=60) as reponse:
                        (dossier / f"{nom}.part").write_bytes(reponse.read())
                    (dossier / f"{nom}.part").rename(dossier / nom)
        return super().obtenir_fichier()

    def lire(self, chemin):
        mesures = objet_exporte((chemin / MESURES).read_text(encoding="utf-8"), "mesuresV2")
        complements = objet_exporte((chemin / COMPLEMENTS).read_text(encoding="utf-8"), "donneesComplementairesMesureV2")
        resultat = []
        for identifiant, m in sorted(mesures.items(), key=lambda e: e[1].get("identifiantNumerique", "")):
            plus = complements.get(identifiant, {})
            details = [texte_brut(m.get("descriptionLongue", ""))]
            if plus.get("porteursSinguliers"):
                details.append(f"Porteurs suggérés : {', '.join(plus['porteursSinguliers'])}.")
            if m.get("referentiel") == "CNIL":
                details.append("Mesure issue des recommandations de la CNIL.")
            resultat.append(MesureImportee(
                identifiant=identifiant,
                intitule=m["description"].strip(),
                categorie=plus.get("thematique") or CATEGORIES.get(m.get("categorie", ""), ""),
                texte="\n\n".join(d for d in details if d),
            ))
        return resultat
