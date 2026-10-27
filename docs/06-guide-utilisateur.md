# Guide de l'utilisateur

Chaque écran, ce qu'il montre et ce qu'on peut y faire. Les droits nécessaires sont rappelés ; le détail est dans [rôles et droits](09-roles-et-droits.md). Les fonctions marquées ✦ n'apparaissent que si l'IA est configurée et autorisée pour votre organisation.

## Connexion

Adresse email et mot de passe. Après plusieurs échecs, les tentatives sont freinées (10 par minute). La session dure deux semaines (valeur par défaut de Django) ; **Quitter** (bas de la barre latérale) déconnecte.

## Tableau de bord

| Bloc | Contenu |
|---|---|
| En-tête | Nom, statut, type de bien, niveau visé, prochaine revue |
| Synthèse | Taux d'évaluation, mesures conformes / applicables, tâches ouvertes, date de décision visée |
| Carte des mesures | Une tuile par mesure et par référentiel, colorée selon son état (conforme, partiel, manquant, non applicable, non évalué) |
| Pour vous | Vos tâches et documents, les décisions qui vous attendent (dérogations, risques à statuer, revue), votre prochaine réunion |
| À valider ✦ | Les conclusions de la dernière analyse IA en attente |
| Activité | Les derniers événements du projet |

## Créer un projet

Assistant en cinq étapes : **le bien** (nom, type, description), **référentiels** (1 à 3, + EBIOS RM facultatif), **niveau visé** (élémentaire, standard, renforcé : il détermine les pièces attendues), **acteurs** (comptes ou contacts externes, avec un rôle), **récapitulatif** (génération de la checklist). Le créateur devient chef de projet.

## Documents

