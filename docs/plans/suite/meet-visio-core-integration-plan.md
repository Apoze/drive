# Meet / Visio — intégration du cœur de visioconférence à la suite Apoze

Date : 8 septembre 2026.
Statut : **exécuté et livré sur le LAN le 8 septembre 2026**.
[Validation finale](../../../output/implementation/meet-visio-core-integration/validation-final.md) ·
[Exploitation](../../operations/suite-meet-visio.md).
Périmètre : visioconférence uniquement, sans enregistrement ni traitement IA.
Dépôt livré : [Apoze/meet](https://github.com/Apoze/meet), branche `main`,
commit `9a3d588907e94d725ebf24576156c141e90892fd`.

Ce plan est autonome pour conduire le chantier jusqu’à sa livraison. Sa
rédaction n’autorise pas à lancer le déploiement. Le chantier
[Grist reste en pause](../paused/suite/grist-community-integration-plan.md) ;
aucun lot de ce document n’en autorise la reprise.

## 1. Résultat attendu

Depuis le catalogue de la suite, une personne autorisée ouvre Visio, retrouve
son compte, crée une réunion, invite des participants et utilise caméra,
microphone, partage d’écran et chat. L’organisateur administre la réunion
depuis le Web. Les droits People/ST restent effectifs pendant l’appel et à
la reconnexion. Le tout fonctionne sur le serveur Docker actuel, avec une
installation persistante, des versions figées et une procédure de restauration.

### 1.1 Inclus

- Audio et vidéo entre navigateurs, sélection des périphériques, mute/unmute,
  affichage des participants et dispositions natives de Meet.
- Partage d’écran natif ; partage du son lorsque le navigateur le permet.
- Chat de réunion natif, non persistant côté application ; il ne remplace pas
  une messagerie et ne produit pas d’archive.
- Création, consultation, modification et suppression des réunions ; liens
  d’invitation, salle d’attente, admission, expulsion et rôles natifs.
- Connexion OIDC directe au même IdP que la suite, configurable sans logique
  dépendant de Keycloak ; preuve ciblée avec Authentik isolé.
- Identité durable et groupes People, politiques d’application et catalogue
  ST, droits sur les réunions dans Meet.
- HTTPS/WSS, transport WebRTC réel, réseau local et repli réseau documenté.
- Paramétrage courant depuis ST, People ou Meet ; paramètres d’exploitation
  Docker/DNS/TLS et secrets dans la configuration privée du serveur.

### 1.2 Exclus et effectivement désactivés

Enregistrement audio/vidéo, transcription, résumés, sous-titres automatiques,
Dictaphone, WhisperX, Moshi, agents IA, téléphonie/SIP, Roomkit, diffusion et
import de flux, intégrations agenda/add-ons, fichiers et fonds personnalisés
téléversés, export vers Drive/Docs et chiffrement de bout en bout expérimental.
Ne pas ajouter des fonctionnalités d’effets vidéo à ce chantier.

Ne déployer ni LiveKit Egress/Ingress, ni workers Summary, ni moteur IA, ni
stockage S3 Meet. La présence de modules optionnels dans les sources natives
n’impose pas de les supprimer : empêcher leur activation et leur accès côté
serveur. Le transport WebRTC chiffré reste natif ; il ne doit pas être présenté
comme du chiffrement de bout en bout entre participants.

Les sauvegardes concernent les comptes, réunions, ACL et configurations. Elles
ne contiennent pas d’enregistrement d’appel. Aucun quota de fichiers, nouvelle
couche de stockage ou facturation par minute n’est ajouté.

### 1.3 Choix d’usage explicites

| Sujet | Décision de travail |
| --- | --- |
| Réseau cible initial | LAN existant. Réutiliser un accès VPN/reverse proxy déjà établi si disponible. Ne pas ouvrir Internet ou le routeur implicitement. |
| Organisation | Une organisation configurée, celle déjà reliée à ST/People. |
| Création de réunion | Utilisateur identifié et autorisé par ST. Aucune création anonyme ou automatique d’une salle depuis un slug inconnu. |
| Salle par défaut | Mode natif `restricted`, avec admission par un organisateur ; ne pas reprendre le défaut `public` de l’exemple officiel. |
| Groupes | People fait autorité. ST décide de l’accès à Meet ; Meet décide des rôles dans une réunion. |
| Invités sans compte | Choix confirmé par l’utilisateur : lien et admission explicite par l’organisateur. Inclure ce mode et son scénario de validation dans la livraison. |
| Charge | Petit usage homelab ; relever la capacité observée. Ne pas promettre 100 participants sur ce serveur. |
| Publication | Code spécifique dans les forks Apoze ; aucune action vers les dépôts officiels. |

Le choix des invités sans compte a été confirmé après la présentation du plan :
invités admis individuellement, jamais réunion ouverte sans contrôle.
L’exécution complète a ensuite été explicitement demandée. Son état réel est
conservé dans le [suivi](../../../output/implementation/meet-visio-core-integration/current-status.md).

## 2. État inspecté et sources

### 2.1 Socle local à préserver

Les 36 conteneurs existants étaient actifs lors de la préparation. Aucun
Meet applicatif n’est déployé par ce travail. La présence de conteneurs actifs
n’est pas une nouvelle preuve fonctionnelle de Drive ou Docs.

| Élément | État utile pour l’intégration |
| --- | --- |
| Drive | Fork `/root/Apoze/drive`, UI LAN port 3000, API 8071 ; espaces NAS/S3 et quotas existants à préserver. |
| ST | `/root/Apoze/st-deploycenter`, UI 8960, API 8961 ; politiques et catalogue disponibles. |
| People | `/root/Apoze/people`, UI 3001, API 8072 ; personnes, groupes, bindings IdP et consommateurs disponibles. |
| Docs | `/root/Apoze/docs`, UI 3002, API 8073 ; identité et catalogue déjà intégrés. |
| IdP actuel | Issuer exact `http://192.168.10.123:8083/realms/drive`. Les clients existants restent inchangés. |
| Organisation | `a9caecae-4ba5-41f7-b447-58049718cbbd`. |
| Bibliothèque commune | `src/packages/suite-identity/` dans Drive ; wheel native `apoze-suite-identity` 0.1.0, Python ≥ 3.13. |
| Données privées | `data/suite-local/` dans Drive et emplacements documentés dans le guide d’installation ; ne pas en publier le contenu. |
| Grist | Travail non livré en pause ; checkout, images, branches et sauvegardes ne sont pas des dépendances de Meet. |

Lire avant exécution :

- [ADR de l’identité durable](../../adr/0003-suite-durable-identity-and-access.md).
- [Installation actuelle](../../installation/suite-identity-and-docs.md).
- [Exploitation, révocation et récupération](../../operations/suite-identity-access.md).
- [Plan du socle livré](identity-access-catalogue-docs-plan.md), seulement les
  contrats nécessaires ; ne pas réexécuter le chantier déjà livré.
- [Environnement local](../../env_freeze_report.md) et instructions de chaque
  dépôt effectivement modifié.

Les modifications préexistantes des dépôts locaux ne sont pas celles de Meet.
Les sauvegarder et ne jamais les écraser pour obtenir un arbre Git propre.
`run_env_local.sh` reste réservé à Drive ; ST conserve son démarrage séparé.

### 2.2 Référence officielle étudiée

Référence de préparation : **Meet v1.31.0**, release stable publiée le
8 septembre 2026, commit **`7565ede0a7b5a8f4b8534cec853f0328e98e867d`**.
Ne pas utiliser implicitement `main` ou `latest` au moment de construire.

Le backend utilise Django 5.2.16, Python ≥ 3.13, django-lasuite 0.0.27,
mozilla-django-oidc 5.0.2 et Celery 5.6.3. Le frontend est React/Vite ; ce
n’est pas le frontend Next.js de Drive. Les dépendances natives sont déjà
compatibles en principe avec notre paquet commun, à vérifier par résolution
des locks et un login réel.

Le Dockerfile LiveKit du tag référence v1.13.6. Le considérer comme candidat,
pas comme une image déjà qualifiée. L’exemple Compose officiel reste annoncé
expérimental et contient des images flottantes : livrer une recette Apoze
figée et vérifiée, sans installer les options expérimentales du produit.

Sources de référence :

- [Release Meet v1.31.0](https://github.com/suitenumerique/meet/releases/tag/v1.31.0).
- [Backend et dépendances](https://github.com/suitenumerique/meet/blob/v1.31.0/src/backend/pyproject.toml).
- [Installation Compose](https://github.com/suitenumerique/meet/blob/v1.31.0/docs/installation/compose.md).
- [Authentification](https://github.com/suitenumerique/meet/blob/v1.31.0/docs/features/authentication.md).
- [Configuration serveur](https://github.com/suitenumerique/meet/blob/v1.31.0/src/backend/meet/settings.py).

### 2.3 Écarts concrets imposant des adaptations

1. Le login natif s’appuie sur `User.sub` et peut créer un compte ou rapprocher
   un email. Réutiliser nos associations People avant cette résolution.
2. Les jetons LiveKit et leur authentification HTTP réutilisent actuellement
   `user.sub`. Certains chemins de modération supposent un identifiant UUID.
   Un subject IdP opaque et changeant ne doit devenir ni clé de propriété ni
   identité transport permanente.
3. Les `ResourceAccess` des salles portent des utilisateurs. Les groupes
   People exigent un raccord d’ACL spécifique ; les groupes Django projetés
   seuls ne confèrent aucun droit de réunion.
4. Les routes natives permettent la lecture anonyme et, dans certains cas,
   un jeton pour une salle non enregistrée. Les chemins invités et diagnostics
   doivent être explicitement bornés par notre politique.
5. Les flags protègent plusieurs actions optionnelles, mais des routeurs
   `recordings`, `files`, `roomkit` et `addons` sont enregistrés séparément.
   Vérifier la fermeture de tout leur périmètre, pas seulement du bouton.
6. Expulser un participant LiveKit auto-hébergé ne révoque pas nécessairement
   son jeton ; LiveKit peut aussi renouveler les jetons pendant un appel.
   Un TTL court seul ne garantit donc pas notre révocation commune.

Sources des points d’entrée :
[auth backend](https://github.com/suitenumerique/meet/blob/v1.31.0/src/backend/core/authentication/backends.py),
[auth LiveKit](https://github.com/suitenumerique/meet/blob/v1.31.0/src/backend/core/authentication/livekit.py),
[jetons](https://github.com/suitenumerique/meet/blob/v1.31.0/src/backend/core/utils.py),
[modèles](https://github.com/suitenumerique/meet/blob/v1.31.0/src/backend/core/models.py),
[rôles](https://github.com/suitenumerique/meet/blob/v1.31.0/src/backend/core/services/room_roles.py),
[viewsets](https://github.com/suitenumerique/meet/blob/v1.31.0/src/backend/core/api/viewsets.py),
[routes](https://github.com/suitenumerique/meet/blob/v1.31.0/src/backend/core/urls.py),
[cycle des jetons LiveKit](https://docs.livekit.io/frontends/reference/tokens-grants/).

## 3. Architecture de livraison

### 3.1 Services et données

| Service | Choix prévu |
| --- | --- |
| Web Meet | Frontend compilé et proxy HTTPS ; API sur la même origine pour limiter les problèmes cookies/CORS. |
| Backend Meet | Image du fork Apoze, configuration de production, migrations natives et paquet d’identité intégré au build. |
| Tâches | Worker et beat Celery natifs, une petite concurrence ; synchronisation People/ST et contrôle des participants. Aucune file Summary/IA. |
| PostgreSQL | Réutiliser le serveur partagé compatible avec une base et un rôle Meet dédiés ; ne pas redémarrer les autres bases pour cette création. |
| Redis | Instance dédiée à Meet/LiveKit recommandée pour isoler les présences, le broker et les clés transport. Préfixes/bases logiques séparés selon les clients natifs. |
| LiveKit | Serveur SFU auto-hébergé figé, API de contrôle privée, signalisation WSS via proxy contrôlé, ports médias explicitement exposés. |
| TURN | Fonction native de connectivité, pas une option IA. Activer le TURN intégré si nécessaire pour les réseaux retenus ; aucun compte LiveKit Cloud. |
| SMTP | Réutiliser un service existant seulement si l’envoi d’invitations est retenu et réellement livré ; copier un lien ne dépend pas du mail. |
| Stockage | Base et configuration persistantes uniquement ; pas de bucket, volume NAS ou credentials S3 pour Meet dans ce périmètre. |

Fichiers de livraison à conserver dans le fork Meet : Compose autonome,
exemples d’environnement sans secrets, configuration proxy/LiveKit, commande
de préparation idempotente, commandes d’exploitation et documentation.
Employer un projet Compose dédié, par exemple `suite-meet`, relié aux seuls
réseaux nécessaires. Aucun montage de sources depuis `tmp/` sur le runtime.

Les wheels vendorizées doivent être reproductibles, accompagnées de leur
source/version/checksum et accessibles depuis le dépôt Apoze correspondant.
Ne pas transformer le serveur Drive actif en serveur de packages. Adapter
`docker/suite/package_identity.py` pour cibler Meet sans réécrire les quatre
locks existants si leur paquet ne change pas. Aucune duplication manuelle
d’une seconde implémentation de l’identité en Python.

### 3.2 Origines, TLS et réseau

**Le HTTP sur l’IP LAN ne suffit pas pour la caméra/le micro.** Retenir une
origine HTTPS de confiance sur les postes clients, ainsi qu’une origine WSS
pour LiveKit. Les permissions navigateur ne se contournent pas par des flags
« unsafe origin », une exemption Playwright ou `ignoreHTTPSErrors` en recette.
[Contexte sécurisé navigateur](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia).

Lors du relevé initial, rechercher DNS/proxy/certificats déjà utilisés. Choisir
ensuite les noms Meet et LiveKit, leurs certificats et les callbacks exacts.
Préférence : domaine contrôlé avec certificat publiquement reconnu, y compris
via validation DNS pour un usage LAN. À défaut, une autorité locale explicitement
installée comme fiable sur les postes ; sa distribution côté client reste
une action à vérifier, pas une confiance acquise depuis le serveur.

Conserver l’issuer existant pour le raccord LAN initial. La redirection de
navigation vers son HTTP de développement est à distinguer du média ou fetch
HTTP depuis une page HTTPS, qui serait bloqué. Vérifier le retour OIDC, les
cookies Secure et SameSite. Ne pas changer le hostname/issuer de Keycloak pour
mettre Meet en HTTPS ; une exposition Internet exigera aussi un IdP adapté.

| Flux | Règle |
| --- | --- |
| Navigateur → Meet | HTTPS, certificat reconnu, API same-origin, cookies propres à Meet. |
| Navigateur → LiveKit | WSS, toutes les routes d’établissement/reprise passent par le contrôle d’admission. |
| WebRTC | UDP multiplexé 7882 et repli ICE/TCP 7881 comme point de départ, après vérification des conflits et de l’adresse annoncée. |
| TURN | Ports et certificat du relais définis selon le réseau réel ; ne pas confondre TURN/TLS et une route HTTP Nginx. |
| LiveKit → Meet | Webhooks signés, endpoint interne accessible sans session humaine. |
| Meet → People/ST/IdP | Routes serveur privées ou LAN existantes, délais bornés et clés distinctes. |
| Administration LiveKit, PostgreSQL, Redis | Aucun endpoint de contrôle accessible aux navigateurs ou à Internet. |

Ne pas annoncer une IP Docker privée aux clients LAN. Ne pas activer
`use_external_ip` aveuglément : choisir les candidats ICE selon LAN, VPN ou
NAT réel. Un proxy HTTP ne transporte pas à lui seul les médias UDP.

Si TURN/TLS doit utiliser 443 déjà occupé par HTTPS, choisir une architecture
compatible : adresse distincte ou routage TLS de niveau 4 réellement pris en
charge. Ne pas copier une configuration où deux services prétendent écouter
le même socket. Le réseau hôte pour LiveKit est une possibilité native à
retenir seulement avec des binds privés corrects ; un mapping explicite de
ports reste acceptable si la recette média et les mesures le valident.
[Déploiement LiveKit](https://docs.livekit.io/transport/self-hosting/deployment/),
[ports et pare-feu](https://docs.livekit.io/transport/self-hosting/ports-firewall/).

Les domaines, la confiance TLS des postes, l’accès à un éventuel DNS/routeur
et la disponibilité d’un second appareil sont des dépendances réelles. Les
documenter et demander seulement les informations introuvables au moment
utile. Ne pas déclarer la recette distante complète avec deux pages localhost.

## 4. Identité, groupes et droits

### 4.1 Réutiliser le socle existant

1. Ajouter `SUITE_APP_ID=meet`, l’organisation et les endpoints People/ST,
   avec un consommateur People et un service/souscription ST distincts.
2. Intégrer `SuiteSettings`, middleware, mixin OIDC, authentification API,
   URLs catalogue/logout et tâches du paquet partagé dans les points natifs.
3. Ajouter les migrations additives sans remplacer les PK Meet ; conserver
   séparément UUID utilisateur local, principal People et identité externe.
4. Fournir à Meet une projection compatible de `full_name`, `short_name` et
   email facultatif. Ne pas supposer qu’un `sub` est un UUID, ni inventer un
   email pour satisfaire un formulaire. Aucun privilège issu d’une claim libre.
5. Associer `(issuer, subject, client Meet)` sur preuve vérifiée. Un login
   inconnu déclenche une demande People ; aucun rapprochement par email et
   aucune autorisation avant approbation.
6. Garder les leases du socle : synchronisation 30 s, fraîcheur positive 90 s,
   preuve humaine maximale 900 s, révocation d’exploitation ≤ 120 s.
7. Les associations de groupes utilisent leurs UUID People. Les imports SCIM
   continuent à passer par People, jamais directement de l’IdP vers les ACL.

Client OIDC dédié proposé : `apoze-meet`. Authorization Code, PKCE S256,
nonce/state, discovery et issuer exact, vérifications de signature/audience/
temps, `auth_time` et `max_age=900`, callbacks et retours de logout exacts.
Désactiver l’auto-création et le fallback email des backends natifs. Utiliser
les noms de variables réellement présents dans v1.31.0, sans recopier une
configuration ProConnect obligatoire. Les claims signés UserInfo et les
subjects pairwise restent compatibles avec le contrat existant.

Le mode suite activé doit échouer fermé si ses clés/URLs sont incohérentes.
Un oubli de configuration ne doit pas réactiver le login natif permissif.
Le compte local de secours ouvre l’administration restreinte, pas les appels
ou API utilisateur. Les clés de lecture People, de mutation/logout, de ST,
du client OIDC et de LiveKit restent distinctes et ne sont jamais exposées.

### 4.2 Autorité et permissions des salles

| Acteur / décision | Autorité |
| --- | --- |
| Authentifier une personne | IdP configuré. |
| Identité durable, groupes, suspension | People. |
| Utiliser Meet et apparaître dans le catalogue | Politique ST active, avec priorité des refus. |
| Créer une réunion | Personne identifiée, active, autorisée à Meet. |
| Propriétaire / coorganisateur | Attribution explicite dans Meet ; aucun admin People/ST implicitement propriétaire. |
| Accès direct d’un groupe à une salle | Attribution explicite dans Meet à un UUID People publié. |
| Invité sans compte | Admission locale dans cette réunion ; aucun compte People/ST ni accès au reste de la suite. |

Conserver `Resource`, `Room`, `ResourceAccess`, le lobby et les services natifs.
Ajouter seulement l’association de groupe aux ressources qui manque, reliée
aux groupes People projetés, avec contrainte d’unicité. Rôles de groupe :
membre ou coorganisateur ; conserver une propriété individuelle explicite.

Centraliser la résolution du rôle effectif dans les accès de ressource, puis
l’utiliser dans listes, détail, lobby, tokens, mutations et modération. Éviter
de recopier les membres d’un groupe en grants individuels permanents : un
retrait People doit retirer la contribution du groupe aux droits. Un autre
grant individuel ou de groupe toujours valide continue d’accorder son rôle.

Les listes et sélecteurs sont filtrés par organisation, publication People et
droits de l’acteur. Interdire groupes arbitraires, attributs `is_staff` fournis
par le navigateur et contournements via les API de `ResourceAccess`. Protéger
le dernier propriétaire contre suppression/déclassement concurrents au niveau
de la transaction parent ; une suspension de sécurité reste prioritaire.

Une révocation d’accès à Meet l’emporte sur la propriété d’une réunion.
L’expulsion locale invalide l’admission de la session visée : un vieux jeton
ne permet pas de revenir. Une nouvelle admission par l’organisateur, si elle
reste permise, doit créer une autorisation distincte et traçable.

### 4.3 Invités et réunions par lien

Si le mode invités est retenu :

- N’autoriser que le lobby d’une réunion persistante existante, avec une
  référence difficile à deviner ; une URL inconnue ne crée ni salle ni jeton.
- Donner avant admission le minimum d’informations nécessaire et aucun média,
  historique de chat, liste complète de participants ou privilège de gestion.
- Réutiliser les cookies de lobby et les throttles natifs ; ne pas accepter
  comme preuve une simple valeur UUID de cookie fournie par le client.
- L’admission exige un organisateur actuellement autorisé. La lier à une
  session invitée aléatoire, à la salle et à une durée maximale explicite.
- Aucun invité ne devient coorganisateur ou administrateur de la suite par
  son nom affiché. Le distinguer visuellement d’un utilisateur identifié.
- Expulsion, fermeture de salle et retrait de l’admission bloquent la reprise.
  Le départ du créateur ne termine pas arbitrairement un appel valide ; prévoir
  une fin de réunion explicite qui invalide toutes ses admissions temporaires.
- Une personne anonyme ne peut être identifiée comme un compte People suspendu.
  Si cette interdiction nominative est requise, utiliser le mode authentifié
  uniquement. Ne pas prétendre résoudre cela par fingerprint/IP/email saisi.

## 5. Autorisation des connexions et des appels en cours

### 5.1 Adaptation minimale nécessaire

Le contrôle Django lors de l’émission du JWT ne couvre pas une connexion
directe au SFU avec un JWT conservé ou renouvelé. La solution retenue combine
les services natifs de modération avec une vérification d’admission au proxy,
sans fork du moteur LiveKit ni passerelle média développée sur mesure.

Créer un enregistrement temporaire d’admission, indexé par identité transport
opaque, relié à une salle et à un utilisateur ou invité. Y conserver seulement
les données nécessaires : preuve/epoch, limites temporelles, statut révoqué,
origine de l’admission et permissions effectives. Ne jamais stocker le JWT
en clair comme identifiant métier. Prévoir purge bornée et expiration réelle.

L’identité LiveKit doit permettre de distinguer deux sessions et un ancien
login d’un nouveau. Préférer un UUID par admission, stable pendant sa reprise,
à l’email, au subject IdP ou à un `User.id` réutilisé sans epoch. Adapter les
résolutions natives `identity → user` et la modération à ce mapping ; les PK
et propriétaires de salles restent stables. Ne pas laisser un ancien jeton
profiter de la nouvelle admission d’une même personne.

### 5.2 Émission, handshake et reconnexion

1. Le backend vérifie compte, preuve, politique ST, droit de salle/lobby et
   état d’admission avant tout jeton ; durée bornée par ces autorisations.
2. Les grants du navigateur couvrent la salle et les médias nécessaires.
   **Pas de `roomAdmin` transport dans le navigateur** : les actions
   organisateur passent par Django, qui emploie ses credentials serveur.
   Auditer aussi publication de données, metadata et permissions modifiables.
3. Toutes les routes d’établissement LiveKit, dont `/rtc`, `/rtc/v1` et leurs
   variantes `/validate` à la version retenue, passent par un `auth_request`
   Nginx interne vers Meet, ou le mécanisme natif équivalent du proxy existant.
4. Ce contrôle vérifie cryptographiquement le JWT, son issuer LiveKit et sa
   salle, retrouve l’admission, puis relit la décision locale actuelle.
   Les jetons renouvelés par LiveKit passent par le même contrôle ; la nouvelle
   date JWT ne prolonge pas la preuve ou l’admission enregistrée dans Meet.
5. L’API de contrôle SFU et tout accès direct à 7880 sont privés. Couvrir les
   headers Bearer et les paramètres utilisés par le SDK exact sans double
   interprétation ambiguë. Ne pas journaliser les query strings des connexions.
6. Les métadonnées de rôle envoyées à LiveKit sont une projection d’affichage,
   pas une nouvelle autorité. Le proxy ne décide pas seul à partir de celles-ci.

Qualifier ces points avec le SDK/browser réellement livré, y compris une
reconnexion avec un jeton reçu du SFU. Si un chemin natif échappe au contrôle,
le fermer ou le corriger avant activation ; ne pas conclure sur le seul TTL.

### 5.3 Révocation pendant l’appel et renouvellement

Les tâches natives réévaluent les admissions et participants actifs par lots,
avec un cycle visé de 10 s, délai d’appel borné et exclusion des exécutions
concurrentes. Utiliser la projection locale fraîche ; aucun appel People/ST
par trame, par paquet média ou par message chat. Les webhooks signés accélèrent
le suivi, mais une réconciliation périodique couvre leur perte et les reprises.

Après retrait/suspension/epoch changé, retirer le participant via LiveKit et
invalider l’admission. Après changement de rôle, recalculer les permissions et
forcer une nouvelle admission si nécessaire pour éviter d’anciens grants.
Les appels externes échoués restent à retenter avec une échéance explicite,
pas un simple succès « best effort » affiché à l’organisateur.

L’objectif mesuré est **120 s maximum** après révocation commune, et **15 s**
après une expulsion locale avec contrôle opérationnel. Une projection People
ou ST trop vieille ferme les admissions et les participants concernés ; elle
ne renouvelle pas une décision positive. L’indisponibilité est visible.

Prévoir le cas où le contrôleur lui-même s’arrête alors que le SFU transmet
encore : publier un signal de contrôle terminé et frais, surveillé au niveau
du lancement LiveKit. Un garde local minimal arrête le processus LiveKit si
la surveillance est périmée au-delà de la borne ; aucun accès Docker socket.
La procédure de démarrage doit prévoir une amorce bornée, sans dépendance
circulaire entre signal de santé et SFU déjà lancé. Un simple healthcheck
Docker qui devient rouge sans arrêter les médias n’est pas ce mécanisme.
Le signal n’est renouvelé qu’après une passe réussie : un retrait impossible,
un appel de contrôle bloqué ou une boucle seulement vivante ne suffit pas.
Conserver ce contrôle dans le packaging Meet, sans plateforme de supervision
supplémentaire. Tester une interruption ciblée du contrôleur en recette isolée.

Avant expiration de la preuve de 15 minutes, proposer le renouvellement OIDC
et prolonger l’admission seulement sur une nouvelle preuve vérifiée. Une
nouvelle authentification IdP peut être nécessaire ; ne pas allonger la preuve
silencieusement pour préserver un appel. Le renouvellement ne crée ni nouveau
compte ni nouvelle propriété, et ne ressuscite pas une admission révoquée.

La panne complète du serveur ne peut pas être confondue avec une révocation
instantanée garantie en toutes circonstances. Documenter les délais mesurés
et le comportement de fermeture en cas de panne de contrôle ; ne pas déclarer
une coupure de signalisation comme preuve suffisante d’arrêt des médias.

## 6. Interface et fermeture du périmètre

Conserver le style Meet. Ajouter la navigation de suite à son interface native,
alimentée par le catalogue ST filtré. Ne pas réimplémenter le catalogue dans
le navigateur avec une liste fixe ni charger le script public Gaufre comme
autorité. Les autres applications découvrent Meet via leurs consommateurs
déjà en place, sans nouvelle interface dédiée dans Drive.

L’interface doit rendre clairs : association en attente, accès non attribué,
vérification indisponible, fin d’autorisation, expulsion et renouvellement.
Conserver un retour vers la suite sans boucle de login. Les formulaires
utilisent les composants accessibles existants, navigation clavier et labels
français ; aucun redesign.

| Administration courante | Surface |
| --- | --- |
| Activation Meet, règles par personne/groupe, visibilité au catalogue | ST existant. |
| Personnes, groupes, invités devenant des comptes, bindings et révocation | People existant, sans créer automatiquement un compte pour un invité. |
| Salles, personnes/groupes autorisés, propriétaires, coorganisateurs | Meet Web ; compléter le sélecteur de partage si nécessaire. |
| Salle d’attente, admission, mute, retrait, fin de réunion | Meet Web. |
| Accès invité de l’installation et défaut de salle | Administration Meet native restreinte, avec effet serveur ; garder `restricted` par défaut. |
| Santé d’intégration | Page d’administration ou commande native, état et dernière synchronisation sans secrets. |

Configuration de base à figer à `false` : `RECORDING_ENABLE`,
`ROOM_SUBTITLE_ENABLED`, `ROOM_TELEPHONY_ENABLED`, `ROOMKIT_ENABLED`,
`FILE_UPLOAD_ENABLED`, `EXTERNAL_API_ENABLED`, `APPLICATION_ENABLED`,
`ADDONS_ENABLED`. Désactiver les diagnostics qui créent des salles anonymes
(`CONNECTION_TEST_ENABLED`) tant qu’ils n’appartiennent pas au parcours retenu.
Ne pas exposer leurs workers/credentials. Désactiver marketing, télémétrie et
support tiers non configurés ; le fonctionnement du produit n’en dépend pas.

Compléter les guards natifs seulement là où ils manquent, sur listes/détails,
actions de création, URLs de callback et téléchargement. Les endpoints
exclus renvoient un refus cohérent même lorsqu’un client fabrique sa requête.
Ne pas retirer le webhook LiveKit entier : les événements salle/participants
restent utiles. Vérifier signature, type, taille et idempotence des événements,
sans autoriser les traitements Egress/IA désactivés.

## 7. Lots d’exécution

Chaque lot conserve un état de suivi vérifiable. Ne pas commencer par construire
toute la pile puis découvrir les problèmes d’identité ou réseau à la fin.

### M0 — Préserver, inventorier et figer

- Relever services, ports, réseaux, volumes, versions, ressources disponibles,
  branches et modifications locales des seuls dépôts concernés.
- Vérifier DNS/TLS et périmètre LAN/VPN ; récupérer les paramètres manquants
  sans afficher les fichiers privés. Enregistrer le choix invités réellement reçu.
- Sauvegarder les sources non publiées et les configurations/bases que le
  bootstrap modifiera : People, ST, IdP, puis Meet à mesure de sa création.
  Manifeste de checksums et droits 0700/0600 ; aucune purge générale Docker.
- Vérifier l’existence/filiation de `Apoze/meet` avant création, cloner le fork
  et créer la branche locale `codex/meet-visio-core-integration`.
- Figer le tag et l’ascendance choisis. Si la branche copiée dépasse v1.31.0,
  auditer l’écart avant de la retenir ; aucun reset destructeur automatique.
- Neutraliser les pushes vers les dépôts officiels et examiner les workflows
  copiés avant activation : destinations, permissions et tâches planifiées.

**Sortie :** baseline privée, source figée, réseau cible et remotes explicites.
**Contrôle :** lecture d’état et checksums ; aucun test applicatif complet.

### M1 — Construire un Meet minimal et fermer les options

- Recette Compose persistante et indépendante, builds backend/frontend figés,
  LiveKit/PostgreSQL/Redis/proxy épinglés par digest compatible.
- Préparation idempotente des secrets, nouveaux rôles/base, migrations,
  réseaux et healthchecks utiles ; configuration same-origin et HTTPS/WSS.
- Désactivation des fonctions de section 6 à l’UI, aux routes et aux jobs ;
  aucun chargement de modèle/agent ou service S3 pour lancer la visio.
- Isoler la première qualification du LAN public ; vérifier le moteur natif
  avec deux sessions de recette et conserver le résultat, sans en faire une
  seconde suite de tests réutilisant toutes les fixtures Drive.

**Sortie :** images minimales démarrables, stockage persistant de métadonnées,
flux natif de base identifié et endpoints hors périmètre fermés.
**Contrôle :** build, checks Django, quelques appels d’API et un appel de base.

### M2 — Raccorder People, ST et OIDC

- Intégrer la wheel commune et son lock au fork, adapter les points Django
  listés en section 4.1. N’ajouter au paquet partagé que ce qui est réellement
  commun et compatible avec ses consommateurs existants.
- Créer le consommateur `meet` People, publication limitée et service ST
  initialement caché/désactivé pour les utilisateurs ordinaires.
- Client IdP dédié, identité de recette explicitement associée, jobs natifs
  de projection/politique, compte de récupération administratif restreint.
- Traitement Web des refus et de la déconnexion commune ; pas de fallback
  silencieux vers des comptes OIDC non associés.

**Sortie :** compte local stable, login et catalogue filtrés, retrait d’accès
effectif à l’API. **Contrôle :** scénario positif puis refus, et mise à jour
de profil sans changement de PK ; réutiliser les tests communs pertinents.

### M3 — Unifier droits de salles et groupes

- Association de groupes, résolution commune des rôles et sélecteur Web.
- Adaptation des listes, ressources, lobby et modération ; protections du
  dernier propriétaire, cohérence entre grants directs et contributions de groupe.
- Mode restreint par défaut, suppression de l’auto-admission sur salle
  inconnue, invités selon choix retenu et fin explicite d’une réunion.
- Aucun administrateur suite n’obtient implicitement le contenu d’un appel.

**Sortie :** administration Web utilisable et décisions serveur cohérentes.
**Contrôle :** membre, coorganisateur, tiers et retrait d’un groupe ; une
collision concurrente ciblée seulement sur la protection propriétaire ajoutée.

### M4 — Contrôler toute la durée des appels

- Admission temporaire et identité transport opaque, chemin commun de JWT,
  mapping pour les endpoints LiveKit-auth et la modération.
- Proxy d’admission privé, couverture connexion/reconnexion/validation,
  fermeture des accès directs et suppression des grants transport privilégiés.
- Réconciliation périodique bornée, expulsion et retrait de droits, expiration
  des preuves, renouvellement et comportement de panne de contrôle.
- Reprise après redémarrage : réconcilier les admissions et la présence réelle,
  ne pas restaurer un droit expiré à partir d’un cache.

**Sortie :** limites de révocation démontrées avec un vrai SFU auto-hébergé.
**Contrôle :** retrait pendant appel, rejeu du JWT original et d’un JWT
renouvelé, puis panne contrôleur/projection sur l’instance isolée.

### M5 — Finaliser navigation et exploitation

- Retour catalogue dans Meet, liens depuis Drive/Docs/People/ST via le
  catalogue existant ; liens profonds après login sans redirection ouverte.
- Messages utiles de droits et réseau, interface sans fonctions désactivées,
  fonctionnement sans SMTP si seule l’invitation par lien est retenue.
- Commandes dédiées de démarrage/arrêt/sauvegarde/restauration/mise à jour,
  logs sobres avec rotation et diagnostic borné du contrôle média.
- Ressources et limites de simultanéité raisonnables selon l’hôte ; réutiliser
  les limites LiveKit disponibles au lieu d’un moteur de quotas supplémentaire.

**Sortie :** installation opérable depuis ses fichiers durables et son Web.
**Contrôle :** parcours catalogue → réunion → retour et un redémarrage ciblé.

### M6 — Qualifier le second IdP et la restauration

- Instance Meet de recette isolée, mêmes identités locales et mêmes salles.
  Réutiliser le préparateur Authentik déjà disponible, secrets/volumes dédiés.
- Keycloak → Authentik → Keycloak : associations approuvées spécifiques au
  client Meet, aucun rapprochement par email ; conserver UUID et ACL.
- Vérifier un retrait d’accès avec le second IdP et le refus des anciens
  jetons/epochs. Ne pas relancer toute la campagne SCIM du socle si le contrat
  n’a pas changé ; un groupe importé représentatif suffit si disponible.
- Restaurer une petite base Meet sauvegardée dans une cible jetable et
  vérifier salle, propriétaire et droit de groupe. Les admissions et sessions
  transport restaurées restent invalides ; elles doivent être redemandées.

**Sortie :** indépendance IdP et restauration concrètement prouvées.
**Contrôle :** scénarios ciblés, aucune bascule des quatre applications LAN.

### M7 — Activer le LAN et faire la recette finale

- Actualiser la sauvegarde des éléments modifiés, confirmer la confiance TLS
  des postes et démarrer seulement les services Meet nécessaires.
- Activer la souscription/politique et la vignette ST pour le groupe retenu.
- Exécuter les scénarios de section 8 sur le réseau réel, conserver quelques
  preuves sobres et mesurer les délais de révocation et métriques médias.
- Vérifier les services existants et un parcours court Drive/NAS puis Docs.
  Si aucun code de ces parcours n’a changé, ne pas les soumettre à une suite
  complète d’upload/conversion ni refaire les anciens chantiers.
- Supprimer salles, admissions, comptes/clients exclusivement de recette et
  données temporaires ; conserver les comptes réels et la configuration LAN.

**Sortie :** Visio utilisable, environnement conservé et essais nettoyés.

### M8 — Livrer les sources et clôturer

- Écrire les guides et le rapport de validation ; inclure les écarts corrigés,
  versions/digests, état des services, limites navigateur/réseau et rollback.
- Passer les contrôles ciblés et de publication applicables, publier uniquement
  le code accepté vers les dépôts Apoze autorisés dans l’exécution du plan.
- Rendre la branche principale du fork Meet installable et cohérente avec
  l’image livrée. Ne pas supprimer des branches préexistantes pour imiter la
  règle « une seule branche » propre au chantier Grist suspendu.
- Aucun chantier terminé tant qu’un échec d’accès, de média, de TLS ou de
  restauration obligatoire reste présenté comme « à vérifier plus tard ».

**Sortie :** code et documentation concordants, publication Apoze identifiée,
critères de fin renseignés avec preuves et éventuelles limites explicites.

## 8. Validation minimale et utile

Pas de nouvelle usine à tests : utiliser pytest natif, linters et build React,
puis un petit parcours navigateur partagé. Regrouper les assertions de
sécurité dans quelques scénarios métier. Ne pas écrire un test par fonction,
des fixtures de tout le serveur, un test de contenu des sources ou une matrice
exhaustive de navigateurs/IdP. Les contrôles de secrets et de provenance sont
distincts des tests fonctionnels et restent autorisés.

### 8.1 Pendant les modifications

- Lancer seulement les tests couvrant les chemins changés. Employer
  `make test-back ARGS="<fichiers ou sélection ciblée>"` avec le Compose de
  recette isolé, ou sa commande pytest équivalente ; jamais la base LAN.
- Ruff/pylint sur le backend concerné ; le `make lint` natif englobe aussi
  agents et Summary : choisir `lint-back` ou les commandes ciblées pour Meet.
- ESLint sur le frontend touché et `npm run build` quand le parcours est prêt.
  Réutiliser le lock et `npm ci`, sans ajouter un framework frontend de tests
  pour quelques boutons. Le navigateur couvre le flux réel.
- En cas de modification du paquet commun, exécuter ses tests identité/policy
  pertinents et un contrôle de consommateur existant, sans requalifier toute
  la suite à chaque itération.

### 8.2 Petite matrice de sortie

| Scénario | Preuve attendue |
| --- | --- |
| Compte et accès | Login OIDC, même compte après changement de profil, tiers refusé, demande d’identité inconnue sans accès. |
| Salle et groupe | Créer la salle, attribuer un groupe, gérer un coorganisateur, refuser une mutation du tiers, retirer le groupe sans supprimer un grant direct valide. |
| Appel réel | Deux contextes distincts échangent audio/vidéo, un écran et un message ; admission invitée et expulsion si ce mode est retenu. |
| Révocation | Retrait ST/People en plein appel, média effectivement interrompu, ancien JWT et JWT renouvelé refusés à la reconnexion dans les bornes publiées. |
| Panne bornée | Projection indisponible puis contrôleur arrêté sur cible isolée : plus d’accès conservé indéfiniment ; reprise saine après retour. |
| Fonctions exclues | Une sélection paramétrée de requêtes directes vers enregistrement, transcription/sous-titres, upload et extensions est refusée, sans création de travail ou de fichier. |
| IdP et persistance | Aller-retour Authentik avec mêmes comptes/ACL ; restauration d’une salle dans une base jetable, sessions restaurées inutilisables. |

Un passage Chromium principal et un participant Firefox vérifient ensemble
l’interopérabilité utile, sans répéter tous les scénarios par navigateur.
Faire un appel de quelques minutes et une reconnexion réseau ; relever via
`getStats` les octets et frames reçus, les pertes et le type de candidat ICE.
Une interface « connecté » sans son/image reçu n’est pas une réussite.

Médias synthétiques déterministes permis pour la preuve technique ; ajouter
une vérification courte caméra/micro réels sur un poste LAN lorsque disponible.
Tester le partage d’écran reçu, pas seulement le clic du bouton. Le son
système et le partage mobile dépendent des capacités du navigateur ; annoncer
ces limites natives plutôt que développer une capture alternative.

Si l’accès VPN/externe fait partie du réseau retenu, un participant depuis ce
réseau et un repli TCP/TURN contrôlé sont requis. Sinon, rapporter explicitement
« LAN qualifié » : un test local ne prouve pas le fonctionnement derrière tous
les NAT. Pas de test de charge massif ; quelques mesures sur l’appel suffisent
pour fixer une limite conservatrice, sans extrapoler une capacité certifiée.

Pour les vérifications navigateur, lire le skill `browser-qa` et le contrat
local avant leur exécution. Les preuves restent expurgées des tokens/cookies
et contenus réels. Les éventuels fichiers de média synthétique ou traces de
recette sont supprimés après capture des seuls résultats nécessaires.

## 9. Sauvegarde, mise à jour et retour arrière

- Sauvegarder base Meet, configurations, versions d’images, secrets Django/
  LiveKit/OIDC et empreintes de la wheel ; sauvegarder les entrées People/ST/
  IdP modifiées avant leur modification.
- PostgreSQL fait autorité sur comptes/salles/ACL. Redis contient de l’état
  transitoire ; une restauration ne doit pas ressusciter admissions, lobby
  accepté ou ancienne fraîcheur de politique. Révoquer/réinitialiser l’état
  transitoire et resynchroniser avant réouverture.
- Documenter les connexions perdues lors d’un redémarrage du SFU unique : la
  reprise se fait avec une admission valide. Ne pas promettre du zéro coupure.
- Mise à jour : build et contrôles ciblés, sauvegarde, migration avant ouverture
  du trafic, recréation des seuls services concernés, appel court de vérification.
- Rollback : masquer/désactiver Meet dans ST, fermer les nouvelles admissions,
  arrêter les seuls services Meet, restaurer la version et le schéma compatibles
  si nécessaire ; annoncer la coupure des appels concernés.
- Ne pas restaurer toute la base People/ST ni celle de Keycloak par réflexe :
  préserver les changements intervenus ailleurs ; retrait ciblé des objets
  Meet quand cela suffit. Aucun retour arrière Drive/S3/NAS requis par Meet.

## 10. Git, forks et limites d’autorisation

Pour Meet :

- `origin` : `https://github.com/Apoze/meet.git`, fork utilisateur, fetch/push.
- `upstream` : `https://github.com/suitenumerique/meet.git`, fetch-only,
  URL de push neutralisée ; aucune PR, issue, action, publication ou écriture.
- Ne pas laisser les workflows copiés publier des images, notifier ou agir
  vers des ressources officielles. Garder seulement la CI nécessaire du fork,
  avec permissions minimales et destinations Apoze explicites.
- Versionner tous les changements nécessaires au build et à l’installation,
  les migrations, le paquet vendorizé documenté et ses tests ciblés.
- Commits lisibles, changelog approprié, contrôles de secrets/provenance,
  linters et gitlint selon les règles applicables avant tout push.

Les adaptations communes relèvent de `https://github.com/Apoze/drive.git` et
les adaptations ST de `https://github.com/Apoze/st-deploycenter.git`, avec leurs
sources `suitenumerique` respectives en lecture seule. Ne publier aucun travail
préexistant sans rapport avec Meet. People/Docs devraient être configurés par
leurs interfaces existantes ; si une modification de leur code est nécessaire,
elle doit être conservée dans un fork Apoze correctement routé, jamais poussée
depuis un checkout dont la destination est le dépôt officiel. Préserver d’abord
leurs adaptations locales existantes.

Ce plan ne demande aucune action GitHub pendant sa préparation. Lors de son
exécution autorisée, vérifier chaque destination avant mutation ; un rapport
de publication nomme URL du dépôt, branche, base/head et PR éventuelle en entier.
Aucune PR vers les organisations officielles n’est une condition de livraison.

## 11. Livrables et critères de clôture

Dans le fork Meet : code, configuration Compose, exemples sans secrets,
guide d’installation, droits/identité, exploitation et rollback. Dans Drive :

```text
docs/plans/suite/meet-visio-core-integration-plan.md
docs/installation/suite-meet-visio.md
docs/operations/suite-meet-visio.md
output/implementation/meet-visio-core-integration/
  current-status.md
  deployment-manifest.md
  validation-final.md
```

Créer les rapports d’exécution quand le travail correspondant existe, pas des
fichiers marqués « validé » à la préparation. Le manifeste contient seulement
les références et chemins de secrets, jamais leurs valeurs. Mettre à jour
l’index des plans et les routes `AGENTS.md` utiles ; Grist reste classé en pause.

- [x] Meet libre auto-hébergé, source et images figées, aucun service commercial
  nécessaire aux fonctions livrées.
- [x] Audio, vidéo, écran et chat réellement échangés sur le réseau retenu.
- [x] HTTPS/WSS local de confiance dans les profils de qualification, sans
  contournement. Confiance à installer sur les appareils personnels ; certificat
  public/exposition Internet différés explicitement par le propriétaire.
- [x] Identité durable People, accès ST et catalogue reliés, administration Web
  des salles et groupes fonctionnelle ; comptes existants préservés.
- [x] Choix invités documenté et appliqué ; aucune admission anonyme implicite.
- [x] Rôles et révocation effectifs côté serveur pendant l’appel et à la reprise,
  y compris anciens jetons renouvelés ; panne de contrôle bornée et vérifiée.
- [x] Keycloak/Authentik qualifiés dans l’instance isolée, sans bascule du LAN.
- [x] Enregistrements, transcription, IA, extensions et upload inaccessibles,
  sans service auxiliaire ni stockage média inutile.
- [x] Redémarrage et restauration prouvés ; nettoyage des seules données d’essai.
- [x] Drive, Docs, People, ST, IdP et NAS existants conservés fonctionnels.
- [x] Code installable depuis les forks Apoze autorisés, documentation cohérente,
  aucun push/action vers les dépôts officiels, aucune reprise du chantier Grist.

« Entièrement livré » signifie que ces critères sont démontrés. L’agent doit
signaler précisément une dépendance extérieure réelle, sans compenser son
absence par un contournement ni déclarer une simple compilation comme une
preuve de visioconférence opérationnelle.

## 12. Clôture du 8 septembre 2026

M0–M8 exécutés. La matrice et les limites mesurées sont dans la validation
finale liée en tête. Le guide détaillé est canonique dans Apoze/meet ; les
entrées installation/opérations de Drive y renvoient. Aucune fonctionnalité
expérimentale ni chantier Grist repris. La qualification réseau porte sur UDP
et une reconnexion après interruption réelle du proxy ; aucun benchmark de
charge ni validation de périphériques physiques de l’utilisateur revendiqués.
