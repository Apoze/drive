# Transfers et Chat Apoze — intégration complète web, serveur et mobile

Date : **10 septembre 2026**.
Statut : **EN COURS — TC1/TC5 Chat ; Transfers qualifié, livraison finale en attente**.
Périmètre : Transfers, Matrix/Synapse, Matrix Authentication Service (MAS),
Element Web, Element X Android et iOS, raccordements à la suite existante.
Ce document est le suivi canonique de ces deux chantiers. Le propriétaire a
autorisé l'exécution complète, les corrections utiles et les tests réels ciblés.

## 0. Mode d'emploi et règles de clôture

L'agent exécutant lit d'abord `AGENTS.md`, ce plan, l'ADR identité et le contrat
stockage, puis les instructions des dépôts effectivement modifiés.
Il déroule les lots ci-dessous jusqu'à la livraison, maintient les cases et
consigne les décisions, commits et preuves au fil du travail. Une case cochée
signifie « implémenté, validé dans son périmètre et documenté ».

- États des lots : à faire, en cours, bloqué avec cause précise, terminé ;
  validations mobiles reportées sur instruction du propriétaire distinguées
  du travail de code restant (§1).
- Un lot bloqué par une ressource externe ne bloque que ses dépendants : avancer
  sur les autres, sans annoncer le chantier entier comme terminé.
- Garder un seul lot de développement actif et une prochaine action explicite.
- Corriger les causes racines sur tous les chemins concernés ; pas de contournement
  limité à l'écran utilisé pour la recette.
- Toute amélioration utile découverte entre dans le registre §12 avant sa mise
  en œuvre : besoin concret, périmètre, dépendance, validation et statut.
- Les corrections nécessaires et optimisations mesurées sont intégrées au lot
  pertinent. Les nouveaux produits et changements de politique sensibles restent
  des décisions explicites ; aucune reprise de Grist ou ClipSync par ce plan.
- Tests réels minimaux selon §10 ; pas de matrice exhaustive par défaut, pas de
  tests cherchant des chaînes ou la présence d'éléments dans les fichiers source.
- Publication de tous les changements implémentés sur les forks **Apoze** après
  les gates locales ; aucune publication, PR ou action d'écriture vers l'amont.

À créer au début de l'exécution sous
`output/implementation/transfers-element-chat/` :
`current-status.md`, `execution-journal.md`, `validation-final.md` et
`publication.md`. État privé, captures, fichiers de recette, clés et sauvegardes
restent sous `data/` ou `tmp/`, hors Git. Ne créer aucun rapport de réussite vide.

## 1. Résultat attendu et périmètre

| Surface | Résultat requis |
| --- | --- |
| Transfers | Création depuis l'ordinateur ou Drive S3/NAS, gros fichiers, reprise, modes standard/confidentiel, expiration, désactivation, envoi Messages et retour vers Drive |
| Chat serveur | Utilisateurs de la suite, conversations directes et salons privés chiffrés, groupes People, permissions et révocation serveur, stockage et quotas ST |
| Chat web | Element Web intégré au catalogue ; fonctions natives utiles préservées, accès Drive/Docs, Transfers, Meet, Calendars et Projects cohérents |
| Mobile | Code et configuration des forks Element X Android/iOS complets ; builds et tests sur simulateur/émulateur si disponibles, recette physique reportée selon la décision ci-dessous |
| Administration | Configuration métier depuis People, ST ou l'application compétente ; aucun SQL manuel requis au quotidien |
| Exploitation | Docker persistant, images figées, démarrage/reprise, sauvegarde/restauration, supervision simple et procédure d'upgrade |

**Matrix est le protocole ; aucun conteneur supplémentaire nommé Matrix n'est
nécessaire. Synapse est le serveur retenu. MAS fournit l'authentification Matrix
compatible avec Element X ; l'IdP existant continue d'authentifier les personnes.**
People reste l'autorité de l'identité durable et des groupes, ST des accès aux
applications et budgets. Il n'y a pas de remplacement de Keycloak ni de nouvelle
source concurrente de groupes.

Choix du propriétaire : Element Web + Element X ; pas de fork Tchap ni Hub.
Reprendre seulement les idées utiles de Tchap : annuaire compréhensible,
identification des membres, règles de salons lisibles. Ne pas recopier son UI.

### Décision du propriétaire : validation mobile différée

Mise à jour du **10 septembre 2026** : aucun téléphone Android ni iPhone n'est
connecté. Ne pas demander un appareil pour poursuivre ce chantier.

- Au préflight d'exécution, vérifier si un Mac accessible dispose de Xcode et
  du simulateur iOS, et si un émulateur Android utilisable est disponible sur
  le Mac ou l'environnement de travail. Leur présence n'est pas présumée.
- Si disponibles, compiler et exécuter les applications sur ces environnements
  avec des parcours ciblés contre le vrai serveur de recette. Une simple page
  Web redimensionnée ne constitue pas une recette Element X.
- Si l'exécution mobile n'est pas possible, réaliser tout le code et la
  configuration nécessaires, ainsi que les contrôles de compilation/lint
  accessibles. Reporter les tests mobiles, sans bloquer serveur, web ou publication.
- Préparer les paramètres de signature et de push ; si les credentials/outils
  manquent, ne pas inventer de secrets, acheter de compte ou exiger une signature
  de distribution pour terminer le code. Reporter les opérations dépendantes.
- Distinguer dans le rapport : code réalisé, build exécuté ou non, test sur
  simulateur/émulateur, et tests physiques/APNs/FCM restant à faire. Une notification
  injectée dans le simulateur ne prouve pas sa livraison par APNs/FCM.
- Un build ou test qui échoue avec les outils disponibles doit être diagnostiqué
  et corrigé ; cette décision ne permet pas de reporter un défaut connu du code.

Le périmètre courant peut être clôturé avec **serveur/web livrés et code mobile
préparé, recette mobile différée**. Cela ne signifie jamais « applications mobiles
validées sur appareils ». Conserver la checklist de reprise §14 pour plus tard.

### Périmètres explicitement différés

- Comptes invités du chat, salons publics et fédération avec d'autres serveurs.
  Le téléchargement d'un transfert par lien sur le LAN est un usage distinct,
  inclus ; il ne crée pas un compte invité Matrix.
- Exposition WAN de la suite, mail Internet et accès mobile hors LAN/VPN.
- Enregistrement, transcription, IA, téléphonie SIP/PSTN et seconde pile visio.
- Interface d'appel téléphonique système avec sonnerie écran verrouillé,
  CallKit/ConnectionService et appels d'urgence : extension ultérieure, pas
  assimilée à la notification d'une invitation Meet incluse ici.
- Publication publique App Store/Google Play et dépenses liées aux comptes de
  distribution : préparer les builds/signatures, sans soumission ou achat tacite.
- Recherche serveur du texte des salons chiffrés, robots lisant tous les messages,
  synchronisation bidirectionnelle générale de tous les objets de la suite.

Ces exclusions ne permettent pas de remplacer les lots mobiles par une simple
mention « compatible Element X ». Un build non exécuté ou une notification non
testée garde son statut non validé.

## 2. État de départ inspecté et sources

### 2.1 Suite Apoze existante

Drive, Docs, People/IdP, ST, Meet, Messages, Calendars et Projects sont livrés sur
le LAN selon leurs rapports. La pile Drive était démarrée lors de cette
préparation ; les nouveaux services ne sont ni installés ni testés.
Relire les états réels au démarrage, sans réinitialiser les bases ni remplacer
un environnement existant par les Compose de démonstration amont.

Références locales :

- [ADR identité durable](../../adr/0003-suite-durable-identity-and-access.md).
- [Contrat stockage](../../agent-storage-contract.md).
- [Identité et exploitation](../../operations/suite-identity-access.md).
- [Docs natifs dans Drive](docs-drive-native-documents-integration-plan.md).
- [Meet et admission](../../operations/suite-meet-visio.md).
- [Messages et Calendars](../../operations/suite-messages-calendars.md).
- [Projects et échanges privés](../../operations/suite-projects.md).
- [Environnement local](../../env_freeze_report.md).
- [Contrat de recette navigateur](../../qa-browser-testing-contract.md).

| Point d'entrée existant | Réutilisation attendue |
| --- | --- |
| Drive `src/packages/suite-identity/suite_identity/` | Contrats People/ST, association OIDC, snapshots complets, révisions, preuves et déconnexion |
| Drive `src/backend/core/api/suite_files.py` et `core/services/suite_files.py` | Lecture/copie privée, observation source, export Docs et import journalisé |
| Drive `src/frontend/apps/drive/src/features/sdk/SuiteFilePicker.tsx` | Sélecteur canonique S3/NAS, origines autorisées et requêtes corrélées |
| Drive `docker/suite/prepare_*.py`, `provision_*.py`, `*_operations.py` | Provisionnement idempotent, préservation des secrets, sauvegarde et restauration isolées |
| ST `core/entitlements/resolvers/{storage_policy,projects_storage_entitlement_resolver}.py` | Politiques d'accès et budgets cumulatifs, convention zéro/absence = illimité, blocage de croissance distinct |
| Meet `core/suite/{access,api}.py` et `core/services/room_creation.py` | Admission, révocation des participants et création native de réunion |
| Messages `core/suite/project_notifications.py` | Intention restreinte, résolution People/boîte, journal durable et état SMTP incertain |
| Projects `server/api/helpers/utils/suite-*.js` | Sémantique des contrats hors Django et permissions natives ; référence, pas duplication du code |

L'échange privé Drive actuel n'accepte que Messages/Projects et **1 octet à
25 Mio**. Il faut l'étendre proprement pour Transfers/Chat, gros fichiers et
fichiers vides, sans relever silencieusement les plafonds Messages/Projects.
Le sélecteur actuel choisit un élément : ajouter la sélection multiple là où
Transfers la nécessite, sans créer un second explorateur.

### 2.2 Révisions de référence

Sources relevées le 10 septembre 2026 par API GitHub, puis inspection ciblée.
Transfers : lecture du code au SHA ci-dessous dans un checkout temporaire.
Pour les composants Matrix : inspection des documentations/interfaces et
références de release, **pas encore revue exhaustive ni combinaison validée**.
TC0 fige le jeu compatible avant développement ; ne pas déployer `develop`,
`main` ou une image `latest` implicitement.

| Dépôt source en lecture seule | Référence candidate | SHA |
| --- | --- | --- |
| `suitenumerique/transfers` | `main`, pas de release publiée relevée | `1286dfa4c7f8d5165b0dff050da69af911562e76` |
| `element-hq/synapse` | `v1.160.0` | `92fb8a06dc351c184eb96360c67b124f26c2d54b` |
| `element-hq/matrix-authentication-service` | `v1.24.0` | `c7c13a2137f03abcff2e7619f4a10611c0cd5f9a` |
| `element-hq/element-web` | `v1.12.27` | `6dffa5058057e7a0edf2e6270598d7c27d2030cb` |
| `element-hq/element-x-ios` | `release/26.09.1` | `e57d872fc880cfb7ee86fdd0e0175352cf09011a` |
| `element-hq/element-x-android` | `v26.09.1` | `18bb4632f2448b21464cea77d38fb7b6a2d0d1bf` |
| `matrix-org/sygnal` | `v0.15.1`, à requalifier avant réutilisation | `924930019ea968b8354442b909cc97848a96b5b8` |

