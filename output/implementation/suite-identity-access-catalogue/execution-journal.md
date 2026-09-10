# Journal historique — exécution du 8 septembre 2026

Ce journal conserve les états intermédiaires, désormais dépassés.
Pour l’état livré, lire [current-status.md](current-status.md) et
[validation-final.md](validation-final.md).

# Socle identité, accès et catalogue — état d’exécution

Exécution autorisée le 8 septembre 2026. Chantier en cours, non livré.
Référence : [plan L0–L11](../../../docs/plans/suite/identity-access-catalogue-docs-plan.md).

## Point de reprise

- Les 22 services habituels Drive/ST restent démarrés, sans modification.
- Sauvegardes privées des trois serveurs PostgreSQL, configurations et code
  courant dans `tmp/suite-identity-execution-20260908/` (accès restreint).
- Code Drive, y compris les modifications stockage non committées, reproduit
  dans `/root/Apoze/drive-worktrees/suite-identity-access`.
- Code ST reproduit dans
  `/root/Apoze/st-deploycenter-worktrees/suite-identity-access`.
- Les deux worktrees utilisent `codex/suite-identity-access-catalogue`.
- People `v1.25.4` et Docs `v5.6.1` récupérés depuis leurs dépôts officiels
  dans `/root/Apoze/people` et `/root/Apoze/docs`, sans publication.

## Lots

| Lot | État | Preuve / prochaine action |
| --- | --- | --- |
| L0 | En cours | Sauvegardes et worktrees réalisés ; inventaire fonctionnel et recette isolée à préparer. |
| L1 | À faire | Contrats, associations d’identité et migration additive. |
| L2 | À faire | People et administration homelab. |
| L3 | À faire | Projection des groupes et statuts. |
| L4 | À faire | Raccordement Drive. |
| L5 | À faire | Identifiants durables et accès ST. |
| L6 | À faire | Docs, groupes et coédition. |
| L7 | À faire | Catalogue et parcours Web. |
| L8 | À faire | Provisioning SCIM entrant. |
| L9 | À faire | Qualification réelle du changement d’IdP. |
| L10 | À faire | Activation et recette LAN réelle. |
| L11 | À faire | Restauration, nettoyage, guides et clôture. |

## Validation

Aucune nouvelle recette d’identité exécutée. Les sauvegardes et l’inspection
du runtime ne valent pas qualification fonctionnelle des futurs raccordements.
Pas de commit, push ou modification des données applicatives réelles.

## Avancement du 8 septembre — socle en qualification

- Recette privée `suite-identity-qa` démarrée : PostgreSQL (5 bases/roles),
  Redis, Keycloak, SeaweedFS et les quatre backends. Ports 19100–19104/19180.
  Configuration sous le worktree Drive `data/suite-identity-qa/`, privée.
- Migrations additives du paquet `src/packages/suite-identity` appliquées dans
  les quatre bases de recette uniquement. Association issuer/subject explicite,
  principal durable, projection et fraîcheur, compteur de session et borne
  d’authentification. Aucun compte réel migré.
- People : organisation locale sans SIRET, mappings, principaux, consommateurs,
  identités par application, administration Django bornée et API paginée.
  Révisions PostgreSQL transactionnelles couvrant les écritures en masse.
- Synchronisation réelle People → Drive/ST/People/Docs effectuée (révision 36)
  avec trois principaux, un groupe et quatre consommateurs synthétiques.
- ST : politiques d’accès distinctes des quotas ; règles utilisateur/groupe,
  priorité au refus et endpoint de décision machine limité à l’organisation.
  Quatre souscriptions de qualification créées, pas de modification du ST réel.
- Contrôle commun raccordé aux sessions OIDC et aux résolveurs de rôles
  Drive/Docs ; raccordements API/resource server en cours, non qualifiés.
- Tests ciblés passés : 12 contrats identité, 1 import/rejeu/retrait/page
  manquante, 1 décision ST (groupe, refus individuel, organisation, expiration).
  Les modifications suivantes (epoch API, garde des rôles) restent à valider.
- Images backend People/Docs et frontend People/collaboration Docs construites.
  Construction frontend Docs lancée ; aucun frontend de recette encore démarré.

