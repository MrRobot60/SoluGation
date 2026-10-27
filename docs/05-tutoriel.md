# Tutoriel : une homologation complète

Nous allons homologuer **« Portail des démarches »**, une application web, au niveau **Standard**, selon le **guide d'hygiène ANSSI** et le **RGS**, avec une analyse de risques **EBIOS RM**.

Comptez une heure. Prérequis : SoluGation installé, référentiels importés, et trois comptes dans votre organisation (vous, un collègue RSSI, et l'autorité d'homologation, qui peut être un contact externe). Voir [premiers pas](04-premiers-pas.md).

> Les étapes marquées ✦ utilisent l'IA. Sans IA configurée, faites la même chose à la main : rien ne bloque.

---

## Étape 1 — Créer le projet

1. **Créer un projet** (page d'accueil) ou **Nouveau projet** dans le sélecteur de projet.
2. **Le bien** : nom « Portail des démarches », type **Application**, une description courte.
3. **Référentiels** : cochez le guide d'hygiène ANSSI et le RGS (3 au maximum). Activez **EBIOS RM** : c'est une méthode, elle ne compte pas dans la limite.
4. **Niveau visé** : **Standard** (dossier complet, audit et test d'intrusion).
5. **Acteurs** : vous êtes chef de projet d'office. Ajoutez votre collègue comme **RSSI** et l'autorité d'homologation (un compte, ou un contact externe avec son email).
6. **Récapitulatif** : laissez « Générer la checklist des documents attendus » coché, puis **Créer le projet**.

Vous arrivez sur le **tableau de bord** : synthèse (évaluation, conformité, plan d'action, date de décision visée), carte des mesures par référentiel, « Pour vous » (vos tâches, documents et décisions en attente), activité récente.

## Étape 2 — La checklist documentaire

Menu **Documents**. La checklist a été générée selon le contexte (type de bien, niveau, référentiels) : PSSI, analyse de risques, dossier d'architecture, stratégie d'homologation… chacun avec un responsable et une échéance.

1. Ouvrez une ligne pour voir le détail et les mesures que le document couvre.
2. **Déposez** un fichier en le glissant sur la ligne (ou « choisir un fichier ») : PDF, Word, Excel, OpenDocument, texte, CSV, XML, images ; 50 Mo maximum. Le type réel est vérifié, le fichier empreinté (SHA-256), son nom régénéré.
3. Un nouveau dépôt sur la même ligne crée une **nouvelle version** ; les précédentes restent téléchargeables.
4. Le **RSSI** (ou l'autorité, ou l'administrateur) **valide** ou **refuse** la pièce. Une pièce refusée reste « Refusé » jusqu'au dépôt d'une nouvelle version, qui la repasse « En relecture ».

## Étape 3 — ✦ L'analyse IA des documents

Toujours dans **Documents**, carte **Analyse IA** → **Analyser les documents**. L'IA lit la dernière version de chaque document et propose, mesure par mesure, **couvert / partiel / absent**, avec les passages cités (une conclusion sans citation retrouvée mot pour mot dans le document est écartée).

Quand c'est terminé : **Voir les propositions** (ou menu **Mesures**, filtre « IA à valider »).

## Étape 4 — Évaluer les mesures

Menu **Mesures**. Choisissez le référentiel en haut, filtrez (non évaluées, manquantes…), cherchez par identifiant ou intitulé.

Pour chaque mesure :

1. Lisez le texte de la mesure.
2. ✦ Si l'IA a fait une proposition : le **RSSI** l'**accepte** (elle devient l'évaluation) ou la **rejette**.
3. Sinon, évaluez : **Conforme**, **Partiel**, **Manquant** ou **Non applicable**. Une justification est demandée pour « partiel » et « non applicable ».
4. Rattachez des **preuves** (fichiers versionnés et empreintés), réutilisables d'une mesure à l'autre.

Chaque mesure **manquante** ou **partielle** crée automatiquement une **tâche** dans le plan d'action (priorité haute à 30 jours pour un manquement, moyenne à 60 jours pour un partiel), assignée au RSSI ou, à défaut, au chef de projet.

## Étape 5 — Le plan d'action

Menu **Plan d'action**. Filtres : ouvertes, en retard, mes tâches, clôturées.

1. Ouvrez une tâche : statut (à faire, en cours, en revue, terminée), responsable, échéance, priorité, **preuve attendue**, description.
2. Commentez : le responsable, les chefs de projet et les personnes qui ont déjà commenté sont prévenus (appli et mail). Les commentaires ne se modifient pas.
3. L'**historique** (issu du journal d'audit) montre chaque changement.
4. ✦ **Proposer des recommandations** : l'IA rédige, pour chaque tâche ouverte, les étapes pour combler le manquement et la preuve à fournir. Acceptée, la recommandation s'ajoute à la description (sans rien effacer).

## Étape 6 — Les scans de vulnérabilités

Menu **Scans de vulnérabilités**. Déposez un rapport **Nessus** (`.nessus`), **OpenVAS** (`.xml`) ou un export **CSV** (Cyberwatch…).

1. Le bilan s'affiche : constats par sévérité, nouveaux / déjà vus / disparus depuis le scan précédent.
2. Dépliez une vulnérabilité : hôtes, CVE, solution proposée.
3. Cochez celles à traiter puis **Créer les tâches** (ou « toutes les hautes et critiques ») : **une tâche par vulnérabilité**, tous hôtes confondus, jamais en double.
4. Un faux positif se marque avec justification ; un risque accepté est réservé aux décisionnaires.

## Étape 7 — L'analyse de risques EBIOS RM

Menu **EBIOS RM**. Les cinq ateliers sont accessibles dans l'ordre voulu ; les incohérences sont signalées par atelier.

1. **Atelier 1 — Cadrage et socle** : valeurs métier (processus, informations), événements redoutés avec leur gravité (1 à 4), biens supports. **Pré-remplir depuis la conformité** crée les écarts au socle à partir de vos mesures manquantes ou partielles. ✦ **Proposer avec l'IA** suggère événements redoutés et biens supports.
2. **Atelier 2 — Sources de risque** : sources (cybercriminel, hacktiviste, État, interne…), objectifs visés, couples évalués (motivation, ressources, activité, pertinence) ; **cochez « retenu »** pour ceux à étudier. ✦ L'IA propose des couples, jamais retenus d'office.
3. **Atelier 3 — Scénarios stratégiques** : parties prenantes cotées (leur niveau de menace place chacune dans la cartographie danger / contrôle / veille), scénarios stratégiques sur les couples retenus, chemins d'attaque. ✦ L'IA propose scénarios et chemins.
4. **Atelier 4 — Scénarios opérationnels** : mode opératoire de chaque chemin, biens supports visés, vraisemblance. ✦ L'IA propose un mode opératoire par chemin.
5. **Atelier 5 — Traitement** : un risque par scénario (gravité et vraisemblance reprises des scénarios), option de traitement (réduire, transférer, éviter, accepter), cotation résiduelle, et **mesures de traitement** qui deviennent des tâches du plan d'action. La **matrice** montre les risques avant et après traitement. Un risque « accepté » s'inscrit au registre des risques résiduels.

Pour chaque proposition de l'IA : **Accepter**, **Corriger** puis accepter, ou **Rejeter**. Rien n'est créé sans votre accord.

## Étape 8 — Risques résiduels et dérogations

Menu **Risques et dérogations**.

1. **Risques résiduels** : ceux d'EBIOS RM s'y trouvent ; ajoutez les autres. Le **RSSI ou l'autorité** les **accepte** avec un motif et une date de revue, ou les clôt. Modifier la cotation d'un risque accepté lève l'acceptation.
2. **Dérogations** : **Demander une dérogation** sur une mesure manquante ou un risque, avec motif, mesures compensatoires et échéance. Les décisionnaires sont prévenus ; ils **acceptent** (avec une date d'expiration) ou **refusent** (en motivant). Une dérogation décidée ne se modifie plus ; elle expire automatiquement.

## Étape 9 — Une réunion de comité

Menu **Réunions** → **Planifier une réunion** : objet, horaires, lieu ou lien de visio, participants, ordre du jour. Chacun reçoit une **invitation d'agenda** (`.ics`, compatible Outlook, Google, Apple). Après la réunion : rédigez le **compte rendu**, ajoutez les **actions décidées** (elles deviennent des tâches), puis **Valider et diffuser**.

## Étape 10 — Le rapport d'état des lieux

Menu **Rapports** → **Générer un état des lieux**. Les données du projet sont **figées** à cet instant ; ✦ l'IA rédige la synthèse (sinon, un texte factuel automatique est produit). Les chiffres cités par l'IA qui n'existent pas dans les données sont **signalés** pour vérification.

1. Relisez et corrigez chaque section, **Enregistrer les modifications**.
2. **Aperçu PDF (brouillon)** pour contrôler la mise en page.
3. Le **RSSI ou l'autorité** **valide et fige le PDF** : il est empreinté (SHA-256), daté, signé du nom du valideur.
4. Plus tard, **Comparer deux versions** montre ce qui a progressé.

## Étape 11 — La décision d'homologation

Menu **Réglages** → **Décision d'homologation**. **Seule l'autorité d'homologation** du projet peut la prononcer : homologation, homologation provisoire ou refus, avec une date de fin de validité (ou un motif de refus). Les points encore ouverts sont rappelés avant de décider. La prochaine **revue périodique** est calculée ; un rappel partira 30 jours avant.

---

**Et ensuite ?** Les rappels (réunions, revues, dérogations) tournent seuls si les [tâches planifiées](11-commandes.md) sont en place ; le **journal d'audit** retrace tout ; l'**export calendrier** (Réglages) met les échéances dans votre agenda.
