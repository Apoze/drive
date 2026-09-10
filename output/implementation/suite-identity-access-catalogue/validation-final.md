# Validation finale — identité, accès, catalogue et Docs

Date : 8 septembre 2026. **Livraison locale qualifiée, L0–L11 terminés.**
[Plan](../../../docs/plans/suite/identity-access-catalogue-docs-plan.md) ·
[État livré](current-status.md) · [Manifeste](delivery-manifest.json) ·
[Installation](../../../docs/installation/suite-identity-and-docs.md) ·
[Exploitation](../../../docs/operations/suite-identity-access.md).

## Installation réellement active

- **36 conteneurs** démarrés : Drive 16, ST 7, People/Docs `suite-local` 13.
  Tous les services sont running ; aucun healthcheck déclaré unhealthy.
- Keycloak commun **26.3.2**, issuer Drive existant conservé. L'ancien Keycloak
  ST **26.2.5** reste disponible pour reprise, sans servir les nouveaux logins.
- People **v1.25.4**, Docs **v5.6.1**, adaptations locales décrites au manifeste.
- Authentik **2026.8.1** testé directement dans la qualification isolée,
  puis retiré avec ses volumes après retour réussi à Keycloak.
- Paquet installé `apoze-suite-identity` **0.1.0**, même wheel dans les quatre
  dépendances natives ; migrations additives appliquées et images reconstruites.
- 23 principaux projetés dans chaque application, état d'annuaire et politique
  frais. Les deux personnes actives migrées retrouvent leurs associations
  explicites ; les autres profils préexistants attendent leur preuve de login
  si leur identité externe n'était pas vérifiée. Aucune fusion par email.

## Critères du plan

| Critère | Résultat vérifié | Preuves principales |
| --- | --- | --- |
| V1 — Conservation | PK et références historiques Drive/ST conservés. NAS, S3, origines et clients existants préservés. Quota test **20 000 000 000 octets**, usage final **59 471 422 octets**, identique à l'avant-recette. | Audit des sources avant activation ; snapshots DB ; recette réelle S3/NAS ; `final-storage-state-private.json`. |
| V2 — Identité | Associations issuer/subject par consommateur, collisions refusées, aucun rapprochement email ; replay sans doublon, subjects pairwise explicites. Les deux personnes migrées se connectent aux quatre applications avec leurs PK locaux conservés. | Tests partagés d'identité ; approbation Web People ; parcours Keycloak/Authentik ; `final-sso.private.log`. |
| V3 — Groupes | Renommage sans remplacement d'UUID/grant, retrait réel, pagination complète, restriction d'organisation et de source. Les ancêtres visibles ne deviennent pas des adhésions. Un ancien snapshot ne rétablit pas un accès retiré. | Tests de projection, périmètre, arbre People, transfert d'autorité ; retrait Web LAN ; mesure 200 groupes/1 000 adhésions. |
| V4 — ST | Account, overrides et historique conservés ; clé durable utilisée par les métriques. Refus d'application prioritaire sur une ACL de document. Rôle de gestion d'équipe distinct de l'administration ST. | Tests ciblés politique/liaison de comptes ; métriques après bascule ; quota LAN final ; refus ST 403 après retrait. |
| V5 — Docs utilisable | Création et coédition à deux, sauvegarde relue après redémarrage backend et S3, partage de groupe, tiers refusé, médias privés et export PDF natif. | Recettes navigateur isolée et LAN ; export **5 827 octets**, signature PDF ; médias lecteurs 200/anonyme 403 ; captures examinées. |
| V6 — Révocation | Sessions ouvertes, WebSocket, anciennes délégations WOPI S3/NAS et publication de jobs recontrôlés. Un propriétaire conserve son droit individuel après retrait du groupe. | Mesures ci-dessous ; tests ciblés ZIP et baux de collaboration ; trois anciens tokens WOPI refusés. |
| V7 — Pannes | Import incomplet et ancien snapshot refusés sans effacement ; fraîcheur expirée refusée en 503 ; suspension et URL privée bornées ; nouvelle synchronisation idempotente. | Tests comportementaux partagés de projection, accès, HTTP machine et échéance ; reprise des synchronisations après relances LAN. |
| V8 — Web/SSO | Une saisie de mot de passe pour les quatre apps ; catalogues et administration accessibles selon les rôles, cookies distincts, accès privé contrôlé côté serveur. Déconnexion commune et reprise sans logout IdP qualifiées. | Chromium sur les quatre UI ; approbation et retrait Web People ; politique ST ; quatre sessions 401 après logout. |
| V9 — Annuaire externe | Vrai Authentik SCIM vers People : provisioning, liaison stable, changement de groupe, désactivation/réactivation, replay et transfert explicite d'autorité. Groupes externes protégés des modifications People. | Tests SCIM/admin ; parcours de transfert Web ; `authentik-revocation-result.json`, `authentik-suspension-result.json`. |
| V10 — OIDC hostile | Signature, issuer, audience, expiration, nonce/state, concordance UserInfo et redirections contrôlés. Un ID token ou un access token d'un autre client ne donne pas accès à l'API ST. | Tests paramétrés d'identité/HTTP/Bearer ; RSA réel Mozilla 4 et 5 ; ST LAN : valide 200, ID token 401, audience étrangère 401, signature altérée 401. |
| V11 — Bascule IdP | **Keycloak → Authentik direct → Keycloak**, mêmes UUID, groupes, grants, Account, quota et fichiers. Relecture Drive avec même hash ; document partagé toujours accessible ; anciens cookies Authentik 401 au retour. | Snapshots avant/après ; relecture du fichier de 49 octets et coédition ; rapports privés de conservation. Aucun intermédiaire Keycloak dans l'étape Authentik. |
| V12 — Exploitation | Quatre bases restaurées séparément et comparées ; cinq versions Docs restaurées avec hashes/métadonnées identiques. Quatre comptes de secours testés sans IdP. Relances, nettoyage et sauvegardes durables terminés. | `restore-databases-result.json`, preuve de restauration objets, `recovery-browser-result.json`, manifeste final des services et nettoyage. |