### Reprise immédiate

Poursuivre depuis les worktrees isolés, pas depuis le code monté par la pile
habituelle. Finir les tâches périodiques de synchronisation, qualifier les
sessions OIDC et les API, puis les UI/Docs/coédition. SCIM, Authentik,
conservation complète des métriques ST, activation LAN et restauration ne sont
pas encore réalisés. L0–L11 ne sont pas déclarés terminés.

Commandes utiles : `docker compose -f data/suite-identity-qa/compose.json ...`
depuis le worktree Drive ; `docker exec suite-identity-qa-<app>-1 python
manage.py suite_sync_directory` et `suite_sync_policy`.
Les identifiants et secrets de recette restent dans des fichiers privés et ne
doivent pas être imprimés. Les sauvegardes du stack habituel restent intactes.

### Avancement du 8 septembre — connexion commune et groupes Docs

- Correction du backend OIDC ST : la méthode historique masquait la résolution
  des associations explicites. Le mode historique reste disponible hors socle.
- Connexions navigateur People → Docs → Drive → ST avec le même Keycloak de
  qualification : quatre réponses `/users/me/` 200, sans ressaisie entre apps.
- Docs : sélecteur d’équipes publié par organisation, pagination/recherche,
  partage natif par UUID, affichage et modification des ACL d’équipe sans faux
  utilisateur. Contrôle serveur indépendant du sélecteur.
- Test ciblé Docs : groupe étranger refusé, partage autorisé, membre autorisé,
  retrait de membership effectif, document et grant conservés : 1 test passé.
- Création réelle d’un document synthétique et partage d’équipe depuis le Web :
  201. Coédition à deux et révocation de socket restent à qualifier.
- Correction de l’initialisation du bail WebSocket : Hocuspocus traite les
  messages en attente avant son hook `connected`; les deux chemins utilisent
  désormais la même preuve établie par `onConnect`.
- Typage frontend Docs passé avec les types Vitest explicitement chargés ;
  typage du serveur de collaboration passé avant la dernière correction.
- Aucun changement activé sur le Drive/ST LAN existant, aucune publication.

Le chantier global reste **en cours**, notamment ST/métriques, administration,
catalogue, SCIM, bascule Authentik, activation LAN et restauration.

### Qualification Docs et progression ST — 8 septembre

- Coédition navigateur Alice → Bob et Bob → Alice confirmée, sauvegarde S3
  `PATCH content` 204 et relecture après navigation ; tiers refusé 403.
- Retrait réel du membership synthétique dans People : accès API Docs 403 et
  WebSocket déjà ouvert fermé en **19,232 secondes**. Membership rétabli après
  la mesure, avec le même identifiant. Les fichiers restent dans la recette.
- ST : champ principal durable ajouté aux comptes de métriques, ancien
  `external_id` conservé comme alias de reprise ; commande d’association
  explicite avec simulation, collision et organisation contrôlées.
- Appels et métriques Drive raccordés au principal et à l’organisation projetée.
  Test ciblé ST : même Account, quota spécifique de 20 Go conservé, replay
  idempotent et rapprochement email refusé : 1 test passé.
- Administration ST des règles d’accès en cours : réutilisation des écrans de
  services, contrôle opérateur/organisation et version pour refuser une
  sauvegarde depuis un écran périmé. Pas encore qualifiée dans le navigateur.

### Administration et qualification Authentik — 8 septembre

- ST : règles d’accès d’application administrables depuis les écrans de
  services ; tests ciblés d’organisation et de version concurrente passés,
  sauvegarde réelle navigateur 200, typage et lint ciblé frontend passés.
- People : serveur SCIM entrant Users/Groups, source authentifiée et bornée
  par organisation, collisions refusées, suppression logique et epoch de
  session. Profil SCIM limité annoncé, charge utile bornée à 2 Mio, pagination.
- Administration People : source/credential, historique sans payload,
  associations explicites, aperçu signé de reprise d’un groupe et confirmation
  avec contrôle des changements concurrents ; retour local conservant les
  membres. Deux tests ciblés de cycle SCIM et de reprise sont passés.
