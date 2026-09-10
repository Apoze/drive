# Docs dans Drive — validation finale

Livraison LAN du 9 septembre 2026. D0–D9 et C1–C10 vérifiés dans le
[plan canonique](../../../docs/plans/suite/docs-drive-native-documents-integration-plan.md).

## Résultat

Docs et Drive partagent classement, accès, invitations, corbeille et quotas.
Docs conserve UUID, contenu, médias et versions dans son stockage privé.
Création depuis les deux applications, sous-documents, copie, déplacement,
partage People, liens, PDF et dossiers mixtes sont raccordés.

La régression « Mes fichiers » était confirmée : la route utilisait un catalogue
simplifié `SpacesExplorer`, alors que le shell historique `AppExplorer` existait
encore. La route réutilise maintenant ce shell avec `ResourceCollection` en mode
`home`, les filtres, colonnes, menus, sélection, aperçus et transferts communs.
Les 54 allocations S3 historiques ayant un fichier pour racine s’affichent comme
des fichiers ; les sélecteurs de destinations restent limités aux dossiers.
Aucune allocation ni donnée historique n’a été transformée pour réparer l’UI.

Principales surfaces : services `docs_*`, arbre/quotas/transferts et API
`storage_resources` dans Drive ; services `drive_*`, éditeur, partage, création
et reprises dans Docs ; paquet commun `suite_identity`. Contrats :
[stockage](../../../docs/agent-storage-contract.md),
[ADR](../../../docs/adr/0004-docs-drive-native-documents.md),
[exploitation](../../../docs/operations/docs-drive-native-documents.md).

## Preuves ciblées

| Contrôle | Résultat / preuve |
| --- | --- |
| Connexion commune et pile | Drive/Docs authentifiés ; catalogue, S3, NAS, ST, People, Docs et Meet HTTP 200 ; 43 conteneurs actifs sans service unhealthy. [Santé](health-final.json), [images](deployment-final.json). |
| Explorateur | Grille historique, filtre PDF réel, NAS depuis Mes fichiers, clavier, mobile sans débordement ; Docs mobile et dossier S3 mixte. [Preuve](lan-explorer.json). |
| Office conservé | Ouverture d’un ODT existant dans un nouvel onglet, iframe et échanges WOPI HTTP 200. [Preuve](lan-conservation.json). |
| Coédition / révocation | Deux comptes réels ; commentaire et édition selon rôle ; révocation HTTP 403 et WebSocket fermé en 10 522 ms. [Preuve](lan-revocation.json). |
| Panne Drive | Lecture refusée 503, coédition coupée en 9 818 ms, service rétabli. [Preuve](lan-outage.json). |
| Quota | Refus réel 413, brouillon conservé et reprise 204 après restauration des 20 Go. [Preuve](lan-quota.json). |
| PDF / ZIP | Exports S3 et NAS relus, texte et image vérifiés ; ZIP réel de dossier mixte avec parent, enfant et PDF existant. [PDF](lan-pdf-check.json), [dossier mixte](lan-mixed.json). |
| S3 / NAS | Document et dossier mixte déplacés S3–NAS–S3, UUID/contenu conservés ; remplacement de chemin NAS sans vol d’ancre ; disparition refusée puis récupération propriétaire. [Ancre](lan-anchor.json). |
| Liens | Lecture publique contrôlée, média refusé après révocation ; lien de dossier limité au sous-arbre, fragment retiré. [Document](lan-public.json), [dossier](lan-folder-link.json). |
| Invitation | SMTP capturé localement et supprimé ; acceptation explicite Web 200, fragment retiré, propriétaire existant conservé sans doublon. Refus du mauvais destinataire et acceptation avec profil local obsolète couverts par le contrôle PostgreSQL ciblé. [Preuve Web](lan-invitation.json). |
| IdP | Keycloak–Authentik–Keycloak isolé : UUID, contenu, classement et groupe conservés ; anciennes sessions 401 et groupe révoqué 403. [Preuve](isolated-idp.json). |
| Restauration | Deux bases et S3 Docs versionné restaurés sans ports ni NAS ; cinq documents comparés, médias/versions hachés identiques, reprise sans double charge. [Preuve](isolated-restore.json). |
| Nettoyage | Six liaisons purgées, aucun Item vivant, zéro octet documentaire facturé, réservation active, média, version ou écriture de recette ; exports supprimés. [Preuve](lan-purge.json). |

Les invitations utilisent désormais l’adresse **vérifiée par l’IdP dans la
preuve de session**, et non un profil Drive potentiellement vide ou ancien.
Aucun rapprochement de comptes par courriel. Les IdP doivent fournir
`email_verified: true` pour ce parcours ; les anciennes sessions doivent se
reconnecter. Le profil Keycloak temporairement ajusté pour le test a été remis
à son état initial ; aucune modification globale des mappers de l’IdP LAN.

Les derniers contrôles automatisés ont été limités aux zones modifiées :
explorateur SQL/permissions, pagination Docs, invitations et notifications,
copie/annulation, manifeste, cache frontend, sauvegarde de brouillon et transport
d’identité. Les typages Drive/Docs, linters ciblés et vérifications de migrations
passent. Aucun test de recherche de chaînes dans le code, aucun full E2E lancé.

Le manifeste de 21 puis 201 documents utilise 20 puis 22 requêtes SQL,
respectivement 22,63 et 52,82 ms sur ce serveur. Rejeu sans requête inutile :
[mesure](scale.json). Ce relevé n’est pas une garantie de charge en production.

## Exploitation et données conservées

Les images finales et la wheel 0.1.1 sont consignées dans le manifeste.
SHA-256 de la wheel :
`29ce377994e58bb751c4c7ec2523b9850e60062310ae0d2fb9f0243f8a14f067`.
Migrations Drive 0050–0058 et Docs 0034–0048 appliquées ; aucun modèle sans
migration détecté. Intégration active dans les deux applications.

Les trois projets QA ont été arrêtés avec leurs seuls volumes éphémères.
Les exports téléchargés et profils navigateur de cette recette sont nettoyés.
Les journaux terminaux et témoins de purge restent conservés pour l’idempotence,
sans réservation active. Le quota du compte de test demeure à 20 Go.

Sauvegardes privées conservées sous `data/docs-drive-native-documents/` :
`baseline/`, `pre-activation-20260909/`, `integrated-restore-20260909/`.
Le dernier point contient 57 855 484 octets au relevé de création. Il sert de
preuve et de point de restauration isolée ; ne pas restaurer aveuglément un
ancien état dans le LAN. Aucun secret ni sauvegarde n’est publié dans ce rapport.

## État Git exact

- Drive : branche locale `codex/docs-drive-native-documents` ; `origin`
  `https://github.com/Apoze/drive.git` en lecture/écriture ; `upstream`
  `https://github.com/suitenumerique/drive.git` en lecture seule, push désactivé.
- Docs : branche locale `codex/docs-drive-native-documents` ; `origin`
  `https://github.com/suitenumerique/docs.git` en lecture seule, push désactivé.
  Aucun remote Apoze Docs ajouté pendant ce chantier.
- Modifications antérieures et présentes conservées localement. Aucun commit,
  push, PR ni publication effectué par ce chantier ; aucun dépôt ou branche
  poussé, aucune base/tête/URL de PR. Les contrôles de publication seront à
  appliquer à la livraison GitHub si elle est ensuite autorisée.
- Grist reste en pause. L’exposition Internet et les certificats restent dans
  le périmètre explicitement différé par le propriétaire.

Aucun lot fonctionnel restant du plan Docs–Drive. L’historique détaillé est
conservé dans [execution-journal.md](execution-journal.md).
