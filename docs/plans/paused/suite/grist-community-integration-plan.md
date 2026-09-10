# Chantier 2 — Grist Community intégré à la suite Apoze

Date : 8 septembre 2026.
Statut : **EN PAUSE sur demande explicite du propriétaire, le 8 septembre 2026.**
Reprise : **uniquement sur nouvelle demande spécifique du propriétaire.**
Dépôt créé : **[Apoze/grist](https://github.com/Apoze/grist)**.

Ce document est le plan canonique du chantier. Il complète le
[socle identité, accès, catalogue et Docs](../../suite/identity-access-catalogue-docs-plan.md)
déjà livré. Il ne remplace ni ses contrats ni ses preuves de livraison.

## 0. Mise en pause — état réel au 8 septembre 2026

**Ce chantier n’est pas livré et ne doit pas être repris automatiquement.**
La demande de pause remplace les autorisations antérieures de poursuivre son
exécution. Une tâche générale de maintenance, une demande de continuation
ambiguë ou la lecture de ce plan ne vaut pas autorisation de reprise.
Sans nouvelle demande explicite visant Grist, ne pas poursuivre le code, les
corrections, les tests, le déploiement, les commits/pushes de ce chantier ni
réactiver ses workflows. Les autres chantiers de la suite restent indépendants.
Les sections 1 à 12 conservent le périmètre prévu, pas une autorisation active.

### Avancement conservé

| Lot | État à la pause | Réalisé / restant |
| --- | --- | --- |
| G0 | Préparation réalisée ; CI à terminer | Fork créé, checkout et branche de travail, remotes protégés, sources/configuration et cinq bases sauvegardées. Workflows copiés désactivés sur le fork ; adaptation Community non terminée. Restauration non éprouvée. |
| G1 | Partiel | Image Community de base et image d’outillage construites, bases Docker épinglées. Qualification runtime, sandbox, persistance et S3 non réalisée ; verrouillage complet de la chaîne Community à finir. |
| G2 | Code partiel, non validé | Entités/migration d’identité et projection paginée People, lecteur de politique ST. Consommateur People et service Grist ST non provisionnés ; atomicité/concurrence à vérifier. |
| G3 | Code partiel, non validé | Raccord OIDC au principal, preuve de session et révocation amorcés. Aucun login réel ; cas de collision d’email, récupération et logout à vérifier. |
| G4 | Non réalisé | Partage Web avec groupes People, rôles et conservation des règles fines. |
| G5 | Amorcé, non validé | Gardes HTTP/WebSocket et interruptions esquissées ; couverture des envois, tokens, tâches et liens publics incomplète. |
| G6 | Non réalisé | Quotas stricts ST, réservations concurrentes, stockage et rétention. |
| G7 | Non réalisé | Catalogue, interfaces d’administration, déploiement et documentation d’exploitation. |
| G8 | Non réalisé | Qualification Keycloak → Authentik → Keycloak et annuaire externe. |
| G9 | Non réalisé | Restauration et mesures de performance. |
| G10 | Non réalisé | Activation LAN et recette finale. |
| G11 | Non réalisé | Publication du code et consolidation du fork sur la seule branche principale. |

### Preuves et limites

- Build local réussi : `apoze/grist:community-base`. Il précède le code
  d’intégration People/ST ; ce code n’est donc pas qualifié dans cette image.
- Outillage local construit : `apoze/grist:build` ; dépendances extraites dans
  `/root/Apoze/grist/node_modules` (modules natifs Node 22).
- Compilation TypeScript de production réussie en 18,26 s.
- Dernier ESLint ciblé : **échec, 14 erreurs** de longueur de ligne et d’ordre
  des membres, après corrections automatiques. Aucun correctif supplémentaire
  n’est lancé après la demande de pause.
- Aucun test comportemental ni parcours navigateur Grist réalisé. Aucun
  conteneur Grist présent à la pause ; aucun déploiement Grist LAN.
- Les 36 conteneurs existants sont actifs lors du contrôle de pause. Ce constat
  d’activité ne constitue pas une nouvelle recette fonctionnelle de la suite.
- Aucun changement applicatif Grist publié, aucun commit du chantier créé.

### Conservation et reprise conditionnelle

Le travail incomplet reste dans `/root/Apoze/grist`, sur la branche locale
`codex/suite-community-integration`, avec ses modifications non commitées.
La branche locale `main` est conservée : la consolidation finale est suspendue,
pas exécutée avec du code incomplet. Base source :
`690c8dfdd32046a4de2558eb812c704ea5619229` (v1.7.19 + un commit officiel).

- `origin` : `https://github.com/Apoze/grist.git` (fetch/push), branche distante
  observée `main`. Aucun push du code du chantier, aucune PR créée.
- `upstream` : `https://github.com/gristlabs/grist-core.git` (fetch-only,
  push désactivé). Aucune écriture vers les dépôts officiels.
- GitHub Actions reste désactivé sur **Apoze/grist** pour empêcher l’exécution
  des automatismes hérités non adaptés. Ne pas le réactiver pendant la pause.
- Sauvegardes privées initiales : `data/grist-execution/baseline/` dans Drive
  (14 fichiers et manifeste SHA-256, sources/configurations et cinq dumps DB).
- Copie privée du travail à la pause : `data/grist-execution/pause-20260908/`
  dans Drive (sources Grist modifiées/nouvelles, patch et manifeste SHA-256).
  Ces copies ne sont ni commitées ni destinées à GitHub.
- Journaux privés : `data/grist-execution/{base-build,tools-build,types,lint}.log`.
- [État de suivi](../../../../output/implementation/grist-community-integration/current-status.md).

**Seulement après demande spécifique de reprise :** relire cet état, vérifier
les changements intervenus depuis la pause, préserver les travaux concurrents
et actualiser les sauvegardes avant toute mutation. Reprendre la qualification
G1 et les corrections ciblées G2/G3/G5 : verrouillage de projection,
nettoyage des timers, fermeture des accès de secours, durée de vie des tokens,
validation native de la migration et des identités sans email. Ne pas déclarer
ces fondations acquises sur la seule compilation TypeScript. Puis suivre les
lots restants du plan avec des tests comportementaux ciblés.

## 1. Résultat attendu et contraintes acceptées

Livrer un Grist utilisable dans l’environnement local existant, avec connexion
commune, identité durable, groupes People, accès et budgets administrés dans
ST, navigation entre applications, stockage persistant et restauration prouvée.
Les adaptations nécessaires appartiennent au fork Apoze ; elles doivent être
construites avec lui, sans fichiers montés depuis un répertoire temporaire.

Les exigences suivantes sont obligatoires :

- Community exclusivement : aucune clé d’activation, période d’essai,
  souscription commerciale ou dépendance fonctionnelle à Grist Cloud.
  Conserver les licences libres et leurs notices ; « sans licence » signifie
  ici sans licence commerciale à obtenir, pas supprimer Apache-2.0.
- Le dépôt source du logiciel est
  [gristlabs/grist-core](https://github.com/gristlabs/grist-core).
  Les dépôts de La Suite peuvent servir de documentation en lecture seule.
- **Aucune PR, issue, poussée, publication, modification de configuration ou
  autre écriture vers Grist Labs ou La Suite numérique.** Aucun automatisme
  installé par le fork ne doit agir vers leurs dépôts ou services.
- À la clôture, `Apoze/grist` a une seule branche locale et distante,
  **`main`**, avec tous les développements intégrés et un arbre de travail
  propre. Les branches d’autres dépôts ne sont pas à supprimer pour cela.
- Préserver Drive, Docs, People, ST, Keycloak, les comptes existants, le NAS,
  les stockages S3, les droits et les quotas déjà configurés.
- Faire des tests ciblés sur les comportements et un parcours final utile.
  Aucun scénario qui valide une fonctionnalité en cherchant du texte dans
  les fichiers source. Les contrôles de secrets et de provenance de l’image
  restent nécessaires.
- L’interface Web doit permettre l’administration courante. Les secrets
  Docker, le bootstrap de confiance, les sauvegardes et le déploiement gardent
  des commandes d’exploitation documentées.

### Périmètre concret de cette livraison

| Livré par ce chantier | Règle |
| --- | --- |
| Grist Community | Tables, formules, vues, coédition, imports, exports, pièces jointes, historique et restauration natifs qualifiés |
| Identité commune | Client OIDC Grist, association au principal People, changement d’IdP et d’email sans changer de compte |
| Groupes et droits | Groupes People proposés dans le partage Grist ; rôles et ACL Grist conservés |
| Administration | Activation, accès et budgets dans ST ; personnes et groupes dans People ; documents et partages dans Grist |
| Catalogue | Grist apparaît aux personnes autorisées, depuis les applications existantes et réciproquement |
| Quotas Grist | Budget de l’application/organisation et budgets par propriétaire, appliqués dans Grist, indépendants du stockage physique |
| Exploitation | Stack persistant, image Community reproductible, sauvegarde/restauration, reprise et nettoyage des essais |
| Fork | Source, développements, tests ciblés et documentation propres sur `Apoze/grist` `main` |

La classification universelle de documents Drive/Docs/Grist dans un même
explorateur, la recherche fédérée et un quota dynamique unique consommable
indifféremment dans toutes les applications constituent un chantier distinct.
Ici, chaque application garde son modèle documentaire et ses ACL. Les budgets
Grist sont raccordés à ST et réellement appliqués ; une addition de métriques
dans ST ne sera pas présentée comme un quota transactionnel partagé avec Docs.

Grist n’est pas un moteur Excel complet : qualifier les formats réellement
proposés par la version retenue et documenter leurs limites de conversion.
Les classeurs Office et leurs éditeurs existants restent utilisables dans Drive.

## 2. Point de départ vérifié et contexte à préserver

La préparation a consulté les sources locales, les configurations OIDC actives
sans révéler leurs secrets, les conteneurs et les sources officielles Grist.
Elle n’a démarré aucun Grist ni créé de fork GitHub.

| Composant actuel | État et conséquence pour le chantier |
| --- | --- |
| Drive `/root/Apoze/drive` | Fork adapté, espaces unifiés, NAS et S3 existants ; nombreux changements locaux à préserver |
| ST `/root/Apoze/st-deploycenter` | Organisation durable, politiques, catalogue et budgets ; changements locaux à préserver |
| People `/root/Apoze/people` | Base officielle v1.25.4 adaptée au socle ; autorité des personnes et des groupes |
| Docs `/root/Apoze/docs` | Base officielle v5.6.1 adaptée ; coédition, groupes et contrôle des sessions livrés |
| Connexion | Les quatre applications ont chacune leur client OIDC sur le même issuer Keycloak |
| Issuer LAN actif | `http://192.168.10.123:8083/realms/drive` |
| Clients existants | `drive`, `apoze-st`, `apoze-people`, `apoze-docs` |
| Grist | Aucun checkout applicatif ni conteneur Grist présent lors de la préparation |
| Recette Authentik précédente | Qualifiée puis nettoyée ; les projets isolés sont à recréer pour cette recette |
| Stockage Docs | SeaweedFS 4.46 dédié, volume persistant et IAM séparé ; l’ancien S3 Drive n’a pas été remplacé |

**People n’est pas un IdP.** Grist utilisera le même schéma que Drive et Docs :
l’IdP authentifie ; People définit la personne et ses groupes ; ST autorise
l’application ; Grist vérifie ensuite les droits sur chaque ressource.

Documents à relire avant exécution :

- [Décision d’identité durable](../../../adr/0003-suite-durable-identity-and-access.md).
- [Installation du socle](../../../installation/suite-identity-and-docs.md).
- [Exploitation et révocation](../../../operations/suite-identity-access.md).
- [Dernier état livré](../../../../output/implementation/suite-identity-access-catalogue/current-status.md).
- [Validation du socle](../../../../output/implementation/suite-identity-access-catalogue/validation-final.md).
- [Environnement local](../../../env_freeze_report.md) et
  [contrat de stockage Drive](../../../agent-storage-contract.md) si un chemin
  Drive de lecture, écriture ou transfert doit être touché.

Les sauvegardes du premier chantier sont sous
`data/suite-local/backups/2026-09-08/`, hors Git. Elles constituent un point de
reprise historique, pas une sauvegarde fraîche dispensant du lot G0.

## 3. Qualification des sources et choix Community

### 3.1 Référence étudiée

Sources Grist inspectées au tag
[v1.7.19](https://github.com/gristlabs/grist-core/releases/tag/v1.7.19), commit
`298d4661ce3513a6a459c5441f9c5baea4356cc8`. C’est la référence de recherche,
pas l’autorisation d’écraser l’historique d’un fork existant pour y revenir.
Au démarrage, vérifier les correctifs de sécurité disponibles et figer le
commit choisi, les dépendances et les digests d’images dans le manifeste.

| Constat vérifié | Décision pour notre fork |
| --- | --- |
| `coreLogins.ts` enregistre le fournisseur OIDC dans le chemin Core, tandis que la documentation OIDC affiche une exigence d’activation | Réutiliser le fournisseur Core et prouver son fonctionnement dans notre image sans activation ; ne pas conclure à partir de la documentation commerciale seule |
| `install_edition.sh` choisit `full` si aucune édition n’est précisée | Fixer Community avant le premier `yarn install`, en local, CI et Docker ; empêcher tout téléchargement automatique d’extensions complètes |
| `Authorizer.ts` résout normalement le profil par email | Ajouter la résolution explicite par principal durable avant toute création/récupération du compte local |
| Les groupes natifs distinguent groupes de rôle et groupes d’équipe | Réutiliser les groupes d’équipe pour People et les ACL natives pour les rôles |
| Le support SCIM expose des groupes, mais cela ne prouve pas un partage Web complet | Compléter le sélecteur de groupes et les droits ; ne pas livrer une simple synchronisation invisible |
| Les limites natives comprennent des mesures différées et une période de grâce | Développer l’application stricte des budgets ST ; ne pas réutiliser la grâce comme quota dur |
| Le chemin Core propose du stockage S3 compatible et des pièces jointes externes via le stockage des snapshots | Qualifier ces chemins dans le build Community retenu avant configuration LAN |

Sources de ces constats :
[Core login](https://github.com/gristlabs/grist-core/blob/v1.7.19/app/server/lib/coreLogins.ts),
[installation d’édition](https://github.com/gristlabs/grist-core/blob/v1.7.19/buildtools/install_edition.sh),
[résolution des utilisateurs](https://github.com/gristlabs/grist-core/blob/v1.7.19/app/server/lib/Authorizer.ts),
[groupes](https://github.com/gristlabs/grist-core/blob/v1.7.19/app/gen-server/entity/Group.ts),
[SCIM](https://support.getgrist.com/install/scim/),
[limites](https://github.com/gristlabs/grist-core/blob/v1.7.19/app/common/DocLimits.ts),
[construction Core](https://github.com/gristlabs/grist-core/blob/v1.7.19/app/server/lib/coreCreator.ts),
[services Core](https://github.com/gristlabs/grist-core/blob/v1.7.19/app/server/lib/ICreate.ts).

### 3.2 Choix à appliquer, sans ajouter de composants inutiles

1. Construire le logiciel libre de `Apoze/grist`. `gristlabs/grist-oss` peut
   servir de témoin de qualification ; l’image déployée contient nos sources.
2. Réutiliser OIDC Core et sa bibliothèque `openid-client`. Ajouter seulement
   l’adaptation identité/session du socle. Aucun client OIDC artisanal.
3. Fixer le choix du fournisseur : une erreur de configuration ne doit jamais
   retomber sur `MinimalLogin`, un utilisateur par défaut ou une authentification
   de test. Désactiver également la connexion getgrist.com dans ce déploiement.
4. Si le commit finalement retenu rend un raccord nécessaire indisponible en
   libre, développer le raccord libre minimal dans le fork. Ne pas retirer
   un contrôle d’activation d’un module propriétaire ni importer ce module.
5. Un proxy OIDC à en-têtes n’est un repli qu’en cas de nécessité prouvée.
   Il doit transmettre une identité vérifiée durable, retirer tout en-tête
   fourni par le navigateur et être le seul accès au backend. Il ne remplace
   jamais les contrôles applicatifs de ressources, sessions et révocation.
6. Aucun nouveau service d’identité, serveur SCIM Grist ou framework générique
   multiapplications n’est requis : les API People/ST existent déjà.

La différence entre éditions et images est décrite dans la
[documentation d’auto-hébergement](https://support.getgrist.com/self-managed/).
La [page OIDC](https://support.getgrist.com/install/oidc/) et le
[code OIDC épinglé](https://github.com/gristlabs/grist-core/blob/v1.7.19/app/server/lib/OIDCConfig.ts)
doivent être lus ensemble. Le présent plan distingue la présence du code de
la preuve d’exécution, qui reste à produire en G1.

## 4. Contrats d’intégration

### 4.1 Répartition des responsabilités

| Autorité | Données ou décision |
| --- | --- |
| IdP OIDC sélectionné | Authentification, MFA éventuelle, preuve signée, session IdP |
| People | `principal_id` durable, identités externes approuvées, groupes, suspension, version de session |
| ST | `organization_id` durable, activation Grist, accès par personne/groupe, budgets et métriques |
| Grist | Identifiants locaux, sites, espaces de travail, documents, ACL, règles fines, édition et compteurs de consommation |

Le déploiement initial dessert **une organisation ST configurée**, comme les
consommateurs du socle. Un site Grist principal lui est associé explicitement.
Ne pas créer de nouvelles organisations, comptes privilégiés ou sites personnels
à partir de claims IdP. Les espaces de travail du site couvrent le besoin
initial ; la création libre de sites supplémentaires est fermée tant que ses
contrôles et budgets n’ont pas été qualifiés.

### 4.2 Module Grist et API existantes à réutiliser

Créer une adaptation TypeScript cohérente avec les modules natifs de Grist.
Le paquet Python `src/packages/suite-identity/` de Drive est la référence
comportementale du contrat, pas une dépendance importable dans Node.

| Échange | Contrat local à reprendre |
| --- | --- |
| Annuaire People | `/api/v1.0/suite-directory/` ; consommateur `grist` propre à l’organisation ; clé de lecture dédiée |
| Politique ST | `/api/v1.0/suite-policy/?service_id=…` ; corps organisation et UUID des personnes ; authentification du service |
| Catalogue ST | `/api/v1.0/suite-catalogue/` ; décisions filtrées pour la personne et l’organisation |
| Rattachement et déconnexion | Routes du socle exposées par People ; credentials de mutation séparés des clés de lecture |
| Budgets et métriques | Résolveurs ST d’entitlements, comptes identifiés par principal, collecte native des métriques de service |

Points d’entrée locaux déjà inspectés :
`suite_identity/{oidc,directory,policy,access}.py` dans le paquet partagé ;
`suite_directory/{models,views,identity_requests,sessions}.py` dans People ;
`core/api/viewsets/suite_access.py`, `core/services/suite_access.py` et
`core/entitlements/resolvers/` dans ST.

Reprendre leur version de schéma, pagination et sémantique d’erreur. Ne pas
copier le framework Django. Conserver quelques fonctions/services TypeScript
avec une frontière claire entre synchronisation, session et autorisation.

### 4.3 Identité durable et migration

- Association additive du `User.id` Grist au UUID People et au UUID
  d’organisation. Contraintes d’unicité en base dans les deux sens.
- Associer les identités externes par consommateur OIDC, issuer exact et
  subject opaque. Les subjects propres à chaque client ne se déduisent pas
  de ceux de Drive ou Docs.
- Résoudre la session par cette association. Les emails et noms restent des
  attributs de profil ; aucun rapprochement automatique par email, casse,
  domaine, nom ou groupe.
- Un utilisateur préprovisionné sans identité externe approuvée n’obtient pas
  de session. Une identité inconnue passe par la demande de rattachement
  People existante, avec approbation et audit.
- Préserver le même `User.id`, les propriétaires, ACL, documents et quotas
  lorsque l’issuer, le subject ou l’email changent après rattachement approuvé.
- Adapter aussi les chemins secondaires qui résolvent un compte par email :
  sessions, invitation, partage, API, propriétaire et comptes techniques.
  Ne pas fabriquer un email UUID pour contourner seulement le callback.
- Un email déjà occupé par une autre personne ne déclenche ni fusion ni
  transfert. Conserver les deux identités distinctes et produire un conflit
  administrable ; l’ancien email ne doit plus servir à attribuer de nouveaux
  droits à la mauvaise personne.
- Ne pas supprimer les comptes suspendus. Conserver leurs données et rendre
  le transfert de responsabilité possible à un administrateur autorisé.
- Si des données Grist préexistent au démarrage réel : simulation de migration,
  export des correspondances, résolution explicite des conflits, application
  additive et comparaison avant/après. Ne pas remplacer ce cas par un bootstrap
  destructeur sous prétexte qu’aucun Grist n’existait pendant la préparation.

OIDC : validation cryptographique native, issuer/audience/`azp`, expiration,
`state`, PKCE et nonce compatibles avec le fournisseur ; comparaison du subject
userinfo au subject authentifié. Appliquer `max_age` et `auth_time` du socle
avec une preuve de 900 secondes au maximum. Les horodatages et la tolérance
d’horloge sont bornés ; aucune désactivation de vérification TLS ou de signature.
Les métadonnées sensibles et jetons ne doivent pas apparaître dans les logs.

### 4.4 Groupes People et partage Grist

1. Publier Grist comme consommateur People sans élargir les publications des
   quatre applications existantes.
2. Projeter chaque UUID de groupe People vers un groupe natif d’équipe Grist.
   Le nom n’est qu’un libellé. Renommer conserve les droits ; supprimer puis
   recréer un homonyme ne les récupère pas.
3. Synchroniser les appartenances publiées et leurs suppressions. Ne pas
   inventer d’appartenance transitive à partir de parents : les groupes
   d’équipe natifs ne sont pas une hiérarchie libre de groupes imbriqués.
4. Proposer les groupes dans le partage Web du site, de l’espace de travail
   et du document. Accorder le rôle via les groupes de rôle et ACL Grist
   existants, sans recopier un droit permanent sur chaque utilisateur.
5. Préserver les droits manuels distincts et les héritages natifs. Retirer
   une appartenance ne supprime pas un droit accordé séparément ; l’interface
   doit montrer pourquoi un accès subsiste.
6. Garder les appartenances gérées par People en lecture seule dans Grist.
   Le propriétaire choisit le rôle du groupe sur sa ressource ; il ne change
   pas les membres du groupe depuis Grist.
7. Conserver les règles fines de Grist sur lignes et colonnes. Si leur éditeur
   doit exposer les groupes People, ajouter un attribut de groupe calculé
   côté serveur et une aide dans l’éditeur, jamais un claim navigateur fiable.
   Une règle de contenu ne peut rétablir un accès refusé par ST.

| Rôle | Portée ; aucune implication automatique supplémentaire |
| --- | --- |
| Administrateur ST | Configure le service et ses budgets ; pas accès implicite à tous les documents |
| Administrateur People | Administre personnes/groupes ; pas propriétaire implicite des données Grist |
| Administrateur d’installation Grist | Exploitation de Grist ; compte distinct et attribution explicite |
| Propriétaire Grist | Administration de la ressource selon les règles natives |
| Éditeur / lecteur Grist | Modification / consultation de la ressource selon ses ACL et règles fines |
| Groupe « Administration de la suite » | N’accorde un privilège Grist que par une règle explicite et auditée |

Protéger le dernier administrateur de secours et le dernier propriétaire utile.
Les exceptions d’exploitation ne deviennent jamais un compte anonyme par défaut.

### 4.5 Synchronisation et fraîcheur

Reprendre les bornes du socle : synchronisation toutes les 30 secondes,
décision positive utilisable au plus 90 secondes sans vérification et borne
de révocation publiée de 120 secondes après modification dans People/ST.

- Lire les flux paginés personnes, groupes, membres et identités sur une
  révision cohérente ; reprendre les pages de 200 et les curseurs existants.
- Préparer un état borné sur disque ou en tables de staging, puis publier
  atomiquement une projection complète. Une page manquante, une révision
  changée ou une réponse malformée ne doit pas vider l’annuaire.
- Appeler ST par lots de 200 personnes au maximum. La fraîcheur locale ne
  dépasse jamais le bail renvoyé ni la fraîcheur de la projection People.
- Utiliser les tâches et verrous disponibles dans Grist. Un ordonnanceur
  actif par déploiement ; pas un scan global lancé par chaque requête.
- Invalidation locale des caches de sessions et d’ACL après changement.
  Les caches ne prolongent pas la validité du bail.
- Après redémarrage ou restauration, aucune décision positive ancienne n’est
  réactivée sans resynchronisation. Utiliser des durées monotones dans le
  processus et vérifier les horodatages persistés à la reprise.
- Une panne temporaire conserve la dernière projection complète mais cesse
  d’autoriser après son échéance. Un refus certain produit 403 ; une décision
  indisponible produit 503 avec une explication, pas une liste vide trompeuse.

Le délai d’un annuaire externe jusqu’à People s’ajoute à cette borne. Il n’est
pas garanti par Grist. Le mode SCIM reste **annuaire externe vers People** ;
Grist consomme ensuite le même annuaire que dans le mode People natif.

### 4.6 Révocation, sessions et chemins de contournement

Appliquer la décision commune avant l’autorisation Grist, sur les chemins
partagés du serveur, sans disperser un contrôle différent par route.

| Chemin | Contrôle requis |
| --- | --- |
| Connexion et retour direct sur un lien | Identité approuvée, personne active, accès ST, puis ACL de la ressource |
| API HTTP | Même contrôle pour session, clé API ou autre authentification disponible |
| WebSocket/coédition | À l’ouverture, avant chaque opération et avant d’envoyer des mises à jour au client |
| Connexion inactive | Fermer ou réautoriser à l’échéance du bail même sans nouvelle saisie du client |
| Réduction éditeur → lecteur | Empêcher la prochaine écriture, invalider les permissions en cache ; conserver seulement la lecture encore permise |
| Pièces jointes, exports, snapshots | Autorisation propre à la ressource, lien privé borné, pas d’URL longue durée contournant la révocation |
| Copie, restauration, import et transfert | Droits source/destination et accès courant revérifiés à l’exécution différée |
| Clé API ou compte de service | Propriétaire durable actif, portée explicite, révocation ; aucun compte humain technique omnipotent |
| Webhook/automatisation/widget | Identité et autorisations documentées, sorties réseau autorisées, pas de chemin privilégié caché |

Étendre la déconnexion de suite par la version de session People. Utiliser
la déconnexion OIDC disponible sans dépendre d’une API d’administration
Keycloak. Sans endpoint de logout IdP, fermer les sessions applicatives et
indiquer que la session IdP peut subsister ; exiger une nouvelle preuve selon
le contrat du socle. Prévoir le compte de récupération Grist en accès restreint.

Les liens publics et formulaires anonymes sont désactivés par défaut pour le
nouveau service. Leur activation explicite se fait dans l’administration ST
et n’ouvre que les ressources publiées par un responsable Grist. Leur droit
public a son propre cycle de vie ; la suspension d’une personne ne rappelle
pas un lien public autonome. La fermeture du service, la dépublication et la
suppression du lien doivent arrêter les nouvelles requêtes, y compris sans
session. Une invitation nominative reste soumise à People et à ST.

Les octets déjà téléchargés et les flux acceptés ne sont pas rappelables.
Limiter les nouveaux téléchargements délégués à la durée de leur autorisation.
Ne pas prétendre fermer la copie d’un fichier déjà reçue sur un ordinateur.

## 5. Quotas applicatifs et stockage

### 5.1 Budget Grist : une couche applicative réelle

ST configure le plafond Grist de l’organisation, le plafond utilisateur par
défaut et les exceptions par principal. Grist applique ces plafonds au moment
de l’opération. Le quota du NAS, du volume ou du serveur S3 reste indépendant.

Un plafond physique connu borne la capacité que l’on peut garantir ; une
capacité inconnue est affichée comme inconnue. L’espace libre observé n’est
pas une réservation et ne remplace jamais un budget applicatif. Ne pas lire
des quotas OpenZFS en supposant que tout endpoint S3 ou SMB les expose.

Le propriétaire comptable est explicite : un principal People ou
l’organisation pour une ressource collective. Un document est imputé une
fois à ce propriétaire, même si plusieurs personnes/groupes le modifient.
La création pour le compte de l’organisation nécessite un droit dédié ; elle
ne doit pas devenir le contournement du plafond personnel.

| Mesure | Traitement |
| --- | --- |
| Données vivantes et métadonnées du document | Comptées dans l’usage applicatif suivant une unité stable documentée |
| Pièces jointes | Taille utile comptée une fois par document, internes ou externes ; pas double compte dans les pages SQLite |
| Corbeille et données encore restaurables | Restent imputées tant qu’elles sont conservées pour ce propriétaire |
| Historique conservé | Compté séparément et soumis à un plafond/rétention explicite inclus dans l’enveloppe Grist ; pas de croissance illimitée hors quota |
| Réplication du même état vers S3 | Mesure physique séparée ; ne double pas artificiellement l’usage logique du document |
| Snapshots historiques et sauvegardes | Stockage retenu surveillé et borné ; sauvegardes d’exploitation dans une enveloppe physique distincte |
| Temporaires, WAL, cache et moteur de formules | Réserve d’exploitation et limites de ressources ; pas présentés comme de l’espace personnel disponible |

Le lot G6 fixe la formule exacte, ses unités et sa migration **avant** de
brancher l’interface. Réutiliser les compteurs natifs lorsqu’ils correspondent
à la mesure. `DocStorage.getDataSizeUncached()` lit `dbstat`, exclut notamment
les tables système et peut parcourir la base entière : ce n’est ni le total
physique retenu ni un contrôle à exécuter à chaque frappe.
[Source](https://github.com/gristlabs/grist-core/blob/v1.7.19/app/server/lib/DocStorage.ts).

### 5.2 Admission et comptabilité sans dépassement concurrent

- Réutiliser les transactions et la sérialisation natives par document.
  Réserver atomiquement le budget partagé organisation/propriétaire dans la
  base Home ; plusieurs documents et uploads concurrents doivent respecter
  la même enveloppe. Ordre de verrouillage stable, pas de verrou global serveur.
- Pour un upload, contrôler la taille annoncée puis les octets réellement lus.
  Réserver avant d’accepter la croissance, borner les temporaires et libérer
  les réservations après échec ou annulation. Ne pas charger le fichier en RAM.
- Pour l’édition, considérer les effets des actions stockées et des formules,
  puis contrôler la croissance avant commit durable et avant diffusion.
  Réutiliser `Sharing`, `ActiveDoc`, `DocStorage` et leurs mécanismes de rejet.
  Une simple mesure différée après commit est insuffisante.
- Le moteur Python, les caches d’actions et SQLite doivent rester cohérents
  après un rejet. Réutiliser l’annulation native lorsque sûre ; si un retour
  arrière échoue ou produit un état incertain, recharger le dernier état
  validé sans publier l’action rejetée. Couvrir les formules non déterministes.
- La base Home et les fichiers SQLite n’ont pas de transaction distribuée.
  Réutiliser le journal d’actions et ajouter un identifiant d’opération et une
  réservation récupérable. Confirmer après preuve du commit ; une reprise
  résout l’incertitude avant de rendre du crédit. Aucun crédit rendu sur une
  simple expiration si l’opération a pu réussir.
- Les réservations de croissance et les deltas permettent un coût borné par
  action. Si une estimation ne garantit pas une borne supérieure, effectuer
  la mesure exacte ciblée dans la transaction ; aucune heuristique ne doit
  être annoncée comme quota strict. Comparer les coûts sur deux tailles de
  document avant de figer l’algorithme.
- Une suppression, purge ou restitution de quota conserve une marge
  d’exploitation pour son journal et ses écritures techniques. Elle reste
  possible quand le budget utilisateur est plein.
- Abaisser un plafond sous l’usage ne supprime aucune donnée : bloquer la
  croissance, expliquer le dépassement, conserver lecture/export et opérations
  de libération autorisées. Aucun délai de grâce natif de deux semaines pour
  une règle définie comme quota dur.
- Copie, import `.grist`, annulation/rétablissement, formulaire, duplication,
  restauration et transfert de propriétaire passent par les mêmes règles.
  Une copie est un nouvel usage ; un transfert réserve la destination avant
  de libérer la source. Dédupliquer les reprises avec l’identifiant d’opération.
- Les valeurs sont des octets entiers, sans `NaN`, dépassement d’entier ou
  confusion GB/GiB ; documenter la représentation JSON/SQL et la plage sûre
  de JavaScript. L’UI affiche les unités et les plafonds effectifs.

Une politique de quota indisponible empêche une nouvelle croissance après
expiration de sa version en cache. La lecture suit son propre bail d’accès. Le message
de quota conserve les modifications non enregistrées dans l’interface et
explique comment libérer de l’espace ou demander un plafond supérieur.

Le verrou documentaire, le commit SQLite puis la diffusion sont déjà
centralisés dans
[Sharing](https://github.com/gristlabs/grist-core/blob/v1.7.19/app/server/lib/Sharing.ts).
C’est le point à approfondir pour l’adaptation, pas une autorisation de
réécrire le moteur documentaire.

### 5.3 Stockage retenu

- Documents de travail `.grist` sur volume persistant local POSIX compatible
  SQLite, jamais ouverts simultanément depuis Drive ou directement sur SMB.
- Base Home PostgreSQL dédiée, utilisateur dédié ; sessions/coordination
  Redis dédiées si requises par la configuration native retenue. Réutiliser
  un serveur existant seulement si l’isolation, les sauvegardes et le cycle
  de vie sont garantis ; ne pas coupler Grist au conteneur de tests d’un autre
  projet pour économiser un service.
- Snapshots et pièces jointes externes par le backend S3 natif Community,
  avec bucket(s), préfixes et credentials Grist distincts. Choisir d’abord un
  endpoint existant compatible, après qualification des opérations réellement
  utilisées : versioning, copie, remplacement de métadonnées, suppression,
  restauration et pièces jointes. Sinon ajouter un service dédié épinglé.
- Ne pas réutiliser aveuglément le SeaweedFS 4.12 de Drive : le premier chantier
  a déjà rencontré une incompatibilité de copie versionnée avec Docs. Ne pas
  modifier le S3 Docs pour Grist sans en qualifier les effets sur Docs.
- Les objets restent privés. Credentials S3 côté serveur uniquement ; IAM
  limité au périmètre Grist. Aucun accès utilisateur direct aux fichiers vivants.
- La destination physique choisie ne change ni principal, ni groupes, ni ACL.
  Grist utilise ses API de stockage ; il ne devient pas un MountProvider Drive.
- Rétention paramétrée des versions, corbeilles et temporaires, avec purge
  idempotente et garde sur les références encore utilisées.

Les snapshots S3 sont des versions de stockage, pas à eux seuls une sauvegarde
cohérente du site. La restauration de la base Home est également nécessaire.
Voir [stockage cloud officiel](https://support.getgrist.com/install/cloud-storage/).

## 6. Interface et exploitation

### 6.1 Parcours Web à livrer

| Interface | Actions disponibles |
| --- | --- |
| ST | Activer Grist, régler l’accès par personnes/groupes, plafonds globaux/personnels, règles de publication publique, consulter usage et fraîcheur |
| People | Publier les groupes vers Grist, gérer membres et suspensions, approuver les identités, utiliser le mode annuaire externe existant |
| Grist | Navigation de suite, espaces de travail/documents, partage avec personnes/groupes, rôle effectif, quota et état de synchronisation pertinent |
| Exploitation Grist | État de connexion People/ST, version/digest, dernière synchronisation et raison d’un refus, sans divulguer de secrets ni contenu |

Le catalogue s’appuie sur les décisions ST existantes. Une tuile cachée ne
constitue pas une autorisation : les URL directes doivent appliquer la même
politique. Préserver les liens profonds après connexion. Le retour vers Drive,
Docs et People utilise leurs URL configurées, pas des domaines codés en dur.

Conserver les composants et styles natifs, les traductions françaises et
l’accessibilité clavier. Ajouter uniquement les contrôles manquants. Les
écrans destinés aux utilisateurs n’exposent ni issuer/subject ni secrets.

### 6.2 Déploiement local et configuration

Prévoir le projet Compose `grist-local` dans le fork, séparé de `grist-qa-*`.
L’URL proposée est `http://192.168.10.123:8484`, sous réserve du contrôle du
port en G0. Enregistrer le client OIDC `apoze-grist` et son callback exact.
L’IdP actif est celui du socle, sans nouveau Keycloak de démonstration.

Le script `run_env_local.sh` de Drive reste Drive uniquement ; ST et le socle
People/Docs gardent leur démarrage propre. Grist dispose de commandes simples
pour construire, démarrer, arrêter, consulter l’état, migrer, sauvegarder et
restaurer son projet. Les documenter avec l’ordre des dépendances ; ne pas
ajouter un nouvel orchestrateur ni redémarrer toute la suite à chaque build.

Configuration reproductible avec exemples sans secrets et fichiers privés :
URL publiques/internes, client OIDC, organisation, endpoints People/ST,
credentials par usage, volumes, S3, sessions, ressources et délais. Contrôles
de démarrage explicites pour configuration invalide et migrations requises.
Cookies propres à Grist, même sur l’adresse LAN commune, CORS/origines WebSocket
bornés et redirections validées.

Le mode HTTP reste le LAN de développement existant. Fournir la configuration
documentée HTTPS/DNS pour exploitation ; ne pas exposer publiquement le stack
ni inventer de certificat/domaine. La recette LAN ne vaut pas recette Internet.

### 6.3 Sécurité et ressources utiles au fonctionnement

- Activer et vérifier le sandbox natif des formules sur ce serveur. Ne pas
  résoudre un échec de sandbox par un mode non isolé ou un conteneur privilégié.
- Respecter le fonctionnement non privilégié de l’image, les droits des
  volumes et les besoins minimaux du sandbox ; aucun socket Docker exposé.
- Borner calculs, imports, temporaires, connexions et parallélisme à partir
  des ressources libres mesurées. Conserver de la marge pour Drive/Docs/NAS.
- Désactiver télémétrie, téléchargements de mises à jour et intégrations cloud
  non requises. Ne pas ajouter de clé d’IA, SMTP ou service payant pour valider
  le chantier. Les partages internes fonctionnent sans email d’invitation.
- Héberger les widgets retenus avec version figée et licences libres ; tester
  les permissions du widget. Aucun widget externe avec plein accès aux données
  sans décision explicite. Préserver l’isolation d’origine prévue par Grist.
- Pour les imports par URL et webhooks activés, appliquer les protections
  réseau natives et une liste de destinations ; pas d’accès implicite aux
  métadonnées cloud ou aux interfaces administratives internes.
- Logs de production sans tableaux, pièces jointes, jetons ou bundles d’actions.
  Journaliser seulement les événements administratifs et erreurs nécessaires,
  avec rétention et accès limités.
- Santé : processus, migrations, stockage, fraîcheur People/ST, compteurs en
  reprise, files et marge disque. Une page de login 200 ne suffit pas à déclarer
  le service prêt.

## 7. Lots d’exécution, dépendances et critères de sortie

Chaque lot doit laisser un état démarrable ou une migration inspectable et
réversible. L’agent exécute lui-même les lots ; aucune délégation implicite.
Tenir l’état de reprise à jour après chaque lot, sans déclarer le chantier
terminé avant G11.

### G0 — Préserver l’existant et préparer le fork

**Dépendance :** aucune.

1. Relire les instructions des dépôts touchés et les documents de section 2.
2. Inventorier branches, commits, changements locaux et services avec leur
   projet Compose ; mesurer disque/RAM, ports et volumes. Ne pas relancer
   de prune général ni arrêter les services existants.
3. Sauvegarder les bases/configurations nécessaires avant leur modification ;
   archiver les changements locaux non publiés avec checksums et droits privés.
4. Vérifier en lecture seule le compte GitHub Apoze et l’existence éventuelle
   de `Apoze/grist`. Réutiliser uniquement un dépôt correspondant ; aucune
   suppression/recréation d’un dépôt existant.
5. Créer le fork `Apoze/grist` à partir de `gristlabs/grist-core`, avec la seule
   branche par défaut copiée si l’outil le permet. Enregistrer la filiation.
6. Cloner dans `/root/Apoze/grist`, configurer les remotes selon la section 10,
   puis créer une branche de chantier locale à partir de son historique audité.
7. Figer la base source choisie. Si la branche copiée dépasse le tag étudié,
   qualifier ces commits ou retenir une stratégie conservant l’historique ;
   ne pas faire de reset forcé pour atteindre le tag.
8. Lire les workflows copiés avant leur activation : dépôts/registries de
   destination, permissions, publication, télémétrie et tâches programmées.
   Adapter seulement ceux nécessaires à une CI Community du fork.

**Sortie :** baseline privée restaurable, source libre figée, fork correctement
routé, branche de travail et budget de ressources ; aucun impact sur le LAN.
**Vérification :** état Git, remotes, checksums, liste des services et ports.

### G1 — Prouver le build Community et les capacités natives

**Dépendance :** G0.

1. Fixer Community avant installation ; rendre le choix persistant dans les
   commandes développeur et CI. Aucun contexte d’extension propriétaire Docker.
2. Construire l’image à partir du fork, dépendances verrouillées et bases
   épinglées ; relever provenance, inventaire des dépendances et licences.
3. Lancer un Grist jetable isolé : connexion OIDC Core sans activation,
   création/modification de document, formule avec sandbox, partage natif,
   pièce jointe et redémarrage persistant.
4. Qualifier S3 snapshots/attachments et l’interface de groupes du build exact.
5. Consigner les écarts natifs qui imposent du code en G2–G7. Une capacité
   nécessaire indisponible doit être développée en libre, pas remplacée par
   une activation « gratuite ».

**Sortie :** preuve d’un produit Community autonome ; décision OIDC et stockage
justifiée ; pas d’incertitude commerciale repoussée après le développement.
**Vérification :** un smoke runtime ; la configuration et l’image sont examinées
pour cette contrainte essentielle, sans scripts d’assertion de contenu métier.

### G2 — Associations durables et synchronisation People/ST

**Dépendance :** G1.

1. Ajouter migrations Home pour les associations, états de projection et
   versions de session ; réutiliser les entités natives pour utilisateurs/groupes.
2. Livrer bootstrap en simulation/application, réexécutable et sans restauration
   implicite d’un droit volontairement retiré.
3. Ajouter le consommateur Grist People et le service ST, avec organisation et
   identifiants stables ; émettre des credentials limités et distincts.
4. Implémenter le lecteur de snapshots et les décisions ST selon section 4.5.
5. Ajouter une commande de diagnostic/synchronisation limitée à Grist, sans
   dump d’annuaire nominatif ou secret dans les logs publics.

**Sortie :** projection complète visible, idempotente, refus d’une projection
partielle et décisions expirant correctement.
**Vérification :** contrat paginé, révision modifiée en cours de lecture et
rejeu sur une petite base ; mêmes identifiants après deux synchronisations.

### G3 — Connexion, rattachement et déconnexion

**Dépendance :** G2.

1. Raccorder OIDC au principal avant résolution de l’utilisateur Grist.
2. Étendre les types de session et chemins secondaires fondés sur l’email.
3. Ajouter l’attente de rattachement approuvé, les erreurs utiles et le retour
   au document demandé sans ouverture anticipée.
4. Appliquer preuve récente, suspension et version de session ; raccorder la
   déconnexion de suite et l’administrateur de récupération.
5. Désactiver les modes de test/démonstration et les associations implicites.

**Sortie :** connexion commune Keycloak, identité inconnue refusée, aucun
compte doublonné par changement de profil, logout cohérent.
**Vérification :** un parcours OIDC réel et tests ciblés de mauvais issuer,
subject/audience, collision d’email et preuve périmée.

### G4 — Groupes, partage et administration des ressources

**Dépendance :** G2–G3.

1. Projeter les groupes d’équipe et les membres par UUID ; gérer tombstones,
   renommage et reprise sans héritage par homonymie.
2. Raccorder les groupes natifs aux ACL du site, workspace et document.
3. Compléter les sélecteurs Web et la lisibilité des droits effectifs ; gérer
   recherche/pagination, groupes retirés et refus serveur.
4. Garantir la provenance des droits et la distinction administration/contenu.
5. Qualifier les règles fines ; ajouter seulement le contexte de groupe qui
   manque pour leur application côté serveur.

**Sortie :** un responsable partage un document avec un groupe People depuis
le Web ; ses membres ont les bons droits sans ACL individuelles dupliquées.
**Vérification :** lecteur/éditeur, retrait du groupe, droit manuel indépendant,
groupe homonyme recréé et accès hors organisation.

### G5 — Révocation sur toute la surface documentaire

**Dépendance :** G3–G4.

1. Tracer HTTP, WebSocket/RPC, diffusion, téléchargements, pièces jointes,
   exports, copies, tâches et jetons disponibles dans le build.
2. Brancher le contrôle partagé et invalider les caches natifs concernés.
3. Faire respecter les échéances sans action du client ; traiter le passage
   en lecture seule et les messages déjà en file.
4. Raccorder la politique de publications publiques ; respecter la distinction
   entre lien autonome, invitation nominative et accès à l’application.
5. Fermer les contournements par clés API, comptes techniques ou endpoints
   exceptionnels, sans bloquer le bootstrap et la santé machine nécessaires.

**Sortie :** borne de révocation prouvée sur document déjà ouvert et API ;
indisponibilité distincte du refus ; aucun contrôle limité à la tuile catalogue.
**Vérification :** suspension, retrait ST, downgrade et expiration du bail ;
vérifier aussi l’absence de réception de mises à jour après révocation.

### G6 — Stockage, budgets ST et quotas stricts

**Dépendance :** G1–G2 ; G5 avant qualification finale.

1. Finaliser la formule d’usage, le propriétaire comptable et les réserves
   d’exploitation de section 5 ; écrire des exemples chiffrés vérifiables.
2. Configurer le volume documentaire, Home, Redis et S3 privés ; qualifier les
   opérations de stockage et l’isolation d’IAM.
3. Adapter les entitlements ST nécessaires à Grist en réutilisant les comptes
   par principal et les métriques existantes. Exposer plafonds explicites et
   révision, pas seulement `can_store` calculé sur une collecte ancienne.
4. Implémenter réservations, mesure transactionnelle, rejets sans corruption,
   récupération après interruption et contrôle sur toutes les opérations de
   croissance ; aucun scan global à chaque frappe.
5. Ajouter réglages Web, compteur utilisateur et métriques ST : mêmes unités,
   usage confirmé/réservé, date de mesure et état de reprise.
6. Livrer la rétention et la purge qui libèrent réellement le quota ; surveiller
   l’enveloppe physique des snapshots, sauvegardes et temporaires.

**Sortie :** plafonds par organisation/propriétaire effectifs, concurrence sûre,
messages de quota exploitables, données conservées lors des refus.
**Vérification :** deux croissances concurrentes près de la limite, import et
pièce jointe, formule entraînant une croissance, copie/transfert, interruption
entre commit et confirmation, purge et redémarrage avec réservations en cours.

### G7 — Catalogue, navigation et installation reproductible

**Dépendance :** G3–G6.

1. Enregistrer URL et métadonnées Grist dans ST ; réutiliser le catalogue
   générique des quatre applications, sans listes spécifiques dupliquées.
2. Ajouter le retour vers la suite dans Grist, logout, liens profonds et états
   de refus/indisponibilité/quota, avec traductions et clavier.
3. Livrer Compose, exemples de configuration, scripts natifs et documentation
   de bootstrap, mises à jour et récupération.
4. Vérifier sandbox, journaux, limites et santé avec le profil LAN retenu.

**Sortie :** installation relançable depuis un checkout propre du fork et
navigation cohérente entre les cinq applications.
**Vérification :** parcours navigateur ciblé catalogue → Grist → document
partagé → retour Drive/Docs ; démarrage avec configuration manquante refusé.

### G8 — Prouver l’indépendance IdP et le mode annuaire externe

**Dépendance :** G3–G7.

1. Recréer une recette isolée avec noms, ports, bases et volumes propres,
   reprenant les scripts et contrats utiles du premier chantier.
2. Créer Authentik Community en version épinglée, sans changer l’issuer LAN.
3. Établir les associations approuvées pour les subjects du client Grist et
   effectuer Keycloak → Authentik → Keycloak sur la même base Grist de recette.
4. Conserver entre les étapes le même principal, `User.id`, document, ACL,
   quota, compte métrique et pièce jointe. Ne pas effacer/recréer la base pour
   donner l’illusion d’une migration réussie.
5. Tester le groupe initial People puis l’import SCIM externe vers People,
   y compris retrait d’appartenance et suspension. Ne pas confondre absence
   de claim groupe avec suppression complète d’un annuaire.
6. Vérifier connexion commune et logout des applications raccordées ; ne
   relancer du socle existant que les contrôles touchés par cette extension.

**Sortie :** conservation d’identité/données/droits et révocation mesurées avec
deux IdP. Entra et les autres IdP sont compatibles par contrat, non déclarés
testés sans leur environnement réel.
**Vérification :** un scénario de bascule réversible, avec refus et retrait
d’accès réels ; conserver uniquement les preuves assainies.

### G9 — Sauvegarde, restauration et mesure de coût

**Dépendance :** G6–G8.

1. Livrer la sauvegarde coordonnée de section 9 et son manifeste privé.
2. Restaurer dans un projet isolé : Home, documents, pièces jointes et versions ;
   vérifier intégrité, formules, ACL et accès avec l’état actuel de People/ST.
3. Mesurer navigation, ouverture, sauvegarde d’une action et gros import sur
   petit document puis document représentatif plus volumineux. Réutiliser les
   fixtures, sans créer une campagne de benchmark permanente.
4. Vérifier absence d’appels People/ST par frappe, nombre de requêtes borné,
   synchronisation paginée et mémoire stable sur transferts ; optimiser
   seulement les surcoûts mesurés du raccord.

**Sortie :** restauration réelle et coût de l’adaptation mesuré, sans
régression bloquante de coédition ou épuisement du serveur.
**Vérification :** une restauration et comparaison avant/après sur les opérations
touchées ; reprendre uniquement les essais affectés par une correction.

### G10 — Activer le LAN et faire la recette finale utile

**Dépendance :** G7–G9.

1. Vérifier une sauvegarde fraîche, puis démarrer Grist en conservant tous les
   services existants. Appliquer uniquement les adaptations nécessaires des
   autres applications, avec redémarrages ciblés si requis.
2. Enregistrer Grist dans le Keycloak réel via son client dédié ; publier le
   consommateur People, le service ST et les politiques choisies.
3. Utiliser des documents de test identifiables et des comptes de recette.
   Le quota Drive de test de 20 Go est conservé ; ne pas le modifier en
   supposant que cela configure aussi Grist.
4. Effectuer la matrice de section 8, réutilisant les preuves déjà acquises
   pour les mêmes sources/images plutôt que tout refaire.
5. Vérifier une connexion existante Drive/Docs et les accès NAS/S3 concernés
   si leurs services ou chemins ont été touchés ; aucun nouveau scan NAS.
6. Supprimer les données de recette créées, downloads locaux, uploads,
   corbeilles/versions de test et projets Authentik isolés, par leurs identifiants
   enregistrés. Conserver les sauvegardes de reprise et les données antérieures.

**Sortie :** les cinq applications sont utilisables sur le LAN, le Keycloak et
les stockages précédents fonctionnent, et aucun déchet de recette ne reste.

### G11 — Documenter, publier le fork Apoze et clôturer Git

**Dépendance :** tous les lots précédents validés.

1. Produire guides, état final et manifeste de section 11 ; vérifier qu’une
   nouvelle session peut reprendre sans fichiers cachés dans `tmp/`.
2. Relire le diff final pour identité, autorisation, quotas et stockage ; lancer
   les contrôles ciblés restant nécessaires et la checklist de publication.
3. Intégrer les commits validés sur `Apoze/grist` `main` et les publier
   uniquement vers `https://github.com/Apoze/grist.git`.
4. Supprimer les branches de chantier intégrées conformément à section 10,
   et vérifier branche par défaut, références locales/distantes et arbre propre.
5. Relever le SHA et le digest déployés, l’état des services, les preuves et
   les éventuelles limites opérationnelles. Toutes les exigences du périmètre
   doivent être cochées ; un point bloquant n’est pas une « finition future ».

**Sortie :** `Apoze/grist` propre avec seulement `main`, code publié et
reconstructible, environnement fonctionnel, aucune écriture officielle.

## 8. Validation minimale fondée sur le comportement

Les ajouts de tests doivent protéger une frontière ou une panne réelle.
Réutiliser Mocha, les tests serveur/navigateur et les fixtures déjà présents
dans Grist. Utiliser les outils existants des dépôts Django/Next seulement
pour leurs fichiers touchés ; ne pas introduire un second framework de tests.

| Réf. | Preuve minimale | Exécution |
| --- | --- | --- |
| T1 | Image Community sans clé, OIDC et sandbox effectifs | Une fois sur l’image qualifiée ; à refaire si chaîne de build modifiée |
| T2 | Principal/local user conservés, subject inconnu et collision email refusés | Test d’intégration de l’adaptation + parcours OIDC G3 |
| T3 | Snapshot partiel refusé, révision obsolète non appliquée, reprise idempotente | Petit test paramétré de synchronisation |
| T4 | Groupe lecteur/éditeur, retrait, droit manuel indépendant, homonyme, isolation | Une fixture partagée serveur, un partage Web réel |
| T5 | Révocation HTTP/WebSocket entrant et sortant, connexion inactive, panne > bail | Horloge simulée côté test ; une mesure réelle de la borne de 120 s |
| T6 | Clé API, URL privée, formulaire/lien public respectent leur politique | Cas négatifs ciblés sur les chemins activés |
| T7 | Quota global/personnel, concurrence, dépassement, libération et reprise | Tests transactionnels avec petites limites et fichiers réduits |
| T8 | Table, formule, coédition à deux, import/export, pièce jointe, historique | Un document de recette réutilisé dans le parcours final |
| T9 | Keycloak → Authentik → Keycloak conserve IDs, droits et données ; SCIM retire l’accès | Une recette isolée sur la même base |
| T10 | Redémarrage et restauration récupèrent documents/ACL/versions sans réactiver un compte révoqué | Un restore isolé réel |
| T11 | Catalogue des cinq applications et non-régression Drive/Docs/NAS/S3 touchée | Un smoke LAN ciblé, pas un full E2E du premier chantier |
| T12 | Build, migrations et configuration depuis checkout propre, publication Apoze seulement | Une fois sur le candidat final, puis vérification Git distante |

Jeu de données partagé : un propriétaire, un éditeur, un lecteur/révoqué,
deux groupes et un cas étranger à l’organisation. Employer des limites de
quelques Mo pour éprouver la saturation ; ne pas uploader 20 Go uniquement
pour tester une comparaison de quota. Pour les performances, ajouter un seul
document plus volumineux, sans contenu utilisateur.

Commandes Grist à sélectionner d’après le `package.json` retenu : build/type
check natif, ESLint sur le diff, puis fichiers Mocha précis ou `GREP_TESTS`
sur les suites serveur concernées. Ne pas lancer `yarn test` sans filtre :
ce script inclut plusieurs familles de tests et des navigateurs.
[Scripts étudiés](https://github.com/gristlabs/grist-core/blob/v1.7.19/package.json).

Faire une seule revue navigateur ciblée des écrans modifiés avec les contrats
QA du dépôt. Réexécuter une preuve seulement après modification concernée,
échec, changement de dépendance significatif ou doute non résolu. Un full
multinavigateur n’est pas un préalable automatique à chaque lot.

Les tests de version/digest, secrets, absence d’extensions propriétaires et
routage Git vérifient des contraintes de déploiement importantes. Ils ne
remplacent aucun test de comportement. Ne pas écrire de tests `readFile`/regex
pour prétendre prouver qu’un contrôle de quota ou d’accès fonctionne.

## 9. Sauvegarde, restauration et retour arrière

### Données nécessaires

Sauvegarder la base Home, les fichiers documentaires cohérents, pièces jointes,
snapshots/références et versions S3 nécessaires, configuration privée, versions
de schéma, SHA/digest et correspondances de principals. Les sessions sont
invalidables ; leur restauration ne doit jamais réactiver une ancienne preuve.

Utiliser les mécanismes de snapshot natifs puis un point coordonné : bloquer
brièvement les nouvelles écritures Grist, laisser finir les opérations
acceptées, vider les écritures différées et relever une génération cohérente
avant dumps et snapshots. Ne pas copier un SQLite ouvert au hasard ni
considérer un `pg_dump` seul comme sauvegarde complète. Limiter cette pause
à Grist et mesurer sa durée.

### Preuve et retour arrière

1. Restaurer vers volumes, base et buckets de recette distincts, sans écraser
   l’environnement actif ; ouvrir les documents et leurs versions attendues.
2. Comparer checksums des pièces jointes, contenu de la fixture, nombre de
   documents, IDs propriétaires et ACL ; ne pas journaliser de données réelles.
3. Resynchroniser People/ST et vérifier qu’une suspension postérieure à la
   sauvegarde reste appliquée. Recalculer les compteurs/réservations incertains.
4. Préférer migrations additives compatibles avec un rollback d’image ;
   documenter les migrations qui ne le permettent pas et leur restauration.
5. En cas d’échec LAN, désactiver l’entrée Grist et arrêter ses nouvelles
   écritures, préserver les données, remettre la version connue compatible.
   Ne pas remettre une ancienne base sans traiter les écritures intervenues.
6. Une panne Grist ou son rollback ne doit pas imposer de restauration Drive,
   Docs ou NAS. Pour une adaptation People/ST, utiliser sa sauvegarde et sa
   procédure propres, sans perdre les opérations concurrentes du reste de la
   suite.

Conserver un manifeste assaini dans Git et les sauvegardes sous répertoire
privé durable hors Git. Supprimer les ressources de tests uniquement à partir
de leur inventaire ; un volume Docker inutilisé n’est pas une preuve qu’il
ne contient pas de données à conserver.

## 10. GitHub et clôture avec une seule branche

### Règles de publication de ce chantier

| Dépôt | Usage autorisé à l’exécution |
| --- | --- |
| `https://github.com/Apoze/grist.git` | Création du fork, développements, commits, publication sur `main`, nettoyage des branches intégrées |
| `https://github.com/gristlabs/grist-core.git` | Lecture/fetch seulement ; push désactivé localement |
| `https://github.com/suitenumerique/*` | Consultation seulement ; aucune écriture ni proposition de modification |
| Drive/ST/People/Docs locaux | Adaptations strictement nécessaires et sauvegardées ; leurs publications ne sont pas implicitement autorisées par l’objectif de propreté du fork Grist |

À la rédaction de ce plan, aucune création/publication GitHub n’est effectuée.
Lorsque l’utilisateur demande son exécution, la création et la publication
finale du fork Apoze décrites ici font partie du résultat demandé. Ne pas
ouvrir de PR officielle pour accomplir une dépendance locale. Enregistrer les
adaptations des autres dépôts dans le manifeste de livraison pour une reprise
reproductible, sans les publier subrepticement.

Dans `/root/Apoze/grist` : `origin` doit nommer explicitement
`https://github.com/Apoze/grist.git` en lecture/écriture ; `upstream`, s’il est
configuré, doit nommer `https://github.com/gristlabs/grist-core.git` en lecture
seule avec URL de push neutralisée. Fixer la destination de push à Apoze et
inclure `--repo Apoze/grist` pour les commandes GitHub qui le permettent.
Les scripts et workflows ne doivent pas déduire une destination officielle
du champ `repository` historique de `package.json`.

### Séquence de clôture

1. Fetch de `https://github.com/Apoze/grist.git` ; déterminer `main`, les
   différences et d’éventuels nouveaux commits. Aucun force-push ni reset.
2. Vérifier le diff, les secrets, notices libres, changelog et conventions
   locales du fork ; pas de commit `fixup!` laissé dans la livraison.
   Passer les checks natifs exigés et la validation ciblée de section 8.
3. Intégrer la branche de chantier sur `Apoze/grist` `main` par avance rapide
   si possible, sinon merge normal après résolution et test ciblé. Les PR ne
   sont pas nécessaires pour cette livraison ; aucune PR vers les sources.
4. Publier uniquement `Apoze/grist` `main`, avec un diff et une destination
   explicites. Vérifier ensuite que le SHA distant est le SHA validé.
5. Définir `main` comme branche GitHub par défaut de `Apoze/grist` si nécessaire.
6. Inventorier toutes les branches locales/distantes du fork, pas seulement
   la branche de travail courante. Vérifier leur intégration avant suppression.
   Utiliser une suppression locale normale des branches intégrées et supprimer
   leurs correspondantes Apoze après publication réussie.
7. Si une branche préexistante contient un travail unique, l’inspecter et
   l’intégrer proprement avant suppression. Une divergence inconnue n’autorise
   pas à effacer du travail pour afficher « une branche ».
8. Retirer les worktrees temporaires propres, passer le checkout principal
   sur `main`, vérifier les fichiers suivis et non suivis. Ne pas masquer de
   code requis dans `.gitignore` pour obtenir un arbre propre.
9. Vérifier que `refs/heads/` local et les heads GitHub de `Apoze/grist`
   contiennent uniquement `main`, sans avance/retard et avec le même SHA.
   Les tags et références distantes de lecture ne sont pas des branches de
   développement à supprimer indistinctement.
10. Relever les remotes et leur rôle, la branche par défaut et l’URL complète
    `https://github.com/Apoze/grist/tree/main` dans la livraison.

Respecter les checklists spécifiques de tout dépôt supplémentaire qui serait
explicitement autorisé à être publié. Une publication Grist ne justifie pas
de lancer les suites complètes Drive ou de nettoyer ses changements antérieurs.

## 11. Documents, suivi de reprise et définition de terminé

### Documents à livrer avec le code

Le présent plan reste canonique dans Drive, à son emplacement indexé. Le fork
Grist doit en revanche être autonome pour son installation et son exploitation :

- `README.md` : identité du fork, Community, commandes de démarrage et liens.
- `AGENTS.md` court : règles Apoze, remotes officiels en lecture seule, tests
  ciblés et documents à consulter ; aucun long historique recopié.
- Documentation Grist d’identité/accès, installation, quotas et restauration
  dans un dossier logique de son arborescence, avec un index unique.
- Une décision d’architecture courte pour le raccord People/ST, son schéma
  versionné et la comptabilité retenue ; pas un second modèle d’identité.
- Exemples Compose/env sans secrets, fixtures et commandes de recette ciblée.
- Manifeste d’intégration : SHA de chaque dépôt touché, patches locaux requis
  et leurs empreintes, versions/digests, schémas/API, résultats de validation.
- Guide de mise à jour à partir des sources officielles en lecture seule,
  conservation des adaptations Apoze et liste des zones à retester.

L’état de chantier et les preuves assainies sont à ranger sous
`output/implementation/grist-community-integration/` dans Drive :
`current-status.md`, `validation-final.md`, `delivery-manifest.json`.
Éviter de multiplier plans concurrents et listes de tâches. Les anciens plans
identité/stockage et leurs rapports gardent leurs chemins actuels.

À chaque arrêt ou reprise, `current-status.md` indique : lot courant, critères
déjà prouvés, fichiers/dépôts modifiés, SHA/digest réellement lancé, état des
services, prochaine action précise, problèmes non résolus et ressources de
test restantes. Ne jamais écrire « fini » parce qu’un build ou login passe.

### Critères cumulatifs de clôture

- [ ] Build et runtime Community sans activation, extension propriétaire ou
  dépendance à Grist Cloud pour les fonctions livrées.
- [ ] Fork `Apoze/grist` autonome ; seules ses destinations autorisées ont
  reçu des écritures ; `main` est l’unique branche locale et distante.
- [ ] Identité durable et absence de fusion par email ; bascule réversible
  Keycloak/Authentik avec conservation des comptes, données, droits et quotas.
- [ ] Groupes People partageables depuis le Web, rôles Grist effectifs,
  provenance des accès préservée et frontière d’organisation vérifiée.
- [ ] ST administre l’accès et les budgets ; politiques réellement appliquées
  sur URL directes, API, coédition, fichiers et tâches concernées.
- [ ] Révocation et logout qualifiés avec échéances mesurées ; refus,
  indisponibilité et publication publique correctement distingués.
- [ ] Quotas indépendants du stockage, concurrence et reprise après interruption
  vérifiées ; corbeille, historique, temporaires et purge maîtrisés.
- [ ] Table, formule, coédition, import/export, pièce jointe et restauration
  fonctionnent sur l’image déployée, avec sandbox actif.
- [ ] Catalogue et navigation cohérents entre les cinq applications ;
  administration courante possible depuis ST, People ou Grist.
- [ ] Environnement LAN précédent conservé, Keycloak réel et NAS/S3 Drive
  utilisables ; aucun doublon applicatif de recette laissé actif.
- [ ] Sauvegarde restaurée réellement, documentation reproductible et preuves
  assainies conservées hors des répertoires temporaires.
- [ ] Fichiers, downloads, objets/versions et conteneurs de recette nettoyés,
  sans suppression de données antérieures ni de sauvegardes nécessaires.
- [ ] SHA local, SHA GitHub `Apoze/grist` `main` et source de l’image déployée
  concordent ; aucun correctif requis ne reste seulement sur le serveur.

La livraison finale doit nommer les URL utilisables, ce qui a été développé,
les preuves acquises, le SHA/digest et les limites explicites de périmètre.
Toute exigence ci-dessus non satisfaite doit rester marquée inachevée.