- Authentik 2026.8.1 de recette : vrai provisioning de quatre profils et d’un
  groupe via SCIM ; associations des trois comptes existants conservées.
  Correction de négociation `Accept: application/scim+json` après cet essai.
- Keycloak → Authentik dans les quatre applications de recette : quatre
  `/users/me/` 200, une seule saisie de mot de passe. Docs utilise un subject
  différent des autres clients ; associations explicites par application.
- Reprise du groupe existant confirmée depuis le Web People, UUID conservé.
  Retrait Authentik → SCIM People → projection Docs : API 403 et socket fermé
  en **29,669 secondes** ; membre rétabli dans Authentik après la mesure.
- WOPI et tickets de streaming Drive : raccordement à l’epoch, à l’issuer et
  à l’échéance d’authentification en cours ; tests ciblés lancés. Qualification
  des éditeurs LAN et du NAS toujours à faire. Aucun changement du stack LAN.

La recette tourne actuellement sur **Authentik**. Le retour Keycloak, la
réactivation SCIM complète, le catalogue, la déconnexion commune, les garanties
sur tous les accès/emplois, l’installation persistante, la restauration et
l’activation LAN restent à terminer. **Chantier global non terminé.**

### Catalogue, déconnexion et tickets privés — 8 septembre

- 32 tests ciblés Drive passés en 2,27 s : tickets WOPI S3 et natifs,
  streaming, génération de signatures ; ajout d’un contrôle d’epoch/issuer et
  conservation de l’échéance d’authentification lors d’une délégation.
- Les rôles préchargés d’un Item/accès/invitation ne sont plus réutilisés
  implicitement par un worker après une nouvelle lecture des droits.
- Catalogue ST par abonnements publiés et organisation, décisions d’accès
  indépendantes ; menu local commun raccordé aux quatre en-têtes, sans charger
  le widget distant quand le socle est actif. 4 liens observés dans chaque UI.
  Ajustement CSS après inspection réelle du menu Drive.
- Déconnexion commune : credential distinct de la lecture, reçu idempotent
  dans People, endpoint navigateur avec CSRF et principal dérivé de la session.
  Action réelle depuis Docs : POST 200 et quatre anciens `/users/me/` 401 en
  **14,686 secondes**. Retour de logout de recette mal configuré vers
  localhost:3000 identifié ; correction du générateur ajoutée, à réappliquer
  et requalifier avant de déclarer ce parcours terminé.
- CSRF Drive de recette : l’environnement attend `CSRF_TRUSTED_ORIGINS` sans
  préfixe Django ; configuration corrigée, PATCH des préférences 200.
- Typage des quatre frontends passé ; 4 tests People (SCIM/admin/déconnexion)
  et 3 tests ST (droits/admin/catalogue) passés. Lint complet des nouveaux
  modules et qualification du logout sans support IdP encore en attente.

### Rattachement, métriques et reprise de connexion — 8 septembre

- Échange HTTP réel Drive → ST qualifié : consommation attachée au principal
  durable ; même Account ST, quota spécifique 20 Go appliqué via
  `storage_policy.account.limit_bytes`, quota d’organisation de recette 40 Go.
  Le champ natif `max_storage_account` reste le défaut de 5 Go ; son override
  est exposé séparément. Le premier assert de recette ciblait le mauvais champ.
- Métriques Drive : filtres UUID du principal et d’organisation, refus des
  anciennes clés `sub`, exclusion des comptes non associés. Les utilisateurs
  suspendus restent comptabilisés. 14 tests métriques passés avant le dernier
  ajout couvrant explicitement la suspension.
- ST : association du compte de métriques accessible dans l’administration
  Django, réservée à l’administrateur plateforme, avec confirmation. Même
  opération partagée par le formulaire et la commande. Test Web ciblé passé.
- People : demande de rattachement issue d’un login vérifié, credential machine
  distinct de la lecture, issuer approuvé par consommateur, plafond de 1 000
  demandes en attente, preuve valable 7 jours. Administration scoped, validation
  explicite, note de preuve, conflits sans fusion et journal du valideur.
  Migration 0010 appliquée dans la recette uniquement.
