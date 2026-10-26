"""Couche d'abstraction des fournisseurs d'IA. Le reste du code n'appelle que `obtenir_fournisseur()` et
`completer_json()` : changer de fournisseur (ou passer en local) ne touche ni l'analyse ni l'API.

Tous les fournisseurs distants passent par l'API « compatible OpenAI » (`/chat/completions`), que parlent
Mistral, Scaleway Generative APIs, OVHcloud AI Endpoints, IONOS AI Model Hub, Ollama et vLLM.

Confidentialité (CLAUDE.md : aucun document client conservé par le fournisseur) :
- Scaleway applique par défaut la conservation zéro, sans entraînement (hébergement en France) : fournisseur
  recommandé. Mistral garde par défaut 30 jours, sauf ZDR accordé sur demande.
- Quel que soit le fournisseur, l'envoi est refusé tant que la conservation zéro n'est pas confirmée
  explicitement dans la configuration, après vérification des conditions contractuelles (DPA).
- On n'utilise que `chat/completions`, sans état (jamais Files, Agents, Batch : stockés par le fournisseur).
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


class CompatibleOpenAI(Fournisseur):
    ESSAIS = 4

    def __init__(self, nom, url, modele, cle="", zdr_confirme=False, cle_requise=True, delai=120):
        self.nom, self.url, self.modele, self.cle = nom, url.rstrip("/"), modele, cle
        self.zdr_confirme, self.cle_requise, self.delai = zdr_confirme, cle_requise, delai

    def verifier_configuration(self):
        if not self.zdr_confirme:
            raise IAIndisponible(f"Envoi au fournisseur d'IA ({self.nom}) bloqué : la conservation zéro (ZDR) "
                                 "n'est pas confirmée dans la configuration.")
        if not self.url or not self.modele:
            raise IAIndisponible("URL ou modèle du fournisseur d'IA absent de la configuration.")
        if self.cle_requise and not self.cle:
            raise IAIndisponible(f"Clé d'API {self.nom} absente de la configuration.")

    def completer_json(self, systeme, utilisateur):
        self.verifier_configuration()  # garde-fou répété au plus près de l'envoi
        corps = json.dumps({
            "model": self.modele,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}],
        }).encode()
        entetes = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.cle:
            entetes["Authorization"] = f"Bearer {self.cle}"
        for essai in range(self.ESSAIS):
            requete = urllib.request.Request(f"{self.url}/chat/completions", data=corps, method="POST", headers=entetes)
            try:
                with urllib.request.urlopen(requete, timeout=self.delai) as r:  # noqa: S310 (URL fixée par la config)
                    reponse = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and essai < self.ESSAIS - 1:
                    attente = min(float(e.headers.get("Retry-After") or 2 ** (essai + 1)), 30)
                    journal.warning("%s HTTP %s, nouvel essai dans %ss", self.nom, e.code, attente)
                    time.sleep(attente)
                    continue
                raise IAIndisponible(f"Le fournisseur d'IA a refusé la requête (HTTP {e.code}).") from None
            except (urllib.error.URLError, TimeoutError):
                if essai < self.ESSAIS - 1:
                    time.sleep(2 ** (essai + 1))
                    continue
                raise IAIndisponible("Fournisseur d'IA injoignable.") from None
        try:
            texte = reponse["choices"][0]["message"]["content"].strip()
            # Certains petits modèles entourent le JSON d'un bloc de code malgré le mode JSON.
            texte = re.sub(r"^```(?:json)?\s*|\s*```$", "", texte)
            contenu = json.loads(texte)
        except (KeyError, IndexError, TypeError, AttributeError, json.JSONDecodeError):
            raise IAIndisponible("Réponse du fournisseur d'IA illisible.") from None
        usage = reponse.get("usage") or {}
        return ReponseIA(contenu if isinstance(contenu, dict) else {}, usage.get("prompt_tokens", 0),
                         usage.get("completion_tokens", 0))


class Factice(Fournisseur):
    """Fournisseur hors ligne, pour le développement et les démonstrations sans clé : rapproche les mots de
    l'intitulé de chaque mesure des phrases du document, et produit des recommandations et une rédaction de rapport génériques. Aucune donnée ne sort de la machine. Ses résultats
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

    MANQUEMENT = re.compile(r'<manquement cle="(?P<cle>[^"]+)">\n(?P<corps>.*?)\n</manquement>', re.S)

    def _recommandations(self, utilisateur):
        recos = []
        for m in self.MANQUEMENT.finditer(utilisateur):
            exigence = re.search(r"^Exigence : \[[^\]]+\] (.+)$", m["corps"], re.M)
            objet = (exigence[1] if exigence else re.search(r"^Tâche : (.+)$", m["corps"], re.M)[1]).rstrip(". ")
            recos.append({
                "tache": m["cle"], "effort": "moyen",
                "synthese": f"Mettre en œuvre l'exigence « {objet[:120]} » et en conserver la trace (fournisseur de test).",
                "etapes": ["Désigner un porteur et préciser le périmètre concerné",
                           f"Mettre en œuvre : {objet[:200]}",
                           "Documenter la mise en œuvre et la faire relire par le RSSI"],
                "preuve": "Procédure validée et capture ou export de configuration datés.",
            })
        return ReponseIA({"recommandations": recos}, len(utilisateur) // 4, 0)

    def _rapport(self, utilisateur):
        d = json.loads(utilisateur.split("\n", 1)[1])
        c = d["conformite"]
        texte = (f"Rédaction de test hors ligne : {c['conforme']} mesures conformes, {d['nb_manquements']} manquements, "
                 f"{d['plan_action']['ouvertes']} tâches ouvertes.")
        return ReponseIA({"sections": [{"cle": cle, "texte": texte} for cle in
                                       ("synthese", "conformite", "documents", "plan_action", "suite")]}, len(utilisateur) // 4, 0)

    def completer_json(self, systeme, utilisateur):
        if utilisateur.startswith("Données du projet (JSON)"):
            return self._rapport(utilisateur)
        if "<manquement " in utilisateur:
            return self._recommandations(utilisateur)
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
    choix = settings.IA_FOURNISSEUR
    if choix == "factice":
        return Factice()
    if choix == "mistral":
        return CompatibleOpenAI("mistral", settings.MISTRAL_URL, settings.MISTRAL_MODELE, settings.MISTRAL_API_KEY,
                                settings.MISTRAL_ZDR_CONFIRME)
    if choix == "scaleway":
        return CompatibleOpenAI("scaleway", settings.IA_URL or "https://api.scaleway.ai/v1",
                                settings.IA_MODELE or "mistral-small-3.2-24b-instruct-2506", settings.IA_CLE,
                                settings.IA_ZDR_CONFIRME)
    if choix == "compatible":  # OVHcloud, IONOS, Ollama ou vLLM auto-hébergé… (clé facultative en local)
        return CompatibleOpenAI(settings.IA_NOM or "compatible", settings.IA_URL, settings.IA_MODELE, settings.IA_CLE,
                                settings.IA_ZDR_CONFIRME, cle_requise=False)
    raise IAIndisponible("Fournisseur d'IA inconnu dans la configuration.")