ST contient aussi les nouveaux comptes de métriques provisionnés pour les
profils historiques : **88 → 109 Account**, sans remplacement des anciens
Account/Entitlement/Metric. Les comptes natifs de secours sont distincts des
23 principaux : ils n'obtiennent aucun accès au contenu via les API de la suite.

## Mesures de révocation

| Action réelle | Résultat | Délai mesuré |
| --- | --- | --- |
| Retrait du groupe dans Authentik, provisioning SCIM réel | Docs 403 et fermeture de la coédition | **29,669 s** |
| `active=false` dans Authentik | Docs 403 et fermeture de la coédition | **9,831 s** |
| Déconnexion commune | Quatre API utilisateur 401 | **20,737 s** |
| Retrait depuis l'administration Web People sur le LAN | WebSocket fermé | **17,603 s** |
| Même retrait LAN | Document, média et ST 403 ; propriétaire 200 | **19,303 s** |
| Retrait LAN avec trois délégations WOPI déjà émises | Trois anciens tokens 403 : S3 DOCX, S3 ODT, NAS ODT | **23,694 s** |

Ces délais sont des observations de recette. La borne applicative publiée
reste 120 s ; un délai de provisioning externe s'y ajoute lorsqu'il n'est pas
maîtrisé. Les memberships retirés pour ces essais ont été rétablis.

## Coût ciblé et validations de code

Mesure transactionnelle annulée après lecture, sans données de charge
persistantes ni appels réseau par élément :

| Parcours | Petit jeu | Jeu prévu au plan | Coût SQL |
| --- | --- | --- | --- |
| Liste des groupes | 10 : 6,24 ms | 200 : 7,25 ms | 6 requêtes par page |
| Adhésions paginées | 50 : 6,74 ms | 1 000 : 62,14 ms, 5 pages | 6 requêtes par page, zéro doublon/perte |
| Autorisation dans une requête | 1 contrôle : 0,94 ms | 1 000 contrôles : 3,16 ms | 1 requête SQL, aucun appel distant |

Il s'agit d'un contrôle de pagination et de N+1 sur ce serveur, pas d'une
promesse de débit en production. Aucun cache global de droits supplémentaire.