### 2.3 Constats qui influencent directement l'implémentation

| Constat | Travail requis |
| --- | --- |
| Transfers : Django/DRF, Celery, PostgreSQL, S3 ; React/Vite avec Cunningham/ui-kit | Réutiliser les composants et workers ; pas de refonte Next.js ou nouvelle file de tâches |
| Code Transfers récent : chiffrement par chunks dans les deux modes ; clé serveur en standard, absente en confidentiel | Se fier au code figé ; son README décrit encore en partie un ancien mode optionnel |
| `DriveAttachButton.tsx` utilise le SDK historique et un permalink public ; import via `requests.get(source_url)` | Remplacer tout le chemin par une délégation privée à des ressources Drive identifiées, sans passage public |
| `DriveAttachButton.tsx` documente un bouton pouvant rester occupé après fermeture de popup et une variante visuelle lien | Corriger le cycle de sélection/annulation et employer de vrais boutons natifs selon §8 |
| `UserManager.get_user_by_sub_or_email` contient un repli email | Remplacer en mode suite par l'association People explicite |
| Suppressions de brouillons S3 « best effort » puis effacement DB | Garder un journal de nettoyage jusqu'à confirmation pour éviter fuites de stockage et quotas libérés trop tôt |
| Téléchargement : redirection vers URL S3 ; option one-shot comptée à l'accès, avant sauvegarde réelle | Borner la durée des capacités, rendre la sémantique honnête et empêcher les aperçus de consommer un téléchargement |
| Statuts scan `SKIPPED`/`TOO_LARGE` acceptés dans certains chemins | Appliquer la politique administrée ; jamais présenter un fichier non analysé comme sain |
| Import Drive natif interdit en confidentiel | Prévoir un chemin client chiffrant les octets privés, sans transmettre la clé au serveur Transfers |
| MAS possède une API Admin REST pour gérer comptes, liens IdP et sessions | Utiliser l'API prise en charge, pas des écritures dans ses tables ou l'ancien GraphQL interne |
| Modules Synapse disponibles, mais un hook d'événements ne contrôle pas toutes les lectures | TC1 doit prouver l'interception des accès, sync et médias ; patch ciblé dans la fork si le hook manque |
| Nouvelle API de modules Element Web encore évolutive | Vérifier les extensions sur la release retenue ; patch natif limité si nécessaire, pas d'injection DOM |

Sources primaires :