- Parcours navigateur réel : compte SCIM non associé → page « Rattachement en
  attente » et API 401 → validation Web People → API Docs 200 après 30,037 s.
- Reconnexion : paramètre OIDC standard `prompt=login,max_age=0` disponible
  depuis une page explicite quand l’authentification précède une révocation.
  ST conserve son client Mozilla ; Drive/People/Docs leur client La Suite.
  Qualification du scénario IdP sans logout encore à terminer.
- Authentik réel `active=false` : API Docs 403 et socket ouvert fermé en
  **9,831 s** ; compte réactivé ensuite. Groupe et document conservés.
- Déconnexion commune requalifiée : 4 sessions 401 en **20,722 s**, retour
  correctement sur l’interface Docs de recette port 19114.
- Catalogue requalifié sur les 4 interfaces après correction CSS/CSRF.
- Échanges machine mutualisés : HTTP(S), aucun redirect, délai 5 s, corps et
  credentials bornés. Projection séparée en étapes dans la même transaction.
  **15 tests du paquet partagé passés, lint Ruff partagé passé.**
- Tests People rangés sous `src/backend/suite_directory/tests/`. Nettoyage
  style/documentation People en cours ; dernier cycle complet ciblé People à
  reprendre avec ce nouveau chemin. Aucun changement activé sur le LAN réel.

Restent notamment : logout sans support IdP et retour Keycloak avec preuves,
API/resource-server et accès délégués/emplois, qualification des éditeurs,
installation persistante et migration LAN conservant NAS/Keycloak/quotas,
restauration réelle et nettoyage, docs finales. **Chantier non terminé.**

### Qualification sans logout IdP et accès API — 8 septembre

- Parcours complet avec endpoint logout IdP absent (Docs de recette) : avertissement
  visible, quatre sessions API 401, ancienne session Authentik refusée sur une
  page de récupération, `prompt=login,max_age=0`, nouvelle saisie et même compte
  Docs rétabli (200). Configuration logout Authentik restaurée ensuite.
- Nonce : distinction entre transaction navigateur et jeton d’accès ; état limité
  à l’instance du backend, signature et audience toujours vérifiées. Un vrai
  test RSA signé passe sur Mozilla OIDC 4 (Drive) et 5 (Docs). Un ID token sans
  scopes OAuth est refusé comme bearer.
- HTTP réel : bearer Drive et People 200 ; jeton d’un autre service 401,
  signature altérée 401, ID token 401. Resource-server SCIM Me People par
  introspection Authentik : 200. Docs conserve son API native par session
  (un bearer sur son API utilisateur est normalement refusé).
- Paquet commun : 15 tests avant ajout du test RSA ; ce test ajouté passe sur
  les deux versions de bibliothèque. Ruff partagé passé avant derniers imports.
- People : lint complet du nouveau module passé ; 5 tests ciblés (annuaire,
  rattachement Web, logout, SCIM, reprise des groupes) passés en 3,68 s.
- Les accès ST via bearer restent à requalifier (la recette n’a pas encore
  conservé son access token). Les preuves d’expiration/révocation API après
  ces corrections restent à compléter.

### Retour Keycloak et intégrité — 8 septembre

- Recette revenue à Keycloak dans Drive, ST, People et Docs ; une connexion
  commune et quatre API utilisateur 200. Anciens cookies Authentik : quatre 401.
- Snapshot DB comparé avant/après : UUID des principaux, PK des utilisateurs
  locaux, UUID des groupes, PK des groupes locaux et memberships identiques
  dans les quatre apps.
- Fichier Drive synthétique de 49 octets uploadé par les API natives avant
  bascule, avec un grant au groupe existant ; relecture après bascule par Alice
  et Bob : 200 et même SHA-256. Document Docs partagé : 200 pour les deux,
  reconnexion à la coédition confirmée.
- Métriques Drive → ST après bascule : 49 octets consommés, quota spécifique
  **20 Go**, même Account ST et anciennes lignes Metric toujours présentes.
- Correction du générateur de recette : URL publique S3 port 19100 ; le défaut
  localhost:9000 de l’image rendait les nouvelles politiques upload inutilisables.
  Un premier Item synthétique resté pending est à nettoyer avec la recette.
