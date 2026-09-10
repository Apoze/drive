# Projects — intégration complète à la suite Apoze sur le LAN

Date : 10 septembre 2026.
Statut : **PLAN PRÉPARÉ — IMPLÉMENTATION NON COMMENCÉE**.
Ce document sert de contrat d'exécution et de suivi pour l'agent.
La rédaction et la publication du plan ne démarrent pas le chantier.

## 1. Résultat attendu et décisions de périmètre

Livrer Projects utilisable depuis le catalogue commun, avec connexion OIDC,
identités et groupes People, accès et budgets ST, collaboration en temps réel,
fichiers privés Drive S3/NAS et notifications reçues dans Messages.
L'administrateur et les utilisateurs doivent accomplir les opérations courantes
depuis les interfaces web, sans commandes SQL ou édition de fichiers secrets.

| Domaine | Livraison obligatoire |
| --- | --- |
| Projects natif | Projets, dossiers/tableaux, listes, cartes, tâches/checklists, affectations, étiquettes, commentaires, échéances, suivi du temps, filtres, duplication, suppression et export CSV selon les capacités de la base retenue |
| Identité | Même personne People et mêmes données après changement d'IdP ; Keycloak existant conservé, Authentik qualifié séparément |
| Accès | Attribution de l'application dans ST ; groupes dans People ; rôles de projet/tableau et droits directs administrables dans Projects |
| Fichiers | Pièces jointes natives privées ; ajout de liens Drive/Docs, copie explicite depuis Drive et enregistrement vers Drive, avec S3 et NAS transparents |
| Gouvernance | Quotas propres à Projects, réservations atomiques, propriétaire de facturation explicite et métriques ST |
| Communication | Notifications natives dans Projects et mails transactionnels internes reçus dans Messages |
| Suite | Catalogue et déconnexion communs ; liens authentifiés vers les autres applications, sans propagation implicite de droits |
| Exploitation | Docker LAN persistant, démarrage/reprise, sauvegarde cohérente, restauration isolée, supervision minimale, nettoyage et publication GitHub |

Le périmètre reste **LAN uniquement**. Adresse proposée :
`http://192.168.10.123:8940`, à confirmer libre au préflight ; port interne
natif `1337`. Ne remplacer aucun service sur un port déjà utilisé.

Conserver l'interface et les fonctions natives Projects. Aucun clonage de
l'explorateur Drive dans Projects, aucune réécriture de Sails/React, aucun
nouveau service d'identité, aucun moteur de workflow généraliste.

Limites choisies pour ce chantier, à présenter clairement dans la livraison :

- Les échéances restent des données Projects. Pas de synchronisation
  bidirectionnelle cartes/agendas, de flux ICS supplémentaire ni de création
  automatique de rendez-vous. Calendars reste accessible par le catalogue.
- Un lien vers une réunion Meet existante peut être placé dans une carte ;
  l'admission reste celle de Meet. Pas de nouvelle orchestration de réunions.
- Les documents Docs sont liés par leurs ressources Drive existantes, ou
  exportés explicitement ; aucune seconde copie de document vivant dans Projects.
- Tableaux privés et partages internes seulement dans ce déploiement. Le mode
  natif de tableau public est désactivé côté serveur et masqué dans l'interface.
- Les notifications mail suivent les événements natifs et préférences Projects.
  Une échéance seule ne promet pas un rappel planifié que Projects ne fournit pas.
- Pas de WAN, application mobile spécifique, IA, enregistrement, transcription,
  webhooks externes ou reprise du chantier Grist. Aucun service sous activation
  payante ; conserver la licence libre et les notices de la base Projects.

Ces exclusions ne peuvent pas servir à reporter un point obligatoire du tableau.
Une anomalie empêchant une fonction native retenue doit être corrigée à sa source,
ou faire l'objet d'une décision explicite du propriétaire avant clôture.

## 2. État inspecté et base technique

### 2.1 Sources figées

Inspection en lecture seule du dépôt `suitenumerique/projects` le 10 septembre.
Checkout temporaire : `tmp/projects-source/`, non publié et non déployé.
Référence inspectée : **`7858be2a22ca87cacd6ff5d67a149aa06cb11b6b`**,
commit du 7 septembre 2026 sur `main`.

L'API GitHub annonce encore la release `v1.2.0` du 6 février, alors que
`package.json` et le changelog du code inspecté portent `1.3.0`.
Ne pas confondre la dernière release publiée et la révision réellement livrée.
Le commit inspecté apporte notamment le correctif d'en-têtes des pièces jointes
contre les extensions trompeuses ; ne pas repartir d'une image ancienne qui
l'omet. Retenir ce SHA comme base par défaut, vérifier les avis/correctifs
pertinents au démarrage et consigner toute révision différente avant de coder.