- Ruff ciblé et format des backends Drive/ST/People/Docs : passent ; contrôle
  additionnel des noms Python indéfinis People/Docs : passe.
- Paquet partagé : lint et format à 100 colonnes, migrations natives exclues.
  Helpers d'installation : lint et format passent.
- ESLint et types des quatre frontends, plus collaboration Docs : passent.
  Docs utilise ses types existants `vitest/globals,node` pour le contrôle TS.
- Tests ciblés d'identité, projection, SCIM, comptes/politiques ST, garde ZIP,
  partage Docs et baux Hocuspocus : passés pendant les lots concernés.
  Derniers ajouts : protection Web du dernier administrateur/owner et replay
  du bootstrap vérifiés ; aucune suite globale relancée pour du formatage.
- Checks Django de sécurité sur les quatre backends actifs et
  `git diff --check` dans les quatre dépôts : passent.
- Pas de tests cherchant du texte dans les fichiers de code, ni de full E2E
  de réinitialisation sur l'installation réelle.

## Stockage, nettoyage et reprise

ONLYOFFICE S3 DOCX, Collabora S3 ODT et Collabora NAS ODT ont été ouverts,
modifiés au clavier et sauvegardés dans les vrais éditeurs. La relecture des
octets a confirmé les modifications ; fichiers et téléchargements supprimés.

La recette Docs a révélé une incompatibilité CopyObject versionné de
SeaweedFS Drive 4.12. Docs utilise désormais **SeaweedFS 4.46 dédié**, figé par
digest, réseau privé, volume persistant `suite-local_docs-s3`, aucun port
publié, IAM limité à son bucket. Le Drive/NAS n'a pas été reconfiguré pour
cette correction. Voir l'[ADR](../../../docs/adr/0003-suite-durable-identity-and-access.md).

Nettoyage vérifié :

- Trois fixtures S3 Drive : lignes supprimées, clés absentes, **10 anciennes
  versions/marqueurs** supplémentaires retirés sous leurs seuls UUID.
- Fixtures NAS TXT/ODT supprimées ; document Docs, pièces jointes, versions
  et marqueurs supprimés après les essais de restauration/persistance.
- Ancien bucket Docs temporairement créé sur le S3 Drive vidé puis supprimé ;
  ancienne identité IAM Docs retirée, identité Drive préservée.
- Projets `suite-identity-qa` et `suite-identity-authentik-qa` :
  **21 conteneurs et 14 volumes** supprimés. Absence vérifiée après arrêt.
- Deux anciens volumes de cache Next inutilisés supprimés ; les volumes des
  services actifs restent présents. Aucun prune global.

Sauvegardes privées : `/root/Apoze/drive/data/suite-local/backups/2026-09-08/`.
Le manifeste privé distingue état initial, dumps ayant été restaurés, sources,
configuration, preuves détaillées et dumps finaux après nettoyage. Les
captures utiles restent sous `output/playwright/suite-identity/`.
Les guides donnent les procédures de restauration ; une sauvegarde intégrale
de tous les octets préexistants du NAS demeure une opération d'exploitation,
distincte de la restauration du scénario demandée dans ce chantier.

## Limites assumées du périmètre accepté

Keycloak et Authentik sont testés ; Entra et les autres IdP ne sont pas
présentés comme qualifiés sans leur tenant. Le profil OIDC/SCIM est générique
et ses capacités exactes sont documentées. Une organisation est configurée
par consommateur déployé ; aucune organisation n'est déduite d'une claim libre.

L'installation reste en HTTP LAN. Les octets déjà téléchargés et les flux
déjà acceptés ne sont pas rappelables ; les liens publics restent autonomes.
Docs conserve ses documents/ACL/S3 et n'est pas encore classé dans Drive.
Le quota commun à toute la suite, Grist, Messages, Meet et Find sont hors de
ce lot. Aucun de ces travaux n'empêche l'usage livré des quatre applications.

Les changements sont **locaux** dans les quatre dépôts. Aucun commit, push,
ticket ou PR n'a été effectué pour cette livraison.