- `current-status.md` demeure la référence d’avancement ; le plan canonique
  indique maintenant « exécution autorisée, en cours — non livré ».

La recette est **actuellement sur Keycloak**. Le déploiement LAN réel reste
inchangé. Installation persistante, activation LAN, éditeurs et restauration
ne sont pas encore livrés. **Ne pas annoncer la fin du chantier.**

### Compléments Docs et installation — 8 septembre, suite

- Docs coédition : changement éditeur → lecteur referme la connexion au document
  pour réutiliser la relecture native des droits dans l’UI. Les messages en attente
  ne peuvent pas recréer un bail après retrait de la connexion. Test avec vraie
  connexion Hocuspocus : première écriture acceptée, retrait du rôle, écriture
  suivante absente. 13 tests ciblés provider/backend passés (2,67 s).
- Proxy de pièces jointes ajouté à Docs (`docker/suite/media.nginx.conf.template`),
  recette port 19124 : contrôle natif `media-auth` par lecture, S3 signé côté
  serveur, cache privé désactivé. Alice/Bob : 200 et mêmes octets ; anonyme : 403.
  Nouvelle pièce jointe synthétique consignée dans `docs-attachment-private.json`.
- Export PDF natif par l’UI : 5 149 octets, signature PDF vérifiée ; fichier
  téléchargé supprimé. Logs privés `docs-media-export.private.log`,
  `docs-export.private.log`. Capture visuelle Docs examinée.
- Déconnexion commune : receipt créé avant incrément de l’epoch dans la même
  transaction ; `get_or_create` traite une collision concurrente de l’UUID.
  Réutilisation par un autre principal : 409, aucun incrément chez ce dernier.
- Paquet partagé : 16 tests existants passés en 0,41 s ; contrôle additionnel
  de configuration passé (délais contractuels et endpoints obligatoires).
  Administration native de lecture des projections ajoutée (compte, groupe,
  dernier état de synchronisation), bornée par organisation et permissions.
- Wheel `apoze-suite-identity` intégré aux quatre dépendances natives et locks
  (uv / Poetry), ainsi qu’aux quatre Dockerfiles ; builds dev des quatre images
  effectués. **Le wheel doit être régénéré après les derniers ajouts admin/checks**
  puis les images actualisées avant installation. Outil canonique ajouté :
  `docker/suite/package_identity.py`. NGINX 1.30.4-alpine vérifié sur les sources
  officielles https://nginx.org/en/download.html et image téléchargée.
- Aucun changement de données LAN. Relevé actuel : 22 comptes Drive et zéro
  groupe Django ; plusieurs `sub` historiques sont des noms/emails ou null.
  L’ancien backend autorise le fallback email : il faut capturer une connexion
  OIDC réelle pour associer le principal utilisateur actif, jamais déduire une
  fusion d’un email. ST : un utilisateur opérateur existant, organisation UUID
  `a9caecae-4ba5-41f7-b447-58049718cbbd` ; préserver tous les Account/Metric/grants.

Installation persistante et activation LAN toujours **à faire**. Ne pas annoncer
la clôture. Les nouvelles preuves complètent la qualification, pas la livraison.

### Préparation persistante LAN — 8 septembre, suite

- Les bases People/Docs et Redis dédiés sont démarrés dans `suite-local`.
  Migrations natives et partagées appliquées ; interfaces 3001/3002, API
  8072/8073, collaboration 4444 et média 8084 démarrées. Le mode commun
  reste désactivé à ce point : **le chantier n'est pas livré**.
- Les quatre images backend embarquent désormais le wheel partagé et leurs
  verrous natifs. La commande de packaging actualise explicitement ce seul
  paquet pour éviter une empreinte périmée lors d'une reconstruction.
- Keycloak existant conservé. Le profil obligatoire du compte administrateur
  technique a été complété (nom/prénom), sans changer son mot de passe.
  Trois nouveaux clients `apoze-people`, `apoze-docs`, `apoze-st` sont créés ;
  le client Drive existant n'a pas été remplacé.
