# Premiers pas

Après [l'installation](02-installation.md), quatre choses à faire, dans l'ordre.

## 1. Les référentiels

Vérifiez qu'ils sont importés : menu **Bibliothèque** (barre latérale). Vous devez y voir au moins NIST CSF, OWASP ASVS et le guide d'hygiène ANSSI ; II 901 et RGS si vous avez déposé leurs fichiers. Sinon : [importer les référentiels](08-referentiels.md).

## 2. L'organisation et les comptes

Une installation peut servir **plusieurs organisations**, totalement cloisonnées (un cabinet et ses clients, plusieurs directions). Chaque compte appartient à une seule organisation.

```bash
# Première organisation et son administrateur (qui administre aussi l'installation)
docker compose exec backend python manage.py creer_organisation --nom "Ma collectivité" --email admin@exemple.fr --admin-installation

# Collègues
docker compose exec backend python manage.py creer_utilisateur --organisation ma-collectivite --email rssi@exemple.fr --prenom Camille --nom-famille Martin --fonction RSSI
docker compose exec backend python manage.py creer_utilisateur --organisation ma-collectivite --email audit@exemple.fr --role auditeur
```

Rôles d'**organisation** :

| Rôle | Effet |
|---|---|
| `admin` | Voit tous les projets de l'organisation, règle l'organisation (dont « autoriser l'IA »), voit le journal hors projet. |
| `membre` | Voit les projets dont il est acteur. C'est le cas général. |
| `auditeur` | Lecture seule partout où il est acteur. |

Les rôles **dans un projet** (chef de projet, RSSI, autorité d'homologation, contributeur, auditeur) se donnent dans le projet : voir [rôles et droits](09-roles-et-droits.md).

> Il n'existe pas encore d'écran de gestion des comptes : utilisez ces commandes, ou l'admin Django (<http://localhost:8000/admin/>) pour désactiver un compte ou changer son rôle.

## 3. (Facultatif) L'IA

Connectez-vous avec le compte administrateur de l'installation, ouvrez **Administration** (bas de la barre latérale), section **Intelligence artificielle**. Sans rien faire, SoluGation fonctionne sans IA. Voir [Intelligence artificielle](07-ia.md).

## 4. Le premier projet

Sur la page d'accueil, **Créer un projet** (ou, depuis le sélecteur de projet en haut de la barre latérale, **Nouveau projet**). Le [tutoriel](05-tutoriel.md) déroule ensuite une homologation complète.

À la première connexion, chaque compte se voit proposer une **visite guidée** de tous les écrans sur un projet d'exemple qui lui est propre (voir [Aide et visite guidée](06-guide-utilisateur.md#aide-et-visite-guidée)).

## Se repérer dans l'interface

- **Barre latérale** : le sélecteur de projet en haut, les rubriques du projet, puis Réglages, Bibliothèque, Administration, le choix du thème (système, clair, sombre) et votre compte.
- **Cloche** : vos notifications ; un clic ouvre l'élément concerné.
- **Sur mobile** : une barre d'onglets en bas (Accueil, Mesures, Documents, Actions) et un bouton pour déposer un document.
- **Mails** : en développement, ouvrez <http://localhost:8025> (Mailpit) pour voir ce qui serait envoyé.
