# Messages et Calendars — intégration complète à la suite Apoze sur le LAN

Date : 10 septembre 2026.
Statut : **LIVRÉ SUR LE LAN — 10 septembre 2026**.
Exécution autorisée le 10 septembre 2026. Suivi :
[journal d'exécution](../../../output/implementation/messages-calendars/execution-journal.md).
Livraison : [validation finale](../../../output/implementation/messages-calendars/validation-final.md)
et [guide d’exploitation](../../operations/suite-messages-calendars.md).
Sauvegarde nettoyée `20260910T130928Z`, restauration isolée vérifiée.
**GitHub : corrections Messages/Calendars publiées sur les forks Apoze,**
**branche `codex/suite-messages-calendars` ; aucun push/PR amont.**
Voir le [rapport de publication](../../../output/implementation/messages-calendars/publication.md).
Ce document remplace le périmètre envisagé « Calendars seul ».
Le propriétaire a demandé Messages et Calendars ensemble, **LAN maintenant,
WAN plus tard**. Son exécution a été autorisée par le propriétaire.

## 1. Résultat à livrer

Une messagerie web personnelle et collaborative, et des agendas réellement
interconnectés, accessibles depuis le catalogue commun. Un utilisateur peut :

- ouvrir Messages et Calendars avec la connexion commune de la suite ;
- envoyer et recevoir des mails entre les boîtes du LAN, avec pièces jointes ;
- utiliser les boîtes et agendas partagés autorisés par les groupes People ;
- créer une invitation dans Calendars, la recevoir dans Messages, y répondre
  et retrouver le même événement avec le bon statut chez l'organisateur ;
- modifier ou annuler cet événement sans doublon ni perte des exceptions ;
- ajouter une vraie salle Meet, et échanger des pièces jointes avec les espaces
  Drive S3/NAS sans contourner leurs permissions ou quotas ;
- retrouver ses boîtes, messages, agendas et droits après changement d'IdP.

L'administrateur gère les accès applicatifs dans ST, les personnes et groupes
dans People, les domaines/boîtes dans Messages et les agendas dans Calendars.
Les opérations quotidiennes passent par les interfaces web. Les secrets,
déploiements et sauvegardes suivent les outils d'exploitation existants.

La livraison comprend configuration, développements nécessaires, démarrage
persistant, documentation, vérifications ciblées, restauration et nettoyage.
Un service qui démarre ou une invitation uniquement visible dans Mailcatcher
ne suffisent pas à déclarer le chantier terminé.

### Périmètre accepté

| Inclus et à qualifier | Limite explicite |
| --- | --- |
| Messages web : boîtes personnelles/partagées, rédaction, réponses, transfert, brouillons, destinataires To/Cc/Bcc, pièces jointes, dossiers/libellés, recherche, corbeille | Réutiliser les fonctions présentes ; corriger les défauts bloquant les parcours retenus |
| Partage de conversations, commentaires et affectations présents dans Messages | Conserver la composition des droits boîte/conversation |
| Calendars : vues natives, agendas personnels/partagés, événements, fuseaux, journée entière, récurrences et exceptions | Pas de remplacement du moteur CalDAV ou de l'interface existante |
| Invitations, réponses, mises à jour, annulations, disponibilités, ressources et liens Meet | Pas d'enregistrement, transcription ou IA Meet |
| Import/export natifs MBOX et ICS, connexions CalDAV et abonnements ICS | Un exemple représentatif par format utile ; pas de migration d'une messagerie réelle inexistante |
| Stockage Messages, quotas applicatifs et échanges de pièces jointes Drive | Messages garde son stockage métier ; le NAS ne remplace pas sa gestion de quotas |
| Connexion Keycloak actuelle et qualification Authentik isolée | Aucun développement dépendant des API d'administration Keycloak |
| Transport SMTP interne complet, filtrage et gestion des erreurs | Aucun envoi ou réception Internet pendant ce chantier |

Hors chantier : exposition WAN, DNS publics, certificats publics, réputation
SMTP, migration de boîtes externes, applications mobiles natives, serveur
IMAP/POP3 ou JMAP complet, ponts expérimentaux, IA, DIMAIL/Open-Xchange et Grist.
Les connecteurs natifs non nécessaires ne sont pas activés automatiquement.
Un rappel `VALARM` conservé dans un événement n'est pas présenté comme un
service de notifications navigateur ou d'envoi de rappels par mail.

## 2. État des lieux vérifié et conséquences

Inspection en lecture seule des sources le 10 septembre 2026 :

- Calendars : `00487b531328dfb9989181b6d446504d4f6aca3a`, version 0.1.0 ;
- Messages : `1cb101c0659256212ec8f803d96aa2a24334c4f8`, version 0.9.0.

Ces références sont des bases étudiées, pas une qualification de déploiement.
Les réévaluer au lot MC0 si l'exécution commence sur une autre révision.
Ne pas déduire l'état du code d'une ancienne issue ou du numéro de version.

| Constat dans les sources | Travail requis |
| --- | --- |
| Calendars est React/Vite/TanStack Router, Django et SabreDAV ; son worker est Dramatiq | Utiliser ces composants ; ne pas lui imposer Next.js ou une seconde pile Celery |
| Messages est React/Vite, Django, Celery, PostgreSQL, OpenSearch, stockage de blobs et transport SMTP | Déployer le parcours complet ; son profil de développement allégé ne suffit pas |
| Le transport sortant Messages est assuré par Celery, directement vers les MX ou via relais | Réutiliser le mode relais pour le LAN ; pas de nouveau MTA sortant sans nécessité |
| L'identité et les principaux CalDAV utilisent encore largement l'email ; Messages a aussi des mécanismes d'autojoin et de synchronisation Keycloak | Brancher l'identité durable People et supprimer ces dépendances du mode suite |
| ST local fait actuellement dépendre l'accès Calendars d'une souscription Messages | Créer deux accès administrables et un raccordement explicite, sans dépendance cachée |
| Le partage d'agendas de boîtes existe, avec projection d'ACL depuis Messages | Réutiliser cette projection, la rendre durable, périodique, bornée et fondée sur les UUID |
| Le client Calendars met les boîtes Messages en cache pendant 300 secondes | Aligner la fraîcheur des droits avec la borne de révocation de la suite |
| Messages possède déjà une interface RSVP et un client CalDAV ; la configuration commune utilise un secret avec l'email comme utilisateur | Remplacer cette délégation implicite par un acteur durable et des autorisations vérifiées |
| Le simple accès applicatif amont ne bloque pas nécessairement toutes les lectures/écritures DAV | Contrôler aussi Basic, ICS, tâches différées et appels internes |
| Les liens RSVP Calendars ouvrent une page qui soumet automatiquement un POST en JavaScript | Exiger un geste explicite pour éviter une réponse par un prévisualiseur de mails |
| Le bouton Meet de Calendars construit une URL aléatoire | Utiliser la création de salle existante de notre Meet, avec son propriétaire et son admission |
| Le connecteur Drive Messages relaie le jeton OIDC et filtre les fichiers créés par l'utilisateur | Adapter à notre délégation de suite et aux espaces/ressources autorisés, y compris NAS |
| Messages possède des métriques et ST un entitlement de stockage ; cela ne prouve pas une réservation atomique sur chaque écriture | Vérifier les points d'admission et ajouter le contrôle effectif manquant |
| Les blobs Messages ont un stockage PostgreSQL/S3, chiffrement, déduplication et collecte natifs | Conserver leur modèle et sauvegarder les clés ; ne pas copier les blobs dans des Items Drive |

Sources immuables et documentation de référence : section 10.

## 3. Décisions d'architecture

### 3.1 Responsabilités et identité durable

Appliquer l'[ADR 0003](../../adr/0003-suite-durable-identity-and-access.md)
et réutiliser `src/packages/suite-identity/`. Chaque application reste cliente
OIDC de l'IdP ; People n'est pas un proxy de connexion obligatoire.

| Objet | Autorité et identifiant |
| --- | --- |
| Personne | UUID People ; association explicite `(issuer, subject, consommateur)` |
| Groupe | People `Team.external_id` ; source People initialement, import externe selon le mode SCIM déjà livré |
| Organisation | UUID ST configuré pour ce déploiement ; pas de domaine email ou SIRET implicite |
| Accès à Messages/Calendars et budgets attribués | Politiques ST projetées dans chaque application |
| Domaine, boîte, adresse d'envoi, accès à la boîte | Messages ; UUID de boîte distinct de son adresse |
| Agenda, événements, droits personnels, disponibilités, ressources | Calendars/SabreDAV ; identifiants stables |
| Accès à l'agenda lié à une boîte | Droits effectifs de la boîte Messages, projetés dans Calendars |
| Droits sur fichiers/documents et salles | Drive/Docs et Meet, selon leurs contrats existants |

Les principaux DAV utilisateurs reposent sur l'UUID People ; ceux des boîtes
sur l'UUID Messages ; les ressources gardent leur UUID. Les adresses servent
au routage mail/iTIP et à l'affichage. Un changement d'adresse ne crée pas
un nouveau propriétaire et ne réattribue pas une ancienne boîte.

Désactiver en mode suite le rattachement par email, `oidc_autojoin` et
`identity_sync` vers Keycloak. Prévoir une attribution explicite des boîtes
à des personnes/groupes, y compris avant leur première connexion. Une personne
sans email IdP peut utiliser une boîte qui lui est attribuée ; cela ne justifie
pas de modifier son `sub` ou les mappers du Keycloak existant.

Pour les nouvelles boîtes, l'adresse est un attribut métier administré dans
Messages. Pour un compte externe inconnu, conserver la demande de rattachement
People et le refus d'accès tant que l'association n'est pas approuvée.

### 3.2 Accès, groupes et révocation

Deux décisions séparées : accès ST à l'application, puis permission sur la
ressource. Un administrateur de catalogue n'obtient pas la lecture des mails.
Ne pas convertir automatiquement un administrateur de domaine en superuser
Django : l'administration technique amont a des pouvoirs plus larges.

| Messages | Agenda lié à cette boîte |
| --- | --- |
| Viewer | Lecture selon la confidentialité de l'agenda |
| Editor | Lecture ; pas d'envoi d'invitation au nom de la boîte |
| Sender | Écriture d'événements et invitations au nom de la boîte |
| Admin | Sender + administration de la boîte et du cycle de vie de ses agendas |

Un agenda personnel peut être partagé directement ou avec un groupe People
en disponibilité seule, lecture ou écriture, selon les capacités natives.
Pour une boîte partagée, Messages reste la seule autorité des membres et
rôles : pas de deuxième écran permettant de contourner ces rôles dans Calendars.

Réutiliser les tables d'accès natives. Ajouter seulement la provenance des
attributions groupe/directes et la projection nécessaire : le rôle effectif
est calculé à partir des attributions encore valides. Retirer un groupe ne
supprime pas un droit direct distinct, et ne laisse pas une copie permanente
du droit de groupe. La suppression/recréation d'un groupe homonyme ne récupère
aucun droit. La synchronisation ne recrée pas les invitations de partage.

Une projection SabreDAV par bénéficiaire est appropriée à ses
`calendarinstances`, avec provenance et réconciliation, en réutilisant le
mécanisme d'ACL gérées existant. Ne pas inventer un deuxième moteur de groupes
ou une arborescence de boîtes factices pour représenter les groupes People.

Conserver le contrat de fraîcheur existant : synchronisation environ toutes
les 30 secondes, décision positive périmée après 90 secondes sans observation
valide, retrait effectif au plus tard en 120 secondes. Cette borne couvre
aussi la chaîne People → Messages → Calendars : les caches ne réinitialisent
pas l'âge d'une même observation à chaque étape.

Une panne ne vaut ni liste vide ni autorisation illimitée. Conserver la dernière
projection complète pour la reprise, refuser son utilisation après échéance,
et ne publier une nouvelle révision qu'après application complète. Vérifier
les droits au démarrage des tâches et avant leur effet externe.

La déconnexion commune ferme les sessions humaines. Les mots de passe
d'application ont leur propre rotation/révocation ; une suspension de compte,
un retrait d'accès applicatif ou de ressource s'applique aussi à eux. Une
action explicite de révocation de tous les accès coupe également ces canaux.
Ni la révocation ni l'annulation d'un mail ne rappellent une copie déjà reçue.

La suspension d'une personne ne supprime pas sa boîte. Une boîte partagée
active continue à recevoir les mails indépendamment de la session de ses
membres. Sa fermeture, son quota et le retrait du service de l'organisation
ont des politiques d'admission distinctes, visibles dans l'administration.

### 3.3 Transport LAN, prêt à être reconfiguré pour le WAN

Par défaut, utiliser un domaine de recette interne `mail.apoze.test`, avec
adresses attribuées dans Messages. Il ne dépend pas d'un domaine public.
Consigner l'adresse LAN, les ports libres et les URLs effectives au lot MC0.
Ne pas déplacer les services existants pour réutiliser un port déjà occupé.

Parcours : navigateur → API Messages → file Celery → SMTP interne →
MTA-in Postfix → MDA Messages → stockage/indexation → boîte destinataire.
Réutiliser la livraison locale native si elle couvre déjà un segment, sans
livrer une seconde fois le même mail. Qualifier aussi une véritable entrée
SMTP pour vérifier MTA-in/MDA et ses réponses d'erreur.

Configurer le mode relais vers le transport interne et interdire les
destinataires hors domaines LAN autorisés. Aucun fallback direct vers un MX
Internet. Les destinataires inconnus sont refusés ; le serveur n'est pas un
relais ouvert. Mailcatcher est seulement un outil de diagnostic, pas la boîte
de réception finale et pas une preuve de livraison à un utilisateur.

Les interfaces web sont accessibles sur le LAN. Les ports PostgreSQL, Redis,
OpenSearch, SabreDAV, MDA et administration Rspamd restent privés. Le SMTP
de recette reste interne/loopback sauf besoin LAN explicite et restriction
réseau adaptée. Pas de changement NAT, routeur ou pare-feu WAN.

Le profil LAN est explicite. Les exceptions aux vérifications DNS publics
sont limitées aux domaines de test configurés ; conserver les vérifications
normales pour le futur profil WAN. Ne pas désactiver globalement CSRF, TLS
sortant, validation de destinataires ou protections SSRF pour faciliter le LAN.

### 3.4 Invitations : un seul événement, un seul expéditeur autorisé

Activer `FEATURE_MESSAGES_INTEGRATION` dans Calendars. L'agenda associé à une
boîte est le parcours par défaut pour les invitations de cette boîte. Garder
la possibilité d'agendas personnels autonomes, sans créer deux agendas
automatiquement pour une même personne.

Les appels Calendars → Messages utilisent les canaux API natifs, avec secrets
séparés par usage, organisation et permissions minimales. Le provisioning
retourne les UUID de personnes/boîtes et toutes les pages nécessaires, pas
uniquement les emails. La soumission vérifie la boîte, l'acteur ou l'opération
de planification autorisée et les destinataires. Une clé de transport seule
ne doit pas devenir un droit d'envoyer depuis n'importe quelle boîte.

Messages → Calendars réutilise le client HTTP/CalDAV existant et une délégation
bornée au principal, à la boîte et à l'opération. Préférer les mécanismes de
preuve déjà livrés dans la suite ; ne pas exiger de token exchange Keycloak,
ni partager un mot de passe humain global. Les tâches portent des identifiants
stables et rechargent les ressources autorisées, pas seulement l'email du clic.

Tracer et terminer ces quatre flux :

1. `REQUEST` : création/invitation → mail reçu → affichage et proposition de
   réponse dans Messages ; aucune acceptation automatique d'un expéditeur.
2. `REPLY` : réponse depuis Messages ou lien RSVP → statut de participation
   actualisé chez l'organisateur, sans nouvelle invitation en boucle.
3. Mise à jour : même `UID`, évolution valide de `SEQUENCE`, bonne occurrence
   et bon fuseau ; une mise à jour ancienne n'écrase pas la nouvelle.
4. `CANCEL` : annulation de série ou d'occurrence répercutée, mail lisible et
   état cohérent dans chaque agenda concerné.

Il faut inspecter le chemin MIME entrant jusqu'à l'application iTIP : la
présence de boutons RSVP ne démontre pas le traitement automatique des REPLY
et CANCEL reçus. Si ce traitement manque, ajouter une étape ciblée dans le
pipeline/worker natif, réutilisant SabreDAV et les parseurs existants.
Valider organisateur, participant, boîte destinataire, origine authentifiée
du transport local et événement ciblé ; un simple `From` ne prouve pas une
identité. Les messages non fiables restent consultables sans modifier l'agenda.

Réutiliser l'idempotence existante, ou la compléter au point de soumission et
d'application iTIP : identité d'opération, boîte, UID, occurrence, séquence,
méthode et participant selon le flux. Ne pas dédupliquer tous les mails sur
`Message-ID` seul. Les retries après réponse perdue ne créent pas plusieurs
événements ; ne pas promettre l'exactly-once SMTP.

Une invitation enregistrée mais non expédiée affiche son état réel et une
reprise possible. Ne jamais annoncer « envoyée » sur la seule mise en file.
Les liens RSVP expirent, restent limités à l'événement/participant et demandent
une confirmation explicite ; une prévisualisation ne change aucun statut.

### 3.5 Données, quotas et pièces jointes

Garder les bases métier et le stockage natif des blobs Messages. Un bucket
privé et des credentials Messages distincts peuvent utiliser un S3 existant
compatible. Ne pas reprendre automatiquement l'image S3 alpha du compose de
développement. Réutiliser un service stable déjà qualifié si ses opérations
requises passent ; aucune modification des buckets Drive/Docs.

Les quotas Messages sont applicatifs, indépendants du volume Docker, du S3
ou du NAS. ST attribue les budgets ; Messages réserve et comptabilise au point
d'écriture. Prévoir budget d'organisation et plafond par boîte, personnelle
ou partagée. Le quota d'une boîte partagée n'est pas multiplié par son nombre
de lecteurs ; un utilisateur a un budget personnel via ses boîtes attribuées,
avec agrégation si plusieurs boîtes consomment la même allocation.

Documenter une règle stable : octets logiques non compressés, non affectés
par chiffrement/offload/déduplication physique ; même contenu référencé
plusieurs fois dans une boîte compté selon un ensemble de références distinctes,
sans compter deux fois une pièce jointe déjà incluse dans le MIME facturé.
Comptabiliser les réservations de pièces jointes et brouillons, les imports,
les copies reçues/envoyées, la corbeille et les pièces encore référencées.
Une purge effective libère la charge ; déplacer en corbeille ne la libère pas.
La déduplication technique entre boîtes ne donne pas de stockage gratuit à une
autre boîte. La mesure physique reste un indicateur d'exploitation séparé.

Réserver atomiquement avec les écritures concurrentes et libérer après échec
ou expiration. La baisse d'un plafond sous l'usage bloque les ajouts sans
supprimer le contenu ; lecture, export et purge restent possibles. Si le
stockage ou la politique ne sont pas vérifiables, ne pas accepter un mail pour
le perdre ensuite : réponse SMTP temporaire adaptée, retries et état visible.
Traiter les destinataires multiples individuellement pour éviter pertes ou
doublons à la reprise. Fixer aussi une taille maximale MIME/ICS et des limites
d'import/récurrence ; pas de nouvelle comptabilité globale de toute la suite.

Messages ↔ Drive doit utiliser les droits de l'utilisateur effectif et le
sélecteur d'espaces/dossiers canonique : pièces jointes vers S3 ou NAS,
fichier autorisé vers une pièce jointe, conflit de nom explicite, réservation
du quota de destination, transfert borné/streaming et reprise idempotente.
Supprimer le rapprochement ambigu « même nom + même taille = même fichier ».
Un document Docs vivant peut être partagé par son lien authentifié ou exporté
via son mécanisme natif ; jamais lu comme un objet S3 ou rendu public à l'insu
de l'utilisateur. Une pièce jointe envoyée est une copie indépendante.

### 3.6 Meet et simplicité de déploiement

Le bouton de visioconférence doit créer une salle via le parcours SDK/popup
et callback déjà présent dans notre Meet. Qualifier origine, corrélation,
expiration et droits du retour ; corriger ce chemin s'il ne suffit pas.
La salle appartient à son créateur et conserve les règles d'admission.
Une invitation calendrier ne transforme pas automatiquement le destinataire
en administrateur ou participant admis. Retirer un lien d'événement ne supprime
pas une salle partagée. Aucun microservice de réservation de salles supplémentaire.

Conserver Celery/beat dans Messages et Dramatiq dans Calendars. Pour Calendars,
réutiliser les fonctions synchrones du paquet d'identité et un lancement
périodique simple, supervisé et sans exécutions concurrentes ; ne pas ajouter
Celery/beat uniquement pour cet agenda. Mutualiser PostgreSQL/Redis existants
seulement si versions, permissions et isolation sont compatibles : bases/rôles,
files, caches et préfixes distincts. Sinon, services dédiés issus des images
natives figées, sans migration imposée aux autres applications.

## 4. Ordre d'exécution et suivi

Tous les lots ci-dessous sont obligatoires pour déclarer le **LAN livré**.
Le lot WAN de la section 9 est distinct et explicitement différé.
Avancer dans l'ordre ; mettre à jour ce tableau et les cases à chaque reprise.

| Lot | Livrable | Dépendance | État | Preuve |
| --- | --- | --- | --- | --- |
| MC0 | Baseline, sources, ressources et configuration cible | — | Terminé | Journal |
| MC1 | Checkouts/forks et builds reproductibles | MC0 | Terminé | Journal |
| MC2 | Socle Docker, stockage et transport SMTP LAN | MC1 | Terminé | Journal |
| MC3 | Identité, politiques ST, catalogue et administration | MC2 | Terminé | Journal et validation finale |
| MC4 | Boîtes/groupes, quotas et messagerie complète | MC3 | Terminé | Journal et validation finale |
| MC5 | Calendars, identifiants durables et partages | MC3–MC4 | Terminé | Journal et validation finale |
| MC6 | Invitations Messages ↔ Calendars de bout en bout | MC4–MC5 | Terminé | Journal et validation finale |
| MC7 | Drive/Docs et Meet, parcours intégrés | MC4–MC6 | Terminé | Journal et validation finale |
| MC8 | Reprise, sauvegarde, restauration, exploitation | MC2–MC7 | Terminé | Validation finale et restauration-readback.json |
| MC9 | Recette minimale, second IdP et nettoyage | MC3–MC8 | Terminé | identity-roundtrip.json et cleanup-readback.json |
| MC10 | Documentation et clôture vérifiable | MC9 | Terminé | Validation finale |

### MC0 — Préparer sans perturber l'existant

- [x] Lire les `AGENTS.md` des dépôts réellement touchés, le contexte commun,
  l'ADR identité et les plans livrés uniquement sur les interfaces utiles.
- [x] Exécuter les statuts Docker Drive et suite ; inventorier les ports,
  réseaux, volumes, bases, versions, espace disque et mémoire disponibles.
- [x] Relever les URL LAN existantes, leur mode local et les chemins de
  démarrage ; ne pas changer le script Drive pour lui faire démarrer ST.
- [x] Relever les modifications Git préexistantes dans chaque dépôt. Le
  checkout Drive était déjà fortement modifié à la rédaction de ce plan :
  aucun reset, nettoyage de fichiers inconnus ou publication englobant ces
  changements sans audit. Ne pas reprendre Grist ou le rattrapage upstream.
- [x] Sauvegarder les données et configurations touchées, sans afficher les
  secrets ; établir une preuve courte que Drive/Docs/Meet/People/ST fonctionnent.
- [x] Figer les révisions de base, dépendances et images ; vérifier les avis
  de sécurité pertinents et corriger les incompatibilités bloquant ce périmètre.
- [x] Consigner le plan des ports, le domaine interne, les allocations de
  stockage et les services réutilisés dans le journal MC0.

Sortie : configuration cible concrète et restauration de l'existant possible.

### MC1 — Sources et builds

- [x] Travailler dans `/root/Apoze/messages` et `/root/Apoze/calendars`, sur
  branches locales dédiées au chantier, avec code hors du dépôt Drive.
- [x] Cibles des forks : `https://github.com/Apoze/messages.git` et
  `https://github.com/Apoze/calendars.git`. Amonts :
  `https://github.com/suitenumerique/messages.git` et
  `https://github.com/suitenumerique/calendars.git`, fetch-only, push désactivé.
  Vérifier existence et autorisation avant création/publication ; une absence
  de fork distant n'empêche pas les checkouts, le développement et la recette.
- [x] Respecter les runtimes observés : Messages Python 3.14/Django 5.2,
  Calendars Python 3.13/Django 5.2 ; Node 24 et gestionnaire/lockfile natif de
  chaque frontend. Vérifier la compatibilité de la wheel d'identité avec les
  versions différentes de `django-lasuite`, sans mise à jour globale aveugle.
- [x] Conserver le verrouillage SabreDAV et ses correctifs d'installation ;
  ne pas remplacer sa référence figée par un `dev-master` flottant.
- [x] Préparer des images étiquetées par révision et un montage de sources
  explicite en développement. Aucun montage temporaire indispensable au runtime.
- [x] Conserver licences libres et notices ; aucun composant payant ou compte
  SaaS obligatoire. Désactiver les fonctionnalités IA et télémétries optionnelles.

Sortie : builds réexécutables et modifications Apoze isolées des amonts.

### MC2 — Docker et mail interne réels

- [x] Décliner l'orchestration suite existante avec préparation idempotente,
  démarrage, statut et arrêt ciblés ; ne pas recopier intégralement les scripts.
- [x] Démarrer Messages API/frontend, worker/beat natifs, OpenSearch, MTA-in
  Postfix, filtrage Rspamd et stockage nécessaires. Choisir Postfix existant,
  sans activer le MTA Python alternatif ni le profil allégé comme livraison.
- [x] Démarrer Calendars API/frontend, SabreDAV et Dramatiq, avec données
  persistantes distinctes. Ne pas lancer leurs Keycloak de démonstration.
- [x] Configurer les routes API, assets, callback OIDC, RSVP, DAV et discovery,
  y compris `MOVE`/`Destination`, cookies distincts et origine LAN réelle.
  Servir le build frontend avec un serveur adapté, pas `vite preview` comme
  serveur permanent de livraison.
- [x] Affecter secrets uniques aux sessions, MDA, API Messages, API SabreDAV,
  chiffrement des blobs et délégations. Les générateurs ne remplacent jamais
  silencieusement les clés d'un environnement existant.
- [x] Configurer le domaine LAN et les boîtes de recette par les services
  métier/commandes de provisioning ; pas de faux états SQL contournant les ACL.
- [x] Relier SMTP sortant et entrant, vérifier destinataire valide/inconnu,
  erreur temporaire, taille maximale et absence de relais vers Internet.
- [x] Activer le filtrage utile au LAN avec exceptions strictement locales ;
  traiter les échecs et pièces suspectes sans les publier comme sûres. Vérifier
  l'antivirus réellement branché ; réutiliser le service existant si compatible.
- [x] Vérifier accès privé aux dépendances, absence de secrets dans logs,
  URLs, captures et erreurs, et consommation au repos. Pas de prune global.

Sortie : deux boîtes peuvent échanger réellement un mail interne ; les autres
applications restent utilisables. Le raccordement d'identité final suit MC3.

### MC3 — People, IdP, ST et administration web

- [x] Intégrer la wheel d'identité, ses migrations, preuves, projections,
  catalogue et déconnexion dans Messages et Calendars.
- [x] Créer les deux consommateurs OIDC avec scopes minimaux et associations
  People distinctes ; préserver la configuration Keycloak des applications
  actuelles. Interdire fusion par email et création d'identités dans l'IdP.
- [x] Remplacer le couplage implicite d'entitlement Calendars/Messages dans ST
  par deux accès explicites ; permettre leur activation conjointe et afficher
  clairement la disponibilité de l'intégration mail. Retirer Messages ne
  supprime pas les agendas ; il bloque les opérations dépendant de ses boîtes.
- [x] Raccorder les groupes People aux accès applicatifs, les organisations et
  rôles administratifs ST, sans droit de contenu implicite. Ajouter les vignettes
  et liens croisés aux menus déjà utilisés par Drive, Docs, Meet et People.
- [x] Exposer dans les interfaces natives l'état de synchronisation, les
  rattachements attendus et les refus utiles ; aucun écran « tout fonctionne »
  si l'autorisation provient d'un backend local qui autorise toujours.
- [x] Brancher la synchronisation périodique, les contrôles de fraîcheur et la
  déconnexion ; couvrir sessions, API, canaux machine, exports et jobs.
- [x] Prévoir l'accès technique de récupération selon le modèle existant,
  séparé des rôles métier, sans mot de passe de démonstration.

Sortie : accès et retrait pilotés par les interfaces ST/People, identité durable
et séparation des rôles prouvés avec deux utilisateurs et un groupe.

### MC4 — Boîtes, groupes, quotas et usages Messages

- [x] Projeter les personnes avant connexion et attribuer une boîte personnelle
  et une boîte partagée depuis l'UI ; adresses explicites et UUID pérennes.
- [x] Ajouter le partage par groupes People au modèle d'accès natif, sans
  écraser les attributions directes ; assurer pagination et recherche des membres.
- [x] Garder les contrôles composés boîte/conversation sur lecture, recherche,
  résultats d'index, téléchargement, rédaction, envoi, partage et commentaires.
- [x] Vérifier From/Sender, alias réellement autorisés, Bcc, réponses/transferts,
  brouillons, état envoyé/reçu/échoué, destinataires partiellement acceptés et
  retry après redémarrage. Ne pas accorder l'envoi au rôle Editor.
- [x] Implémenter les budgets et réservations décrits en 3.5 aux frontières
  communes : SMTP/MDA, API submit, uploads/brouillons, envoi, imports et copies.
  Les métriques remontées à ST ne remplacent pas ces contrôles atomiques.
- [x] Afficher usage/plafond et état de quota dans Messages et ST, administrables
  par les rôles prévus. Journaliser changements sans contenu de mails.
- [x] Vérifier un import MBOX réduit, son statut/reprise, recherche et export,
  pièces jointes, corbeille/purge, collecte native et intégrité des blobs.
- [x] Formaliser suspension, retrait d'un groupe, transfert d'administration,
  changement d'adresse et suppression d'une boîte : confirmation, conservation
  ou export préalable, dépendances agenda visibles, aucun effacement au logout.

Sortie : messagerie utilisable depuis le Web UI, rôles et quotas appliqués
sur les vraies écritures ; pas seulement des paramètres stockés ou des jauges.

### MC5 — Agendas durables, partages et clients

- [x] Adapter provisionnement, `PrincipalBackend`, proxy, découverte, recherche
  de principaux, invitations, canaux, ressources et suppressions aux UUID.
  Résoudre `mailto:` uniquement par correspondance métier autorisée ; pas de
  création implicite d'un utilisateur depuis une adresse arbitraire.
- [x] Si des agendas existent déjà, produire un aperçu puis une migration
  idempotente des chemins, propriétaires, ACL, abonnements et canaux ; préserver
  UID d'événements, organisateurs et adresses historiques autorisées. Si les
  bases sont vides, constater ce fait et ne pas inventer une migration de données.
- [x] Présenter la création d'agenda avec choix de boîte/personnel explicite,
  nom/couleur/fuseau, sans doublon automatique. Définir les règles privées par
  défaut et la différence entre disponibilité seule et contenu lisible.
- [x] Raccorder les ACL de boîtes Messages avec identifiants stables, pagination,
  fraîcheur de bout en bout et changements atomiques dans SabreDAV. Réutiliser
  la synchronisation existante, sans dépendre de l'ouverture du navigateur.
- [x] Ajouter les groupes People aux partages d'agendas personnels et conserver
  l'autorité unique Messages pour les agendas de boîtes. Interdire modification
  directe d'une attribution gérée via DAV ou un second écran.
- [x] Qualifier création/édition/suppression, journée entière, changement de
  fuseau et d'heure, série entière/une occurrence/cette occurrence et suivantes,
  exceptions importées, conflit ETag et absence d'écrasement silencieux.
- [x] Conserver les propriétés iCalendar non éditables ; refuser explicitement
  une modification que l'UI ne sait pas préserver. Ne pas réécrire les séries
  complexes en une approximation différente.
- [x] Raccorder disponibilités/horaires et ressources déjà présents, avec
  confidentialité, rôles de réservation et conflit de réservation vérifiés.
- [x] Exposer les canaux CalDAV et ICS dans l'UI, scopes réellement appliqués,
  rotation/révocation et dernière utilisation. Vérifier `PROPFIND`, `REPORT`,
  `PUT`, `DELETE`, partage et discovery via le proxy ; SabreDAV reste privé.
- [x] Distinguer requêtes DAV à cookie et Basic : CSRF/origine pour le navigateur,
  credential borné pour les clients. Un lien ICS doit perdre l'accès si son
  propriétaire perd les droits sur l'agenda ; pas de cache qui prolonge l'accès.
- [x] Empêcher perte d'agendas partagés à la suppression d'un créateur ou d'une
  boîte ; transfert/archivage/suppression explicites et erreurs récupérables.

Sortie : mêmes agendas et droits dans l'UI et dans un client CalDAV réel,
indépendamment de l'email IdP et de l'ouverture de Messages.

### MC6 — Invitations et réponses intégrées

- [x] Câbler les canaux dans les deux sens, avec contrats UUID, preuve d'acteur,
  permissions de boîte, projection d'organisation et secrets dédiés.
- [x] Réutiliser le service d'invitations et la soumission MIME Messages ;
  afficher la bonne adresse de boîte comme organisateur/participant.
- [x] Relier la réception MIME à iTIP, les cartes d'invitation Messages, le
  sélecteur d'agenda et les liens profonds Calendars au même événement.
- [x] Implémenter les parties manquantes de REQUEST/REPLY/CANCEL et des mises
  à jour, avec déduplication, séquence/occurrence, contrôle d'origine et reprise.
- [x] Revalider les permissions dans les tâches après révocation ; un job
  ancienne session ne doit pas envoyer ou répondre pour une boîte perdue.
- [x] Qualifier invitation à soi-même, boîte partagée avec deux membres,
  réponses concurrentes, modification après réponse et annulation. Un membre
  Viewer/Editor ne répond pas au nom d'une boîte s'il n'a pas le rôle requis.
- [x] Corriger les liens RSVP : confirmation explicite, jeton expiré/altéré,
  événement supprimé et participant retiré ; ne pas réactiver un événement
  annulé via une vieille invitation.
- [x] Simuler une seule panne ciblée du raccordement, reprendre et vérifier
  l'absence de doublon et l'état final ; distinguer enregistrement et livraison.

Sortie : invitation aller-retour, modification et annulation observées dans
les deux applications avec le transport LAN réel, sans Mailcatcher substitut.

### MC7 — Intégration Drive/Docs et Meet

- [x] Adapter le connecteur Drive natif Messages à la preuve de suite et aux
  APIs de ressources existantes, avec autorisation au départ et à destination.
- [x] Réutiliser l'explorateur et le sélecteur de destination canoniques ; inclure
  espaces autorisés S3, NAS et partagés. Aucun nouvel explorateur « montages ».
- [x] Qualifier pièce jointe → dossier Drive et fichier Drive → pièce jointe,
  sur S3 et NAS, refus d'accès, quota insuffisant et conflit de nom ; opérations
  idempotentes et mémoire bornée, sans déduplication sur nom/taille seulement.
- [x] Conserver un lien Docs authentifié et, si l'utilisateur choisit une copie,
  utiliser l'export natif existant. Le destinataire d'un mail ne reçoit pas
  automatiquement un droit sur un document privé.
- [x] Brancher la création de salle Meet existante, avec erreur explicite si
  l'utilisateur n'a pas accès à Meet ; qualifier le lien depuis l'invitation,
  propriétaire réel, attente/admission et persistance après rechargement.
- [x] Conserver la navigation commune, les retours vers l'événement/la boîte,
  les traductions et les états de chargement/échec des composants natifs.

Sortie : les raccordements annoncés sont utilisables, sans contournement des
ACL ni dégradation de l'explorateur Drive restauré au chantier précédent.

### MC8 — Exploitation et reprise

- [x] Fournir démarrage/arrêt/statut/mise à jour ciblés, persistants après
  redémarrage Docker ; le démarrage Drive reste distinct de ST et des ajouts.
- [x] Superviser santé API/DAV/MTA, ancienneté People/ST/ACL, files en retard,
  livraisons échouées, quotas, stockage et indexation avec les outils existants.
- [x] Borner taille MIME/ICS, expansion de récurrence, imports, réponses HTTP,
  retries et concurrence. Réutiliser les index et requêtes par lots ; mesurer
  une boîte et un agenda représentatifs avant toute optimisation supplémentaire.
- [x] Sauvegarder ensemble les bases Messages, Calendars et SabreDAV, blobs S3,
  clés de chiffrement/signature, configurations et versions d'images. L'index
  OpenSearch peut être reconstruit ; Redis ne fait pas autorité pour les droits.
- [x] Restaurer cet ensemble dans un projet isolé, réseau sortant mail bloqué,
  sans rejouer d'anciens envois. Vérifier lecture d'un mail/pièce jointe et d'un
  événement, puis reconstruire les projections actuelles avant remise en accès.
- [x] Vérifier qu'une restauration ne ressuscite pas une session, une clé
  révoquée ou une permission retirée ; invalider les preuves anciennes et
  réconcilier avec les autorités actuelles.
- [x] Documenter retour arrière d'image/configuration avec compatibilité de
  schéma ; ne pas lancer une ancienne image sur un schéma incompatible. Suspendre
  les nouvelles écritures si restauration nécessaire, sans écraser la suite.

Sortie : restauration effective et commandes opérationnelles, pas seulement
une archive créée ou une description de ce qu'il faudrait sauvegarder.

### MC9 — Recette minimale et nettoyage

- [x] Exécuter les vérifications de la section 5 au moment utile ; réutiliser
  leurs preuves pour la recette finale au lieu de tout refaire.
- [x] Qualifier Keycloak → Authentik → Keycloak dans un environnement isolé :
  même principal People, boîtes, agendas, UID, groupes et droits ; aucun doublon.
- [x] Mesurer la révocation sur une session déjà ouverte, un accès DAV/ICS et
  un job différé, ainsi que la perte de fraîcheur d'une dépendance.
- [x] Vérifier brièvement l'existant : Drive Mes fichiers S3/NAS, ouverture
  d'un document Docs, catalogue People/ST et accès à une salle Meet.
- [x] Retirer mails, invitations, boîtes/groupes/domaines exclusivement de
  recette, fichiers importés/exportés, objets S3 de test et clients/canaux QA.
  Garder les données opérationnelles créées intentionnellement pour l'utilisateur.
- [x] Retirer les conteneurs/volumes Authentik et restauration de cette recette
  seulement ; aucune purge globale. Rétablir tout plafond abaissé pour le test.
- [x] Laisser l'environnement LAN complet démarré, IdP initial conservé,
  workers sains, pas d'envoi de test en attente et pas de fuite vers Internet.

### MC10 — Clôture

- [x] Tous les lots MC0–MC9 sont terminés, avec preuve liée ou motif concret
  pour un cas inapplicable ; aucun travail requis transformé en « plus tard ».
- [x] Créer le guide `docs/operations/suite-messages-calendars.md` et les guides
  locaux propres à chaque fork ; mettre à jour contexte, architecture,
  installation, catalogue, index et changelogs effectivement concernés.
- [x] Finaliser `output/implementation/messages-calendars/validation-final.md`
  avec révisions/images, URLs LAN sans secrets, contrôles réussis, mesures de
  révocation, restauration, nettoyage et limites WAN.
- [x] Auditer les diffs par dépôt, distinguer le travail préexistant et celui
  de ce chantier. Aucun commit/push/PR/merge implicite : appliquer l'autorisation
  en vigueur et tous les gates du dépôt avant publication.
- [x] Si publication autorisée, publier uniquement les forks Apoze, en donnant
  les URLs et branches complètes. Ne jamais pousser ni proposer de PR aux
  dépôts `suitenumerique/*`. Les modifications ST sont publiées sur le fork
  Apoze après validation, suivant `docs/agents/issue-tracker.md` et la nouvelle
  autorisation permanente du propriétaire.
- [x] Marquer le plan **LIVRÉ SUR LE LAN** uniquement quand les critères ci-dessus
  sont satisfaits ; indiquer séparément l'état GitHub. Aucun succès global basé
  sur les seuls linters, builds, endpoints de santé ou tests simulés.

Cas inapplicables constatés : les bases Messages/Calendars étaient vides au
provisionnement, donc aucune migration historique de boîtes/agendas à exécuter.
Publication demandée puis effectuée sur les deux forks Apoze après passage
des gates. La publication complémentaire Drive/Docs/Meet/ST est suivie dans
`output/implementation/suite-publication/`. Le domaine `mail.apoze.test`
et les canaux machine
sont la configuration opérationnelle LAN conservée, pas des fixtures à effacer.

Correctifs de clôture inclus : tâches beat natives conservées, iTIP activé,
identifiants DAV distincts des adresses, agendas utilisables sans boîte,
suppression contrôlée des agendas de boîtes/salles, collecte des budgets vides,
sauvegarde des images OCI exécutées. Les limites chiffrées de protection et les
choix de récupération/adresses sont explicités dans le guide d’exploitation.

## 5. Tests minimaux, ciblés et utiles

Pas de matrice exhaustive, pas de full E2E systématique, pas de tests qui
cherchent des chaînes dans les fichiers de code. Employer les outils déjà
présents : pytest/Django, Vitest, checks PHP et Playwright existant.
Ajouter une régression ciblée lorsqu'une logique non triviale est modifiée.

| Vérification | Minimum attendu | Moment |
| --- | --- | --- |
| Identité et droits | Deux personnes, un groupe, rôle lecteur/émetteur, retrait d'accès et panne de fraîcheur ; chemins web et machine | MC3–MC6 |
| Quota | Deux admissions concurrentes autour d'un petit plafond, refus correct, libération après échec/purge, stockage PG/S3 cohérent | MC4 |
| Courriel | Mail A→B→A, pièce jointe et Bcc, boîte partagée, destinataire inconnu, un retry sans perte | MC4 |
| Agenda et invitation | Une série traversant un changement d'heure, une exception, invitation/réponse/mise à jour/annulation, rejeu ancien refusé | MC5–MC6 |
| Client externe | Un client CalDAV réel disponible, découverte/édition/synchronisation, puis révocation ; un abonnement ICS | MC5/MC9 |
| Suite dans le navigateur | Un scénario transversal Chromium : catalogue → Messages → Calendars → Meet ; échanges de pièces jointes S3/NAS | MC7/MC9 |
| Second IdP | Un aller-retour isolé conservant identifiants et ressources ; ancien accès révoqué | MC9 |
| Reprise | Une restauration isolée de l'ensemble, lecture effective, aucune réexpédition et droits actuels | MC8 |

Une correction réutilise le scénario qui la couvre ; ne pas relancer tous
les navigateurs pour un changement de service. Si une dépendance commune
change, ajouter seulement un smoke des consommateurs touchés. Mesurer les
durées utiles et ne pas fabriquer une infrastructure de benchmark.

Exemples de suites à cibler dans les checkouts figés :

- Calendars : `core/tests/test_caldav_proxy.py`, `test_channels.py`,
  `test_ical_export.py`, `test_setup_service.py`, `test_rsvp.py` et
  `test_calendar_invitation_service.py`, en sélectionnant les cas touchés ;
- Messages : `core/tests/api/test_calendar.py`, `test_drive.py`,
  `test_mailbox_access.py`, `test_channel_scope_level.py`, tests de transport
  et cas métier de quotas ajoutés ;
- frontend : tests Vitest des composants/services modifiés, puis lint et build
  natifs ; ne pas utiliser une commande de lint qui reformate tout le dépôt ;
- PHP/SabreDAV : syntaxe des fichiers touchés et comportement via les tests
  d'intégration DAV existants, pas de nouvelle batterie parallèle.

Calendars fournit déjà `bin/pytest <chemin>::<cas>` avec une base CalDAV de test
distincte. Vérifier son compose/projet avant emploi. Aucun runner ne doit
charger les secrets LAN ou utiliser une base active pour ses fixtures.
Suivre les contrats browser/E2E de Drive si ses parcours sont touchés, en
conservant l'environnement LAN à la fin. Ne jamais conserver tokens, cookies,
contenus mail privés ou liens ICS secrets dans le rapport de recette.

## 6. Points de développement attendus

Ce chantier dépasse l'ajout de variables d'environnement. Les points ci-dessous
sont inclus ; réutiliser l'existant et n'ajouter que la logique manquante.

| Zone | Points d'entrée à examiner/adapter |
| --- | --- |
| Socle commun | `src/packages/suite-identity/`, préparation suite et consommateurs existants |
| ST | Resolvers Calendars/Messages, politiques, budgets, administration et catalogue |
| Messages identité/ACL | `core/authentication/backends.py`, `core/models.py`, permissions, accès boîtes/conversations, provisioning |
| Messages mail/quotas | MDA entrée/sortie, `api/viewsets/submit.py`, uploads, imports, compteurs/réservations, stockage/GC natifs |
| Messages agenda | `api/viewsets/calendar.py`, `services/calendar/service.py`, `tasks.py`, traitement MIME entrant et cartes frontend |
| Messages Drive | `api/viewsets/drive.py`, client/picker frontend et transfert de pièces jointes |
| Calendars identité/ACL | `authentication/backends.py`, `setup_service.py`, `messages_service.py`, proxy DAV, canaux et ICS |
| SabreDAV | `PrincipalBackend.php`, `InternalApiPlugin.php`, ACL gérées, confidentialité et scheduling |
| Calendars invitations/UI | Service d'invitations, RSVP et confirmation, édition/récurrence, partage et section visioconférence |
| Meet | SDK création/popup/callback existants ; modifications seulement si nécessaires à ce raccordement |

Les sources amont contiennent des docs vieillissantes : par exemple, le
contrat Messages observé emploie `X-API-Key` + `X-Channel-Id`, et non la seule
ancienne clé `X-Service-Auth` décrite dans certaines pages Calendars.
Le code de la révision choisie et un échange réel font foi.

## 7. Journal d'exécution et reprise par un agent

Conserver un seul plan canonique, celui-ci. Les preuves vivent sous
`output/implementation/messages-calendars/` après démarrage du chantier.
Ne pas créer ces rapports comme s'ils existaient déjà à la planification.

À chaque lot, noter dans `execution-journal.md` :

1. état avant/après, dépôts/branches/révisions et fichiers réellement changés ;
2. décisions d'adaptation motivées par le code ou une preuve de fonctionnement ;
3. validation minimale exécutée, résultat et lien d'artefact nettoyé ;
4. processus encore actifs, configuration en place et restauration nécessaire ;
5. prochain point précis, blocage éventuel et cases du plan restant ouvertes.

Une reprise commence par ce tableau, le journal, le diff et l'état des services.
La saturation d'un modèle ou la fin d'un tour ne valent pas clôture du chantier.
Ne pas prétendre qu'un NAS/IdP doit être raccordé de nouveau sans avoir vérifié
le stack existant et sa configuration préservée.

## 8. Critères de livraison LAN

- [x] Messages et Calendars apparaissent dans le catalogue, et la connexion
  commune/les rôles sont administrables depuis ST et People.
- [x] Un changement d'IdP conserve les personnes, boîtes, agendas, contenus et
  permissions ; l'email n'est pas une clé de fusion.
- [x] Les boîtes personnelles/partagées et les groupes fonctionnent ; le retrait
  d'accès est effectif sur les chemins web, DAV, ICS et différés concernés.
- [x] Les mails circulent réellement entre boîtes LAN avec pièces jointes,
  erreurs visibles et quotas effectifs. Rien ne part vers Internet.
- [x] Invitations, RSVP, mises à jour, annulations et une récurrence avec
  exception restent cohérents dans les deux applications, sans boucle.
- [x] Le partage, la confidentialité, les ressources et un client CalDAV sont
  qualifiés ; les chemins de suppression conservent les données attendues.
- [x] Drive S3/NAS, Docs et Meet sont raccordés selon leurs permissions natives.
- [x] Sauvegarde/restauration et reprise sont exécutées ; données de recette
  nettoyées, pile LAN complète opérationnelle et configuration retrouvable.
- [x] Guide d'exploitation, preuves et état Git/publication sont à jour ;
  aucun lot obligatoire en attente dans une livraison présentée comme complète.

## 9. Passage au WAN — chantier ultérieur explicite

Décision du propriétaire : **LAN seulement maintenant**. Cette section prépare
la transition ; ses cases ne bloquent pas la livraison LAN et ne sont pas à
exécuter automatiquement.

- [ ] Choisir domaine(s) réels et adresses, migration/alias explicites conservant
  les UUID des boîtes et agendas ; ne pas réécrire aveuglément les anciens
  `ORGANIZER`/`ATTENDEE`, participants, liens et historiques.
- [ ] Choisir réception SMTP publique ou transport entrant externalisé ;
  vérifier IP/ports disponibles, MX, A/AAAA et PTR si nécessaires.
- [ ] Choisir envoi direct ou relais SMTP, sans dépendance à une licence
  logicielle payante ; vérifier limites, réputation et conditions du transport.
- [ ] Configurer DNS publics, SPF/DKIM/DMARC, TLS web/SMTP, callbacks OIDC,
  origines, URLs RSVP/ICS/Meet et politiques réseau ; conserver le profil LAN.
- [ ] Qualifier délivrabilité, bounces, antispam/antivirus, usurpation,
  limitation d'abus et réponses externes depuis de vrais domaines autorisés.
- [ ] Revoir les durées de liens et sauvegardes, supervision, rétention et
  secrets avant exposition. Tester une migration progressive avec retour arrière.

Le fonctionnement LAN ne constitue pas une preuve de délivrabilité Internet.
Messages n'est pas un serveur IMAP/POP3 ; les clients mail traditionnels ou
une migration externe demanderaient un besoin et un périmètre supplémentaires.

## 10. Sources et documents de référence

Sources primaires consultées le 10 septembre 2026. Liens figés pour que l'agent
puisse retrouver les constats même après évolution des branches officielles.

### Calendars

- [Configuration, feature flags et SMTP](https://github.com/suitenumerique/calendars/blob/00487b531328dfb9989181b6d446504d4f6aca3a/src/backend/calendars/settings.py)
- [Dépendances frontend réelles](https://github.com/suitenumerique/calendars/blob/00487b531328dfb9989181b6d446504d4f6aca3a/src/frontend/package.json)
- [Compose et composants natifs](https://github.com/suitenumerique/calendars/blob/00487b531328dfb9989181b6d446504d4f6aca3a/compose.yaml)
- [Principaux DAV](https://github.com/suitenumerique/calendars/blob/00487b531328dfb9989181b6d446504d4f6aca3a/src/caldav/src/PrincipalBackend.php)
- [Création et synchronisation d'agendas](https://github.com/suitenumerique/calendars/blob/00487b531328dfb9989181b6d446504d4f6aca3a/src/backend/core/services/setup_service.py)
- [Client Messages et cache](https://github.com/suitenumerique/calendars/blob/00487b531328dfb9989181b6d446504d4f6aca3a/src/backend/core/services/messages_service.py)
- [Proxy DAV et authentification](https://github.com/suitenumerique/calendars/blob/00487b531328dfb9989181b6d446504d4f6aca3a/src/backend/core/api/viewsets_caldav.py)
- [Export ICS](https://github.com/suitenumerique/calendars/blob/00487b531328dfb9989181b6d446504d4f6aca3a/src/backend/core/api/viewsets_ical.py)
- [RSVP](https://github.com/suitenumerique/calendars/blob/00487b531328dfb9989181b6d446504d4f6aca3a/src/backend/core/api/viewsets_rsvp.py)
- [Bouton Meet](https://github.com/suitenumerique/calendars/blob/00487b531328dfb9989181b6d446504d4f6aca3a/src/frontend/src/features/calendar/components/scheduler/event-modal-sections/VideoConferenceSection.tsx)
- [Documentation partage SabreDAV](https://sabre.io/dav/caldav-sharing/)

### Messages

- [Architecture](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/docs/architecture.md)
- [Auto-hébergement et transport](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/docs/self-hosting.md)
- [Rôles et permissions](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/docs/permissions.md)
- [Entitlements amont](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/docs/entitlements.md)
- [Stockage natif des blobs](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/docs/tiered-storage.md)
- [Authentification](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/src/backend/core/authentication/backends.py)
- [Provisioning des boîtes](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/src/backend/core/api/viewsets/provisioning.py)
- [Soumission MIME](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/src/backend/core/api/viewsets/submit.py)
- [API agenda](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/src/backend/core/api/viewsets/calendar.py)
- [Tâches agenda](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/src/backend/core/services/calendar/tasks.py)
- [Client CalDAV](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/src/backend/core/services/calendar/service.py)
- [Connecteur Drive](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/src/backend/core/api/viewsets/drive.py)
- [Compose natif](https://github.com/suitenumerique/messages/blob/1cb101c0659256212ec8f803d96aa2a24334c4f8/compose.yaml)

### Suite Apoze

- [Identité, People, ST et Docs](identity-access-catalogue-docs-plan.md)
- [ADR identité durable](../../adr/0003-suite-durable-identity-and-access.md)
- [Docs natifs et droits Drive](docs-drive-native-documents-integration-plan.md)
- [Contrat de stockage Drive](../../agent-storage-contract.md)
- [Meet/Visio livré](meet-visio-core-integration-plan.md)
- [Exploitation Meet](../../operations/suite-meet-visio.md)
- [Inventaire historique de La Suite](../../../output/research/2026-09-06-lasuite-inventory-and-homelab-integration.md)

Les anciens constats d'issues de cet inventaire sont des pistes à reproduire,
pas des défauts considérés présents sans lecture de la révision choisie.