- [Transfers au SHA inspecté](https://github.com/suitenumerique/transfers/tree/1286dfa4c7f8d5165b0dff050da69af911562e76),
  en particulier `src/backend/core/{models,tasks}.py`,
  `api/viewsets/{draft,download}.py`, `api/serializers.py`,
  `services/{encryption,email}.py`, `src/frontend/src/features/transfers/`.
- [Synapse : installation](https://element-hq.github.io/synapse/latest/setup/installation.html),
  [configuration et nom durable](https://element-hq.github.io/synapse/latest/usage/configuration/config_documentation.html#server_name),
  [modules](https://element-hq.github.io/synapse/latest/modules/index.html),
  [callbacks](https://element-hq.github.io/synapse/latest/modules/third_party_rules_callbacks.html).
- [MAS : OIDC](https://element-hq.github.io/matrix-authentication-service/setup/sso.html),
  [API Admin](https://element-hq.github.io/matrix-authentication-service/topics/admin-api.html).
- [Element Web : API de modules](https://github.com/element-hq/element-web/tree/develop/packages/module-api).
- [Element X iOS : fork](https://github.com/element-hq/element-x-ios/blob/develop/docs/FORKING.md),
  [Android : compilation](https://github.com/element-hq/element-x-android/blob/develop/CONTRIBUTING.md).
- [Matrix : spécification client/serveur](https://spec.matrix.org/latest/client-server-api/),
  [push](https://spec.matrix.org/latest/push-gateway-api/),
  [Sygnal](https://github.com/matrix-org/sygnal).
- [Stockage S3 Synapse existant](https://github.com/matrix-org/synapse-s3-storage-provider),
  [domaines associés iOS](https://developer.apple.com/documentation/xcode/supporting-associated-domains).

## 3. Architecture et responsabilités

### 3.1 Services

| Composant | Responsabilité / déploiement |
| --- | --- |
| Transfers API + workers/beat + frontend | Cycle des transferts, chiffrement standard, scan et copies ; processus natifs en Docker |
| Synapse | Événements, salons, appareils et médias Matrix ; instance unique LAN et PostgreSQL |
| MAS | Connexion OIDC des clients, sessions et refresh tokens Matrix ; base/role PostgreSQL séparés |
| Element Web | Frontend statique avec personnalisation limitée et intégrations suite |
| Element X | Applications natives, SDK Matrix Rust et chiffrement natif ; ne s'exécutent pas dans un conteneur serveur |
| Sygnal | Relais push autohébergé pour les builds Apoze ; activation au lot mobile après qualification |
| Services existants | People, ST, IdP, S3, Messages/MTA, ClamAV, Drive/Docs, Meet et Calendars réutilisés |

Stockage : bucket et identité S3 privés Transfers ; médias Matrix sur volume
persistant natif dédié pour la première livraison, exposés seulement par Synapse.
Ce choix ne copie pas les objets Drive : les références Drive restent privées,
les pièces jointes Matrix sont des copies autonomes chiffrées. Si la capacité
locale constatée impose S3, utiliser le provider existant, tester stockage,
cache, purge et restauration ensemble ; pas de provider S3 artisanal.

Mutualiser les infrastructures compatibles sans partager les identifiants :
bases/rôles, buckets, préfixes, files Celery et credentials machine distincts.
Ne pas installer RustFS, un second Keycloak, un MTA ou une pile LiveKit en double.
Pas de Kubernetes, bus d'événements généraliste ou plateforme de plugins maison.

L'intégration Python Matrix doit rester un paquet/module autonome dans le dépôt
de sa fork serveur ; ne pas charger Django dans Synapse. Réutiliser les contrats
HTTP People/ST. Les tables d'association/journal appartiennent à cette extension,
avec migrations explicites. Un contrôle commun appliqué au bon point serveur
vaut mieux que des validations dispersées dans les trois clients.

### 3.2 Dépôts et publication

À créer ou réutiliser lors de l'exécution :

- `https://github.com/Apoze/transfers.git` depuis
  `https://github.com/suitenumerique/transfers.git`.
- `https://github.com/Apoze/element-web.git`,
  `https://github.com/Apoze/element-x-ios.git`,
  `https://github.com/Apoze/element-x-android.git` depuis les dépôts homonymes
  `https://github.com/element-hq/`.
- `https://github.com/Apoze/synapse.git` pour l'intégration serveur et tout patch
  natif nécessaire, depuis `https://github.com/element-hq/synapse.git`.
- Fork `Apoze/matrix-authentication-service` seulement si une modification de
  MAS est requise par TC1 ; sinon conserver l'image officielle figée.
- Fork de Sygnal ou d'une dépendance seulement si un défaut impose sa modification.

Ces URLs sont des **cibles prévues, pas une déclaration de forks déjà créées**.
Éviter d'écraser un dépôt homonyme. Configurations communes Docker dans Apoze/drive,
code métier dans l'application propriétaire ; pas de copie parallèle des sources.
Les adaptations des apps existantes sont publiées sur leurs forks Apoze.

Au départ relever HEAD, branche, base réelle et fichiers sales de chaque dépôt.
Les intégrations existantes ne sont pas forcément sur `main`. Créer des branches
de travail issues des branches fonctionnelles ; préserver les modifications
préexistantes, notamment People. Aucun nettoyage de branches ou fusion implicite.
À la fin : commits relus, changelogs des comportements, lint/tests ciblés et
gitlint selon chaque dépôt, fetch/base explicites, absence de fixup/secrets,
push sur Apoze et vérification SHA distant. Pas de PR ou merge sans portée dédiée.

## 4. Préflight : décisions persistantes et ressources externes

Traiter ces points tôt dans TC0. Ils n'empêchent pas la rédaction du plan ni le
développement indépendant, mais interdisent une fausse clôture des lots concernés.

| Point | Règle / valeur de départ | Validation nécessaire |
| --- | --- | --- |
| Identifiant du serveur Matrix | Nom DNS durable contrôlé par le propriétaire, indépendant de l'IP LAN | Chercher une décision existante ; sinon demander le nom avant création de comptes durables. `server_name` ne se renomme pas comme une URL |
| URLs | Chat, MAS et Transfers en HTTPS avec DNS LAN ; discovery Matrix et issuer cohérents | Relever ports/domaines occupés, conserver les URLs existantes ; pas d'exposition WAN tacite |
| TLS LAN | Certificat reconnu par navigateur et appareils de recette | CA locale ou DNS/TLS existants ; installer la confiance, jamais désactiver la vérification TLS |
| iOS | Mac/runner macOS et Xcode/simulateur si accessibles ; aucun iPhone connecté | Compiler/tester si possible ; sinon code/configuration et validation reportée selon §1. Signature de distribution différée si indisponible |
| Android | JDK/SDK et émulateur si disponibles ; aucun téléphone connecté | Compiler/tester si possible, build de développement identifié ; sinon code/configuration et validation reportée selon §1 |
| OIDC mobile | App IDs, callbacks, métadonnées clients, domaines associés | Vérifier AASA/iOS et Android App Links. Une configuration LAN seule peut exiger un mode de développement ; distinguer cela de la distribution normale |
| Push | App IDs et credentials APNs/FCM propres à Apoze, relais serveur | Aucune réutilisation des credentials ou passerelles privées Element/Tchap ; aucun achat implicite |
| Réseau mobile | LAN d'abord ; accès distant ultérieur par WAN/VPN | Push via Apple/Google implique des sorties réseau, même si le chat reste privé ; en conserver la liste minimale |

Si le domaine n'est pas encore décidé, les essais utilisent un serveur jetable
sans données durables. Ne pas engager le propriétaire avec un nom provisoire
annoncé comme migrable. Si la validation mobile de production exige des fichiers
de domaine accessibles publiquement, documenter exactement lesquels et obtenir
la décision correspondante ; ne pas ouvrir les API ou contenus de la suite.

Les composants libres sont retenus sans activation payante. Conserver licences,
notices et obligations de redistribution ; les frais éventuels de signature ou
de magasins sont distincts et ne sont pas autorisés par la rédaction du plan.

## 5. Identité, groupes, permissions et sessions

### 5.1 Identité durable

- Associer UUID People, utilisateur Transfers, utilisateur MAS et MXID Matrix
  explicitement. Choisir une partie locale Matrix stable dérivée de l'identité
  durable, jamais de l'email ; les noms lisibles sont des attributs de profil.
- Un seul compte Matrix par personne dans ce déploiement ; contraintes uniques,
  provisioning idempotent et protection contre les appels concurrents.
- Conserver les associations `(issuer, subject opaque, consommateur)` dans
  People, y compris les subjects pairwise. Aucun rapprochement automatique par
  email, nom, groupe ou rôle présent dans les claims.
- Connexion inconnue : parcours d'approbation People, accès aux contenus refusé
  jusqu'à l'association. Les écrans de rattachement/renouvellement restent
  accessibles sans accorder l'application.
- MAS : lier l'identité approuvée au compte existant via l'API Admin. Utiliser
  les mécanismes de provisioning disponibles ; si l'interception avant émission
  des jetons manque, modifier la fork au point approprié et le documenter.
- Bascule Keycloak → Authentik → Keycloak : nouveaux liens externes explicites,
  mêmes MXID, salons, médias et appareils conservés autant que le cycle de
  session le permet. Une reconnexion ne doit pas réinitialiser les clés E2EE.

### 5.2 Droits et fraîcheur

Conserver la sémantique suite : snapshots paginés complets toutes les 30 secondes,
révisions monotones, décision positive valable au plus 90 secondes, révocation
effective au plus 120 secondes après décision autoritaire. Une panne durable
ferme les nouveaux accès ; ne jamais remplacer un snapshot par une page partielle.

**Matrice des contrôles serveur à compléter dans TC1** :

| Entrée | Contrôle requis |
| --- | --- |
| OIDC, refresh, connexion QR/appareil | Association active, accès Chat, epoch/session ; aucun token privilégié contournant ST |
| `/sync`, sliding sync, historique, recherche, profils/annuaire | Compte et politique actuels ; filtrage de l'annuaire aux personnes autorisées de la même organisation |
| Envoi/édition/réaction, création/invitation/join/leave, power levels | Accès application + règles Matrix et autorité locale sur le salon |
| Upload/download/thumbnail, anciens endpoints médias | Compte actif, limites et routes médias privées ; pas d'ancienne route anonyme contournant les contrôles |
| Clés, to-device, backup de clés, appareils | Session autorisée ; SDK/protocole natifs, aucun export des clés vers People/ST |
| API suite, imports/exports, notifications, admission Meet | Identité liée, droit spécifique sur la source/cible et preuve/délégation adaptée |

Un hook de refus d'envoi n'est pas une protection suffisante. Vérifier la lecture
avec un client non modifié, une requête sync déjà ouverte et un token antérieur
à la révocation. Borner les longues attentes pour ne pas livrer de nouveaux
événements après la borne. Ni proxy qui ne vérifie que des URLs connues ni
modification des seuls boutons ne remplace ces contrôles.

### 5.3 Sessions mobiles : adaptation obligatoire du contrat

L'ADR actuel borne les preuves OIDC interactives à quinze minutes. Copier cette
règle sur toutes les synchronisations mobiles rendrait l'app inutilisable en
arrière-plan. Ajouter une ADR **spécifique aux clients Matrix**, sans assouplir
les sessions des autres applications :

- Login OIDC initial avec code/PKCE, state, nonce, issuer/audience et callback
  vérifiés ; jetons et refresh gérés par MAS/SDK, stockage sécurisé du terminal.
- Autorisation du chat renouvelée côté serveur avec les bornes ci-dessus ; une
  session mobile durable n'est pas une autorisation durable hors ligne du serveur.
- Utiliser les durées et rotations natives MAS de la release, fixer et publier
  une expiration absolue finie de session ; proposition initiale 30 jours,
  configurable, jamais des jetons sans échéance.
- Révocation ST/People ou déconnexion globale : fermer les sessions MAS concernées,
  invalider les accès Synapse et arrêter les push ; réactivation explicite sans
  recréer compte ou salon. Suspendre ne signifie pas effacer irréversiblement.
- Gestion des appareils et déconnexion de l'appareil courant compréhensibles ;
  ne pas déconnecter tous les téléphones à chaque fermeture d'un onglet.
- Pour une opération sensible Drive/Docs, présenter une preuve récente acceptée
  par l'application cible, éventuellement via SSO dans le navigateur système.
  Un token Matrix seul n'est pas transformé en preuve OIDC de quinze minutes.

### 5.4 Salons et groupes

- Conversations directes et salons privés chiffrés ; annuaire People intégré.
- Distinguer salons personnels et salons gérés par des groupes People ; une
  appartenance à un Space Matrix n'accorde pas l'accès à tous ses salons enfants.
- Droits directs et de groupes avec provenance ; retirer un groupe préserve
  un droit direct restant. Suppression/recréation homonyme d'un groupe n'hérite
  pas des autorisations de l'ancien UUID.
- Rôles simples : membre, modérateur, responsable. Projeter vers les power levels
  natifs, vérifier invitations et escalades même depuis un autre client Matrix.
- Empêcher l'abandon du dernier responsable actif ; reprise administrative
  explicite et auditée d'un salon orphelin, sans accéder aux clés de déchiffrement.
- Retrait d'accès : sortir des salons concernés et appliquer la politique
  d'historique choisie ; rotation des sessions de chiffrement par les SDK.
  Aucun effacement promis des messages/clé déjà reçus sur un appareil.
- Interdire serveur et UI : auto-inscription, fédération, invitations externes,
  accès invité et publication de salons. Ne pas désactiver les flux natifs de
  vérification d'appareils ou de récupération nécessaires à Element X.

## 6. Stockage, transferts et confidentialité

### 6.1 Gouvernance commune

ST administre des budgets **Transfers** et **Chat** distincts. Les réservations
atomiques sont dans le service propriétaire des octets ; ST expose les règles
et reçoit des métriques, il ne sert pas de compteur distribué par requête.
Additionner limites instance, organisation, utilisateur et limites opérationnelles.
Ne pas annoncer un plafond transactionnel global commun à toutes les applications.

- Transfers facture le propriétaire durable du transfert, brouillons et
  multipart inclus ; octets chiffrés réellement stockés, pas seulement déclarés.
- Chat facture les médias à l'uploader durable, indépendamment des salons dans
  lesquels ils sont référencés. Les pièces jointes E2EE ne révèlent pas forcément
  leur salon au serveur : pas de faux quota par salon.
- L'historique DB et les sauvegardes de clés relèvent de la capacité d'instance,
  avec limites de taille/rate limit natives ; ne pas présenter le quota médias
  comme la totalité de l'espace disque consommé par le chat.
- Zéro/absence de plafond ST = illimité ; blocage de croissance distinct. Une
  baisse sous l'usage bloque les ajouts sans supprimer les fichiers existants.
- Réserver avant admission, mesurer le réel, confirmer publication/purge et
  reprendre les opérations interrompues. Pas de libération avant suppression
  confirmée ; inclure miniatures, fichiers temporaires et réservations au bilan.
- Contrôler les quotas même depuis un client Matrix tiers. Taille inconnue,
  upload asynchrone et envois concurrents doivent rester bornés.
- Administration Web : usage/plafonds, opérations bloquées, reprise et transfert
  de responsabilité avec aperçu ; aucun compteur modifiable par simple claim client.

### 6.2 Transfers : parcours retenus

1. Créer un envoi depuis l'ordinateur ou plusieurs ressources privées Drive.
2. Choisir titre, durée, mode lien ou destinataires Messages et confidentialité.
3. Upload/import avec progression, annulation et reprise ; publication seulement
   après état cohérent, scan requis et contrôle final des droits/quota.
4. Télécharger un ou plusieurs fichiers ; indiquer expiration et restrictions.
5. Désactiver, prolonger dans les limites autorisées, supprimer et suivre les
   envois/erreurs ; conserver un journal technique sans contenu ni clés.
6. Pour un utilisateur autorisé, enregistrer dans un dossier Drive S3/NAS ;
   vérifier collision, quota, nom et permissions, sans écrasement implicite.

Conserver les fonctions natives retenues : fichiers vides, multi-fichiers,
multipart et reprise, durées configurables, historique d'envoi, téléchargement
et suppression. Les valeurs natives observées (20 Gio/fichier et transfert,
20 fichiers, échéances 1/7/30 jours) sont des points de départ à confronter aux
capacités réelles, pas des performances déjà validées.

Le lien Transfers est une capacité de téléchargement autonome : la copie
publiée ne suit plus les droits de la source Drive. L'UI explique cette copie
et son audience avant publication ; vérifier que l'émetteur a le droit d'exporter.
La révocation de l'émetteur suspend les liens selon la politique de service
retenue ici : **aucune nouvelle autorisation de téléchargement après 120 s**.
Un responsable autorisé peut ensuite reprendre explicitement la propriété.

### 6.3 Gros fichiers et échange privé Drive

- Étendre `SuiteFilePicker` et les consommateurs autorisés, avec des capacités
  déclarées par application : sélection multiple, lien/copie/destination,
  plafonds et fichiers vides. Origine exacte, request ID, timeout et annulation.
- Passer des UUID ressource/espace/opération, jamais un permalink public ou une
  URL arbitraire donnée par le client. Les titres et tailles ne sont pas des preuves.
- Ouvrir la source via Storage/Provider, observer version/génération/taille,
  traiter en flux ou spool disque borné et revalider avant publication. Une
  modification NAS directe pendant la copie doit produire un échec propre ou
  une nouvelle observation explicite, pas un mélange de versions.
- Le quota Messages/Projects de 25 Mio est conservé. Nouveau profil Transfers
  séparé, avec admission par taille réelle et multipart ; aucune lecture géante
  en RAM, transaction DB ouverte pendant des gigaoctets ou timeout HTTP augmenté
  comme unique solution.
- Tâches natives, progression persistante, retries idempotents, lease de travail
  récupérable, annulation réellement observée et objets incomplets invisibles.
- Preuves courtes : renouveler les autorisations aux étapes appropriées ; ne pas
  laisser une copie de plusieurs heures dépendre d'un bearer expiré sans reprise,
  ni remplacer celui-ci par un credential machine donnant accès à tout Drive.
- Pour Docs, lien vivant dans le chat ou export PDF explicite vers Transfers ;
  pas de sérialisation improvisée du document collaboratif.
- Désactiver le chemin arbitraire `source_url` en mode suite ; contrôler les
  redirections/SSRF et les destinations S3 explicitement configurées côté serveur.

### 6.4 Deux modes Transfers, aucune promesse cryptographique trompeuse

**Standard** : la clé est disponible au service pour import/scan et restitution.
Conserver le format natif, protéger la clé en base/sauvegardes et la retirer à
la purge. Il s'agit de chiffrement stocké, pas d'E2EE vis-à-vis du serveur.
Réutiliser ClamAV : soit adaptateur étroit vers le scanner existant, soit service
file-scanner natif s'il apporte le flux asynchrone nécessaire. Vérifier son
contrat avant de le déployer ; ne pas dupliquer le moteur antivirus.

**Confidentiel** : chiffrement/déchiffrement par chunks côté client avec le
format natif authentifié. La clé ne passe ni par API Transfers, logs, télémétrie,
Messages ni paramètres serveur. Elle voyage séparément ou dans le fragment du
lien partagé explicitement. Prévenir que perte de clé = récupération impossible
par l'administrateur. Conserver les mécanismes de sauvegarde locale du client
sans collecter leur contenu dans les rapports.

Pour Drive → Transfers confidentiel : source autorisée lue par le client,
chiffrement incrémental puis multipart chiffré. Pour Transfers confidentiel →
Drive : déchiffrement client puis upload privé gouverné Drive, avec information
que Drive recevra une copie lisible. Pas de clé transmise pour « faciliter »
une copie serveur. Fallback navigateur sans streaming : taille explicitement
bornée et parcours de sauvegarde locale/réimport, jamais `blob()` non borné.
Documenter les plafonds réellement supportés par navigateur ; traiter les
grands fichiers sur le chemin streaming, sans annoncer une parité non testée.

Antivirus : standard sain = scan réussi. Infecté ou panne = refus ; trop gros
pour le scan = refus par défaut en standard, sauf politique administrée explicite
« non analysé » avec affichage correspondant. Confidentiel/Matrix E2EE = serveur
incapable d'analyser le contenu, donc aucun badge antivirus trompeur. Corriger
les statuts permissifs hérités ; conserver le choix confidentiel, sans prétendre
obtenir simultanément secret serveur et analyse en clair.

### 6.5 Liens, téléchargement et purge

- Métadonnées et ouverture de page ne consomment pas un envoi one-shot. Une
  action explicite POST obtient une session de téléchargement bornée, protégée
  contre concurrence, réutilisable pour la reprise des fichiers de cet envoi.
- Définir l'option comme une **session de téléchargement**, pas la preuve que
  le destinataire a enregistré tous les octets. Conserver la progression/reprise
  sans qu'un robot d'aperçu consomme l'envoi.
- Expiration contrôlée à chaque admission, sans attendre le prochain cron.
  Une URL S3 déjà délivrée reste une capacité jusqu'à son échéance : limiter
  sa validité au budget de révocation, renouveler les ranges si nécessaire.
  L'âge de la décision en cache et la durée de l'URL s'additionnent : l'expiration
  de l'URL ne dépasse jamais celle de la décision d'accès qui la justifie ni
  celle du transfert. Vérifier cette somme dans la recette, pas chaque TTL isolé.
  Les streams acceptés peuvent finir ; ne pas promettre de rappel des octets.
- Rate limit, jetons non devinables, réponses sans énumération de personnes,
  noms téléchargés assainis, `no-store`, politique Referrer et masquage des
  jetons/liens signés dans tous les logs.
- Purge idempotente par objets exacts/version, multipart abandonnés, dérivés et
  clés ; journal conservé en cas d'échec. Pas de sweep supprimant un autre bucket
  ni de suppression basée seulement sur un nom de fichier.

### 6.6 Médias Matrix et clés

- Employer le format E2EE des SDK ; ne pas appliquer le format AES de Transfers
  aux événements Matrix. Les clés sont dans le contenu chiffré des événements.
- Préserver vérification d'appareils, cross-signing, sauvegarde chiffrée des clés
  et restauration native. Aucune clé maîtresse détenue par People/ST.
- Les médias Matrix authentifiés ne sont pas des ACL Drive par salon. Un MXC
  peut désigner des octets chiffrés accessibles à un utilisateur authentifié qui
  connaît l'identifiant ; leur déchiffrement dépend des clés reçues. Ne pas
  promettre de retirer une clé déjà transmise avec une simple révocation de salon.
- Fichiers sensibles liés depuis Drive : garder l'autorisation Drive à chaque
  ouverture, sans rendre l'URL publique. Copie dans le chat : action explicite,
  chiffrement côté client et information sur son autonomie.
- Interdire l'exposition publique des médias et les anciennes routes anonymes ;
  traiter avatars/miniatures non chiffrés comme métadonnées à portée contrôlée.
- Pas de collecte automatique agressive basée sur l'absence de MXC visible dans
  les événements : les références sont chiffrées. Nettoyer les uploads abandonnés
  prouvés et conserver les médias potentiellement référencés, facturés, jusqu'à
  une suppression explicite ou une politique de rétention documentée.

## 7. Parcours d'intégration aux autres applications

Chaque intégration respecte l'autorité de l'application cible. Une appartenance
au salon ne devient pas automatiquement un droit sur un fichier, une réunion,
un calendrier ou une carte. Les opérations d'écriture portent un principal
People vérifié, une intention bornée et un identifiant idempotent ; les secrets
machine ne sont jamais accessibles aux clients web ou mobiles.

### 7.1 Drive et Docs

- Dans le compositeur : **Ajouter depuis Drive**, puis **Partager un lien** ou
  **Envoyer une copie**. La boîte affiche les destinataires/portée et ce qui
  restera soumis aux droits Drive.
- Pour un lien, vérifier les accès sans révéler les personnes ou ressources
  non visibles. Si l'émetteur peut partager, proposer une attribution explicite
  et confirmée ; sinon lien avec indication des accès manquants ou demande
  d'accès native. Ne pas ouvrir automatiquement le fichier à tous.
- Le lien Docs pointe vers le document vivant ; un export porte son format
  et son statut de copie. Les cartes de lien sont rendues après autorisation,
  sans service d'aperçu serveur qui crawlerait des liens privés arbitraires.
- Action **Enregistrer dans Drive** sur une pièce jointe : déchiffrement dans
  le client pour E2EE, sélection du dossier et nom, contrôle de collision/quota,
  confirmation d'import et lien vers le résultat. Une reprise ne duplique pas.
- Sur mobile, employer les composants de sélection/document picker natifs et
  un parcours suite HTTPS authentifié pour les ressources Drive. Le simple
  `window.opener` du Web n'est pas un contrat mobile : callback lié à la requête,
  à l'application et à l'utilisateur, autorisation courte et non rejouable.
- Le titre d'un document partagé dans un salon est lui-même une information :
  l'envoyer dans le contenu chiffré, avec aperçu explicite avant partage.

### 7.2 Chat et Transfers

- Bouton/menu **Créer un transfert** depuis l'ajout de fichier et action
  **Envoyer avec Transfers** pour les fichiers dépassant le plafond Chat.
- Ouvrir un brouillon associé à une opération courte, sans copier les credentials
  Matrix dans une URL. Revenir au salon avec une carte de transfert contenant
  titre, taille, expiration et une action claire de téléchargement.
- Un fichier déjà chiffré Matrix ne se déchiffre pas sur Synapse pour être copié
  vers Transfers. Le client le déchiffre puis choisit explicitement le mode du
  nouvel envoi ; ne pas exposer une clé Matrix au serveur Transfers.
- Partager un lien confidentiel dans le salon chiffre aussi son fragment dans
  l'événement Matrix. Aucun robot d'aperçu ni notification push ne reçoit la clé.
- Depuis Transfers, **Partager dans le chat** sélectionne un salon accessible
  dans le client authentifié et conserve un texte lisible de repli pour un client
  Matrix standard. Le backend ne poste pas en usurpant le compte humain.
- Désactivation/expiration affichée à l'ouverture de la ressource ; ne pas faire
  dépendre l'accès d'une ancienne carte mise en cache.

### 7.3 Meet / Visio

- Dans l'en-tête du salon, un bouton principal **Démarrer une réunion** puis
  **Rejoindre** quand une réunion valide existe ; menu discret pour planifier.
- Créer une réunion native Meet via une API de délégation restreinte réutilisant
  les services existants. Deux clics simultanés ne créent pas deux réunions pour
  la même opération. L'association room Matrix / réunion Meet est opaque et
  consultable seulement par les personnes autorisées.
- Associer explicitement les participants ou groupes à la réunion ; pas de lien
  anonyme pour contourner l'admission. Retrait du groupe/salon ou révocation
  d'application réévalués à l'entrée et pendant la réunion, selon le contrat Meet.
- Carte de réunion : état actif/terminé, rejoindre et fermeture par responsable.
  Les liens anciens ne recréent pas une réunion fermée. Les états viennent du
  serveur Meet et de ses événements vérifiés, jamais seulement du message client.
- Web : intégration dans un panneau si les politiques CSP/frame et l'authentification
  le permettent ; sinon onglet Meet dédié, explicitement nommé, avec retour au
  chat. Pas d'iframe qui bloque la caméra ou échoue silencieusement au SSO.
- Mobile : ouverture Meet dans un parcours navigateur système fonctionnel,
  retour au salon et gestion correcte micro/caméra/orientation. Une WebView
  générique ne vaut pas validation WebRTC. Conserver une seule réunion Meet
  et son serveur LiveKit ; les appels Element Call/MatrixRTC/Jitsi parallèles
  sont désactivés ou leurs actions réorientées dans les clients Apoze.
- Notification d'invitation incluse ; sonnerie téléphonique native exclue §1.
  L'invitation ne force ni l'ouverture micro/caméra ni l'entrée en réunion.

### 7.4 Calendars

- **Planifier une réunion** ouvre une création préremplie : titre explicite,
  participants autorisés, fuseau, durée et éventuellement réunion Meet.
- L'organisateur choisit un calendrier sur lequel il peut écrire et confirme
  l'envoi des invitations via Messages. Une prévisualisation n'envoie rien.
- Créer l'événement via les services/API natifs ; corréler calendrier/UID/room
  pour éviter les doublons et obtenir les mises à jour/annulations natives.
- Publier une carte avec date/fuseau et actions **Ouvrir l'événement** et
  **Rejoindre** ; mise à jour à l'ouverture. Pas de synchronisation arbitraire
  du texte du salon vers des agendas.

### 7.5 Projects

- **Partager une tâche** dans le chat : carte + lien, détails visibles seulement
  selon le droit Projects ; même principe pour un tableau.
- **Créer une tâche depuis ce message** : action du client après déchiffrement,
  aperçu du texte qui sort du salon, choix du projet/tableau et confirmation.
  Le lien retour au message respecte l'accès au salon. Ne pas exporter tout le
  fil ni ses pièces jointes sans sélection explicite.
- Notifications d'affectation/commentaire choisies par l'utilisateur ou le
  responsable du salon. Réutiliser le journal de notifications et les événements
  natifs Projects ; recontrôler les droits au moment de la remise.
- Dans un salon chiffré, tout bot de notification est un membre identifié avec
  un vrai client/SDK E2EE et un état de clés persistant. Sa présence nécessite
  une activation explicite et l'UI explique sa portée ; pas d'identité invisible
  possédant toutes les clés. Par défaut, notifications génériques et liens,
  sans texte de carte ou de document confidentiel.

### 7.6 Messages et catalogue

- Transfers utilise le MTA Messages déjà configuré : adresse de service,
  destinataires internes autorisés, mails sans clé confidentielle et réponses
  d'erreur/reprise visibles. L'email d'acheminement n'est pas une clé d'identité.
- Réutiliser la réception d'intentions restreintes si utile, en séparant les
  credentials et types de notification Transfers/Chat/Projects ; pas d'API ouverte
  acceptant expéditeur, destinataire et corps arbitraires.
- Journal par UUID/Message-ID ; distinguer retry certain et résultat SMTP
  incertain. Aucun « exactement une fois » annoncé après perte d'accusé SMTP.
- Résumés mail de messages manqués facultatifs et désactivés au départ, sans
  extraction serveur des salons chiffrés. Les push et notifications natives du
  chat sont prioritaires ; pas de multiplication automatique des notifications.
- Enregistrer **Transferts** et **Chat** dans le catalogue ST avec URLs LAN,
  accès et état. Retour à la suite depuis les apps ; un menu masqué ne remplace
  pas le refus de l'API. Le catalogue mobile ouvre les apps/URLs disponibles
  avec des retours compréhensibles et sans duplication de compte.

## 8. UI/UX : règles de réalisation et critères visuels

Le style de chaque application est la référence. Transfers/Drive/ST utilisent
leurs composants Cunningham/ui-kit existants ; Element utilise ses composants
et tokens natifs Compound ; Element X conserve SwiftUI/Compose et le design
natif correspondant. Ne pas injecter Cunningham dans les apps natives ni
reconstruire l'interface Element pour imiter Tchap.

| Emplacement | Action / présentation attendue |
| --- | --- |
| Transfers, zone d'ajout | Deux vrais boutons cohérents « Ajouter des fichiers » / « Ajouter depuis Drive », lisibles avant et après sélection |
| Transfers, récapitulatif | Taille, expiration et mode ; un bouton principal Publier/Envoyer ; avancement distinct de la confirmation finale |
| Transfers, page destinataire | Titre, expiration, liste des fichiers, statut de confidentialité/scan, action Télécharger ; retour ou erreur expliqués |
| Chat, en-tête salon | Nom, membres, réunion ; action Rejoindre visible seulement quand pertinente |
| Chat, compositeur | Menu d'ajout regroupant Fichier, Drive et Transfers ; pas de barre saturée de boutons |
| Message/carte | Menu contextuel : enregistrer, partager, créer une tâche ; actions secondaires discrètes mais réellement accessibles |
| Paramètres du salon | Membres/rôles/groupes, portée, notifications ; séparer les droits du salon des droits des ressources liées |
| Paramètres personnels | Appareils, sauvegarde de clés, notifications et accès à la suite |
| ST/People | Accès applicatif, groupes et budgets au même endroit que les services déjà livrés |

Exigences de finition obligatoires :

- Actions = boutons natifs, jamais texte souligné/clickable déguisé en bouton.
  Les liens restent réservés à la navigation ; une action importante navigante
  peut utiliser le composant bouton-lien prévu par le kit.
- Une action principale par étape, espacement et alignements natifs, icône
  accompagnée d'un libellé sauf commande universelle avec nom accessible.
- Pas de jargon backend dans les parcours : les utilisateurs choisissent leurs
  fichiers/espaces, pas « SMB vs S3 » ou un nom de provider technique.
- Messages courts distinguant accès refusé, quota plein, scan en cours, réseau
  indisponible, clé manquante, source modifiée et transfert expiré.
- Étapes longues non bloquantes avec progression, annulation, retour et reprise.
  Rechargement/SSO/fermeture popup ne perdent pas le brouillon silencieusement.
- Gestion robuste de la fermeture popup et du changement d'origine OIDC/COOP ;
  pas de surveillance `popup.closed` qui annule une connexion encore active.
- Modales au bon niveau, focus piégé/restauré, navigation clavier, labels et
  contrastes accessibles, zone de contenu défilable et actions toujours visibles.
- Français cohérent et anglais conservé via les fichiers de traduction ; modes
  clair/sombre et tailles de texte mobiles respectés si présents dans l'app.
- Vérification visuelle réelle desktop et écran étroit ; appareils mobiles avec
  clavier affiché, safe areas et portrait/paysage. Pas de boutons hors écran,
  surcharge, badges ambigus ou mise en page évaluée seulement par le DOM.

Ne modifier aucune autre UI sans besoin démontré. Capturer l'écran avant/après
pour chaque ajout significatif, avec données de recette et sans tokens/clé/QR
de récupération dans les captures publiées.

## 9. Lots d'exécution et suivi

Ordre : **TC0 → TC1 → TC2 → TC3 → TC4 → TC5 → TC6 → TC7 → TC8 → TC9 →
TC10 → TC11 → TC12**. Commencer l'inventaire des prérequis mobiles dès TC0.
TC2/TC3 et les interfaces peuvent avancer pendant une attente externe des lots
Matrix/mobile. Ne pas attendre la fin du chantier pour découvrir un blocage iOS.

| Lot | Périmètre | Dépendance | État initial |
| --- | --- | --- | --- |
| TC0 | Préflight, versions, forks, décisions et préparation | — | À faire |
| TC1 | Preuve de faisabilité auth/permissions Matrix et mobile | TC0 | À faire |
| TC2 | Docker persistant et services communs | TC0, conclusions TC1 | À faire |
| TC3 | Transfers : identité, cycle de vie, quotas, scan et mail | TC2 | Fonctionnel et testé ; exploitation/publication TC11/TC12 restantes |
| TC4 | Échanges privés Drive/Docs et gros transferts | TC3 | Fonctionnel et testé ; clôture TC11/TC12 restante |
| TC5 | Synapse/MAS : identité, sessions, groupes et stockage | TC1–TC2 | À faire |
| TC6 | Element Web et échanges chat/fichiers/Transfers | TC4–TC5 | À faire |
| TC7 | Meet, Calendars, Projects et notifications | TC6 | À faire |
| TC8 | Element X Android | TC5–TC7 | À faire |
| TC9 | Element X iOS | TC5–TC7, ressources Apple | À faire |
| TC10 | Push, reprise et cohérence multi-appareils | TC8–TC9 | À faire |
| TC11 | Exploitation, restauration et recette finale ciblée | Lots fonctionnels | À faire |
| TC12 | Nettoyage, documentation et publication | TC11 | À faire |

### TC0 — Préparer sans endommager l'existant

- [ ] Relire les contrats ; relever services, ressources CPU/RAM/disque/volumes,
  ports et URLs en usage, sauvegardes disponibles, bases Git et changements sales.
- [ ] Identifier domaines, certificats, moyens de compilation et appareils ;
  renseigner les prérequis §4 et demander seulement les informations introuvables.
- [ ] Vérifier versions compatibles, avis de sécurité pertinents, licences et
  variantes de build libres ; compléter le manifeste SHA + images/digests.
- [ ] Créer/réutiliser les forks et branches Apoze, remotes amont sans push ;
  ne pas activer les workflows upstream de déploiement/distribution officiels.
- [ ] Créer état/journal d'exécution, fixer les interfaces d'intégration et
  consigner les plafonds initiaux, échéances et règles de conservation.
- [ ] Préparer une sauvegarde ciblée de ce qui sera modifié et la procédure de
  retour, sans arrêter la pile entière.

Sortie : inventaire concret, ressources manquantes nommées et bases reproductibles.

### TC1 — Lever les inconnues serveur et préparer la validation mobile

- [ ] Sur environnement jetable, faire connecter Element Web au couple
  Synapse/MAS candidat ; ajouter Element X sur simulateur/émulateur si disponible,
  sinon reporter cette partie selon §1. Vérifier discovery, TLS, PKCE et sliding
  sync natif. Pas d'ancien proxy sliding-sync ajouté sans nécessité observée.
- [ ] Tracer les points natifs d'authentification et de refresh MAS/Synapse,
  API Admin de rattachement et invalidation ; choisir le mécanisme approuvé
  d'association People avant de créer des comptes durables.
- [ ] Compléter la matrice §5.2 : pouvoir refuser lecture/sync/médias/écriture
  avec un token existant ; identifier les patchs serveur nécessaires. Tester
  aussi un accès natif sans les personnalisations Element.
- [ ] Examiner upload médias synchrone/asynchrone et admission de quotas ;
  ne pas choisir un hook post-upload si la réserve doit précéder les octets.
- [ ] Vérifier menus/compositeur/cartes/réunions via l'API de modules Element
  retenue ; préférer un petit patch natif lorsque l'extension manque.
- [ ] Implémenter la voie d'authentification des forks mobiles, callbacks de
  retour suite et domaine associé iOS ; vérifier leur exécution si l'environnement
  mobile est disponible, sinon consigner précisément les vérifications différées.
- [ ] Écrire l'ADR Matrix/session mobile et le choix de backend médias, avec
  limites connues. Reporter les résultats dans ce plan, retirer le code jetable
  qui ne sert pas à la solution finale.

Sortie : choix techniques vérifiés, pas seulement une page d'accueil affichée.
L'absence de simulateur/émulateur ou d'outillage mobile entraîne une validation
différée autorisée (§1), sans bloquer les lots suivants ni valider fictivement
les parcours mobiles. Les preuves serveur restent obligatoires.

### TC2 — Déployer les fondations persistantes

- [ ] Générateurs ciblés `prepare_transfers.py` / `prepare_chat.py` et commandes
  de provisioning idempotentes selon les conventions `docker/suite/` existantes.
- [ ] Bases/rôles séparés, bucket Transfers privé, médias Matrix persistants,
  secrets neufs par consommateur, workers natifs et files identifiées.
- [ ] TLS/DNS/discovery et reverse proxy cohérents. Les pages HTTPS ne chargent
  pas de sous-ressources/API HTTP ; ajouter si nécessaire des alias TLS ciblés
  aux intégrations existantes, en conservant leurs anciens accès LAN.
- [ ] Supprimer du profil livré seeds, comptes de démonstration, clés publiques
  de développement, inscription libre, fédération et services redondants.
- [ ] Configurer CORS/CSP/CSRF, origines, redirects et cookies propres aux apps,
  listeners internes et droits minimaux. Admin MAS/Synapse non exposées au LAN.
- [ ] Enregistrer les deux applications People/ST et catalogue, initialement
  fermées tant que la première recette d'autorisation n'est pas passée.
- [ ] Laisser le script Drive existant inchangé ; commandes distinctes pour ces
  services, et ST toujours géré séparément conformément au choix du propriétaire.

Sortie : redémarrage persistant et santé des dépendances vérifiables.

### TC3 — Terminer Transfers en mode suite

- [x] Intégrer `suite-identity`, associations People, politique ST, sessions,
  déconnexion et refus des rapprochements email/claims métiers.
- [x] Compléter les budgets Transfers dans ST et leur édition Web ; admission
  atomique sur brouillons, sign-part, complete, finalize, rétention et purge.
- [x] Corriger concurrence et idempotence des opérations, dont finalize après
  perte de réponse et jobs d'import/scan redélivrés.
- [x] Vérifier les tailles réelles, signatures multipart, content-length/parts,
  intégrité des chunks et limites avant publication ; aucune écriture sans réserve.
- [x] Raccorder l'antivirus, les statuts standard/confidentiel et reprises de
  panne ; conserver le secret confidentiel hors de tout serveur.
- [x] Implémenter les sessions one-shot, expiration/révocation et purge §6.5.
- [x] Raccorder Messages pour les invitations et reprises contrôlées ; aucun
  destinataire WAN ou clé confidentielle dans les mails.
- [x] Finir les écrans de création, suivi, téléchargement et administration,
  avec les boutons et états §8.

Sortie : envoi local réel, invitation reçue, download vérifié et refus critiques.

### TC4 — Drive/Docs et gros fichiers

- [x] Étendre le sélecteur canonique et les capacités par consommateur ; corriger
  annulation, multi-sélection et retour SSO.
- [x] Remplacer permalink/publicisation/source_url par délégation privée,
  observation source et copies bornées compatibles S3/MountProvider.
- [x] Ajouter profil gros transferts et fichiers vides sans modifier les plafonds
  des consommateurs existants ; preuve des droits pendant l'opération.
- [x] Implémenter les chemins confidentiels côté client et leur reprise contrôlée ;
  aucune clé envoyée à Transfers pour un import Drive confidentiel.
- [x] Ajouter retour Transfers → Drive, exports Docs et confirmation des copies
  autonomes ; noms sûrs, collisions sans écrasement et résultat idempotent.
- [x] Mesurer une copie réelle multi-chunks ; corriger seulement les goulots
  constatés, pas de suite de benchmarks générale.

Sortie : aller-retour réel S3 et NAS, digest identique et source toujours privée.

### TC5 — Gouvernance complète du serveur Chat

- [ ] Implémenter le module d'association/réconciliation et les patchs Synapse/MAS
  identifiés ; transactions natives/API prises en charge, aucune écriture sauvage.
- [ ] Contrôler toutes les entrées §5.2, révision/epoch, session/refresh et panne
  d'autorité ; empêcher les accès alternatifs par listeners/routes oubliés.
- [ ] Projection People vers comptes/annuaire/groupes/salons avec provenance,
  rôles natifs, dernier responsable et reprise orpheline.
- [ ] Budgets Chat dans ST : médias uploader/org/instance, quotas atomiques,
  usages affichés, purge et suspension non destructive.
- [ ] Vérification et sauvegarde de clés natives, déconnexion par appareil ou
  globale ; conserver l'historique après changement d'IdP.
- [ ] Désactiver fédération, invités, inscriptions et médias publics ; conserver
  des sessions standard compatibles avec un client Matrix non modifié.

Sortie : deux utilisateurs communiquent ; un troisième non autorisé est refusé,
même avec le client natif ; retrait effectif dans la borne annoncée.

### TC6 — Chat Web fonctionnel et intégré

- [ ] Personnalisation minimale Element Web, catalogue et lien de retour suite,
  composants Compound natifs et build autonome reproductible.
- [ ] Conserver messages, réponses/fils supportés, édition, suppression,
  réactions, mentions, états non lus, recherche locale disponible et fichiers.
  Établir la parité précise avec la release retenue, sans activer des labs.
- [ ] Annuaire, membres et paramètres de salon compréhensibles, sans invités.
- [ ] Drive/Docs : liens privés, copie explicite, sauvegarde vers Drive et
  partage de droits confirmé, avec contrôle par les applications cibles.
- [ ] Transfers depuis le compositeur et carte de résultat, y compris lien
  confidentiel et retour au bon salon.
- [ ] Brouillons/reconnexion, vérification d'appareil et récupération de clés
  testés par une vraie navigation, sans perte de données client.
- [ ] Validation visuelle desktop/étroit et clavier, boutons correctement placés.

Sortie : parcours de collaboration web utilisable, pas un simple lien catalogue.

### TC7 — Meet, Calendars, Projects et communication

- [ ] Créer/rejoindre/terminer une réunion Meet depuis un salon, droits et
  association persistants ; actions d'appel concurrentes non dupliquées.
- [ ] Planifier dans Calendars avec invitations Messages et carte ; modifications
  et annulation via l'application propriétaire, sans doublons.
- [ ] Partager/créer une tâche Projects depuis le chat avec aperçu explicite ;
  lien de retour et refus si l'accès Projects ou Chat manque.
- [ ] Notifications Projects choisies et bot E2EE visible seulement dans les
  salons où il est activé ; répétition/révocation n'envoient pas un doublon indu.
- [ ] Préserver les fonctions Meet/Calendars/Projects existantes, dont retrait
  de participation, changement de groupe et permissions des pièces jointes.

Sortie : vrai échange chat → réunion/événement/tâche, avec les refus pertinents.

### TC8 — Application Apoze Android

- [ ] Fork Element X, app ID/nom/icône/cohérence visuelle, endpoints et découverte
  du serveur configurés ; conserver notices, SDK et composants natifs.
- [ ] Désactiver/réorienter les parcours vers serveur public, invités et seconde
  pile d'appels ; pas de credentials Element embarqués ou secret serveur compilé.
- [ ] Configurer OIDC/MAS, liens applicatifs, partage système, fichiers/photos
  avec permissions OS minimales, stockage sécurisé et sauvegarde de clés native.
- [ ] Ajouter les actions suite au bon endroit : Drive/Transfers, Meet, cartes
  Calendars/Projects et retour au salon. Réutiliser les écrans Web lorsque leur
  usage sur mobile est validé ; ne pas recopier chaque application en natif.
- [ ] Préparer le build versionné et la signature Apoze ; compiler avec les
  outils disponibles. Un APK de développement suffit à la recette sur émulateur,
  sans le présenter comme signé pour la distribution. Retirer les services
  commerciaux non requis ; reporter signature/AAB si leurs prérequis manquent.
- [ ] Si un émulateur Android est utilisable, installer et vérifier login,
  envoi/réception, pièce jointe, récupération de session, Meet et partage système
  dans les capacités disponibles ; sinon reporter la recette selon §1.

Sortie : code Android complet, résultat des builds/essais disponibles et liste
des validations différées. Aucun téléphone requis pour clôturer ce périmètre.

### TC9 — Application Apoze iOS

- [ ] Fork Element X, bundle IDs/app group/signature, nom/icône, endpoints et
  callbacks OIDC/domaines associés selon les instructions de la release.
- [ ] Keychain, sauvegarde chiffrée de clés, permissions micro/caméra/photos,
  extension de partage et Notification Service Extension configurées pour Apoze.
- [ ] Même portée fonctionnelle des intégrations que TC8, avec composants natifs,
  safe areas, clavier, retour SSO et parcours Meet audio/vidéo à vérifier dans
  les capacités du simulateur disponible, puis sur appareil ultérieurement.
- [ ] Préparer le build reproductible macOS/Xcode ; compiler pour simulateur
  si un Mac accessible le permet, sans exiger une signature de distribution.
  Sinon livrer le code/configuration et noter le build non exécuté. Préparer
  la signature sans certificat tiers ni publication sur un magasin.
- [ ] Si le simulateur iOS est utilisable, installer et exécuter les parcours
  ciblés ; noter ses limites. Reporter la recette physique et les fonctions non
  vérifiables, notamment caméra réelle et conditions d'arrière-plan.

Sortie : code iOS complet, résultat des builds/essais disponibles et liste des
validations différées. L'absence de Mac ou d'iPhone ne bloque pas cette livraison.

### TC10 — Notifications et multi-appareils

- [ ] Qualifier/configurer Sygnal et les IDs APNs/FCM Apoze ; vérifier compatibilité
  HTTP/API actuelle et corriger sa fork si nécessaire. Credentials privés et
  séparation sandbox/production, pas de relais Element privé réutilisé.
- [ ] Payload push minimal avec IDs opaques ; aucun texte privé, titre de
  document ou fragment de clé. Déchiffrement d'aperçu éventuel sur l'appareil
  selon préférences, sinon notification générique.
- [ ] Enregistrer/supprimer les pushers natifs, limiter leurs destinations aux
  passerelles autorisées pour éviter SSRF et fuite de métadonnées.
- [ ] Notification reçue app en arrière-plan, ouverture dans le bon salon,
  compteur non lu, mode silencieux et réglages OS/app respectés.
- [ ] Révoquer utilisateur/appareil, vérifier arrêt des nouvelles remises ; les
  notifications déjà acceptées par APNs/FCM peuvent arriver, mais n'ouvrent aucun
  nouveau contenu interdit.
- [ ] Perte réseau puis reconnexion sans doublons, message envoyé hors ligne
  signalé en attente, vérification d'appareils et historique Web/Android/iOS.
- [ ] Ne pas promettre les push iOS en mode totalement déconnecté d'Apple ; si
  credentials ou environnement manquent, préparer tout le code/configuration
  puis reporter la livraison de notifications et la recette dépendante selon §1.

Les essais de ce lot utilisent les émulateurs/simulateurs disponibles et leurs
capacités réelles. Une injection locale teste l'affichage/interaction, pas le
transport APNs/FCM. L'absence de moyens mobiles n'empêche pas les vérifications
serveur possibles (pushers, permissions, payloads et invalidation).

Sortie : intégration push codée et contrôles accessibles effectués ; distinguer
notifications effectivement reçues, simulations locales et recette reportée.

### TC11 — Exploitation et recette finale

- [ ] Commandes séparées start/stop/status/backup/restore/cleanup-restore pour
  Transfers et Chat ; extraire seulement les mécaniques dupliquées démontrées
  dans les opérations existantes, sans framework générique de déploiement.
- [ ] Santé DB, disque/temporaire, S3/médias, workers/scan, MAS, snapshots,
  réservations/purges et notifications bloquées ; métriques sans contenu privé.
- [ ] Sauvegarde cohérente : DB Synapse/MAS/Transfers, tables suite, médias,
  signing keys, clés standard Transfers, configurations et révisions d'images.
  Les clés E2EE utilisateur restent chiffrées et récupérées côté client.
- [ ] Restaurer sur réseaux/volumes isolés, sans push/mail, fédération ou écritures
  vers les services vivants. Une identité Matrix restaurée ne doit pas fonctionner
  simultanément comme second serveur actif avec le même nom.
- [ ] Revalider People/ST actuels avant ouverture ; ancien token ou droit révoqué
  depuis la sauvegarde refusé. Reconnexion avec récupération des clés nécessaire
  à la lecture de l'historique restauré.
- [ ] Démontrer une reprise : transfert finalisé, salon, média et liens suite
  cohérents ; intents déjà remis non rejoués après restauration.
- [ ] Documenter upgrade avec migrations et limites de rollback ; image ancienne
  seule ne garantit pas le retour après migration DB. Revenir via sauvegarde
  cohérente quand la migration n'est pas réversible.
- [ ] Exécuter seulement les scénarios §10 non déjà prouvés sur les versions
  finales ; aucun full automatique pour compenser un doute non diagnostiqué.

Sortie : exploitation répétable et restauration réelle validée.

### TC12 — Nettoyer et livrer

- [ ] Supprimer fichiers de recette uploadés/downloadés, transferts, salons,
  médias de test identifiés, mails, calendriers/cartes/Docs de recette et rôles
  temporaires ; vérifier purges effectives et restituer les quotas modifiés.
- [ ] Retirer comptes/clients IdP temporaires, pushers/devices de recette et
  environnements de restauration ; remettre Authentik QA à son état initial.
  Conserver comptes administrateur opérationnels et données préexistantes.
- [ ] Vérifier tous les services existants, routes LAN et catalogue ; aucune
  instance en double ou source bind de recette dans les images livrées.
- [ ] Guides `docs/operations/suite-transfers.md`, `suite-chat.md` et
  `suite-chat-mobile.md` : usages, administration, limites, versions, installation,
  sauvegarde, reprise et mise à jour. Liens depuis l'index des plans/roadmap.
- [ ] Mettre le plan, journal et registre des améliorations à jour ; chaque
  blocage externe/limite a un statut visible, aucun TODO obligatoire oublié.
- [ ] Gates de publication de chaque dépôt, commits/push Apoze et SHA distants
  vérifiés ; rapport avec URLs complètes des forks et branches, amonts fetch-only.
- [ ] Fournir accès LAN, sources mobiles et artefacts effectivement construits,
  preuves disponibles et instructions d'installation. Joindre la checklist de
  recette mobile différée §14. Clôturer le périmètre selon §13 avec ce statut
  explicite, sans annoncer une validation physique non effectuée.

## 10. Validation minimale, réelle et réutilisable

Principe : une petite recette continue avec deux comptes internes actifs et un
compte refusé, un groupe People, un salon et des objets de test identifiés.
Réutiliser ces données entre lots ; ajouter seulement les cas critiques liés
aux modifications. Capturer des résultats/digests/timings, pas les contenus.

Contrôles de code : lint/typecheck/build des seuls composants touchés selon les
scripts natifs. Ajouter un test ciblé uniquement pour une logique fragile qui
doit rester protégée (réservation concurrente, rattachement, token/rejeu ou
chiffrement), en réutilisant les frameworks existants. Ni tests par fonction ni
nouveau harnais généraliste. Les assertions de comportement dans une vraie
recette sont permises ; les recherches de texte dans le code ne sont pas des tests.

| Recette | Parcours réel regroupé | Preuve minimale |
| --- | --- | --- |
| R0 — socle | Redémarrer nouveaux services, connexion/approbation, droits ST ; accès refusé depuis client natif puis autorisé | URLs, images, identité stable et refus serveur |
| R1 — Transfers | Fichier vide, petit multi-fichiers, un multi-chunks, upload/import/reprise, standard et confidentiel, invitation Messages, téléchargement avec digest | Hashes/taille, clé jamais envoyée en confidentiel, aucune source rendue publique |
| R2 — Drive/Docs | Aller-retour S3 et NAS, fichier modifié pendant copie, export Docs, collision et reprise après réponse perdue | Résultat unique, fichier existant intact, quotas exacts |
| R3 — limites | Deux admissions concurrentes près du quota, EICAR en standard, panne ClamAV puis reprise, retrait source/droit pendant un job | Un seul dépassement refusé correctement, aucun fichier publié improprement |
| R4 — cycle | Désactivation/expiration, robot ouvrant les métadonnées sans consommer one-shot, acquisition concurrente et reprise, purge S3 en panne puis réussie | Aucun accès nouveau après borne, quota libéré après purge confirmée |
| R5 — chat | DM et salon, groupes/directs, édition/réaction, média chiffré, lecteur refusé, retrait utilisateur avec sync ouvert et ancien token | Historique correct, révocation ≤120 s sur Web et client natif |
| R6 — suite | Drive/Transfers dans le salon ; réunion Meet à deux, planification/annulation Calendars, carte Projects et notification choisie | Objets natifs uniques, refus par l'app cible et UI inspectée |
| R7 — mobile | Sur émulateur Android/simulateur iOS si disponibles : login, restauration clés, message/fichier, Meet et retour, perte réseau | Versions et environnement réellement exécutés ; sinon recette différée §14, appareils physiques ultérieurs |
| R8 — push | Réception arrière-plan, ouverture du salon, silence et révocation lorsque l'environnement le permet ; contrôles serveur accessibles maintenus | Distinguer APNs/FCM réellement reçus et notification injectée ; essais manquants reportés §14 |
| R9 — migration/reprise | Keycloak → Authentik → Keycloak sur contexte isolé, logout global ; sauvegarde/restauration avec retrait ST intervenu depuis | Même People/MXID/historique, récupération média, anciennes sessions refusées |

R1 : le multi-chunks doit dépasser plusieurs chunks et l'ancien plafond de
25 Mio. Un seul essai réel proche du plafond maximal annoncé suffit à valider
le mode « gros fichiers » ; le faire seulement lorsque la pipeline est stable,
avec l'espace et le quota nécessaires. Si le plafond annoncé reste 20 Gio,
ne pas appeler un test de 100 Mio une validation de ce plafond. Les limites de
scan et de navigateur doivent être cohérentes avec le mode effectivement testé.
Pas de fichier gigantesque répété sur toutes les plateformes : petit fichier
sur mobile, gros transfert sur le parcours destiné à cet usage.

Le quota de recette peut être augmenté temporairement selon l'autorisation
permanente du propriétaire ; relever/restaurer sa valeur et nettoyer les octets.
Ne pas confondre GB décimaux et Gio binaires dans les paramètres ou l'UI.

Navigateurs : Chromium pour la recette web principale ; une vérification ciblée
Firefox si le Service Worker/confidentiel/CORS est modifié. Safari iOS dans le
simulateur si disponible, puis recette physique différée ; sinon consigner les
parcours non testés. Pas de full trois navigateurs automatique.
Un défaut observé impose diagnostic/correction puis rerun de son chemin, pas
de recommencer toute la suite. Tests de panne limités aux nouveaux services ou
réseaux isolés ; ne pas couper le NAS, People, l'IdP ou le MTA partagé pour cela.

## 11. État d'exécution à maintenir

| Information | Valeur initiale |
| --- | --- |
| Derniers lots fonctionnels validés | TC3 et TC4 ; exploitation, nettoyage et publication restent dans TC11/TC12 |
| Lot actif | TC1/TC5 — identité, autorisation et déploiement Chat |
| Prochaine action | Finir gouvernance médias/salons, puis intégrations Web/mobile ; domaine Matrix permanent attendu |
| Préconditions externes | Domaine Matrix et TLS reconnu ; Mac/simulateur iOS, émulateur Android et outils de build à inventorier, sans bloquer le code mobile |
| Validation mobile | Aucun Android/iPhone connecté ; tests virtuels si possibles, sinon report explicite autorisé par le propriétaire |
| Blocage constaté | Identité Matrix durable : domaine attendu ; code et serveur jetable possibles. Aucun Mac/SDK mobile disponible identifié |
| Validation produit | Transfers : API/navigateur S3/NAS/Docs. Chat jetable : deux connexions OIDC approuvées, annuaire, invitation et échange chiffré réels ; révocation ST mesurée à 22,6 s, sessions MAS terminées. Mobile non exécuté |
| Publication du produit | Jalon TC3/TC4 poussé sur Apoze/drive, Apoze/transfers, Apoze/messages, Apoze/st-deploycenter et Apoze/docs ; SHA dans publication.md. Chat non livré |

Le journal de l'agent contiendra pour chaque lot : heure, SHA, surfaces touchées,
résultat, test réutilisable, état de la pile, cause exacte d'un blocage et prochaine
action. Aucun compte-rendu « tout est parfait » ne remplace ces éléments.

## 12. Registre des améliorations et problèmes à traiter

Registre initial issu de l'inspection ; ajouter les découvertes utiles pendant
l'exécution. Aucun ajout de périmètre obligatoire ne reste seulement dans une
conversation. Revoir aussi les critères de validation du lot concerné.

| ID | Besoin / cause | Lot | Statut initial | Vérification |
| --- | --- | --- | --- | --- |
| I01 | Le picker Transfers rend la source publique via l'ancien contrat | TC4 | À faire | Source S3/NAS toujours privée, copie autorisée |
| I02 | Bouton d'ajout pouvant rester bloqué après popup/SSO | TC4 | À faire | Annulation, fermeture et nouvelle sélection réelles |
| I03 | Échange suite limité à 25 Mio et excluant les fichiers vides | TC4 | À faire | Gros fichier/vide acceptés pour Transfers, plafonds autres apps inchangés |
| I04 | Cleanup best-effort pouvant perdre la trace des objets | TC3 | À faire | Panne purge, journal conservé puis quota libéré |
| I05 | Scan ignoré/trop gros non distingué d'une publication saine | TC3 | À faire | Refus standard par défaut et état confidentiel honnête |
| I06 | One-shot consommé à l'accès à l'URL S3 | TC3 | À faire | Metadata GET neutre et session explicite concurrente |
| I07 | Repli email de l'identité Transfers | TC3 | À faire | Identité durable, homonyme refusé, bascule IdP |
| I08 | Session web courte incompatible avec l'usage mobile arrière-plan | TC1/TC5 | À faire | Refresh natif et révocation effective sans reconnecter toutes les 15 min |
| I09 | Différences entre ACL Drive et médias Matrix chiffrés | TC5/TC6 | À faire | Droits et limites décrits correctement, partage explicite |
| I10 | Imports Drive confidentiels absents du chemin serveur natif | TC4 | À faire | Copie client bornée, absence de clé côté Transfers |
| I11 | HTTP existant face aux nouvelles origines HTTPS | TC2/TC6 | À faire | Aucun mixed content, retour SSO/Meet/Drive réel |
| I12 | Versions Transfers figées avec vulnérabilités connues | TC0/TC3 | Backend corrigé, audit sans vulnérabilité connue ; frontend à qualifier | Audit des dépendances et recette sur les versions corrigées |
| I13 | Cookie CSRF générique partagé entre applications sur une même IP | TC2/TC3 | Correctif en cours de qualification | Écriture réelle avec le cookie propre à Transfers |
| I14 | Passage standard → confidentiel après divulgation de la clé au serveur | TC3 | Refus ajouté, recette à faire | Le même brouillon ne peut plus annoncer une clé jamais reçue |
| I15 | Les paramètres Django remplacent le calendrier Celery | TC2/TC3 | Cause racine corrigée dans CELERY_BEAT_SCHEDULE ; fraîcheur automatique observée | Synchronisations People/ST, quota et nettoyage exécutés réellement |
| I16 | Le scanner partagé est limité à 64 Mio par flux | TC3 | Scan 60 Mio vérifié ; exemption des gros fichiers standard ajoutée à la politique organisation ST, désactivée par défaut et en qualification | Aucune modification du scanner partagé ; fichiers non analysés explicitement signalés, erreurs/infections jamais exemptées |
| I17 | Quotas Transfers/Chat sans traductions dédiées ni gel de croissance visible | TC3/TC5 | Formulaire Cunningham ST complété, validation à faire | Édition depuis le Web ; libellés humains et validation stricte du serveur |
| I19 | La limite affichée porte sur les fichiers, mais l’API la comparait aux octets chiffrés | TC3/TC4 | Limite de fichier et cumul corrigés sur la taille claire ; quota ST conserve les octets réservés réels | Un fichier au plafond annoncé reste admissible si le budget couvre le chiffrement |
| I20 | Rejeux add-file et complete-upload non idempotents | TC3 | Identifiant de requête et empreintes ajoutés ; rejeux réels passés | Une seule réservation ; mêmes parties acceptées au rejeu, requête différente refusée |
| I18 | Finalize perd sa réponse puis renvoie 404 au rejeu | TC3 | Empreinte et identité du brouillon conservées sur le transfert ; recette réelle passée | Même transfert au rejeu ; options différentes refusées |

Pour chaque ajout : préciser s'il est nécessaire à l'acceptation ou amélioration
mesurée, son responsable applicatif, le test minimal et le résultat. Les gains
de performance se mesurent sur le parcours concerné ; aucune optimisation sans
signal ni nouvelle dépendance seulement « pour plus tard ».

## 13. Définition de terminé

- [ ] TC0–TC12 réalisés dans le périmètre courant et améliorations obligatoires
  closes ; validations mobiles non exécutables reportées explicitement en §14
  selon la décision du propriétaire, sans les cocher comme réussies.
- [ ] Transfers utilisable depuis le Web, modes réellement annoncés fonctionnels,
  S3/NAS/Docs reliés, mail LAN et cycle expiration/révocation/purge cohérents.
- [ ] Synapse/MAS/Element Web opérationnels avec People/ST, mêmes règles via un
  autre client Matrix, chiffrement natif, quotas et révocation mesurée.
- [ ] Meet, Calendars, Projects, Drive/Docs et Transfers intégrés selon §7, avec
  autorisation dans chaque application et UI humaine vérifiée.
- [ ] Code/configuration Android et iOS complets, contrôles/builds accessibles
  effectués et défauts connus corrigés ; tests sur simulateur/émulateur si
  disponibles. Signature/distribution et recette physique différées si nécessaire.
  Clôture autorisée : « serveur/web livrés, code mobile préparé ; recette mobile
  différée », avec résultats précis et checklist de reprise conservée.
- [ ] Sauvegarde et restauration isolée validées, services existants conservés,
  données temporaires et droits de recette nettoyés.
- [ ] Code/configuration non secrète/docs poussés sur tous les forks Apoze
  concernés ; SHAs et branches distantes vérifiés, aucune écriture upstream.
- [ ] Roadmap, guides d'exploitation et rapport de validation reflètent l'état
  réellement livré, avec limites LAN et options différées toujours visibles.

## 14. Recette mobile différée — à reprendre ultérieurement

Cette checklist conserve le travail de validation autorisé à être reporté.
Elle ne bloque pas la livraison du périmètre courant. Au terme de l'implémentation,
indiquer pour chaque ligne ce qui a été testé sur environnement virtuel, le SHA,
les outils manquants et la prochaine action. Ne pas qualifier un test non exécuté
de réussi et ne pas relancer automatiquement une campagne sur appareils.

- [ ] Compléter les builds non exécutés faute d'outils ; préparer/valider la
  signature pour installation physique avec les moyens Apoze disponibles.
- [ ] Installer sur un Android et un iPhone ; connexion MAS/IdP, liens de retour,
  messages/fichiers, partage système, Drive/Transfers et ouverture de Meet.
- [ ] Vérifier récupération des clés et historique entre Web, Android et iOS,
  reprise hors ligne, déconnexion et révocation d'accès.
- [ ] Vérifier micro/caméra, clavier, orientation, permissions et cycle réel de
  mise en arrière-plan sur les deux OS.
- [ ] Configurer les credentials push manquants, puis vérifier la remise APNs/FCM
  réelle, interaction, silence et révocation. Une simulation locale antérieure
  n'acquitte pas cette étape.
- [ ] Nettoyer données/appareils/pushers de recette, publier les corrections
  éventuelles sur Apoze et mettre à jour le statut de validation mobile.

- I21 (TC3) : administration native non protégée contre les mutations brutes ;
  écrans désormais en lecture seule et opérations avec aperçu signé, contrôle
  du responsable et budget à la confirmation. Recette HTTP réelle passée.
- I22 (TC2/TC3) : STATIC_ROOT de l’image ne correspondait pas au runtime ;
  chemin par défaut aligné. Les pages natives d’administration répondent.
- I23 (TC2/TC3) : accès direct aux routes SPA servi avec statut 404 ;
  réponse HTML corrigée en 200, ressources absentes conservées en 404.
  Référence : https://caddyserver.com/docs/caddyfile/directives/file_server
- I24 (TC3, nécessaire) : le S3 partagé était limité à 32 volumes de 1 Gio,
  ce qui interrompait le transfert maximal vers 12 Gio. Configuration native
  d'allocation automatique et réserve de disque de 5 % dans le Compose Docs,
  sans changement d'image, de données ou de credentials. Recette réelle de
  20 Gio : upload, téléchargement, digest et suppression réussis en 165,3 s.
  Budgets temporaires utilisateur/organisation remis à 20 Go après la recette.
- TC4 en développement : source privée observée et lectures de 25 Mio,
  journal des parties pour reprise serveur, chemin confidentiel côté navigateur.
  Ces changements ne sont pas encore déployés ni qualifiés. Les lots chat et
  mobile restent à faire ; aucune clôture globale ni publication annoncée.

- I25 (TC4, corrigé, recette en cours) : après approbation People, la reprise
  OIDC perdait la destination du sélecteur. Le paquet identité 0.1.5 conserve
  la destination validée ; retour réel au sélecteur Drive réussi.
- I26 (TC4, nécessaire) : une réponse 401 rechargeait Transfers et perdait
  le brouillon et sa clé. Reconnexion dans une fenêtre dédiée, même compte
  obligatoire, conservation du brouillon, rejeu unique de la requête refusée ;
  code réalisé, recette navigateur en cours.
- I27 (TC4, corrigé, contrôle visuel à finaliser) : navigation et pied du
  sélecteur débordaient. Mise en page flex bornée et boutons natifs regroupés.

Preuves TC4 supplémentaires : copies privées S3 et NAS de 32 Mio, standard
serveur et confidentiel client, empreinte vérifiée ; source NAS modifiée
refusée ; reprise après arrêt du processus worker conservant la première
partie multipart déjà enregistrée. Aucun lien public créé dans Drive.
Le retour Transfers vers Drive reste à réaliser ; aucun lot Chat livré.

- I28 (TC4, conception retenue) : le retour confidentiel déchiffre dans le
  navigateur et transmet des blocs bornés à Drive. Admission et journal Drive,
  spool privé persistant borné, puis publication par le moteur natif S3/NAS ;
  aucun nouveau moteur de stockage et aucune clé de déchiffrement serveur.
  La validation doit couvrir reprise, collision, annulation et nettoyage.

- I29 (TC2/TC4, corrigé, validation en cours) : l’ordonnanceur ST est sorti
  après une panne DNS Docker transitoire le 10 septembre à 23:50 UTC. Le
  worker et beat de développement n’avaient pas de politique de redémarrage.
  Ajout de `restart: unless-stopped`, appliqué aux conteneurs existants ;
  résolution DNS vérifiée, reprise des décisions fraîches à mesurer. Aucun
  allongement des baux d’autorisation.

- I30 (TC4, corrigé, recette en cours) : `fetchAPI` remplaçait le signal
  d’annulation du demandeur lorsqu’un timeout était configuré. Le contrôleur
  transmet désormais aussi l’annulation explicite et retire son écouteur.
  La copie par blocs doit confirmer ce comportement au navigateur.

Le retour Drive côté API a passé la recette réelle S3 32 Mio, NAS 32 Mio et
fichier vide, avec rejeu des blocs, digest final et suppression du spool.
Le branchement navigateur chiffré est en cours, pas encore qualifié.

- I31 (TC4, corrigé et validé) : les contrôles de plage S3 étaient masqués
  par CORS ; le proxy expose maintenant Content-Range et ETag. Les en-têtes
  de blocs Drive sont autorisés entre les origines déjà enregistrées.
- I32 (TC4, corrigé, contrôle final en cours) : un lien de téléchargement
  public pouvait imposer une reconnexion après expiration d’un ancien cookie.
  Le client rejoue une seule fois après suppression de cette session ; toutes
  les vérifications du lien et de son propriétaire restent côté serveur.
- I33 (TC4, corrigé) : les erreurs API transitoires du moteur de copie étaient
  classées définitives. Les statuts 5xx, 408 et 429 conservent la reprise ;
  les droits de la copie entrante sont revérifiés avant publication.

11 septembre — retour confidentiel navigateur → Drive S3 32 Mio validé,
empreinte identique ; export PDF Docs privé valide (1 285 octets) ;
collision et annulation vérifiées avec conservation de l’original et
suppression du spool. Les choix du dossier et du nom restent en session
pour reprendre une authentification Drive sans transmettre la clé.

- I34 (TC4, corrigé, recette en cours) : un 401 entre le chargement du
  compte Drive et celui des espaces quittait le SDK. Le sélecteur relance
  maintenant une seule authentification native avec la demande originale.
  Les outils de débogage ne recouvrent plus les boutons des vues SDK.

- I35 (TC4, corrigé et validé) : les actions natives de copie/suppression
  apparaissaient dans la barre du sélecteur. Le sélecteur conserve uniquement
  sa sélection ; le bouton des choix mixtes indique une copie, pas seulement PDF.
- Recette finale TC4 : sélection S3 + Docs PDF simultanée et reconnexion
  Transfers sans perte des deux fichiers réussies ; retour S3/NAS/vide rejoué
  après les derniers correctifs, empreintes et nettoyage du spool confirmés.

11 septembre — fondation Chat réellement exercée sur `chat-qa.invalid` :
deux connexions approuvées People, invitation privée, échange chiffré
aller-retour et révocation ST en 22,6 s. Les sessions MAS OAuth/navigateur
sont terminées ; le domaine permanent et les autres lots restent ouverts.

- I36 (TC5, corrigé en recette) : contrôles post-sync sans réaffecter le
  requester natif ; callback OAuth exact, PKCE et découverte LAN épinglée.
- I37 (TC5, en cours) : distinguer demande People en attente, droit refusé
  et panne d'autorité dans les erreurs natives MAS ; ne pas tout exposer en 500.
- I38 (TC5, en cours) : réutiliser le jeton machine MAS jusqu'à son expiration
  pour éviter une nouvelle session administrative toutes les 30 secondes.
- I39 (TC5, à qualifier) : réserver les médias avant leur écriture native,
  conserver les réservations lors d'une interruption et n'acquitter la purge
  qu'après disparition effective des fichiers. Limites ST, fichiers chiffrés,
  uploads synchrones/asynchrones et compteurs visibles doivent être cohérents.
- I40 (TC5, en cours) : les corps HTTP temporaires précèdent l'admission
  applicative native Synapse. Les borner dans un tmpfs privé de 384 Mio,
  compté comme réserve opérationnelle d'instance, et limiter à deux uploads
  simultanés. Les quotas utilisateur/organisation portent sur les médias et
  réservations attribués après authentification ; aucun temporaire anonyme
  n'est attribué arbitrairement à un utilisateur. Préserver les miniatures
  natives, en réservant leurs octets réels avant chaque écriture.

### I41 — Révocation d’une liaison OIDC modifiée

Une liaison conserve parfois son UUID après correction du couple issuer/sub.
Comparer aussi l’empreinte du couple pour terminer les sessions natives MAS
associées à l’ancienne identité. Migration du journal de recette : les anciennes
entrées contenant seulement l’UUID provoquent une déconnexion conservatrice.
État : implémenté ; migration réelle du journal, fin des sessions MAS et refus
du jeton antérieur vérifiés avant publication Chat.

### Précision de recette des propriétaires

Le refus de départ du dernier propriétaire actif est vérifié. La restauration
par rétrogradation d’un autre propriétaire de même niveau est refusée par la
règle Matrix native. Le second propriétaire de recette reste temporairement
présent ; le nettoyage final doit passer par sa propre session ou supprimer le
salon de recette. Aucun droit d’un utilisateur réel n’a été modifié.