- **Checklist** des documents attendus, filtrable (tous, à déposer, en relecture, validés…), avec responsable et échéance (en rouge si dépassée).
- **Déposer** : glisser un fichier sur la ligne ou « choisir un fichier ». Contrôles : type réel du contenu (pas l'extension), taille, macros Office refusées, archives piégées refusées. Le fichier est empreinté (SHA-256) et rangé sous un nom régénéré.
- **Versions** : chaque dépôt crée une version ; toutes restent téléchargeables (téléchargement tracé).
- **Valider / refuser** une pièce : RSSI, autorité d'homologation, administrateur.
- **Autres pièces** : dépôts hors checklist.
- ✦ **Analyse IA** : voir le [tutoriel, étape 3](05-tutoriel.md). Les images et PDF scannés (sans texte) ne sont pas analysés (pas de reconnaissance de caractères).

## Mesures

- Onglets par **référentiel**, filtres par état, recherche. Un compteur ✦ signale les propositions de l'IA par référentiel.
- **Évaluer** : conforme, partiel (justification requise), manquant, non applicable (justification requise). Un manquement crée sa tâche.
- ✦ **Proposition de l'IA** : passages cités, confiance estimée. Accepter ou rejeter : RSSI, autorité, administrateur.
- **Preuves** : déposer, versionner, rattacher à plusieurs mesures.

## Plan d'action

- Liste filtrable : ouvertes, en retard, mes tâches, clôturées, toutes.
- **Fiche de tâche** : titre, statut, responsable, échéance, priorité, preuve attendue, description ; commentaires ; historique (journal d'audit).
- Une tâche ne se supprime pas : elle s'**abandonne** (elle reste dans l'historique).
- **Origine** affichée : manquement évalué, proposition IA validée, scan, EBIOS RM, réunion, saisie manuelle.
- ✦ **Recommandations** : étapes et preuve suggérées ; accepter (ajout à la description, preuve reprise si vide ou générique) ou rejeter.
- Rattrapage : « Créer les tâches des manquements déjà évalués ».

## Scans de vulnérabilités

- Formats : **Nessus** (`.nessus`), **OpenVAS / Greenbone** (`.xml`), **CSV** (Cyberwatch et autres : colonnes reconnues en français ou en anglais : actif, CVE, CVSS, criticité, titre, solution…).
- Bilan : par sévérité, nouveaux / déjà vus / disparus par rapport au scan précédent du même outil.
- Vulnérabilités regroupées (tous hôtes) : hôtes, CVE, description, solution.
- **Créer les tâches** des vulnérabilités cochées, ou de toutes les hautes et critiques. Priorité et échéance selon la sévérité (critique 15 j, haute 30, moyenne 60, faible 90).
- **Faux positif** (justifié) : membres qui écrivent. **Risque accepté** : décisionnaires. Ces qualifications sont reprises aux scans suivants.

## Risques et dérogations

- **Risques résiduels** : intitulé, gravité × vraisemblance, propriétaire, date de revue. Décisions (RSSI, autorité, administrateur) : **accepter** (motif + date de revue future), **clore**, **rouvrir**. Modifier la cotation d'un risque accepté lève l'acceptation.
- **Dérogations** : sur une mesure manquante/partielle ou un risque ; motif, mesures compensatoires, échéance proposée. Décisions : **accepter** (date d'expiration future), **refuser** (motif obligatoire), **révoquer**. Figées après décision ; expirées automatiquement.

## EBIOS RM

Activable par projet (Réglages). Cinq ateliers, avancement par atelier (non commencé, en cours, terminé), date, participants et notes. Voir le [tutoriel, étape 7](05-tutoriel.md).

Règles de cohérence : un scénario stratégique part d'un couple **retenu** ; un scénario opérationnel doit découler du scénario stratégique choisi. Menace d'une partie prenante = (dépendance × pénétration) / (maturité cyber × confiance) ; seuils par défaut : danger ≥ 2,5, contrôle ≥ 0,9.

## Réunions

- À venir / passées. **Planifier** : objet, début, fin, lieu, visio, participants (acteurs du projet), ordre du jour ; invitation d'agenda envoyée (décochable).
- Modifier l'horaire, le lieu ou les participants envoie une **mise à jour** ; **annuler** envoie une annulation (organisateur ou administrateur du projet).
- **Compte rendu** : brouillon, puis **valider et diffuser** (figé, envoyé aux participants y compris externes).
- **Actions décidées** : deviennent des tâches.

## Rapports

- **Générer un état des lieux** : instantané des données, rédaction ✦ par l'IA ou texte automatique.
- Sections modifiables tant que le rapport n'est pas validé ; chiffres non retrouvés dans les données signalés.
- **Aperçu PDF** (brouillon, filigrané, jamais stocké) ; **Valider et figer le PDF** (RSSI, autorité, administrateur) : PDF figé, empreinte SHA-256.
- PDF : couverture, synthèse chiffrée et écarts, sections, annexes (conformité par référentiel, manquements, documents, plan d'action, risques et dérogations, EBIOS RM, acteurs).
- **Comparer deux versions** : indicateurs et écarts, manquements résolus / apparus, documents et tâches, différentiel du texte.

## Journal d'audit

- Par projet (barre latérale) ou pour toute l'organisation (Administration, administrateur).
- Filtres : action, auteur, période, recherche ; entrées hors projet (connexions, réglages) pour l'administrateur.
- Détail : valeurs avant → après, adresse IP, empreintes.
- **Exporter (CSV)** : tracé au journal.
- **Vérifier l'intégrité** (administrateur) : recalcule la chaîne de hachage ; conservez la dernière empreinte hors de l'application.

## Réglages du projet

Chef de projet, RSSI, autorité d'homologation ou administrateur. Les autres consultent.

- **Projet** : nom, type, niveau, description, avancement (brouillon, en cours, en attente de décision).
- **Référentiels** : 1 à 3 ; un référentiel retiré masque ses évaluations (rien n'est supprimé).
- **Acteurs et rôles** : ajouter un compte ou un contact externe, changer un rôle, retirer (il reste toujours un chef de projet).
- **Options** : EBIOS RM, notifications, calendrier (export `.ics` des échéances).
- **Revue périodique** : périodicité, prochaine date, « la revue a eu lieu ».
- **Décision d'homologation** : autorité d'homologation seule.
- **Archivage** : lecture seule pour tous ; désarchivage possible.

## Bibliothèque

Référentiels disponibles (communs et copies privées de l'organisation), mesures par catégorie, recherche dans un ou tous les référentiels, fiche de mesure (texte, état dans vos projets, **correspondances** avec d'autres référentiels, propres à votre organisation).

## Administration

- **Intelligence artificielle** (administrateur de l'installation) : voir [IA](07-ia.md).
- **Organisation** (administrateur d'organisation) : autoriser ou non l'IA pour l'organisation.
- Lien vers le **journal d'audit** de toute l'organisation.

## Aide et visite guidée

- **Aide** (barre latérale, ou **?** en haut sur mobile) : cette documentation, avec recherche (insensible aux accents) et sommaire de page. Depuis un écran, le bouton ouvre directement la section correspondante de ce guide.
- **Visite guidée** : proposée à la première connexion. **Commencer la visite** crée un **projet d'exemple** personnel (« Exemple — Intranet RH », marqué *Projet d'exemple*, notifications coupées), puis parcourt chaque écran. Flèches ← → du clavier pour naviguer, **Échap** ou **Plus tard** pour reprendre à la prochaine session au même endroit, **Passer** ou **Ne plus proposer** pour l'arrêter. **Revoir la visite guidée** sur l'accueil de l'Aide la relance (le projet d'exemple est réutilisé). Un compte en lecture seule visite un projet existant sans rien créer.
- Le projet d'exemple se modifie librement ; archivez-le (Réglages du projet) quand vous n'en avez plus besoin.

## Notifications et mails

La cloche affiche les notifications ; un mail part en parallèle (sauf si le projet a désactivé les notifications). L'auteur d'une action n'est jamais notifié de sa propre action. Un mail par destinataire : aucune adresse n'est exposée aux autres. Les contacts externes reçoivent les mails, sans accès à l'appli.
