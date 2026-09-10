# Socle commun d’identité, d’accès et de catalogue — Drive, ST, People et Docs

Date : 6 septembre 2026.
Statut : **livré et qualifié localement le 8 septembre 2026**.
Bilan : [validation finale V1–V12](../../../output/implementation/suite-identity-access-catalogue/validation-final.md).
Périmètre : premier chantier d’intégration de la suite Apoze.

Ce document est la référence de l’agent chargé d’exécuter le chantier de A à Z.
L’utilisateur a autorisé l’exécution complète de ce plan. Suivre les lots
et conserver leurs preuves. Le suivi courant est conservé dans le dépôt
Drive de travail principal, sous
`output/implementation/suite-identity-access-catalogue/current-status.md`. Un lot commencé ou seulement configuré n’est pas un lot livré.

Lecture de reprise : [décisions](#3-décisions-darchitecture-à-appliquer),
[migration](#4-migration-des-données-existantes),
[lots](#5-lots-dexécution-et-critères-de-sortie),
[validation](#6-validation-minimale-fondée-sur-le-comportement),
[clôture](#10-définition-de-terminé).

## 1. Résultat attendu et périmètre

L’utilisateur se connecte avec le fournisseur d’identité choisi, ouvre Drive,
People et Docs depuis le catalogue et retrouve les accès qui lui ont été
accordés. Un administrateur peut gérer les équipes, l’accès aux applications
et les quotas dans les interfaces prévues. Le changement d’IdP conserve les
comptes applicatifs, propriétaires, fichiers, documents, espaces et droits.

Le chantier doit livrer :

1. Une identité interne durable, indépendante de l’email et de l’IdP.
2. People comme source initiale des groupes, avec correspondances explicites
   vers les groupes et droits déjà présents dans les applications.
3. Un mode optionnel d’import des utilisateurs et groupes d’un annuaire
   externe, qualifié avec SCIM 2.0 et Authentik ; le mode People reste le défaut.
4. Les contrats de rôles, d’organisation, de suspension et de révocation,
   appliqués côté serveur et aux sessions déjà ouvertes.
5. Drive et ST raccordés sans perdre leurs données ni leur configuration.
6. People et Docs installés de façon persistante et utilisables sur le LAN.
7. Une connexion commune et une navigation locale entre les applications.
8. Une qualification isolée Keycloak → Authentik → Keycloak, avec conservation
   des identifiants et vérification des refus d’accès.
9. Une procédure de sauvegarde, restauration, bascule et reprise réellement
   exercée sur un petit jeu de données.

La configuration des groupes, correspondances, droits applicatifs et
suspensions doit être utilisable depuis le Web. Les secrets des clients OIDC,
le DNS, TLS et le déploiement restent des opérations d’installation documentées,
avec les interfaces d’administration de l’IdP et les fichiers privés existants.
Ce plan ne promet pas un orchestrateur Docker entièrement administrable dans ST.

### Frontières avec les chantiers suivants

Docs conserve ses documents natifs, sa coédition et ses ACL. Ce chantier livre
son usage autonome intégré au SSO, aux groupes et au catalogue. Il ne déplace
pas les documents Docs dans les espaces Drive et ne remplace pas Collabora ou
ONLYOFFICE. La délégation complète du classement et des ACL Docs à Drive, les
exports interapplications, Grist, Messages, Meet et Find restent les lots
suivants de la feuille de route.

Ne pas utiliser ici le sélecteur Drive qui publie une source privée, ni intégrer
les prototypes Docs/Drive par anticipation. Ces travaux et leurs limites sont
décrits dans [l’inventaire de la suite](../../../output/research/2026-09-06-lasuite-inventory-and-homelab-integration.md).
Les budgets Drive/ST existants sont préservés. Un quota dynamique partagé entre
toutes les applications et le contrôle exhaustif des écritures Docs ne sont
pas livrés par le seul raccordement d’identité.

## 2. Point de départ vérifié

Inspection du code local et des sources officielles le 6 septembre 2026 ;
les constats ci-dessous ne constituent pas une nouvelle recette fonctionnelle.

| Élément | Existant | Conséquence pour ce chantier |
| --- | --- | --- |
| Environnement | 16 services Drive et 6 services ST démarrés lors de la rédaction | Préserver leurs données et leurs services ; ajouter People/Docs séparément. |
| Démarrage | `bash run_env_local.sh` pour Drive ; `make start` dans ST | Garder le script Drive dans son périmètre actuel. |
| Identité actuelle | Keycloak Drive et Keycloak ST distincts | Deux connexions valides ne constituent pas un SSO commun ; raccorder progressivement ST au même issuer que Drive. |
| Comptes Drive | UUID local ; `User.sub` unique ; rapprochement email configurable | Ajouter les associations externes sans recréer les utilisateurs. |
| Comptes ST | Lookup par `sub` ou email ; comptes de métriques distincts des utilisateurs administrateurs | Migrer les deux catégories et leurs références, pas seulement le login ST. |
| Quotas Drive → ST | `account_id` alimenté par `user.sub` | Stabiliser cette clé et conserver exceptions, compteurs et historique du même compte ST. |
| Groupes Drive | Groupes Django ; `User.teams` renvoie `group:<pk>` | Conserver ces clés et ajouter une correspondance vers People. |
| People | `User`, `Organization`, `Team`, `TeamAccess`, `ServiceProvider`, API d’équipes | Réutiliser ces modèles ; distinguer membership réel et visibilité d’ancêtres. |
| Identité de groupe People | `Team.external_id`, UUID destiné aux synchronisations | L’utiliser comme clé interapplications ; ne pas le confondre avec le `externalId` fourni par un annuaire SCIM. |
| SCIM People | Lecture `/resource-server/v1.0/scim/Me/` ; mécanismes de webhooks sortants | Ce n’est pas un serveur complet de provisioning entrant Users/Groups ; une extension ciblée est nécessaire. |
| Docs | OIDC, documents/ACL par utilisateur ou équipe, collaboration Yjs/Hocuspocus | Dans le code inspecté, `User.teams` renvoie `[]` ; le raccordement des groupes reste à implémenter. |
| Collaboration Docs | Contrôle d’accès à la connexion WebSocket et mécanismes de réinitialisation | Auditer puis compléter la révocation pendant une connexion ouverte. |
| Catalogue | Gaufre v2 dans Drive ; `lagaufre/services` public dans ST | Réutiliser le catalogue et séparer données publiques et état d’accès personnel. |

Repères locaux de lecture avant modification :

- Drive : `src/backend/core/models.py`, `core/authentication/`,
  `core/api/permissions.py`, `core/entitlements/backends/deploycenter.py`,
  serializers de métriques, `core/services/storage_access.py`,
  `core/services/storage_spaces.py`, `src/backend/drive/settings.py`.
- Drive Web : `features/ui/components/gaufre/Gaufre.tsx`, configuration
  frontend, pages d’administration et sélecteurs de bénéficiaires existants.
- ST, dans `/root/Apoze/st-deploycenter` : `core/models.py`,
  `core/authentication/backends.py`, `core/api/viewsets/entitlements.py`,
  `core/entitlements/resolvers/`, `core/api/viewsets/lagaufre.py`, interface
  d’administration des organisations, services, comptes et quotas.
- People et Docs : chemins et commits officiels en section 12. Ils ne sont
  pas encore des installations locales au moment de la rédaction.

Les fichiers Drive/ST comportent des modifications locales du chantier
stockage, dont certaines ne sont pas suivies par Git. Elles appartiennent au
point de départ à sauvegarder. La branche de rédaction
`codex/plan-suite-identity-people-docs` ne représente pas à elle seule une
livraison propre du chantier précédent.

Les [espaces unifiés](../storage/unified-storage-spaces-plan.md) ont déjà été
qualifiés sur [l’environnement réel local](../../../output/implementation/unified-storage-spaces/local-environment-validation.md).
Le [nettoyage Docker](../../../output/operations/2026-09-06-docker-cleanup.md)
est terminé : environ 151 Go récupérés et 239 Go disponibles au relevé.
Relever à nouveau capacité et services au démarrage ; ne pas relancer un prune.

## 3. Décisions d’architecture à appliquer

### 3.1 Responsabilités et identifiants durables

| Entité | Autorité et identifiant | Règle |
| --- | --- | --- |
| Personne de la suite | People, UUID du `User` existant | Identifiant `principal_id` durable ; aucune seconde table de personnes si ce modèle suffit. |
| Compte applicatif | Chaque application, sa clé primaire existante | Association unique au principal People, sans réécrire les propriétaires et ACL. |
| Identité de connexion | Association vérifiée `(issuer, subject)` vers un principal | Plusieurs associations possibles pour une personne, jamais une même association pour deux personnes. |
| Client OIDC | Enregistrement propre à chaque application | Audiences, callback et secret distincts ; le client ne devient pas l’identité humaine. |
| Organisation de la suite | UUID ST existant | Correspondance explicite vers `People.Organization` et les apps ; SIRET facultatif en homelab. |
| Groupe | `People.Team.external_id` | Nom modifiable ; identité et permissions indépendantes du nom. |
| Groupe Drive | Clé Django actuelle | Table de correspondance People → groupe local ; conserver `group:<pk>` dans les grants. |
| Droit sur une ressource | Application propriétaire | Ni l’IdP, ni un groupe seul, ni une vignette de catalogue ne donnent automatiquement ce droit. |
| Budget | ST pour la politique, Drive pour les écritures et compteurs | Une suspension ou un changement d’IdP ne libère pas la consommation existante. |

People fournit ici l’annuaire commun, pas un nouvel IdP. Ne pas activer son
mode d’authentification Mailbox, installer Accounts/Menshen ou imposer Keycloak
comme intermédiaire pour faire fonctionner ce contrat.

Les applications conservent leurs bases séparées. Les identifiants People/ST
qu’elles référencent ne sont pas des clés étrangères SQL entre bases. Les
associations, versions et contrôles de cohérence sont portés par les services
existants. Aucun nouveau microservice d’identité ni moteur universel de rôles.

Éviter une dépendance circulaire de démarrage : les API machine de
synchronisation sont autorisées par leurs credentials et périmètres propres,
sans exiger une session utilisateur ni appeler en retour la politique qu’elles
sont en train de synchroniser. Le bootstrap et les comptes de secours restent
utilisables quand une projection n’est pas encore initialisée.

### 3.2 Connexion et correspondance des personnes

Réutiliser les clients OIDC et bibliothèques des projets. Ajouter uniquement
les points manquants de validation, de résolution d’identité et de session.

- Issuer exact issu d’une configuration approuvée, discovery, algorithmes
  autorisés, signature/JWKS, audience et `azp` lorsqu’applicable, `exp`, nonce,
  state, PKCE S256 et redirections exactes. Contrôler aussi la concordance
  `sub` entre ID token et UserInfo. Ne jamais découvrir un issuer arbitraire
  fourni par le navigateur ou décoder un JWT sans validation.
- Les `sub` sont opaques. Ne pas appliquer à de nouvelles associations la
  regex restrictive historique de `User.sub`, ni normaliser leur casse.
  Ne pas utiliser un ID token comme jeton d’accès à une autre application.
- Garder séparés `principal_id`, UUID utilisateur local, issuer et subject.
  Un ancien `sub` n’est plus la clé de propriété ou de quota interapplications.
- Désactiver le rapprochement automatique par email pour les flux du socle.
  L’email reste un attribut de contact, y compris lorsqu’il est vérifié.
  Un changement d’adresse met à jour cet attribut, sans déplacement de données.
- Une collision d’identité ou deux comptes portant le même email produisent
  un conflit administrable ; jamais une fusion automatique. La procédure
  historique de réconciliation de comptes n’est pas une migration d’IdP.

**Cas des subjects différents selon le client.** OIDC autorise les subjects
pairwise. Chaque application peut donc recevoir un `sub` différent pour la
même personne. Résoudre ce cas par une correspondance explicite enregistrée
dans People et répliquée à l’application concernée :

1. Pour les comptes existants, importer une table de correspondance auditée
   entre identités vérifiées et comptes applicatifs, puis valider les lignes.
2. Pour les nouveaux comptes, utiliser un identifiant d’annuaire stable
   uniquement lorsqu’il est émis par une source approuvée, configuré par issuer
   et relié au principal préprovisionné. Il ne peut pas contredire une liaison
   déjà enregistrée ni provenir d’un attribut modifiable par l’utilisateur.
3. Sans identifiant transversal fiable, recueillir le login OIDC vérifié en
   demande de rattachement, puis faire valider l’association dans People.
   L’utilisateur ne reçoit pas de droits avant cette validation.

Ainsi, le mode générique fonctionne sans claim propriétaire obligatoire.
Le provisioning peut automatiser les associations lorsqu’une preuve stable
existe. Un `externalId` SCIM ne doit jamais être supposé égal au `sub` OIDC.
Tester aussi deux issuers ayant le même `sub`, et un même issuer avec subjects
distincts selon les clients. [OIDC : stabilité et types de subjects](https://openid.net/specs/openid-connect-core-1_0.html#ClaimStability).

Pour cette installation, utiliser initialement l’issuer Keycloak déjà utilisé
par Drive comme fournisseur commun. Enregistrer des clients distincts pour
People, Docs et ST. Le compte administrateur ST actuel doit être relié au
principal approprié avant de changer son issuer. Si la même personne possède
deux anciens comptes, la preuve de correspondance est obligatoire.
Conserver la base et la configuration de l’ancien Keycloak ST pour la reprise ;
son décommissionnement n’est pas un prérequis à la clôture de ce chantier.

### 3.3 Organisations, groupes et rôles

En homelab, le rattachement initial utilise l’organisation ST existante et une
association explicite dans People. Ne pas inventer un SIRET, déduire des droits
administrateur du domaine email ou changer d’organisation à chaque login à
partir d’un claim non gouverné. Une modification du rattachement est une
opération administrative avec aperçu d’impact ; elle ne transfère pas les
contenus ni leur imputation comptable implicitement.

People reste la source de membership. Chaque groupe est publié seulement aux
applications autorisées via les mécanismes `ServiceProvider` existants.
Les noms sont affichés ; les UUID sont utilisés pour les décisions.

- Reprendre les groupes Django présents dans Drive, leurs membres et leurs
  grants. Créer/associer un groupe People et conserver la clé Django actuelle.
- Après transfert d’autorité, les adhésions de ces groupes sont gérées dans
  People. Les écrans Drive permettent de sélectionner ces groupes et consulter
  leur source, sans créer une seconde liste de membres concurrente.
- Les groupes Django purement techniques, permissions Django et superusers
  restent locaux tant qu’ils n’ont pas été explicitement associés.
- Les groupes People peuvent être arborescents, mais la visibilité d’un parent
  n’est pas une adhésion à celui-ci. Le contrat initial utilise les adhésions
  explicites `TeamAccess`. Les parents servent à la présentation ; aucun droit
  hérité n’est inventé à partir de l’arbre.
- Les groupes imbriqués externes non pris en charge doivent être refusés ou
  signalés comme non importables avant activation. Ne pas les aplatir en
  attribuant des accès plus larges. Le profil SCIM livré porte des membres users.

| Rôle ou action | Gestion | Effet autorisé |
| --- | --- | --- |
| Administrateur technique | Compte local de secours et administration de chaque app | Maintenance explicite ; jamais déduit d’un groupe IdP nommé « admin ». |
| Administrateur d’organisation | ST pour les services/budgets ; People pour l’annuaire, avec mapping explicite | Administration limitée à l’organisation concernée. |
| Propriétaire/administrateur d’équipe | People, rôles natifs de `TeamAccess` | Gestion de l’équipe ; n’accorde pas la propriété des documents de ses membres. |
| Bénéficiaire d’application | Politique ST, attribution utilisateur/groupe | Peut entrer dans l’application si son compte est actif. |
| Lecteur/éditeur/propriétaire de contenu | ACL natives Drive ou Docs | Accès au périmètre de ressource concerné. |

Les grants de contenu gardent leurs règles actuelles de cumul. Le retrait d’un
groupe retire uniquement les droits obtenus par ce groupe : un droit individuel
indépendant peut rester. La suspension globale ou le refus d’accès ST prime
sur les grants de contenu et interdit l’accès authentifié à l’application.
Pas de transposition automatique d’un rôle People en `is_staff`/`is_superuser`.

### 3.4 Import optionnel d’un annuaire externe

Livrer deux modes, sélectionnables par groupe/source :

- **People** : gestion des membres dans People, mode initial de l’installation.
- **Annuaire externe** : utilisateurs et membership importés dans People via
  une source SCIM 2.0 authentifiée ; les champs gouvernés sont en lecture seule
  dans People. Les ACL et quotas restent gérés par ST/les applications.

Réutiliser les serializers, erreurs SCIM et modèles People existants. Compléter
un profil entrant Users/Groups documenté, sans réimplémenter un IdP. Le profil
doit exposer les opérations effectivement nécessaires au client qualifié :
discovery des capacités et schémas, lecture unitaire/liste paginée, filtres
`eq` utiles, création, remplacement/PATCH de profil et membership, désactivation
`active=false` et suppression logique. Les réponses, codes d’erreur, unicité,
conflits et limitations suivent SCIM ; ne pas annoncer Bulk, filtrage général
ou groupes imbriqués s’ils ne sont pas implémentés.

Conserver une correspondance unique `(source_id, type, externalId)` vers le
principal/groupe People. Le `id` retourné par People est stable ; le nom et
l’email ne sont pas des clés de rapprochement. Une source ne peut modifier ni
un autre annuaire, ni les groupes locaux, ni les rôles d’administration.
La désactivation suspend l’identité dans le périmètre prévu ; aucune suppression
SCIM ne supprime les fichiers, budgets ou journaux des applications.

Le passage d’un groupe People à un groupe importé exige simulation, association
à un identifiant externe précis et validation de l’écart de membres. Il conserve
l’UUID People et tous ses grants. Le retour à une gestion People est lui aussi
explicite, conserve les membres observés et bloque les écritures de l’ancienne
source. Aucun mélange implicite de deux autorités dans le même membership.

Authentik fournit un provider SCIM sortant, distinct de son provider OIDC.
L’utiliser pour la recette du mode externe, avec un jeton technique propre à
cette source ; ne pas dépendre de son API d’administration dans le code métier.
[Authentik SCIM](https://docs.goauthentik.io/add-secure-apps/providers/scim/),
[protocole SCIM 2.0](https://www.rfc-editor.org/rfc/rfc7644.html).

### 3.5 Synchronisation et échanges entre services

People distribue aux consommateurs leur projection autorisée : principal,
organisation, statut, groupes publiés, version et date de fraîcheur. Chaque
application conserve une projection locale pour les contrôles ordinaires.
Réutiliser DRF, PostgreSQL, cache et Celery déjà présents. Pas d’appel distant
par fichier, par groupe ou par ligne d’explorateur.

Le chemin de fiabilité initial est une réconciliation périodique paginée,
avec intervalle de **30 secondes** et pages bornées à **200 entités** par
défaut. Les webhooks existants peuvent accélérer le rafraîchissement ; ils ne
sont pas la seule preuve qu’un retrait a été reçu. Ne pas dépendre de leurs
retries synchrones pour bloquer une modification People.

- API de lecture interservice versionnée et limitée à l’organisation et au
  `ServiceProvider` du consommateur ; étendre la surface existante lorsque ses
  permissions conviennent, sinon créer une action étroite dans People.
- Authentification machine dédiée par consommateur, secret stocké hors Git,
  rotation et révocation individuelles. Réutiliser les mécanismes existants,
  en ajoutant la restriction d’audience/périmètre nécessaire. Un secret de
  synchronisation n’autorise aucune usurpation générale d’utilisateur.
- Écritures locales atomiques, idempotentes, avec ordre/version contrôlés.
  Un ancien message ne peut pas réactiver un membre retiré plus récemment.
- Lecture complète et cohérente avant d’appliquer les retraits déduits d’une
  absence. Une erreur réseau ou une page manquante ne vaut pas liste vide.
  Vérifier la révision avant/après pagination ; reprendre si elle a changé.
- Incrémenter la révision sur tous les chemins concernés : UI, API, SCIM,
  admin et import. Les suppressions conservent une trace suffisante pour les
  consommateurs ou sont déduites d’un snapshot complet validé.
- Ne pas prolonger la fraîcheur à partir du cache local, d’un retry ou d’un
  événement partiel. Seule une vérification complète autorisée la renouvelle.
- Indexer les clés de correspondance et les requêtes de membership ; charger
  les relations en lots. Éviter un scan complet à chaque requête web.

Ce mécanisme doit traiter également les utilisateurs sans session ouverte.
Les claims de groupes d’un ancien jeton ne peuvent pas restaurer un membership
révoqué dans People. Les organisations non visibles au consommateur restent
inaccessibles, y compris par modification d’un identifiant dans l’URL.

### 3.6 Révocation, sessions et indisponibilité

Le délai contractuel commence à l’enregistrement de la décision par son
autorité, et les horodatages suivants doivent être distingués : changement à
l’IdP, réception dans People, application dans chaque service, refus constaté.

| Événement | Contrat du chantier |
| --- | --- |
| Retrait de groupe, suspension dans People ou désactivation d’accès dans ST | Refus des nouvelles opérations concernées dans les quatre apps sous **120 secondes maximum**, sessions ouvertes incluses ; objectif courant 30 secondes. |
| Source People/ST indisponible | Dernière décision positive utilisable au plus **90 secondes** depuis sa dernière vérification autoritative. Ensuite refus temporaire des opérations privées dépendantes ; aucun accès élargi. |
| Révocation du compte directement dans un annuaire avec provisioning | Délai de livraison externe + délai People → applications. Mesurer les deux ; ne pas annoncer 120 secondes depuis l’IdP si son provisioning ne le garantit pas. |
| IdP compatible OIDC uniquement, sans notification de désactivation | Refus aux prochaines authentifications. Borne de réauthentification applicative de **15 minutes** par défaut, sans renouvellement indéfini depuis la seule session locale. |
| Déconnexion de cette application | Session locale immédiatement invalidée. |
| Déconnexion de la suite / révocation administrative des sessions | Invalidation d’un compteur de session du principal et des sessions de chaque app sous 120 secondes ; logout IdP standard en complément s’il est disponible. |

La durée de réauthentification de 15 minutes est une proposition de sécurité
configurable, à qualifier avec `auth_time`/`max_age` et les capacités réelles
du fournisseur. Si celui-ci ne permet pas une nouvelle preuve d’authentification
valide, refuser de prolonger la session. Un refresh token renouvelable n’est
pas, à lui seul, une preuve que le compte n’a pas été désactivé.
Les fournisseurs sans événement de provisioning ne peuvent pas garantir une
révocation immédiate indépendante de leurs capacités. La suspension People
reste le contrôle d’urgence commun, quel que soit l’IdP.

Implémentation nécessaire :

- La session contient une association à un principal et une version de session,
  pas une copie définitive des groupes. Les décisions sont relues dans la
  projection locale et ses bornes de fraîcheur à chaque opération protégée.
- Le statut effectif combine suspension People, statut local, accès ST et
  permission de ressource. Un refresh de profil ne réactive aucun compte
  désactivé localement. Les comptes de secours restent une voie distincte.
- Les backends API, resource server, WebSocket et workers appliquent les mêmes
  conditions. Aucun middleware web seul ne suffit.
- Docs réévalue les connexions actives : passage éditeur → lecteur, retrait
  complet, suspension et accès ST. Fermer/refuser la connexion au plus tard à
  l’échéance et empêcher l’application de nouvelles opérations Yjs après
  révocation ; préserver les écritures déjà acceptées avant cette échéance.
- Drive réévalue aussi les accès WOPI et les tâches longues avant publication.
  Les transferts révoqués suivent leur journal de reprise ; une annulation ne
  doit ni supprimer la seule copie existante, ni publier une écriture interdite.
- Une URL privée signée doit expirer au plus tard à la fin de l’autorisation
  fraîche dont elle dérive : pas de cumul « 90 secondes de cache + longue URL ».
  Vérifier les renouvellements et caches edge. Les flux restent streamés.
- Invalider les anciens cookies/jetons applicatifs lors de la bascule d’IdP.
  Une déconnexion commune ne repose pas seulement sur un changement de page.

Si l’IdP ne fournit pas de logout global, la déconnexion de la suite invalide
quand même ses sessions applicatives et exige une nouvelle authentification
pour les rouvrir ; l’interface précise que la session chez le fournisseur peut
subsister. Ne pas afficher un succès de déconnexion de l’IdP non confirmé.

Limites explicites : des octets déjà téléchargés ne sont pas récupérables ;
une réponse de téléchargement déjà autorisée peut finir son flux. Les requêtes
suivantes, les nouvelles lectures Range et les nouvelles écritures sont
contrôlées. Les liens publics sont un droit autonome : retirer un membre ne
rend pas automatiquement privé un contenu publié. Préserver cette sémantique
et tester séparément le retrait du lien public.

Un refus d’accès confirmé doit se distinguer d’une impossibilité temporaire de
vérifier les droits. Afficher une explication et une possibilité de réessai,
sans boucle de connexion, liste vide trompeuse ou suppression des données.

### 3.7 Catalogue et administration Web

| Action administrative | Interface cible |
| --- | --- |
| Créer/modifier une équipe, gérer ses membres, choisir ses applications destinataires | People, écrans d’équipe existants complétés. |
| Associer des identités, traiter un conflit, suspendre un principal, révoquer ses sessions | People, vues d’administration ciblées avec contrôle du périmètre. |
| Configurer une source d’annuaire, voir les imports/erreurs et transférer l’autorité d’un groupe | People ; secrets masqués, jamais renvoyés dans une liste API. |
| Activer Drive/Docs/People pour l’organisation, attribuer l’accès à un compte/groupe | ST, extension des écrans de services et comptes existants. |
| Administrer les quotas Drive et contrôler leur application | ST, écrans existants et mêmes comptes durables. |
| Attribuer un groupe à un espace/dossier | Drive, administration actuelle des espaces/grants. |
| Partager un document à un groupe | Docs, dialogue de partage natif raccordé aux groupes publiés. |
| Comprendre un accès ou un refus | App concernée : état synthétique ; People/ST : source, révision, dernière synchronisation et motif détaillé autorisé. |

Réutiliser Gaufre v2 et `lagaufre/services`. Le catalogue public ne doit exposer
que les informations prévues pour publication. Si une visibilité personnalisée
est nécessaire, fournir une projection authentifiée depuis le backend de
l’application ; ne pas ajouter groupes, emails ou quotas dans l’endpoint public
avec CORS `*`. L’organisation homelab doit être résolue par UUID sans SIRET.

Configurer les URLs LAN de Drive, ST, People et Docs et les liens de retour.
Une vignette de service actif peut rester visible avec un état « accès non
attribué » ; le serveur reste l’autorité. L’accès direct à une URL interdite
doit échouer même si la Gaufre est contournée. Héberger localement les ressources
de navigation nécessaires pour éviter une dépendance obligatoire à un widget
ou un catalogue de démonstration externe. Garder le style UI actuel et
l’accessibilité clavier des menus, formulaires et erreurs.

### 3.8 Déploiement et intégrité de l’environnement

Conserver les scripts, données et origines Drive/ST actuels. Ajouter les
checkouts People et Docs sous `/root/Apoze/people` et `/root/Apoze/docs` lors
de l’exécution, après vérification de l’absence d’un checkout existant.
Leurs overrides de déploiement restent proches de leurs applications ; le
plan et les preuves transversales restent dans ce dépôt Drive.

- Choisir des versions stables puis figer commits, images et dépendances.
  L’inventaire indique People `v1.25.4` stable (`v1.26.0` préversion) et Docs
  `v5.6.1` ; la lecture de code a porté sur les commits listés en section 12.
  Vérifier les écarts des versions effectivement retenues avant de les adapter.
- Utiliser les recettes Compose officielles comme base. Docs décrit sa recette
  Compose comme expérimentale : compléter et qualifier sa persistance,
  migrations, frontend, backend, collaboration, proxy et services de tâches
  nécessaires, sans prétendre à une qualification Kubernetes.
- Ne pas démarrer leurs Keycloak/MinIO/DIMAIL de démonstration. Utiliser
  l’issuer existant ; les dépendances Mailbox/IdP de People ne sont pas requises.
- Bases et rôles PostgreSQL distincts. Réutiliser un serveur compatible quand
  cela n’impose pas de changement risqué au serveur existant ; aucun partage
  de tables. Isoler cache, queues et cookies par application, même sur la
  même adresse IP avec des ports différents.
- Utiliser un S3 privé Docs, avec un compte limité à son bucket et des endpoints
  navigateur/serveur corrects. **Révision de recette du 8 septembre :** la
  version 4.12 du SeaweedFS Drive échoue sur CopyObject avec versionnement ;
  Docs utilise un service SeaweedFS 4.46 dédié et figé, sans port publié,
  avec son volume persistant. Le stockage Drive reste inchangé. Voir
  [ADR 0003](../../adr/0003-suite-durable-identity-and-access.md).
  Docs ne reçoit ni le compte SMB NAS ni l’accès aux buckets Drive.
- Fixer ports et URLs après relevé des ports utilisés. Noms d’issuer identiques
  vus du navigateur et des conteneurs ; pas de `localhost` depuis un client LAN.
  Vérifier CORS, CSRF, cookies, callback, WebSocket et confiance des proxies.
- TLS requis pour une exposition de production ; le mode HTTP LAN existant
  reste une dérogation locale explicite, pas une modification des origines
  actuelles ni une promesse d’exposition publique sécurisée.
- Secrets privés sauvegardables, permissions restrictives, pas de régénération
  au redémarrage. Pas de socket Docker dans les conteneurs applicatifs.
- Authentik de qualification utilise un projet Compose, réseau, bases, volumes,
  ports, secrets et callbacks distincts. Son port par défaut 9000 entre en
  conflit avec le S3 Drive : attribuer un autre port. Aucun NAS réel dans la
  recette isolée et aucun changement d’issuer des services habituels pour ce test.

Le premier déploiement People/Docs et le raccordement ST peuvent nécessiter de
brefs redémarrages des services modifiés. Les planifier, enregistrer leur durée
et vérifier le retour du stack. Ne pas arrêter la pile historique par
commodité. Aucun `down -v`, reset E2E, import de realm destructif ou remplacement
de base pour « réparer » une connexion.

Dans la qualification L0–L9, l’issuer Keycloak initial est lui aussi une fixture
isolée, de version compatible avec l’installation actuelle, avec des comptes
synthétiques. Les clients People/Docs/ST décrits pour l’issuer Drive existant
sont préparés pour L10. La recette ne modifie ni ses comptes ni ses clients
réels pour simuler un changement d’IdP.

## 4. Migration des données existantes

La migration est additive, rejouable et précédée d’une simulation. Elle ne
fusionne pas de comptes et ne déplace aucun contenu de stockage.

| Donnée | Traitement obligatoire |
| --- | --- |
| Users Drive/ST | Conserver UUID/PK, statut local, préférences, administrateurs et relations. Ajouter le principal et ses associations externes. |
| Ancien `User.sub` | Conserver comme compatibilité transitoire ; auditer tous ses consommateurs avant de lever l’unicité ou retirer un fallback. Les nouveaux lookups utilisent issuer + subject. |
| Fichiers et espaces | Conserver identifiants, créateurs, ACL, grants, clés S3, chemins NAS, favoris, liens, corbeille, réservations et journaux. |
| Groupes Django | Conserver PK et `group:<pk>` ; importer membres/groupes dans People et enregistrer les correspondances. |
| Comptes ST de métriques | Remplacer la dépendance au `sub` par le principal durable dans les échanges, en conservant le même Account et ses associations. |
| Exceptions et métriques ST | Migrer ou aliasser la clé externe sans créer un second compte et sans remettre à zéro valeurs, override, historique ou révision. |
| Organisation | Conserver UUID ST et imputation Drive ; établir le mapping People. Ne pas recalculer l’appartenance d’anciens fichiers depuis les claims de login. |

Ordre de migration :

1. Inventaire privé des identités, associations, groupes, bénéficiaires,
   entitlements et quotas ; compteurs et empreintes non sensibles avant/après.
2. Sauvegarde cohérente des bases, configurations, clés et données nécessaires
   à la restauration, avec procédure pour les écritures concurrentes.
3. Extension du schéma et introduction des tables de correspondance.
4. Création des principaux People et des mappings d’organisation/groupes.
5. Import des associations OIDC existantes avec l’issuer d’origine explicite.
6. Simulation des comptes ST, résolution des conflits et migration de leurs
   identifiants externes ; double lecture de compatibilité limitée aux mappings
   enregistrés, jamais un fallback général par email.
7. Comparaison des accès et plafonds en mode d’observation, sans changer les
   décisions utilisateur ; validation du compte de secours.
8. Activation progressive People → Drive → ST → Docs, puis connexion commune.
9. Invalidation des anciennes sessions lors de la bascule, nouvel essai de
   login et deuxième passage de migration prouvant l’idempotence.

Un rapport d’impact doit lister les créations, associations, conflits,
changements d’autorité et références non résolues. Une seule collision touchant
un compte ou droit actif bloque sa migration. Ne jamais choisir une correspondance
au hasard pour obtenir un tableau sans erreurs.

## 5. Lots d’exécution et critères de sortie

Les identifiants L0 à L11 et les critères V1 à V12 sont stables pour la reprise.
La préparation documentaire actuelle ne coche aucun de ces lots.

L1 à L9 développent et qualifient dans un environnement isolé préparé en L0.
Les références au NAS de ces lots utilisent une fixture de fichiers synthétique.
Les essais sur le NAS réel et la bascule des services habituels sont en L10.
Les composants People/Docs peuvent être préparés auparavant, mais leur
activation dans le stack LAN suit la qualification. L4 et L5 sont une seule
unité de bascule de protocole : aucun mélange des formats d’identité en service.

### L0 — Figer le point de départ et protéger la reprise

**Travail :** lire les `AGENTS.md` des dépôts concernés et les contrats routés ;
relever état Git, services, versions, ports, volumes et capacité. Sauvegarder les
modifications locales et fichiers non suivis avant tout changement de checkout.
Identifier les répertoires de code montés dans les services actifs : leur
autoreload pourrait appliquer une modification avant validation. Développer
dans un checkout/worktree isolé avec une branche locale
`codex/suite-identity-access-catalogue`, reproduisant explicitement l’état
validé, y compris les changements non committés nécessaires. Ne pas supposer
qu’une branche distante contient le travail stockage, ni copier les secrets
du stack réel dans la fixture. Préparer les checkouts People/Docs seulement
au moment de l’exécution. Capturer le petit scénario de référence Drive/ST,
les sauvegardes décrites en section 8 et préparer l’unique recette isolée
Drive/ST/People/Docs qui servira jusqu’à L9.

**Sortie :** référence initiale de V1 ; inventaire et point de reprise utilisables, environnement
inchangé, liste des dépôts/commits précise, aucun secret dans les artefacts publics.
**Reprise :** tant que cette sortie manque, rester en lecture seule sur les données.

### L1 — Contrat commun et migrations additives

**Travail :** formaliser dans `CONTEXT.md`/une ADR les identifiants et autorités
de la section 3 ; écrire le schéma des associations personne/identité/application,
organisation et groupe. Définir les erreurs de conflit et la fraîcheur/version
des projections. Auditer les consommateurs de `sub`, email, `teams` et des
comptes ST, incluant API resource server, tâches, métriques et invitations.
Implémenter les migrations additives et la simulation avant toute activation.

**Sortie :** V2 sur données synthétiques ; mêmes PK et références, conflits
refusés, contrat interservice et mapping ST explicites.
**Reprise :** les anciens flux restent actifs tant que le mode commun n’est pas
activé ; ne pas supprimer les colonnes ou historiques de compatibilité.

### L2 — Installer People et son administration homelab

**Travail :** recette Compose persistante sans IdP/DIMAIL de démonstration ;
raccorder People au Keycloak de recette avec son propre client ; créer l’organisation
et le principal administrateur par association explicite. Adapter le bootstrap
pour qu’il ne nécessite ni SIRET ni organisation déduite de l’email. Activer les
écrans de groupes, membres, applications destinataires et associations d’identité.
Fournir conflit, simulation et aperçu d’impact en interface d’administration.

**Sortie :** People accessible dans la recette, administration bornée par organisation,
création d’un groupe et rattachement de deux comptes par les parcours Web.
Les données persistent après redémarrage ; le stack Drive/ST reste accessible.
**Reprise :** arrêter uniquement les nouveaux services People si nécessaire ;
ne pas basculer Drive/ST avant validation du lot.

### L3 — Distribuer les groupes et statuts de façon fiable

**Travail :** implémenter la projection People et le contrat de lecture machine
restreint ; intégrer la réconciliation paginée dans les tâches existantes ;
appliquer versions, idempotence, complétude et fraîcheur. Préserver le filtrage
des groupes par application et distinguer ancêtres visibles/membres réels.
Ajouter l’état de synchronisation et les erreurs réessayables dans People et
les consommateurs, sans recopier les payloads ou secrets dans les logs.

**Sortie :** V3/V7 sur une projection de qualification : création, renommage,
retrait, suppression logique, message retardé et page manquante correctement
traités. Aucune requête distante par fichier et aucune perte sur retry.
**Reprise :** arrêter les imports fautifs ; conserver les dernières données
valides avec leur échéance, puis refuser temporairement au-delà de celle-ci.

### L4 — Raccorder Drive sans modifier son modèle de stockage

**Travail :** résolution d’identité par associations, conservation des utilisateurs
et import des groupes Django dans People. Relier les projections aux groupes
locaux sans changer les grants existants. Raccorder les sélecteurs Web, statuts
et diagnostics ; contrôler tous les chemins privés, WOPI, resource server et
jobs, conformément aux règles de révocation. Stabiliser les identifiants de
métriques et appels ST en coordination avec L5 ; préparer la bascule sans
activer deux formats incohérents. Aucune modification de provider NAS/S3.

**Sortie :** V2/V3/V6 pour Drive : mêmes fichiers/espaces et droits avant/après ;
retrait de groupe effectif sur S3 et NAS ; autres membres toujours autorisés.
**Reprise :** revenir à la version compatible du schéma et aux mappings validés ;
ne pas effacer les projections ou remettre les droits retirés automatiquement.

### L5 — Stabiliser les comptes ST et la politique d’accès

**Travail :** ajouter le principal durable aux utilisateurs administrateurs et
comptes ST ; migrer les clés utilisées par entitlements/métriques, conserver
exceptions et historiques. Raccorder organisation et groupes People aux
politiques d’accès utilisateur/groupe, avec priorité au refus global. Compléter
les écrans ST et leurs autorisations. Garder l’accès d’administration de secours.
Raccorder ST au fournisseur commun seulement après association de l’ancien compte.

**Sortie :** V4 : le compte test et l’organisation conservent leurs 20 milliards
d’octets de plafond, les autres défauts restent inchangés, le même compte ST
reçoit les métriques avant/après bascule. Une interdiction ST agit côté API
Drive, pas seulement sur le bouton ou au prochain login.
**Reprise :** bascule coordonnée Drive/ST vers les aliases précédents ; aucune
restauration de base ancienne sur une base qui a reçu de nouvelles écritures.

### L6 — Installer Docs et raccorder identité, groupes et accès

**Travail :** Compose persistant, S3 dédié, proxy et collaboration fonctionnels ;
pas d’IdP supplémentaire. Configurer son client OIDC et ses mappings. Remplacer
le résolveur de groupes vide par la projection People et adapter le sélecteur
de partage aux groupes autorisés. Conserver les rôles et ACL Docs natifs.
Appliquer l’accès ST, statut et fraîcheur aux API privées, pièces jointes,
exports, versions et WebSockets ; compléter les mécanismes de déconnexion
existants pour les sessions de coédition déjà établies. SMTP vers le service
local de test, fonctions IA/marketing externes non nécessaires désactivées.

**Sortie :** V5/V6 : création et coédition à deux, sauvegarde réelle, partage
de groupe, refus d’un tiers, export natif et persistance après redémarrage.
Le retrait du groupe interdit aussi les nouvelles modifications depuis une
connexion WebSocket déjà ouverte dans le délai contractuel.
**Reprise :** désactiver l’entrée Docs si nécessaire, conserver sa base/bucket
et ses versions ; Drive/ST ne dépendent pas de son bon fonctionnement.

### L7 — Livrer le catalogue et les parcours d’administration

**Travail :** services de recette dans ST/Gaufre, organisation par UUID, URLs
correctes et assets locaux ; aucune fuite de données privées dans le catalogue
public. Relier People, Drive, ST et Docs avec leurs permissions de visibilité
et liens de retour. Finaliser les écrans définis en section 3.7, l’état d’accès
et les erreurs temporaires. Qualifier noms de cookies distincts et connexion
commune depuis un même navigateur ; préparer les URLs LAN pour la bascule L10.

**Sortie :** V8 ; navigation entre les quatre applications sans ressaisir les
identifiants tant que la session IdP reste valable, accès ST réservé aux rôles
prévus, aucune URL de démonstration à la place d’un service local.
**Reprise :** corriger/désactiver une entrée de catalogue sans changer les ACL.

### L8 — Livrer le mode d’annuaire externe

**Travail :** étendre SCIM People conformément à la section 3.4 ; protéger la
source, organisation et propriété des champs. Ajouter simulation de reprise
d’autorité d’un groupe, historique d’import et erreurs exploitables. Supporter
rejeu, collisions, retrait de membership, désactivation et réactivation
explicite. Documenter les capacités exactes du profil SCIM et le lien distinct
entre identité SCIM et identité OIDC.

**Sortie :** V9, puis vérification avec le vrai provider Authentik en L9. Aucun
connecteur Keycloak Admin, Azure Graph ou Authentik Admin requis par le métier.
**Reprise :** désactiver le credential de la source ; conserver les identifiants
et suspendre les accès périmés. Reprise de gestion People uniquement explicite.

### L9 — Qualifier le second IdP et la bascule réversible

**Travail :** ajouter au projet Compose de qualification isolé Authentik server,
worker, base et dépendances selon la version figée, sans socket Docker inutile.
Réutiliser l’unique recette synthétique Drive/ST/People/Docs préparée en L0,
indépendante des volumes et ports habituels. Utiliser un petit stockage S3 et
un provider de fichiers synthétique ; les tests NAS réel restent la recette
ciblée de L10.

Créer les données avec Keycloak dans cette recette, capturer identités et droits,
puis associer les identités Authentik des mêmes personnes et changer les quatre
clients de la recette. Keycloak ne doit pas servir d’intermédiaire à Authentik.
Vérifier OIDC, SCIM entrant, sessions ouvertes, retrait d’accès et suppression
logique ; revenir à Keycloak sans recréer les données. Tester une association
pairwise explicite sans claim transversal, ainsi que les conflits de claims.

**Sortie :** V9/V10/V11 ; mêmes PK, groupe et droits entre les trois étapes ;
chronométrages de révocation, requêtes interdites et scénario de reprise.
Qualité revendiquée : Keycloak et Authentik testés réellement, profil générique
OIDC/SCIM documenté. Entra ID documenté, pas présenté comme testé sans tenant.
**Reprise :** tous les changements de fournisseur restent dans la recette ;
l’issuer Drive/ST habituel ne change pas vers Authentik.

### L10 — Activer et vérifier le stack LAN complet

**Travail :** répéter la simulation sur les données actuelles, comparer les
références, appliquer le raccordement validé et lancer les nouveaux services.
Conserver le script local Drive et le démarrage ST séparé ; fournir les commandes
People/Docs. Exécuter le petit parcours Keycloak commun avec S3, NAS réel, quotas
ST, Collabora, ONLYOFFICE et Docs. Vérifier le redémarrage ciblé des services
modifiés et le retour des URLs LAN. Nettoyer tous les fichiers de recette.

**Sortie :** V1 à V8 et V12 sur les surfaces applicables ; aucun écart d’inventaire
Drive, aucune perte des références/mappings/budgets, service Docs utilisable.
**Reprise :** procédure section 8 ; en cas de doute, préserver les données et
rétablir uniquement les composants concernés.

### L11 — Clôturer, ranger et préparer les mises à jour

**Travail :** terminer guides d’exploitation, manifestes sans secrets, état des
lots et preuves ; noter les versions locales/patches de chaque dépôt et le
chemin des sauvegardes privées. Exécuter les checks requis par les zones
modifiées, puis une recette finale ciblée seulement si des corrections depuis
la dernière recette le justifient. Arrêter et nettoyer la qualification isolée
après conservation des preuves ; protéger explicitement les nouveaux volumes
People/Docs des opérations de nettoyage futures.

**Sortie :** critères de la section 10 tous satisfaits. Aucun point nécessaire
à cette livraison laissé comme « à raccorder plus tard ». Les limitations
externes documentées ne doivent pas masquer une fonctionnalité non livrée.
**Publication :** aucun commit, push, ticket ou PR sans instruction explicite ;
la clôture locale et la publication restent deux états différents.

## 6. Validation minimale, fondée sur le comportement

Utiliser les frameworks et runners déjà présents. Ajouter quelques tests
paramétrés aux suites existantes pour les branches d’identité et de sécurité ;
ne pas créer un framework, des scripts qui cherchent des mots dans le code,
des tests de structure de fichiers ou une campagne exhaustive hors périmètre.

Les lignes suivantes sont des critères fonctionnels ; plusieurs peuvent être
couvertes par le même parcours. Trois comptes synthétiques suffisent : un
administrateur, un membre et un tiers non autorisé, plus les identités de
connexion de ces mêmes personnes chez les deux fournisseurs.

| Critère | Vérification et résultat exigé |
| --- | --- |
| V1 — Conservation | Même ensemble d’identifiants/relations Drive/ST avant/après, plafonds conservés ; mêmes origines et accès NAS/S3. Nouvelle recette ≠ ancien rapport recyclé. |
| V2 — Identité | Double passage sans doublon ; email modifié et second issuer sans perte ; même email et identités différentes non fusionnés ; même `sub` chez deux issuers non confondu ; subjects pairwise correctement associés ; tentative d’association à un autre principal refusée. |
| V3 — Groupes | CRUD People et renommage conservant UUID/grants ; groupes Django préexistants préservés ; tiers/organisation voisine non visibles ; parent visible sans droits implicites ; ancien événement ne rétablit pas un membership supprimé. |
| V4 — ST | Même Account, overrides et métriques après bascule ; refus d’accès à l’app malgré ACL de contenu ; rôle de gestion d’équipe ne donnant aucun rôle admin ; quotas Drive encore appliqués. |
| V5 — Docs utilisable | Création, coédition de deux sessions, relecture persistée, partage groupe, tiers interdit par URL directe, pièce jointe privée, export et redémarrage avec conservation. |
| V6 — Révocation | Retrait du groupe et suspension avec sessions ouvertes : API, WOPI/écriture Drive et WebSocket Docs refusent dans la borne ; droit individuel distinct encore valide si seule l’adhésion est retirée ; personne suspendue refusée partout. |
| V7 — Pannes | Page de sync perdue, source indisponible puis retour, message retardé : pas d’effacement par défaut ; au-delà de 90 secondes de fraîcheur les opérations dépendantes échouent ; récupération idempotente ; URLs privées non valides après leur échéance. |
| V8 — Web/SSO | Depuis le catalogue LAN, les quatre apps reconnaissent le même principal via leur compte local ; CRUD/admin réalisables avec le rôle prévu ; cookies distincts ; déconnexion locale et commune ont les effets annoncés ; aucun contenu privé dans le catalogue public. |
| V9 — Annuaire externe | Vrai Authentik SCIM → People : création, association stable, mise à jour, changement de groupe, `active=false`, réactivation explicite et replay ; tentative d’éditer un groupe externe depuis People refusée ; délais mesurés. |
| V10 — OIDC hostile | Mauvais issuer/audience, token expiré ou altéré, nonce/state invalides, UserInfo `sub` divergent et redirection interdite refusés ; aucune création de compte privilégié sur claim arbitraire. |
| V11 — Changement d’IdP | Keycloak → Authentik direct → Keycloak : mêmes données/ACL/comptes et quotas, aucune dépendance à un intermédiaire Keycloak dans l’étape Authentik ; anciennes sessions invalidées. |
| V12 — Exploitation | Sauvegarde/restauration isolée du scénario, relance des services utiles, compte de secours fonctionnel, tests nettoyés, état des volumes/projets de qualification consigné. |

Organisation des vérifications :

- Tests backend ciblés sur résolution, mapping/quota ST, ordre des projections,
  périmètres SCIM et refus ; cas de sécurité paramétrés plutôt que doublons.
- Un parcours navigateur Chromium avec les comptes synthétiques couvre le
  catalogue, People, partage Docs, coédition et retrait ; pas de répétition
  automatique complète sur trois navigateurs à chaque lot.
- Une matrice IdP réutilise le même scénario : ne pas dupliquer toutes les
  suites Drive pour prouver un changement de fournisseur.
- Une petite recette LAN préserve les conditions réelles : un fichier S3 et un
  fichier NAS, lecture/sauvegarde avec Collabora et ONLYOFFICE, quota ST effectif,
  plus le document Docs. Utiliser de petits contenus identifiables et vérifier
  les octets par empreinte sans publier leur contenu.
- Une mesure ciblée de la liste d’espaces/groupes et d’un contrôle d’accès
  compare requêtes SQL, appels interservices et latence avant/après. Une fixture
  de 200 groupes et 1 000 adhésions suffit à déceler un N+1 ou une pagination
  incorrecte. Ne pas transformer ce lot en benchmark de charge de la suite.
- Respecter les checks requis par `AGENTS.md` pour les zones réellement
  modifiées : lint/backend, lint/frontend et tests existants correspondants.
  Réutiliser les commandes ciblées durant l’itération ; ne relancer les mêmes
  suites réussies que si un changement ou une anomalie le justifie.

Les tests E2E ordinaires peuvent réinitialiser leurs données et occuper les
ports de l’environnement local : ne jamais lancer leur mode `--from-scratch`
sur les répertoires LAN. La qualification d’IdP est une recette d’intégration
isolée explicitement distincte du mode E2E officiel, sans modifier ce contrat.
Pour les vérifications LAN, suivre les préflights documentés du dépôt et
contrôler qu’ils préservent bien le mode local courant avant de les exécuter.

## 7. Cas limites à traiter avant clôture

- Un compte est suspendu puis revient : mêmes données et identité ; session
  ancienne toujours invalide. La réactivation ne contourne pas un refus ST.
- Une personne change d’adresse : invitations anciennes ne doivent pas être
  automatiquement récupérées par un autre titulaire de cette adresse. Exiger
  les preuves prévues pour la prise d’invitation et ne pas utiliser le flux
  d’invitation comme raccourci de rattachement inter-IdP.
- Retirer le dernier administrateur/owner d’organisation ou d’équipe doit
  produire un transfert explicite ou un refus, pas un espace sans reprise.
- Le même nom de groupe peut exister dans deux organisations/sources : aucune
  collision ; la visibilité reste liée aux UUID et au périmètre.
- Supprimer/recréer un groupe externe homonyme ne récupère pas ses anciens
  grants sans reprise explicite de la correspondance.
- Un accès ST est retiré pendant une coédition, un WOPI PutFile ou un transfert :
  contrôler les nouvelles opérations et la publication, conserver les résultats
  déjà acceptés et suivre la procédure de reprise des fichiers temporaires.
- Si un job est nécessaire à l’intégrité après révocation de son initiateur,
  séparer cette réparation technique de la poursuite d’une action utilisateur
  désormais interdite ; ne pas transformer le worker en accès universel.
- Rejouer une migration ou un événement ne supprime pas une suspension plus
  récente. Une restauration ne doit pas réintroduire d’anciens accès sans
  réconciliation avec l’autorité encore en service.
- Une panne Docs ne doit pas bloquer Drive/ST/People ; une panne People/ST doit
  produire le refus temporaire défini, pas une saturation des workers par retry.
- Un compte technique, un lien public et un utilisateur humain ont des cycles
  de vie différents ; leurs permissions ne sont pas assimilées à un seul rôle.

## 8. Sauvegarde, retour arrière et remise en service

### Avant toute migration

Sauvegarder Drive et ST PostgreSQL, leurs configurations privées, le coffre
stockage Drive et les bases/configurations des deux Keycloak actuels. Préparer
la sauvegarde People/Docs : bases, objets Docs, fichiers persistants, clés et
configuration de collaboration. Enregistrer versions de schéma, commits/images,
horodatages et méthode de cohérence entre métadonnées et objets.

Les archives privées issues du nettoyage Docker sont des sauvegardes de
qualifications anciennes ; elles ne remplacent pas les sauvegardes actuelles.
Ne jamais mettre les archives, CSV nominatifs ou secrets sous `docs/` ou
`output/`. Conserver les chemins et empreintes utiles dans un manifeste privé.

### Retour arrière applicatif

Privilégier des migrations additives compatibles avec le code précédent,
puis désactiver l’activation du socle pour le composant concerné si cela reste
sûr. Le rollback ne doit pas rétablir des grants explicitement retirés depuis.
Si les nouvelles décisions ne sont plus représentables par l’ancien code,
maintenir un refus temporaire et appliquer une correction ; ne pas revenir
silencieusement à des autorisations plus larges.

Restaurer l’ancienne configuration OIDC uniquement après contrôle des aliases
du même principal. Conserver les comptes locaux et invalider les sessions ;
ne pas restaurer une ancienne base entière pour corriger un issuer.
Le compte technique de secours permet l’administration locale sans dépendre
de l’annuaire indisponible, avec secret privé et trace de son utilisation.

### Restauration des données et preuve

Exercer une restauration dans un projet isolé : un principal, un groupe, son
compte ST, un fichier Drive de test, un document Docs et une pièce jointe.
Vérifier les liens entre ces données et les permissions. Les documents Docs
doivent être réellement relus après restauration, pas seulement présents
comme lignes SQL ou objets dans un bucket.

Une restauration après perte de base nécessite un point cohérent et une
réconciliation des changements depuis la sauvegarde. Mettre en pause uniquement
les écritures concernées lorsque nécessaire, avec reprise contrôlée. Documenter
les dernières données récupérables et la durée mesurée sur le scénario ; ne
pas prétendre garantir un RPO nul ou une restauration NAS exhaustive sans preuve.

### Nettoyage final

Supprimer les fichiers, documents, pièces jointes, exports téléchargés,
comptes/groupes temporaires, invitations et jetons de test identifiés par leur
manifest de recette. Purger aussi leurs corbeilles/versions temporaires lorsque
le produit le permet, sans supprimer les données historiques ni les preuves
sanitisées. Vérifier l’absence d’orphelins et de réservations de stockage.

Le compte test et son quota de 20 Go déjà autorisé peuvent rester disponibles.
Ne pas remettre automatiquement son organisation à un plafond inférieur à la
consommation historique. Les sauvegardes de reprise suivent leur conservation
explicite ; elles ne sont pas des uploads de test à effacer.

Arrêter/nettoyer seulement le projet de qualification créé par ce chantier.
Conserver People et Docs utiles dans la pile normale. Pas de prune global à
la clôture ; produire l’inventaire exact des services/volumes conservés.

## 9. Livrables documentaires et règles Git

Documents à produire pendant l’implémentation, seulement lorsqu’ils ont un
contenu réel :

| Emplacement dans ce dépôt | Contenu |
| --- | --- |
| Ce plan | Périmètre et critères ; évolutions décidées, sans le transformer en journal de commandes. |
| `docs/adr/` et `CONTEXT.md` | Décision sur identité durable, autorités et vocabulaire, sans recopier l’intégralité du plan. |
| `docs/installation/suite-identity-and-docs.md` | Installation, configurations sans secrets, clients OIDC, sources SCIM, ports et commandes exactes. |
| `docs/operations/suite-identity-access.md` | Groupes, suspension, révocation, changement d’IdP, diagnostic, secours et restauration. |
| `output/implementation/suite-identity-access-catalogue/current-status.md` | Lots, commits/worktrees, migrations, état runtime, prochaine action et problèmes restants. |
| `output/implementation/suite-identity-access-catalogue/validation-final.md` | Résultats V1–V12, délais, version de chaque IdP, conservation/nettoyage et limites constatées. |

Éviter un ledger supplémentaire par application si le rapport transversal
suffit. Les modifications People, Docs et ST doivent être identifiables dans
leurs propres checkouts et décrites dans le manifeste de livraison local.
Ne pas copier le code de ces applications dans Drive et ne pas faire dépendre
une installation d’un fichier temporaire présent uniquement dans cette tâche.

Identités des dépôts et limites de publication :

- Drive : `https://github.com/Apoze/drive.git`, fork personnel fetch/push ;
  `https://github.com/suitenumerique/drive.git`, source officielle fetch-only,
  push désactivé. Cette spécialisation n’a pas vocation à être refusionnée.
- ST : `https://github.com/Apoze/st-deploycenter.git`, fork personnel ;
  `https://github.com/suitenumerique/st-deploycenter.git`, source officielle
  fetch-only. Garder les adaptations locales isolables.
- People : source `https://github.com/suitenumerique/people.git` en lecture ;
  Docs : source `https://github.com/suitenumerique/docs.git` en lecture.
  Les checkouts locaux et branches de travail ne créent pas automatiquement
  un fork GitHub ni une autorisation de publication.

Ne pas committer, pousser, ouvrir d’issue ou de PR pendant la préparation ni
sans autorisation ultérieure de publication. Si elle est demandée, appliquer
les gates Git/CI de chaque dépôt et présenter leurs URLs et branches exactes.

## 10. Définition de terminé

- [x] L0 à L11 ont un résultat vérifié, et tous les critères V1 à V12 passent.
- [x] Drive, ST, People et Docs sont utilisables depuis le LAN après relance.
- [x] Le SSO commun fonctionne réellement avec le fournisseur actuel, sans
      remplacer ou perdre les identités, données et droits historiques.
- [x] People est l’autorité de groupes active ; le mode externe SCIM est livré
      et testé, mais n’est pas activé par défaut sur les groupes locaux.
- [x] Les rôles et les restrictions d’organisation sont appliqués côté serveur.
- [x] Le retrait d’accès agit aussi sur les sessions, workers et éditeurs
      concernés dans les délais publiés, avec les limites de flux explicites.
- [x] ST conserve les mêmes comptes, plafonds, exceptions et métriques utiles.
- [x] Docs permet une coédition réelle, des partages de groupe et une relecture
      après redémarrage ; les tiers ne peuvent pas accéder aux documents privés.
- [x] La recette isolée prouve le passage à Authentik direct et le retour à
      Keycloak avec les mêmes données ; aucune qualification Entra n’est inventée.
- [x] Sauvegarde/restauration, secours, reprise après panne et nettoyage ont
      des preuves récentes et des commandes reproductibles.
- [x] Les guides, versions, patches, limitations et prochaine étape de la suite
      sont documentés ; l’environnement normal reste démarré.

Ne pas clôturer avec une API d’identité prête mais non raccordée, un login
réussi sans test de révocation, des groupes visibles sans ACL, un Docs vide
sans sauvegarde de coédition, ou une migration non exercée sur l’état actuel.
La publication GitHub éventuelle est une opération distincte de cette clôture.

## 11. Suivi de reprise pour l’agent

À l’autorisation d’implémenter, créer l’état d’exécution mentionné en section 9.
Pour chaque lot, noter `à faire`, `en cours`, `vérifié` ou `bloqué`, la preuve,
les fichiers/dépôts concernés et la prochaine action concrète. Une interruption
ne change pas un lot en cours en lot terminé.

Reprise : lire `AGENTS.md`, ce plan et l’état d’exécution ; vérifier les services,
les modifications locales et la dernière commande éventuellement encore active.
Continuer au premier critère non satisfait, sans rejouer les migrations ou
tests réussis faute de contexte. Signaler un conflit réel de correspondance
au propriétaire, mais résoudre les choix d’implémentation ordinaires dans les
contrats de ce plan.

Ne pas demander au propriétaire de choisir de nouveau la source de groupes,
le fournisseur de qualification ou la préservation du NAS : ces décisions sont
déjà prises. L’utilisateur a autorisé et demandé l’exécution complète ; la livraison locale
est consignée dans l’état courant et la validation finale.

## 12. Sources et niveau de preuve

Les décisions de la section 3 sont des **choix de conception proposés pour
Apoze**, pas des fonctionnalités garanties de tous les produits cités.
Les constats ont été confrontés au code local et aux sources suivantes :

- [Inventaire complet La Suite du 6 septembre 2026](../../../output/research/2026-09-06-lasuite-inventory-and-homelab-integration.md)
  et [manifeste de collecte](../../../output/research/lasuite-inventory-2026-09-06/sources.json).
- [People : modèles](https://github.com/suitenumerique/people/blob/5eafad1d7fb97efeb327b27ddcca0cf29c8182dc/src/backend/core/models.py),
  [authentification](https://github.com/suitenumerique/people/blob/5eafad1d7fb97efeb327b27ddcca0cf29c8182dc/src/backend/core/authentication/backends.py),
  [API d’équipes](https://github.com/suitenumerique/people/blob/5eafad1d7fb97efeb327b27ddcca0cf29c8182dc/src/backend/core/api/resource_server/viewsets.py),
  [SCIM Me](https://github.com/suitenumerique/people/blob/5eafad1d7fb97efeb327b27ddcca0cf29c8182dc/src/backend/core/api/resource_server/scim/viewsets.py)
  et [webhooks](https://github.com/suitenumerique/people/blob/5eafad1d7fb97efeb327b27ddcca0cf29c8182dc/src/backend/core/utils/webhooks.py).
- [Docs : modèles et résolveur de groupes](https://github.com/suitenumerique/docs/blob/3c1275c88da39abb71e045c7deaba3844ca9ac49/src/backend/core/models.py),
  [backend OIDC](https://github.com/suitenumerique/docs/blob/3c1275c88da39abb71e045c7deaba3844ca9ac49/src/backend/core/authentication/backends.py),
  [serveur de collaboration](https://github.com/suitenumerique/docs/blob/3c1275c88da39abb71e045c7deaba3844ca9ac49/src/frontend/servers/y-provider/src/servers/hocuspocusServer.ts)
  et [installation Compose](https://github.com/suitenumerique/docs/blob/3c1275c88da39abb71e045c7deaba3844ca9ac49/documentation/installation/compose.md).
- [django-lasuite : backend OIDC réutilisé](https://github.com/suitenumerique/django-lasuite/blob/c8b3dd963f4508b54bb6283d00c1e46c68b43079/src/lasuite/oidc_login/backends.py).
- [OIDC Core](https://openid.net/specs/openid-connect-core-1_0.html),
  [Back-Channel Logout](https://openid.net/specs/openid-connect-backchannel-1_0.html)
  et [SCIM 2.0](https://www.rfc-editor.org/rfc/rfc7644.html).
- [Authentik : OIDC](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/),
  [SCIM](https://docs.goauthentik.io/add-secure-apps/providers/scim/)
  et [installation Docker Compose](https://docs.goauthentik.io/install-config/install/docker-compose/).
- [Entra ID : claims d’identité](https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference)
  et [profil de provisioning SCIM](https://learn.microsoft.com/en-us/entra/identity/app-provisioning/use-scim-to-provision-users-and-groups)
  pour la compatibilité documentaire ; aucun tenant Entra n’a été testé ici.

Cette rédaction n’a lancé aucun conteneur People/Docs/Authentik, modifié aucun
compte, changé aucun quota ni exécuté de test fonctionnel de ce nouveau socle.

## Suite du socle

L’intégration documentaire native, distincte du catalogue/SSO livré ici, est
[implémentée et qualifiée](docs-drive-native-documents-integration-plan.md)
sur le LAN depuis le 9 septembre 2026. Elle conserve les identités People et
la connexion IdP de chaque application.
