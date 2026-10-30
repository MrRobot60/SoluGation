# Sécurité

## Isolation des données

- Chaque requête est filtrée par **organisation** ; dans une organisation, par **projets accessibles** (ceux dont l'utilisateur est acteur, ou tous pour l'administrateur). Une ressource d'une autre organisation répond « inexistant » (404), sans révéler son existence.
- Chaque lien entre objets (clés étrangères **et relations multiples**) est contrôlé : impossible de rattacher un objet d'un autre projet, donc d'une autre organisation.
- Les fichiers sont rangés sous un préfixe propre à l'organisation, avec un nom régénéré ; le stockage n'est jamais exposé au navigateur (téléchargement servi et tracé par le serveur).
- Près de 200 tests automatisés vérifient ces règles (isolation, droits, sécurité des entrées).

## Authentification

- Mots de passe : 12 caractères minimum, refus des mots de passe courants ou trop proches de l'identifiant ; stockés hachés (algorithme Django, PBKDF2 par défaut).
- Session par cookie `HttpOnly`, `SameSite=Lax`, `Secure` hors développement ; protection CSRF.
- Tentatives de connexion freinées (10 par minute), compteur partagé par tous les processus du serveur.
- **Double authentification** (TOTP, RFC 6238), politique choisie par l'administrateur de l'installation : désactivée, facultative, obligatoire pour les administrateurs ou pour tous. Secret chiffré en base ; un code ne sert qu'une fois (anti-rejeu, y compris pour deux requêtes simultanées) ; 5 essais et 5 minutes après le mot de passe ; codes de secours à usage unique dont seule l'empreinte est conservée. L'obligation est appliquée **côté serveur** sur l'API et l'admin Django (dont le formulaire, qui ne demande que le mot de passe, ne permet pas de contourner le second facteur). Toute modification redemande le mot de passe, est tracée et signalée par mail.
- **Invitation et mot de passe oublié** : liens à usage unique, signés, sans stockage, invalidés dès que le mot de passe change, que le compte se connecte ou est désactivé (1 heure pour une réinitialisation, 7 jours pour une invitation). Le jeton voyage dans le fragment de l'adresse (`#…`) : il n'est jamais transmis au serveur ni écrit dans les journaux du proxy.
- **Aucune énumération** des comptes : « mot de passe oublié » répond toujours la même chose, dans le même délai (envoi du mail en arrière-plan), et est limité à 5 demandes par heure et par adresse IP.
- Changer de mot de passe ferme toutes les autres sessions ; un mail de confirmation est envoyé. Désactiver un compte coupe immédiatement ses sessions.

## Fichiers déposés

- **Liste blanche** de types, vérifiés sur le **contenu réel** (signature), pas sur l'extension.
- Documents Office **avec macros** refusés ; archives à taux de compression anormal (zip bombs) refusées ; HTML, SVG et scripts refusés.
- Taille maximale (`UPLOAD_MAX_MO`), empreinte **SHA-256** à l'enregistrement, fichier **immuable** (une modification = une nouvelle version).
- Téléchargements servis avec `Content-Security-Policy: sandbox` et `X-Content-Type-Options: nosniff`.
- Rapports XML (scans) lus sans entités externes (protection XXE et « milliard de rires »).

## Journal d'audit

- Chaque création, modification, suppression, décision, téléchargement, export et connexion est tracé : qui, quand, quoi, valeurs avant → après, adresse IP.
- **En ajout seul** : refus applicatif, et **trigger PostgreSQL** qui interdit `UPDATE`, `DELETE` et `TRUNCATE` sur la table.
- **Chaîné par hachage** : chaque entrée contient l'empreinte de la précédente. **Vérifier l'intégrité** (Administration ou Journal d'audit) détecte une entrée modifiée ou supprimée, même directement en base.
- Pour détecter aussi une troncature (suppression des dernières entrées), conservez régulièrement la **dernière empreinte** affichée hors de l'application.

## Chiffrement

- **En transit** : HTTPS imposé hors développement (redirection, HSTS, cookies sécurisés). En [production](15-production.md), Caddy termine le TLS (certificat Let's Encrypt automatique) ; base, stockage et serveur ne sont pas exposés.
- **Au repos** : activez le chiffrement côté serveur du stockage (`S3_SSE=AES256` chez un hébergeur S3) et le chiffrement des disques de la base. La **clé d'API de l'IA** est chiffrée en base (Fernet).
- **Secrets** hors du dépôt : `.env` exclu de Git.

## En-têtes et ressources

- Interface servie avec une **CSP stricte** (`script-src 'self'`, aucun script en ligne), `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, `Permissions-Policy`.
- **Aucune ressource tierce** : polices et scripts sont servis par l'installation (aucune adresse IP d'utilisateur transmise à un service extérieur).
- L'adresse IP enregistrée au journal est celle du client (transmise par le proxy), jamais un en-tête accepté sans proxy de confiance.

## Intelligence artificielle

Voir [Intelligence artificielle](07-ia.md) : facultative, responsabilité du fournisseur acceptée par l'administrateur, protection SSRF, données minimisées, conclusions toujours validées par un humain, interrupteur par organisation.

## Décisions humaines figées

Pièces validées, conclusions IA statuées, risques acceptés, dérogations décidées, comptes rendus validés, rapports validés (PDF figé et empreinté), décision d'homologation : chacune est datée, nominative, tracée, et ne se modifie plus (une évolution passe par une nouvelle version ou une nouvelle décision).

## Signaler une vulnérabilité

Merci de ne pas ouvrir de ticket public : écrivez à l'adresse de contact sécurité du projet (à définir dans `SECURITY.md` avant publication).