- Un compte `suite-operator` a été ajouté dans l'IdP commun pour associer
  explicitement l'ancien compte opérateur ST, distinct du compte Drive.
  Connexions OIDC avec PKCE, signature, audience, nonce et issuer vérifiés
  pour les deux personnes et les quatre clients (8 associations).
  L'ancienne identité ST est conservée pour le retour arrière.
- Manifeste privé préparé : 23 comptes existants, 9 associations vérifiées
  (dont l'ancienne ST), 2 groupes initiaux. Aucun rapprochement par email.
- Identifiants S3 Docs dédiés installés via l'IAM natif SeaweedFS ; les
  identifiants administratifs existants sont conservés. Bucket Docs créé,
  versioning activé. Lecture/écriture Docs réussies, lecture/listage du bucket
  Drive refusés, accès Drive inchangé. Objet de qualification et sa version
  supprimés. Référence primaire :
  https://github.com/seaweedfs/seaweedfs/blob/0b80f055c285481eba4ca62ebee7341872c81092/weed/shell/command_s3_configure.go
- Qualification ciblée : 17 tests du socle commun passent ; publication
  d'archive après révocation refusée et nettoyée ; ZIP normal passe avec
  Celery eager explicitement activé dans la recette. Bootstrap administrateur
  People rejoué sans restauration de droits retirés : test passé.
- Correction de préparation : le réglage natif People/Docs de création
  automatique attend `DJANGO_OIDC_CREATE_USER`. Le générateur le désactive
  explicitement avant activation ; le compte vide créé par notre connexion
  technique de préparation doit être nettoyé avec ses gardes de périmètre.
- À faire ensuite : importer le manifeste People, installer les associations
  natives Drive/ST et politiques ST, activer ensemble la synchronisation,
  qualifier le LAN complet (NAS, quotas, éditeurs compris), restauration,
  nettoyage QA, revue ciblée et documentation d'exploitation finale.

### Activation LAN et première connexion commune — 8 septembre

- Les changements ont été intégrés dans les dépôts locaux Drive et ST après
  comparaison avec les archives de départ : aucun conflit, aucune suppression.
  Branches locales : `codex/suite-identity-local-rollout` dans les deux dépôts.
  Aucun commit, push ou PR. Images précédentes gardées sous des tags de retour
  arrière ; nouvelles sauvegardes PostgreSQL `*-pre-rollout.pgdump` privées.
- Compte de connexion préparatoire People et son contact automatique supprimés
  après vérification : aucun groupe ni principal associé. Import People appliqué
  ensuite : 23 principaux, 2 groupes, 9 associations externes vérifiées.
- 22 comptes Drive et 1 compte ST associés sans remplacement de PK.
  Projection des 23 principaux réussie dans les quatre applications.
- Services ST : Drive 2 conservé ; People 7, Docs 8 et Administration 9 ajoutés.
  Accès Drive/People/Docs par groupe « Membres de la suite », ST par groupe
  « Administration de la suite ». Deux administrateurs initiaux explicitement
  provisionnés. Les deux comptes de métriques correspondants sont associés par
  leur ancien identifiant contractuel ; 88 comptes et 175 métriques conservés
  au point de contrôle. Le quota de test existant n'est pas remplacé.
- Synchronisation et règles communes activées. Workers et ordonnanceurs natifs
  démarrés, dont un ordonnanceur ST local séparé. Keycloak, NAS, S3, éditeurs et
  bases existantes conservés ; seuls les processus applicatifs ont été relancés.
- Deux écarts révélés par le LAN corrigés : transmettre uniquement l'UUID
  d'organisation dans les appels ST migrés (ancien réglage SIRET ignoré) ;
  ajouter le scope Keycloak standard `basic` aux trois nouveaux clients pour
  obtenir `auth_time`. Aucun assouplissement des validations OIDC.
  Référence : https://www.keycloak.org/docs/latest/upgrading/
- Connexion navigateur LAN réelle réussie : Drive, ST, People, Docs retournent
  200 après une seule saisie de mot de passe. PK Drive conservé :
  `6c406f20-5a52-4dc5-9411-cbe42cabf7e3`. Les contrôles Django de sécurité
  passent sur les quatre services. Annuaire frais et politiques synchronisées.
- Test ciblé ajouté pour empêcher les anciennes claims IdP de modifier le
  routage compte/organisation ST : passé. Normalisation des UUID lors d'appels
  programmatiques de la commande de liaison : test passé ; **réembarquer ce
  dernier correctif de commande dans les wheels/images avant livraison finale**.
- Toujours à terminer : recette LAN stockage/NAS/éditeurs, révocation et Docs,
  restauration, nettoyage QA, revue de périmètre et guides d'exploitation.

### Recette LAN fichiers et coédition — 8 septembre, suite

- Quota de l'utilisateur Drive : **20 000 000 000 octets**, confirmé par API.
- Opérateur ST connecté avec son nouveau compte IdP commun : PK ST historique
  `e9eacef0-9b9a-4e32-9969-744b197a7c91` conservé. Docs révélait un défaut
  natif de sérialisation des utilisateurs sans email : corrigé sans inventer
  d'adresse ; 5 tests ciblés passent.
- People : contrôles du déplacement de groupes sur les deux chemins Treebeard
  (endpoint et formulaire), sélecteurs de services et webhooks limités à
  l'organisation. Un test comportemental ciblé passe ; lint des fichiers
  concernés passe. Les groupes importés sont consultables et administrés via
  leur source, sans modification native concurrente.
- Le serveur de collaboration Docs restait actif mais sa compilation échouait
  sur le `dist` créé par la QA sous root. Les caches Next, les assets emoji
  générés et le `dist` de collaboration sont désormais isolés par conteneur
  via tmpfs inscriptibles. Les sources ne sont plus partagées pour ces sorties.
- **Docs LAN : création native, partage par groupe, coédition dans les deux
  sens et rechargement du contenu sauvegardé réussis.** Document synthétique
  à supprimer après la suite de la recette :
  `64368765-dd93-4749-9a60-b700dbb8e34e`.
  Preuve visuelle : `output/playwright/suite-identity/docs-lan-coediting.png`.
- **S3/NAS LAN :** fichier synthétique de 69 octets téléversé et relu à
  l'identique dans chaque stockage ; aperçu texte NAS 200. Fichier NAS supprimé
  (204). Pour S3, la suppression définitive exige d'abord la corbeille native :
  nettoyage effectué ensuite avec cette séquence ; vérifier la purge physique
  terminée à partir de `lan-storage-cleanup-private.json`.
- Aucun fichier utilisateur préexistant n'a été supprimé. Les premiers essais
  S3 ont seulement rencontré les validations de sélection d'espace/dossier,
  puis une session expirée : aucune création lors de ces refus.
- À finir : export/attachments/révocation Docs LAN, qualification des éditeurs
  Drive/S3/NAS, retour de droits et déconnexion, sauvegarde-restauration réelle,
  nettoyage final des ressources de QA, packaging du dernier correctif de
  liaison et documentation finale. **Ne pas marquer ce chantier terminé.**

### Recette finale LAN et restauration — 8 septembre, 12 h UTC

- Les quatre applications reconnaissent les deux personnes migrées, avec une
  seule saisie de mot de passe par personne. Les quatre catalogues présentent
  leurs quatre liens dans le viewport. Le menu Docs est repositionné au-dessus
  du bouton situé en bas de sa barre latérale. L'administration People est
  accessible depuis son menu utilisateur pour le personnel autorisé.
- Docs : export PDF natif réussi (5 827 octets), téléchargement local supprimé.
  Pièce jointe native : deux lecteurs autorisés 200, anonyme 403.
- **Écart de déploiement justifié par la recette :** SeaweedFS 4.12 du Drive
  existant ignore les versions dans sa branche CopyObject de remplacement des
  métadonnées sur la même clé. L'upload Docs écrivait les octets mais échouait
  lors du passage au statut prêt. Aucune modification de sécurité Docs et
  aucune mise à jour du stockage Drive pour contourner cet échec.
  Le stockage Docs utilise désormais un service dédié SeaweedFS **4.46**,
  figé sur le digest `08d516132314207d10c8e37cbffc1f32b147d870169688734cc61c6231625b62`,
  volume `suite-local_docs-s3`, réseau interne `suite-local_docs-storage`,
  aucun port publié. Compte applicatif limité au bucket Docs ; compte
  d'installation distinct, absent des conteneurs applicatifs. Les deux objets
  synthétiques existants ont été copiés (464 octets), hashes vérifiés, sources
  encore conservées jusqu'au nettoyage final.
  Sources primaires :
  https://github.com/seaweedfs/seaweedfs/blob/0b80f055c285481eba4ca62ebee7341872c81092/weed/s3api/s3api_object_handlers_copy.go
  https://github.com/seaweedfs/seaweedfs/pull/10594
  https://github.com/seaweedfs/seaweedfs/releases/tag/4.46
- Le générateur privé prépare aussi l'IAM S3 dédié. La commande durable
  `docker/suite/provision_docs_storage.py` initialise le bucket, vérifie une
  copie de métadonnées versionnée, les deux versions et leur contenu, puis
  supprime exactement sa sonde. Qualification réussie.
- Administration People : le bootstrap initial omettait le droit natif de
  suppression d'un membership. Il l'accorde maintenant sans accorder la
  suppression de personnes/groupes ; droit ajouté explicitement aux deux
  administrateurs initiaux. Suppression de masse des memberships désactivée
  pour conserver les contrôles de source par objet. Bootstrap ciblé : 1 test
  passé. Retrait Web réel : document 403, média 403, ST 403 en **19,303 s** ;
  WebSocket fermé en **17,603 s**, propriétaire encore autorisé. Membership
  original rétabli.
- **Éditeurs LAN :** ONLYOFFICE sur S3 DOCX, Collabora sur S3 ODT et Collabora
  sur NAS ODT chargent, acceptent une saisie et sauvegardent. Texte synthétique
  retrouvé dans les octets des trois fichiers relus depuis le stockage.
  Les trois fichiers sont recensés dans le manifeste privé
  `lan-editors-cleanup-private.json` et doivent encore être supprimés.
- Wheel finale du socle reconstruite avec le correctif de normalisation UUID :
  SHA-256 `317e96e61d331b9af82294ea8359f5fb25c130d588b396007a834ec46e1dd5bf`.
  Quatre images reconstruites avec succès ; processus backend/worker/beat LAN
  relancés, venv anonymes Drive renouvelés. Keycloak, NAS et stockage Drive
  conservés. Sources et locks Drive/ST synchronisés avec leurs worktrees.
- Frontend : lint ciblé et types People/Docs/provider corrigés. Le contrôle
  des types Docs utilise les globals Vitest déjà installés :
  `yarn tsc --noEmit --incremental false --types vitest/globals,node`.
  Sans ces types explicites, le tsconfig natif inclut les tests mais ne trouve
  pas leurs globals. Aucun package de tests supplémentaire ajouté.
- Backend : imports et format ciblés remis en ordre ; checks Django de sécurité
  passent sur les quatre apps. Le formulaire natif de rattachement métrique ST
  énumère ses champs ; 2 tests ciblés passent. Dans le montage QA `/code`,
  précharger `code,pdb` avant `pytest.main` évite le conflit avec le module
  standard ; utiliser `DJANGO_CONFIGURATION=Test`, suite désactivée par défaut
  puis activée par les tests qui la ciblent. Ne pas exécuter ce test admin sous
  Development avec le middleware de debug toolbar.
- **Restauration exercée :** dumps des quatre bases LAN après activation,
  restauration complète dans quatre bases isolées du PostgreSQL QA, comparaison
  exacte des colonnes stables d'identité/ownership/groupes/quotas, succès.
  Bases de restauration supprimées. Objets Docs : **5 versions** restaurées
  dans un bucket QA dédié, hashes et métadonnées identiques, bucket et versions
  de restauration supprimés. Sources et dumps privés conservés pour reprise.
- État toujours **non livré** : qualification WOPI révoqué en cours ; vérifier
  aussi le compte de secours et la protection du dernier administrateur/owner
  dans les chemins Web natifs (les API natives ont déjà une garde du dernier
  owner, les chemins Django admin/suspension doivent être revus). Restent la
  qualification Bearer ST, les guides/ADR/manifeste final, la revue des critères
  V1–V12 et le nettoyage des fixtures/projets QA. Ne pas clôturer prématurément.
