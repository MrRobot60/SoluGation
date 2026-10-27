# Présentation

## À quoi sert SoluGation

L'**homologation de sécurité** est la décision, prise par une autorité désignée, d'accepter les risques résiduels d'un système avant sa mise en service (ou son maintien). Elle s'appuie sur un dossier : analyse de risques, conformité à des référentiels, documents, plan d'action, risques acceptés.

SoluGation outille toute la démarche :

1. **Créer le projet** : le bien à homologuer, 1 à 3 référentiels, le niveau visé, EBIOS RM ou non, les acteurs et leurs rôles.
2. **Checklist documentaire** générée selon le contexte, avec responsable et échéance par document.
3. **Déposer les documents** (versions, empreinte SHA-256), puis les faire **analyser par l'IA** si elle est configurée.
4. **Évaluer les mesures** des référentiels (conforme, partiel, manquant, non applicable), avec preuves.
5. **Plan d'action** : chaque manquement devient une tâche (responsable, échéance, preuve attendue).
6. **Suivi collaboratif** : commentaires, historique, notifications et mails à chaque modification.
7. **Recommandations de l'IA** pour combler chaque manquement (si l'IA est configurée).
8. **Scans de vulnérabilités** : import de rapports Nessus, OpenVAS ou CSV, création de tâches.
9. **EBIOS RM** : les 5 ateliers guidés, avec propositions de l'IA à valider.
10. **Risques résiduels et dérogations** : acceptation datée, nominative et motivée.
11. **Réunions** avec invitations d'agenda et compte rendu.
12. **Rapport d'état des lieux** PDF, à tout moment, comparable d'une version à l'autre.
13. **Décision d'homologation** par l'autorité d'homologation, puis revue périodique.

Tout est **tracé** dans un journal d'audit en ajout seul, vérifiable.

## Principes

- **L'IA recommande, l'humain valide.** Toute conclusion de l'IA naît « à valider ». Aucune ne vaut décision d'homologation.
- **Isolation stricte** : une organisation ne voit jamais les données d'une autre, et dans une organisation chacun ne voit que les projets dont il est acteur (sauf l'administrateur).
- **Rien ne s'efface en silence** : documents et preuves sont versionnés et empreintés, les décisions sont figées, le journal ne se modifie pas.
- **Fonctionne sans IA, sans cloud** : tout s'auto-héberge.

## Vocabulaire

| Terme | Sens dans SoluGation |
|---|---|
| Organisation | L'entité cliente (ministère, collectivité, entreprise, cabinet). Une installation peut en servir plusieurs, totalement cloisonnées. |
| Projet | Une homologation : un bien, ses référentiels, ses acteurs. |
| Acteur | Une personne associée à un projet avec un rôle (chef de projet, RSSI, autorité d'homologation, contributeur, auditeur). Peut être un contact externe sans compte. |
| Référentiel | Un ensemble de mesures (RGS, guide d'hygiène ANSSI, II 901, NIST CSF, OWASP ASVS, ISO 27001…). |
| Mesure | Une exigence d'un référentiel, évaluée dans chaque projet. |
| Manquement | Une mesure évaluée « manquant » ou « partiel » : elle crée une tâche. |
| Preuve | Un fichier qui démontre la mise en œuvre d'une mesure, versionné. |
| Instantané | Les données figées dans un rapport à sa génération : le rapport reste fidèle à la date. |
| Autorité d'homologation | La personne qui prononce la décision d'homologation (et elle seule). |
| Décisionnaire | RSSI, autorité d'homologation ou administrateur : valident les pièces, les conclusions de l'IA, les risques. |
| Administrateur de l'installation | Le compte qui configure l'IA pour toute l'installation (superutilisateur). |