| Constat vérifié dans le code | Conséquence pour l'intégration |
| --- | --- |
| Serveur Node/Sails, PostgreSQL/Knex/Waterline ; client React ; Docker fourni | Adapter les mécanismes natifs ; le paquet Python `suite-identity` n'est pas importable tel quel |
| `openid-client` est déjà présent ; association native issuer/sub avec repli par email | Garder la bibliothèque OIDC, remplacer le repli email par le rattachement People approuvé |
| Email requis par le modèle User et le login ; rôle admin et organisation peuvent venir de claims | Permettre un profil People sans email en mode suite ; aucune autorité métier tirée des claims IdP |
| JWT applicatif et table Session ; expiration configurable en jours, défaut 365 | Ajouter les bornes de preuve et de révocation de la suite, indépendamment du JWT natif |
| Hook `current-user` traite `/api/*` et `/attachments/*` ; watcher vérifie surtout l'expiration JWT | Contrôler aussi les droits actuels et retirer effectivement les sockets des canaux de contenu |
| ProjectManager et BoardMembership avec owner/editor/viewer et canComment | Réutiliser les rôles natifs avec provenance des droits directs et de groupe |
| Chemin public `boards/show` distinct | Fermer explicitement les accès publics dans le profil suite ; ne pas compter sur le menu caché |
| `receive-file` passe `maxBytes: null` | Borner toutes les entrées avant traitement et publication |
| Attachment n'enregistre pas de taille/quota ; copie et suppression passent par FileManager | Ajouter taille, facturation et journal de réservation sans remplacer les backends natifs |
| S3 `deleteDir` ne lit qu'une page ; `buildUrl` expose une URL de bucket pour avatars/fonds | Paginer la purge et servir les médias privés à travers des routes autorisées |
| Notifications natives et SMTP existent ; erreurs d'envoi actuellement absorbées | Raccorder le transport LAN et rendre les échecs/reprises visibles et durables |
| `start.sh` appelle `db/init.js`, qui lance migrations et seeds | Séparer migration contrôlée et premier bootstrap ; pas de reseeding privilégié à chaque redémarrage |

Sources primaires figées :

