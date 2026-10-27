# Rôles et droits

Deux niveaux de rôles s'additionnent : le rôle dans l'**organisation** et le rôle dans chaque **projet**. Un rôle « lecture seule » (auditeur), à l'un ou l'autre niveau, interdit toute écriture.

## Rôles d'organisation

| Rôle | Voit | Particularités |
|---|---|---|
| Administrateur | Tous les projets de l'organisation | Règle l'organisation (dont l'IA), décide sur tous les projets, journal hors projet, intégrité du journal |
| Membre | Les projets dont il est acteur | — |
| Auditeur | Les projets dont il est acteur | Lecture seule partout |

**Administrateur de l'installation** (superutilisateur) : configure l'IA pour toute l'installation, accède à l'admin Django. Il ne voit pas pour autant les données des autres organisations dans l'interface.

## Rôles de projet

| Rôle | Pour qui |
|---|---|
| Chef de projet | Pilote l'homologation (le créateur du projet l'est d'office ; il en reste toujours au moins un) |
| RSSI | Décide sur la sécurité : pièces, conclusions IA, risques, dérogations, rapports |
| Autorité d'homologation | Prononce la décision d'homologation |
| Contributeur | Alimente le dossier |
| Auditeur | Consulte |

## Qui peut faire quoi

| Action | Contributeur | Chef de projet | RSSI | Autorité d'homologation | Admin d'organisation | Auditeur |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Consulter le projet | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Déposer, évaluer, commenter, créer des tâches | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| Valider / refuser une pièce | — | — | ✓ | ✓ | ✓ | — |
| Accepter / rejeter une conclusion de l'IA | — | — | ✓ | ✓ | ✓ | — |
| Accepter une recommandation ou une proposition EBIOS de l'IA | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| Accepter un risque résiduel, décider une dérogation | — | — | ✓ | ✓ | ✓ | — |
| Valider un rapport (PDF figé) | — | — | ✓ | ✓ | ✓ | — |
| Réglages du projet, acteurs, archivage | — | ✓ | ✓ | ✓ | ✓ | — |
| **Décision d'homologation** | — | — | — | **✓** | — | — |
| Annuler une réunion, valider son compte rendu | organisateur | ✓ | ✓ | ✓ | ✓ | — |

La **configuration de l'IA** de l'installation revient au seul **administrateur de l'installation** (superutilisateur).

La **décision d'homologation** n'appartient qu'à l'autorité d'homologation désignée parmi les acteurs, sans exception (pas même l'administrateur). Dans une petite structure, l'administrateur qui est aussi l'autorité s'ajoute au projet avec ce rôle.

Un projet **archivé** est en lecture seule pour tous ; seuls ses administrateurs peuvent le désarchiver.

## Contacts externes

Un acteur peut être un **contact sans compte** (nom, email, organisme) : il reçoit les mails (notifications, invitations, comptes rendus) mais n'accède pas à l'application.
