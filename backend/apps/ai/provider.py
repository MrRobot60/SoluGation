"""Couche d'abstraction des fournisseurs d'IA. Le reste du code n'appelle que `obtenir_fournisseur()` et
`completer_json()` : changer de fournisseur (ou passer en local) ne touche ni l'analyse ni l'API.

Confidentialité (CLAUDE.md : aucun document client conservé par le fournisseur) :
- Mistral garde par défaut entrées et sorties 30 jours (surveillance des abus), sauf « Zero Data Retention »
  (ZDR), accordé sur demande et limité aux endpoints sans état. On n'utilise donc que `chat/completions`
  (jamais Files, Agents, Batch, Conversations), et l'envoi est refusé tant que `MISTRAL_ZDR_CONFIRME` n'est pas
  posé après activation du ZDR et refus de l'entraînement dans la console Mistral (Admin › Privacy).
- Les messages d'erreur ne reprennent jamais le contenu envoyé ni la clé d'API.
"""

import json
import logging
import re
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings

journal = logging.getLogger(__name__)


class IAIndisponible(Exception):
    """Configuration ou fournisseur inutilisable : message affichable tel quel à l'utilisateur."""


@dataclass
class ReponseIA:
    contenu: dict
    jetons_entree: int = 0
    jetons_sortie: int = 0


class Fournisseur:
    nom = ""
    modele = ""

    def verifier_configuration(self):
        """Lève IAIndisponible si un appel ne peut pas partir (appelé avant de créer l'analyse)."""

    def completer_json(self, systeme: str, utilisateur: str) -> ReponseIA:
        raise NotImplementedError


class Mistral(Fournisseur):
    nom = "mistral"
    ESSAIS = 4

    def __init__(self, cle, modele, url, zdr_confirme, delai=120):
        self.cle, self.modele, self.url, self.zdr_confirme, self.delai = cle, modele, url.rstrip("/"), zdr_confirme, delai

    def verifier_configuration(self):
        if not self.zdr_confirme:
            raise IAIndisponible("Envoi à Mistral bloqué : la conservation zéro (ZDR) n'est pas confirmée dans la configuration.")
        if not self.cle:
            raise IAIndisponible("Clé d'API Mistral absente de la configuration.")

    def completer_json(self, systeme, utilisateur):
        self.verifier_configuration()  # garde-fou répété au plus près de l'envoi
        corps = json.dumps({
            "model": self.modele,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}],
        }).encode()
        for essai in range(self.ESSAIS):
            requete = urllib.request.Request(f"{self.url}/chat/completions", data=corps, method="POST", headers={
                "Authorization": f"Bearer {self.cle}", "Content-Type": "application/json", "Accept": "application/json",
            })
            try:
                with urllib.request.urlopen(requete, timeout=self.delai) as r:  # noqa: S310 (URL fixée par la config)
                    reponse = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and essai < self.ESSAIS - 1:
                    attente = min(float(e.headers.get("Retry-After") or 2 ** (essai + 1)), 30)
                    journal.warning("Mistral HTTP %s, nouvel essai dans %ss", e.code, attente)
                    time.sleep(attente)
                    continue
                raise IAIndisponible(f"Le fournisseur d'IA a refusé la requête (HTTP {e.code}).") from None
            except (urllib.error.URLError, TimeoutError):
                if essai < self.ESSAIS - 1:
                    time.sleep(2 ** (essai + 1))
                    continue
                raise IAIndisponible("Fournisseur d'IA injoignable.") from None
        try:
            contenu = json.loads(reponse["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise IAIndisponible("Réponse du fournisseur d'IA illisible.") from None
        usage = reponse.get("usage") or {}
        return ReponseIA(contenu if isinstance(contenu, dict) else {}, usage.get("prompt_tokens", 0),
                         usage.get("completion_tokens", 0))


class Factice(Fournisseur):
    """Fournisseur hors ligne, pour le développement et les démonstrations sans clé : rapproche les mots de
    l'intitulé de chaque mesure des phrases du document. Aucune donnée ne sort de la machine. Ses résultats
    sont marqués `factice` et n'ont aucune valeur d'analyse."""

    nom = "factice"
    modele = "mots-cles-v1"
    MESURE = re.compile(r"^- \[(?P<id>[^\]]+)\] (?P<intitule>.+)$", re.M)
    DOCUMENT = re.compile(r"<document[^>]*>\n(?P<texte>.*)\n</document>", re.S)
    VIDES = {"les", "des", "une", "pour", "dans", "avec", "sont", "être", "leur", "leurs", "afin", "doit", "doivent",
             "cette", "ces", "par", "sur", "aux", "son", "ses", "tout", "tous", "toute", "toutes", "plus", "moins"}

    @staticmethod
    def _racines(texte):
        texte = unicodedata.normalize("NFC", texte).lower()  # intitulés importés parfois en NFD (accents combinants)
        return {m[:6] for m in re.findall(r"[a-zàâçéèêëîïôûùüÿœ]{4,}", texte)}

    def completer_json(self, systeme, utilisateur):
        document = self.DOCUMENT.search(utilisateur)
        phrases = [p.strip() for p in re.split(r"(?<=[.;:!?])\s+|\n+", document["texte"] if document else "") if len(p.strip()) > 30]
        racines_phrases = [(p, self._racines(p)) for p in phrases]
        resultats = []
        for m in self.MESURE.finditer(utilisateur):
            cles = self._racines(m["intitule"].split(" (thème :")[0]) - {v[:6] for v in self.VIDES}
            if len(cles) < 2:
                continue
            meilleure, communs = max(((p, len(cles & r)) for p, r in racines_phrases), key=lambda x: x[1], default=("", 0))
            ratio = communs / len(cles)
            if communs >= 2 and ratio >= 0.4:
                resultats.append({
                    "mesure": m["id"], "couverture": "couvert" if ratio >= 0.7 else "partiel",
                    "justification": f"{communs} termes de l'exigence retrouvés dans le document (fournisseur de test).",
                    "extraits": [meilleure[:300]], "confiance": round(min(ratio, 0.9), 2),
                })
        return ReponseIA({"resultats": resultats}, len(utilisateur) // 4, 0)


def obtenir_fournisseur() -> Fournisseur:
    if settings.IA_FOURNISSEUR == "mistral":
        return Mistral(settings.MISTRAL_API_KEY, settings.MISTRAL_MODELE, settings.MISTRAL_URL, settings.MISTRAL_ZDR_CONFIRME)
    if settings.IA_FOURNISSEUR == "factice":
        return Factice()
    raise IAIndisponible("Fournisseur d'IA inconnu dans la configuration.")