- [Code et fonctions natives](https://github.com/suitenumerique/projects/tree/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b).
- [Version applicative](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/package.json),
  [changelog](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/CHANGELOG.md),
  [release publiée](https://github.com/suitenumerique/projects/releases/tag/v1.2.0).
- [Licence AGPL](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/LICENSE),
  [Dockerfile](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/Dockerfile).
- [Rattachement OIDC](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/server/api/helpers/users/get-or-create-one-using-oidc.js),
  [callback](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/server/api/controllers/access-tokens/exchange-using-oidc.js).
- [Authentification des requêtes](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/server/api/hooks/current-user/index.js),
  [watcher](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/server/api/hooks/watcher/index.js).
- [Rôles](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/server/api/models/BoardMembership.js),
  [tableaux publics](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/server/api/controllers/boards/show.js).
- [Réception des fichiers](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/server/api/helpers/utils/receive-file.js),
  [S3 FileManager](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/server/api/hooks/file-manager/S3FileManager.js),
  [correctif d'en-têtes à conserver](https://github.com/suitenumerique/projects/commit/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b).
- [Notifications](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/server/api/helpers/notifications/create-one.js),
  [envoi SMTP](https://github.com/suitenumerique/projects/blob/7858be2a22ca87cacd6ff5d67a149aa06cb11b6b/server/api/helpers/utils/send-email.js).

Ces constats sont une inspection de code, pas une recette déjà réussie.

### 2.2 Contrats locaux à réutiliser

Lire au début de l'exécution, puis uniquement les surfaces nécessaires :

- [ADR identité durable](../../adr/0003-suite-durable-identity-and-access.md),
  [exploitation identité](../../operations/suite-identity-access.md).
- [Contrat stockage](../../agent-storage-contract.md),
  [Docs natifs dans Drive](docs-drive-native-documents-integration-plan.md).
- [Messages/Calendars](messages-calendars-integration-plan.md),
  [exploitation mail LAN](../../operations/suite-messages-calendars.md).
- [Publication des forks existants](../../../output/implementation/suite-publication/publication.md),
  `AGENTS.md` et les instructions de chaque checkout modifié.

Points d'entrée locaux déjà présents :

| Surface | Réutilisation / extension ciblée |
| --- | --- |
| Drive `src/packages/suite-identity/suite_identity/{oidc,login,directory,policy,access,views}.py` | Référence sémantique des contrats People/ST, preuves, fraîcheur et déconnexion ; adapter un consommateur Node |
| Drive `suite_identity/document_transport.py` | Forme du principal et de la preuve de délégation, bornes et validation chez le destinataire |
| Drive `core/api/messages_files.py`, `core/services/messages_files.py` | Mécaniques de lecture/copie privée, export Docs, reprise, digest et quotas à extraire seulement là où Projects les partage réellement |
| Drive `pages/sdk/messages.tsx` | Sélecteur fondé sur AppExplorer ; factoriser pour un second consommateur enregistré |
| ST `core/services/suite_access.py`, resolvers `access_entitlement_resolver.py`, `storage_policy.py` | Accès générique par souscription, décisions bornées, budgets ; nouvelle famille Projects si nécessaire |
| Drive `docker/suite/prepare_local.py`, `prepare_mail.py`, `mail_operations.py` | Configuration persistante, consommateurs machine, sauvegarde et restauration ; réutiliser les helpers existants |

## 3. Architecture et règles à implémenter

### 3.1 Identité Node, sessions et déconnexion

Un adaptateur **dans Projects** applique les contrats HTTP existants People/ST.
Le code commun reste local à `server/api/helpers/suite/` et à un hook de cycle
suite, ou aux répertoires natifs équivalents. Ne pas créer un paquet npm générique
ou un proxy Python uniquement pour ce consommateur.

Conserver tous les identifiants natifs Projects. Ajouter des associations vers
le principal People UUID et l'organisation ST ; ne jamais convertir les IDs
numériques natifs en UUID ou en Number JavaScript susceptible de perdre des bits.

Modèle additif minimal, noms définitifs adaptés aux conventions Knex/Waterline :

- Compte suite : userId unique, principal UUID unique dans l'organisation,
  actif, révisions, groupes, instants de vérification, epoch et auth_not_before.
- Identité externe : issuer exact, subject opaque, consommateur/client et
  principal ; unicité transactionnelle, état actif. Ne pas transférer une liaison
  existante vers une autre personne sans procédure explicitement approuvée.
- État du snapshot : révision complète publiée et métadonnées de synchronisation.
- Preuve de session : principal, organisation, issuer/client, auth_time,
  auth_until, session_version ; rien de tout cela ne provient d'un champ libre
  envoyé par le navigateur.

Réutiliser `openid-client` pour la signature, JWKS et échange de code. Rendre
l'état/nonce/PKCE liés à une transaction de connexion créée côté serveur,
expirante et consommée une seule fois ; ne pas accepter un simple nonce libre
comme preuve de transaction. Utiliser une persistance PostgreSQL bornée si
aucun stockage de session partagé approprié n'est déjà utilisé. Pas de nouveau
Redis uniquement pour mémoriser quelques transactions OIDC.

Valider issuer, audience/azp, subject, expiration, iat, auth_time, nonce/state,
PKCE et égalité du subject UserInfo. Preuve d'authentification maximale :
15 minutes, comme la suite ; demander `max_age=900` au fournisseur.
Après échéance, renouveler par le flux OIDC natif
ou demander une reconnexion ; une session JWT de longue durée ne prolonge pas
cette preuve. Effacer codes et transactions consommés ; ne jamais journaliser
codes, nonce, jetons, cookies ou réponses du fournisseur, même partiellement.

Pour une identité inconnue : demande authentifiée via l'API People existante,
écran « association à approuver », puis réessai après approbation dans People.
Aucune fusion par email, nom, SIRET ou groupe homonyme. Les groupes importés
d'un annuaire restent gérés par People, sans second import SCIM dans Projects.

Permettre une personne sans email en mode suite : adapter modèle, contraintes,
serializers, recherche et affichage natifs ; pas d'adresse fictive routable.
L'email est un contact pour les notifications. Une adresse manquante n'empêche
ni la connexion ni les droits ; l'UI indique l'indisponibilité des mails.
Les utilisateurs historiques ne sont ni supprimés ni automatiquement fusionnés.

Cookies nommés/scopés pour éviter les collisions entre applications sur la même
IP et des ports différents ; HttpOnly pour les secrets de session, SameSite,
contrôle d'origine/CSRF selon le mode natif. Pas d'ouverture CORS globale pour
faire fonctionner le LAN. Les secrets OIDC restent au serveur. Traiter les
onglets, retour arrière et renouvellement sans perdre un commentaire en cours.

Déconnexion Projects et déconnexion commune People : invalidation serveur,
nettoyage client, fermeture des sockets ; conserver les actions et explications
existantes lorsque l'IdP ne fournit pas de logout global.

### 3.2 Synchronisation, accès et groupes

People est autorité des personnes/groupes ; ST de l'accès à Projects ; Projects
de ses projets/tableaux/cartes. Une seule organisation configurée par déploiement.
Désactiver l'auto-organisation et les promotions par claims IdP :
`ORGANIZATION_ID_CLAIM` absent, rôles IdP ignorés. `ALLOW_ALL_TO_CREATE_PROJECTS`
ne vaut jamais un accès à l'application ; exposer une politique de création
explicitement choisie dans l'administration (administrateurs par défaut).

Synchroniser les pages People et les décisions ST toutes les 30 secondes.
Valider intégralement organisation, consommateur, révision, IDs, doublons et
pagination avant publication atomique. Un snapshot incomplet ou plus ancien
ne retire pas de droits et ne remet pas à neuf une décision précédente.
Préférer une table de staging temporaire par synchronisation aux tableaux
illimités en mémoire. Nettoyage des stagings abandonnés.

Borne de validité positive : 90 secondes au maximum, calculée depuis le début
de la vérification et les leases reçus ; ne pas additionner les caches.
Borne de révocation de livraison : **120 secondes au plus**, incluant les sockets.
Contrôler les requêtes HTTP, Socket.IO, téléchargements, vignettes, exports,
reprises et travaux différés. En panne People/ST, refuser après expiration
avec un état de service indisponible ; ne pas accorder des droits par défaut.

Le watcher natif doit consulter sessions et droits actuels, puis faire quitter
les canaux board/project/user ou déconnecter réellement les sockets concernés.
Un simple événement client `logout` ne protège pas contre un client qui l'ignore.
Aucun abonnement, broadcast de changement ou notification ne doit encore livrer
le contenu d'un tableau révoqué après la borne. Vérifier aussi les sockets inactifs
qui reçoivent des événements sans faire de nouvelle requête.

| Rôle | Pouvoirs / limite |
| --- | --- |
| Administrateur ST | Attribue l'application et ses budgets ; ne devient pas automatiquement lecteur de toutes les cartes |
| Administrateur Projects | Administration et création selon politique ; expliciter les pouvoirs natifs réellement conservés, sans promotion par IdP |
| Responsable de projet | Gestion du projet et de ses tableaux dans les limites natives ; attribution par utilisateur ou groupe People explicite |
| Owner de tableau | Administration du tableau et de ses membres |
| Editor | Cartes, tâches, commentaires et pièces jointes selon le modèle natif |
| Viewer | Lecture ; commentaire seulement si canComment est accordé |
| Non-membre / accès ST refusé | Aucun contenu, API, export, fichier ou événement temps réel autorisé |

Ajouter des grants People par projet et par tableau, avec sélection/recherche
bornée et rôles natifs. Conserver une provenance distincte des grants directs.
Droits effectifs = union des grants actifs, priorité owner > editor > viewer,
commentaire explicite ; retrait d'un groupe conserve un grant direct restant.
Le refus ST ou la suspension People interdit l'application malgré cette union.

Ne pas transformer chaque membership matérialisé en grant direct lors d'une
édition. La suppression d'un accès hérité affiche son origine et conduit au
grant source. Renommer un groupe conserve ses droits ; suppression/recréation
homonyme ne les récupère pas. Couvrir membres hors ligne, nouveaux tableaux,
duplication, déplacements et utilisateurs supprimés conservés dans l'historique.
Préserver au moins une voie de récupération d'administration sans donner de
pouvoir implicite au dernier utilisateur qui se connecte.

### 3.3 Stockage natif, quotas et suppression

Choix de base : **bucket S3 privé dédié à Projects**, identité S3 limitée à ce
bucket, sur un service suite existant compatible et vérifié. Aucun accès direct
au bucket Drive ou aux credentials du NAS. L'échange avec S3/NAS Drive utilise
les APIs Drive. Le FileManager natif reste la frontière de stockage Projects.

Réutiliser le S3 existant après contrôle de l'isolation, des autorisations et de
CopyObject ; si ce contrat manque, corriger la configuration ou créer le seul
service S3 nécessaire, sans imposer une mise à jour du stockage Drive.
Conserver le backend local natif compatible si touché, sans le déployer comme
seconde copie concurrente des mêmes pièces jointes.

Servir aussi avatars et fonds privés par des routes applicatives autorisées.
Ne pas rendre le bucket public pour résoudre l'affichage. Borner le cache HTTP
par les leases restantes, ou `private, no-store` lorsque c'est plus simple.
Conserver les en-têtes anti-XSS de la base ; HTML/SVG et contenus inconnus ne
s'exécutent pas sous l'origine Projects. Les assets statiques du produit peuvent
rester publics, pas les fichiers utilisateurs.

Valeurs initiales de garde, centralisées et documentées : 25 MiB par pièce
jointe ou transfert, 5 MiB par avatar/fond, 10 MiB par import JSON ; limites de
pixels/pages et délai Sharp explicites. Les plafonds applicatifs configurables
ne dépassent pas les capacités réellement supportées par les chemins utilisés.
Toutes les entrées passent la même admission : navigateur, import Drive,
duplication, import de tableau, avatar/fond. Ne pas vérifier la taille seulement
après avoir accepté un corps illimité. Temporaires bornés, abandon/timeout nettoyés.

Réutiliser l'antivirus LAN existant par un accès réseau limité et des délais
bornés. Scanner avant publication et génération d'aperçu. Fichier suspect refusé,
scanner indisponible : publication refusée et erreur récupérable. Pas de nouveau
moteur antivirus ou de port ClamAV public pour Projects.

ST expose une famille Projects de budgets en reprenant `storage_policy.py` :
instance, organisation, compte People et projet. Projects en est l'exécuteur
atomique, les métriques ST ne constituent pas un verrou d'admission.
Un projet a un propriétaire de facturation People stable ; les pièces jointes
collaboratives débitent ce propriétaire et le budget du projet, pas le dernier
éditeur. Avatars : propriétaire utilisateur. Fonds : propriétaire du projet.
Migration de propriétaire : aperçu, contrôle des nouveaux plafonds et transfert
atomique de la facturation ; pas de changement silencieux lors du départ d'un membre.

Compter les octets réellement conservés, dérivés compris ; exposer séparément
usage logique original et usage physique si nécessaire. Réservations avant
écriture, verrouillage SQL avec ordre stable, validation finale de la taille,
libération après suppression confirmée. Les copies indépendantes sont facturées
indépendamment ; un simple lien Drive n'est pas une copie Projects.
Le total physique et les budgets d'utilisateur/projet se recouvrent : ne pas
les additionner dans une métrique globale. Pas de quota atomique partagé entre
tous les produits annoncé sans mécanisme correspondant.

Journal durable minimal pour les écritures/copies : clé idempotente, acteur,
destination, taille/digest, état, réservation, objet natif et résultat. Réutiliser
la même mécanique pour upload, copie et export entrant. Une reprise ne publie
pas deux fichiers et ne libère pas la réservation d'un objet encore présent.
Revalider droits et budgets avant publication après une longue interruption.

Corriger `S3FileManager.deleteDir` : pagination complète, préfixe exact terminé
par séparateur, erreurs partielles DeleteObjects traitées, absence d'objet
idempotente. Couvrir suppression pièce/carte/tableau/projet et remplacement
avatar/fond ; aucun préfixe de projet voisin supprimé. Prévoir collecte des
objets orphelins et réservations expirées avec un délai de grâce, inventaire
et aperçu ; aucune purge globale de bucket ou Docker.

### 3.4 Drive, Docs et navigation

Trois actions distinctes dans l'interface :

1. **Ajouter un lien Drive/Docs** : référence ressource/espace et URL canonique.
   Les membres du tableau n'obtiennent aucun droit Drive supplémentaire.
   La présentation précise qu'un accès au document est nécessaire. Aucun
   aperçu de contenu ni titre recalculé sous les droits du créateur pour un tiers.
2. **Copier depuis Drive** : l'acteur dispose de lecture/export côté Drive et
   d'écriture côté Projects. Une copie indépendante est annoncée comme visible
   aux membres autorisés du tableau. Pour Docs, export explicite, jamais lecture
   directe de son S3. Pas de lien public créé pour contourner l'autorisation.
3. **Enregistrer dans Drive** : lecture Projects et création dans la destination
   S3/NAS choisie ; quotas Drive, collision et idempotence natives conservés.

Factoriser le sélecteur `pages/sdk/messages.tsx` autour d'AppExplorer pour les
consommateurs enregistrés Messages et Projects. Origine exacte autorisée,
fenêtre attendue, corrélation imprévisible, données bornées et fermeture propre.
Ne pas accepter une origine arbitraire depuis un paramètre d'URL.
Pas de remplacement du shell Mes fichiers ni de nouvelle page Montages.

Réutiliser les services de copie privés de Drive en séparant la mécanique du
nom Messages. Entrées Projects propres, credentials lecture/mutation distincts,
consommateur vérifié et preuve d'acteur compatible avec `document_transport`.
Ne pas réutiliser les secrets Messages. Un appel machine ne choisit pas librement
un principal humain : la preuve doit provenir de la session OIDC validée et être
recontrôlée chez Drive. Corps, réponses et digests bornés ; aucun fetch serveur
sur URL utilisateur arbitraire, aucun chemin de NAS transmis au navigateur.

Un ajout de lien ne constitue pas une prévisualisation autorisée. Si le titre
fourni est celui saisi volontairement par le membre de la carte, il fait partie
de la carte ; ne pas faire passer cette annotation pour des métadonnées Drive
accessibles à tous. Après suppression source, le lien devient indisponible ;
une copie explicitement réalisée reste une copie indépendante.

Ajouter Projects au catalogue ST avec état masqué jusqu'à validation. Afficher
le catalogue commun dans Projects et tester l'aller-retour depuis Drive/Docs.
Les URLs des applications proviennent de la configuration, pas de domaines
codés dans les composants. Conserver langue FR, clavier, états vides et messages
de refus compréhensibles dans les modales ajoutées.

### 3.5 Messages et notifications

Réutiliser le SMTP et les notifications natives Projects. Expéditeur de service
proposé : `projects@mail.apoze.test`, provisionné distinctement des comptes de
recette. Résoudre les destinataires vers des adresses de boîte attribuées dans
Messages ; ne pas déduire une adresse `@mail.apoze.test` d'un nom ou d'un UUID.
Une personne sans boîte garde ses notifications internes. Si aucune API machine
existante ne fournit cette correspondance, ajouter dans Messages une lecture
étroite « principals People demandés → adresse primaire active », limitée au
consommateur Projects et à son organisation. Credential dédié, réponse bornée,
pas de permission d'administration générale des boîtes ni d'annuaire public.
Règle déterministe en cas d'absence/ambiguïté : aucun envoi et statut explicite,
jamais sélection arbitraire d'une boîte partagée.

Raccorder le transport entrant LAN existant via un chemin interne limité à
Projects et au MTA, sans publier SMTP sur le WAN, sans exposer les clés MDA.
Qualifier ses restrictions de relais et d'expéditeur ; si le transport natif
nécessite une authentification de soumission, ajouter cette capacité au MTA
existant et un credential dédié, pas une nouvelle pile mail. Refuser tout
expéditeur arbitraire et tout destinataire Internet dans le profil LAN.

Avant envoi, revalider le destinataire, l'accès ST et le droit au tableau ; ne
pas envoyer de contenu d'un tableau retiré pendant une panne ou une attente.
Respecter les préférences natives. Éviter le contenu sensible dans l'objet du
mail ; le lien profond conduit au contrôle d'accès de Projects.

Rendre l'envoi durable en enrichissant le journal/notification natif avec état,
clé d'émission, tentatives et prochain essai si nécessaire. Pas de Celery/RabbitMQ
pour ce seul besoin : traitement borné dans le cycle natif, verrou PostgreSQL
empêchant les doubles traitements après redémarrage. Une erreur n'est pas un
succès silencieux. Réutiliser un Message-ID stable ; distinguer une remise SMTP
acceptée, un rejet et un résultat incertain. Ne pas promettre « exactement une
fois » après une perte de réponse SMTP : éviter les retries aveugles et prévoir
une reprise explicite des résultats incertains.

Pour une reprise à résultat certain, la recette doit prouver un seul mail reçu.
Réponse à une notification : indiquer le comportement réel de l'adresse de
service ; pas de promesse de transformation du mail en commentaire.

### 3.6 Déploiement, reprise et exploitation

Préparation proposée dans Drive : `docker/suite/prepare_projects.py`,
`provision_projects_local.py` et `projects_operations.py` seulement si leurs
responsabilités ne sont pas déjà couvertes par un helper existant.
Configuration privée sous `data/projects-local/`, Compose nommé `suite-projects`.
Aucun changement aux scripts de démarrage Drive demandé pour ce chantier.

Application construite depuis le fork, lockfiles respectés avec `npm ci` ;
versions Node et images fixées, notices de licence conservées. DB Projects
et rôle PostgreSQL distincts dans la pile suite existante, bucket privé et
credentials propres. Pas de Keycloak, PostgreSQL ou frontend de développement
supplémentaires issus aveuglément du compose de démonstration.

Une instance applicative suffit au LAN ; boucle de synchronisation, reprises et
collecte native bornées. Verrou advisory PostgreSQL pour éviter deux exécutions
concurrentes lors d'un redémarrage. Ne pas ajouter Redis ou un cluster pour une
charge hypothétique. Les workers ne conservent pas indéfiniment une décision
positive ou un objet User lu avant révocation.

Démarrage : vérifier dépendances, migrer avec verrou, bootstrap idempotent
séparé, démarrer, synchroniser People/ST, devenir prêt seulement ensuite.
Supprimer les comptes/secrets de démonstration du chemin de déploiement. Compte
de récupération protégé, accès limité, distinct d'un contournement public du SSO.
Configuration et clés conservées entre préparations et reconstructions.

Statut exploitable : version, santé DB/S3, âge des snapshots et leases,
réservations/envois/purges en attente ou échec, place disque, état du scanner.
Jamais de contenu, identités externes complètes, cookies ou jetons dans ces
rapports. Codes d'erreur stables et corrélation technique sans données métier.

Sauvegarde : figer les mutations Projects et ses traitements, dump DB cohérent,
objets natifs/dérivés, journaux, configuration privée chiffrée ou protégée,
révision de source et images exactes. Les liens Drive sont des références :
ne pas sauvegarder de nouveau tous les fichiers du NAS. Documenter les besoins
de restauration des ressources liées et conserver les UUID de correspondance.

Restauration : nouveau projet/réseau/volumes isolés ; SMTP, webhooks, OIDC et
traitements d'écriture désactivés. Invalider anciennes sessions et transactions
OIDC. Relecture d'une carte, commentaire, pièce jointe avec empreinte, rôles et
état des réservations ; revalidation des autorités People/ST **actuelles** avant
remise en service. Un retrait de droit postérieur au backup reste effectif.
Aucun réenvoi automatique d'une notification historique restaurée.

Rollback : désactiver la souscription/catalogue Projects, arrêter ses seuls
services ; ne pas revenir à un ancien binaire sur un schéma incompatible.
Restaurer la paire DB/objets cohérente en isolat, puis bascule contrôlée. Ne pas
arrêter Drive, Docs, Meet, Messages, Calendars, People, ST, Keycloak ou le NAS.

## 4. Lots d'exécution et suivi

Tous les lots ci-dessous sont **À FAIRE**. Leur ordre tient compte des dépendances.
Après chaque lot, l'agent renseigne état, commits, preuve et prochain geste précis.
Un arrêt de tour ou une saturation du modèle ne vaut jamais livraison.

| Lot | Travail | Dépendances | État | Preuve / prochaine action |
| --- | --- | --- | --- | --- |
| P0 | Préflight, référence et état initial | — | À faire | Auditer les checkouts/services |
| P1 | Fork, construction et déploiement préparé | P0 | À faire | Créer/relier Apoze/projects |
| P2 | Identité durable Node et sessions | P1 | À faire | Associer un principal People |
| P3 | Accès ST, groupes et révocation | P2 | À faire | Qualifier union et retrait des grants |
| P4 | Stockage privé, quotas et collecte | P1–P3 | À faire | Corriger entrées/purge S3 |
| P5 | Drive/Docs et catalogue | P3–P4 | À faire | Qualifier une copie privée |
| P6 | Notifications Messages | P3 | À faire | Remettre un mail LAN réel |
| P7 | Exploitation et restauration | P2–P6 | À faire | Relire un backup isolé |
| P8 | Recette consolidée et second IdP | P2–P7 | À faire | Réutiliser les preuves précédentes |
| P9 | Nettoyage, publication et clôture | P8 | À faire | Vérifier les SHA distants |

### P0 — Préflight sans toucher aux données

- [ ] Lire ce plan et les contrats pertinents ; vérifier la pile actuelle.
- [ ] Relever branches, HEAD, modifications et remotes des dépôts concernés ;
  ne pas supposer que les travaux précédents sont dans `main` des forks.
- [ ] Vérifier absence ou présence d'un Projects existant, inventaire des données,
  utilisateurs, volumes, ports et sauvegardes. En cas de données existantes,
  préserver les IDs et préparer la correspondance ; ne pas reprovisionner à vide.
- [ ] Confirmer le port 8940, le bucket, la DB et les capacités réseau/stockage.
- [ ] Figer la référence Projects, les dépendances et les correctifs utiles.
  Créer le journal public nettoyé et un manifeste privé de l'état initial.

### P1 — Fork et construction reproductible

- [ ] Créer/réutiliser `https://github.com/Apoze/projects.git` ; `origin` vers
  ce fork, `upstream` vers `https://github.com/suitenumerique/projects.git`
  en lecture seule, push désactivé. Aucune issue/PR/action sur l'amont.
- [ ] Créer une branche locale de chantier, instructions AGENTS courtes,
  référence épinglée, builds Node/React natifs et image locale qualifiable.
- [ ] Préparer Compose/config persistants, migrations séparées des seeds et
  bootstrap de récupération ; pas de comptes ou secrets de démo persistants.
- [ ] Enregistrer Projects dans People/ST avec credentials machine dédiés,
  organisation, URLs, politique d'accès initialement fermée, catalogue masqué.
- [ ] Fournir les commandes de start/stop/status propres à Projects ; ne pas
  lancer le compose amont avec ses doublons d'IdP/base de données.

### P2 — Identité durable et sécurité des sessions

- [ ] Ajouter les associations, contraintes SQL et transactions de connexion.
- [ ] Implémenter le consommateur Node des snapshots et demandes People ;
  préserver les comptes natifs et les associations issuer/client/subject.
- [ ] Supprimer le repli email en mode suite et les promotions/organisations
  automatiques par claims ; faire fonctionner le profil sans email.
- [ ] Appliquer la validation OIDC complète et les limites de preuve.
- [ ] Protéger cookies, CSRF/origines et traitements d'erreur ; ne pas renvoyer
  l'ID token au navigateur s'il n'est plus nécessaire à un flux natif justifié.
- [ ] Raccorder reconnexion, attente d'approbation et déconnexion commune.
- [ ] Vérifier un login approuvé et un refus utile avant de poursuivre.

### P3 — Autorisation, rôles et temps réel

- [ ] Consommer les décisions ST et leases sans chemin permissif de secours.
- [ ] Ajouter grants directs/groupes et leur projection atomique aux rôles
  natifs ; exposer leur provenance et édition dans les interfaces adaptées.
- [ ] Parcourir toutes les routes/mutations, copies, suppressions et exports :
  accès applicatif puis droit natif ; couverture cohérente HTTP et sockets.
- [ ] Fermer le mode public au serveur et retirer son action de l'UI suite.
- [ ] Invalider les canaux et sockets sur retrait, panne prolongée, déconnexion
  commune et changement d'epoch ; mesurer la borne réelle.
- [ ] Préserver historique, dernier administrateur et reprise d'un utilisateur
  désactivé sans recréer propriétaire, carte ou droit.

### P4 — Admission des fichiers et quotas

- [ ] Ajouter tailles, facturation, réservations, reprises et contraintes SQL.
- [ ] Exposer budgets et usage dans ST/Projects, en étendant les champs
  d’override ST pour les projets si nécessaire, avec sémantique de zéro,
  absence de politique, refus de croissance et baisse sous usage documentée.
- [ ] Borner réception, transformations et antivirus sur tous les chemins.
- [ ] Fermer les URL directes des médias privés et conserver les en-têtes sûrs.
- [ ] Corriger pagination et erreurs de purge S3 ; vérifier les appels
  FileManager lors de copie/duplication/remplacement et suppressions parentes.
- [ ] Qualifier une course d'admission sous petit quota, libération confirmée
  et absence de donnée visible après refus ; ne pas allouer des gigaoctets de test.

### P5 — Fichiers et navigation de suite

- [ ] Extraire les seules mécaniques partagées du sélecteur et des échanges
  Messages/Drive ; conserver les anciens endpoints compatibles pendant la bascule.
- [ ] Ajouter le consommateur Projects et ses clés/URLs spécifiques.
- [ ] Livrer les trois actions lien/copie/enregistrement, avec destination,
  autorisation, plafonds, digest et reprise ; adapter les retours asynchrones.
- [ ] Qualifier un fichier S3, un fichier NAS et un lien Docs privé ; refus du
  tiers sans droit, pas de partage public implicite ni d'écrasement de collision.
- [ ] Afficher le catalogue commun, la navigation retour et les états de refus.
- [ ] Rejouer seulement le parcours Messages touché par la factorisation.

### P6 — Notifications internes et mail LAN

- [ ] Provisionner l'adresse de service et raccorder le SMTP natif restreint.
- [ ] Résoudre les contacts Messages sans rapprochement d'identités par email.
- [ ] Ajouter état/reprise des émissions et revalidation des destinataires ;
  désactiver webhooks externes et destinataires WAN dans ce profil.
- [ ] Vérifier commentaire/affectation notifiée et ouverture du lien profond.
- [ ] Vérifier panne ciblée du transport Projects, reprise certaine sans doublon,
  et retrait de droits avant émission ; restaurer la configuration dans finally.

### P7 — Reprise opérationnelle

- [ ] Livrer status, logs sûrs, reprise des journaux et nettoyage borné.
- [ ] Redémarrer Projects seul et vérifier persistance des cartes/fichiers/grants.
- [ ] Exécuter backup cohérent et restauration isolée avec données de recette.
- [ ] Confirmer empreinte du fichier, carte/commentaire présents, anciens
  credentials invalidés, droits actuels reconstruits et mails non réémis.
- [ ] Nettoyer uniquement l'isolat de restauration et conserver le backup utile.

### P8 — Recette minimale consolidée

- [ ] Réutiliser les preuves datées P2–P7 ; compléter seulement les lignes R0–R6
  qui ne sont pas démontrées ou dont le code a changé depuis la preuve.
- [ ] Qualifier Keycloak → Authentik → Keycloak dans un environnement isolé,
  avec les mêmes principals People et données Projects ; ne pas changer l'IdP LAN.
- [ ] Lever chaque anomalie sur le chemin responsable et ses autres appelants.
- [ ] Vérifier un parcours existant des applications réellement touchées et la
  conservation de Drive/NAS/IdP ; ne pas inventer des raccordements manquants.
- [ ] Ouvrir la souscription/catalogue Projects sur le LAN après succès, puis
  confirmer la navigation réelle depuis le catalogue utilisateur.

### P9 — Publication et livraison

- [ ] Supprimer tous les projets/cartes/fichiers/mails/comptes et grants de
  recette créés par ce chantier, via les APIs/services natifs ; vérifier les
  réservations, objets et temporaires restants sans supprimer l'existant.
- [ ] Restaurer quotas, profils et configurations temporairement changés.
  Conserver adresse de service, keys opérationnelles et configuration Projects.
- [ ] Retirer environnements QA, sessions navigateur et téléchargements locaux.
- [ ] Finaliser le guide `docs/operations/suite-projects.md`, les instructions
  du fork Projects, le contexte, les index et les changelogs concernés.
- [ ] Publier **tous** les changements implémentés sur leurs forks Apoze :
  Projects, Drive, ST et tout autre consommateur réellement modifié.
  Appliquer les gates propres à chaque dépôt, ciblés par surface ; gitlint,
  diff propre, absence de secrets/fixup et contrôles backend de publication.
- [ ] Vérifier chaque SHA distant et worktree ; donner les URLs/branches
  complètes. Pas de merge/PR implicite et aucune écriture vers `suitenumerique/*`.
- [ ] Renseigner la validation finale avec preuves, versions et limites réelles.
  Cocher les critères de livraison uniquement quand tout le périmètre obligatoire
  est fonctionnel ; aucune réserve cachée derrière « tests passent ».

## 5. Recette réelle minimale — pas d'usine à tests

Utiliser un administrateur, deux utilisateurs fonctionnels et, si nécessaire,
un utilisateur sans droit déjà disponible. Un seul projet, deux tableaux,
quelques cartes, un petit fichier texte, une image minuscule et un document Docs
suffisent. Chaque fixture a un identifiant de chantier et un nettoyage prévu.

| Référence | Parcours réel regroupé | Preuve minimale |
| --- | --- | --- |
| R0 | Catalogue, login OIDC, approbation People, profil sans email ; droit ST refusé | Navigation réelle + UUID stable + refus d'accès |
| R1 | Projet/tableau, carte, checklist, commentaire, affectation, échéance, filtres, duplication et CSV ; deux navigateurs | Mise à jour reçue en temps réel et relecture après reload ; viewer ne peut pas modifier |
| R2 | Grant de groupe + grant direct, retrait séparé, suspension ST ; ancien socket laissé inactif | Droit direct restant conservé puis refus HTTP/fichier et absence d'événement après révocation, délai mesuré ≤ 120 s |
| R3 | Upload privé, refus de quota concurrent, antivirus indisponible puis rétabli ; copie S3/NAS, lien Docs, collision/reprise | Même empreinte, aucune publication après refus, aucune copie supplémentaire au rejeu ; Messages encore fonctionnel après factorisation partagée |
| R4 | Notification reçue dans Messages, panne ciblée/reprise, destinataire révoqué | Mail livré et lien ouvrable pour le membre ; erreur visible et envoi révoqué bloqué |
| R5 | Restart puis backup/restauration isolée du même jeu | Carte/commentaire/pièce relus, droits actuels, sessions invalides, pas de SMTP ; preuve de nettoyage |
| R6 | Keycloak → Authentik → Keycloak isolé, même jeu de données | Mêmes IDs natifs/principals, mêmes contenus ; anciennes preuves refusées ; aucune bascule du LAN |

Le parcours nominal se fait en français sur un navigateur principal, avec un
second contexte pour le temps réel et les refus. Un contrôle clavier et une
largeur mobile sur les nouvelles modales suffisent ; pas de matrice de trois
navigateurs × rôles × stockages × IdP.

Pendant l'itération : lint/build natifs ciblés, Mocha/test natif restreint si
nécessaire pour une branche de sécurité, un calcul de quota ou une reprise.
Garder le plus petit test durable qui échoue si la correction régresse ; pas
une suite par helper ni un nouveau framework. Aucun test de présence de mots,
imports ou fragments de code. Aucun full pytest/E2E de toutes les applications.

Pour la pagination S3 corrigée, utiliser quelques objets réels avec pagination
forcée à petite taille dans la recette, ou un test ciblé du SDK si ce forçage
n'est pas possible ; ne pas uploader mille fichiers pour une seule vérification.
Pour une nouvelle panne : diagnostic du chemin réel, correction, reprise ciblée.
Les étapes déjà valides ne sont pas rejouées sans changement les affectant.

Limite honnête : un droit retiré ne rappelle ni un téléchargement déjà terminé
ni un email déjà remis. La validation porte sur l'arrêt des accès/émissions
ultérieurs et les bornes documentées, pas sur l'effacement du poste utilisateur.

## 6. Livrables, journal et critères de clôture

Artefacts publics nettoyés sous `output/implementation/projects-integration/` :

- `execution-journal.md` : lot, constat, cause, correction, preuve et suite précise ;
- `current-status.md` : état courant, services, révision et première action de reprise ;
- `validation-final.md` : R0–R6, temps mesurés, limites, nettoyage et commandes utiles ;
- manifeste des révisions/images et de publication, sans secrets ni URLs signées.

Configs et preuves privées sous `data/projects-local/` et `tmp/projects-qa/`.
Ne pas publier DB, objets natifs, sauvegardes, cookies, copies de mails ou jetons.
Les liens des rapports pointent vers les preuves nettoyées, pas vers des credentials.

Après chaque lot, mettre à jour la ligne P correspondante et le journal avant
de passer au suivant. Un lot partiel précise exactement le fichier/parcours,
le résultat acquis, l'erreur restante et le prochain contrôle. Les critères
ci-dessous restent ouverts jusqu'à preuve ; une case non applicable est motivée.

- [ ] Projects est visible et utilisable sur le LAN depuis le catalogue commun.
- [ ] Identité durable indépendante de l'IdP ; aucune fusion par email ni rôle
  implicite ; bascule isolée réalisée, pas seulement configurée.
- [ ] Groupes/rôles sont administrables dans les bonnes Web UI ; grants directs
  conservés ; révocation HTTP, sockets, fichiers et traitements effective.
- [ ] Fonctions natives retenues réellement utilisées sans régression bloquante.
- [ ] Stockage privé, limites, antivirus, quotas et purges sont fonctionnels.
- [ ] Lien/copie/enregistrement Drive fonctionnent pour S3/NAS et Docs selon
  leurs capacités ; aucun élargissement de droits implicite.
- [ ] Notifications reçues dans Messages, échecs visibles, reprise et refus
  après retrait d'accès démontrés.
- [ ] Sauvegarde/restauration exécutées, reprise sûre et absence de réémission
  historique ; pile préexistante toujours fonctionnelle.
- [ ] Fixtures et fichiers téléchargés nettoyés, configuration utile conservée.
- [ ] Guides, suivi et **tous les changements implémentés sont publiés** sur
  les forks Apoze, avec vérification des commits distants.

Passer le statut à **LIVRÉ SUR LE LAN** seulement après clôture P0–P9 et de ces
critères. Le WAN et les extensions explicitement exclues restent des chantiers
ultérieurs ; aucun manque du périmètre obligatoire n'est déplacé là par défaut.
