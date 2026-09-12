# Exploitation — identité, groupes, accès et reprise

[Installation](../installation/suite-identity-and-docs.md) ·
[ADR](../adr/0003-suite-durable-identity-and-access.md) ·
[Suivi de recette](../../output/implementation/suite-identity-access-catalogue/current-status.md).

## Où administrer

| Besoin | Interface et règle |
| --- | --- |
| Équipes et membres locaux | People, interface d'équipes ; administration native accessible au personnel autorisé depuis le menu utilisateur |
| Personne durable, suspension, révocation commune | People `/admin/suite_directory/principal/` |
| Demande de rattachement d'un login | People `/admin/suite_directory/identityrequest/` ; choisir une personne et confirmer une preuve récente |
| Identités déjà vérifiées | People `/admin/suite_directory/externalidentity/` ; aucune fusion par email |
| Organisation People ↔ ST | People `/admin/suite_directory/organizationmapping/` |
| Consommateurs et rotation de clés machine | People `/admin/suite_directory/consumer/` ; secrets saisis sans réafficher leur valeur enregistrée |
| Annuaire externe et autorité de groupe | People `/admin/suite_directory/directorysource/` et `/admin/suite_directory/provisionedgroup/` |
| Applications, droits, comptes et quotas | ST : organisation, service et souscription ; panneau d'accès de l'application et administration native des comptes |
| Droits sur un espace/fichier | Drive : administration des espaces et partages existants |
| Droits sur un document | Docs : partage natif, personnes ou groupes de la suite |

Un administrateur d'équipe ne devient pas administrateur ST. L'accès à ST
requiert sa politique d'application et son rôle opérateur/organisation natif.
Un administrateur People reste limité aux organisations qu'il administre ;
les sélecteurs et déplacements d'équipes appliquent la même limite.

Renommer un groupe conserve son UUID et ses grants. Créer un groupe homonyme
crée une identité distincte. Ne pas remplacer les clés de groupes Django déjà
utilisées dans les ACL Drive. Ne pas attribuer un quota ou un espace depuis
une claim libre de l'IdP.

Pour retirer le dernier propriétaire d'une équipe ou le dernier administrateur
actif d'organisation via les interfaces de gestion, enregistrer d'abord un
remplaçant. Les suppressions/déclassements concurrents sont sérialisés sur leur
parent ; les formulaires en ligne ne peuvent pas supprimer tous les owners
en une seule soumission. La suspension humaine groupée protège le dernier
administrateur. Le signal de sécurité d'un annuaire externe reste prioritaire :
sa désactivation d'un compte est appliquée même si elle impose ensuite une
reprise par le compte natif de secours.

## Délais et déconnexion

- Synchronisation native toutes les **30 secondes**.
- Fraîcheur positive maximale : **90 secondes**. Au-delà, réponse 503 pour une
  vérification indisponible ; aucun accès conservé indéfiniment en cache.
- Borne d'exploitation : retrait effectif dans **120 secondes**. Le backend
  reste l'autorité, même si une vignette de catalogue est encore affichée.
- Preuve de connexion : **15 minutes** au maximum. Une nouvelle authentification
  peut être nécessaire à l'expiration ; ce n'est pas une création de compte.
- La révocation commune augmente l'epoch et la date minimale d'authentification.
  Les cookies, anciens jetons et délégations doivent présenter une preuve
  postérieure. Une réponse perdue de logout ne double pas arbitrairement l'action.

La coédition Docs revalide ses droits pendant la connexion et avant les
nouveaux messages d'écriture. Un déclassement en lecture ferme la connexion
éditable et force une reconnexion avec le rôle actuel. Les délégations WOPI
et URLs privées sont bornées par la preuve et la fraîcheur disponibles.

Un fichier téléchargé et un flux déjà accepté ne peuvent pas être rappelés.
Les liens publics autonomes doivent être révoqués séparément. Ne pas annoncer
qu'une suppression de groupe détruit un accès individuel encore explicitement
accordé au même document.

## Mode annuaire externe, sans imposer un IdP

People reste le mode initial. Pour connecter une source SCIM :

1. Créer une `DirectorySource` dans l'organisation autorisée et y saisir une
   clé longue dédiée ; ne pas réutiliser les clés du catalogue ou d'un client OIDC.
2. Configurer le fournisseur SCIM avec la base People
   `/api/v1.0/suite-scim/`, son Bearer dédié et les ressources Users/Groups.
   L'environnement Authentik de qualification utilise cette API réellement.
3. Importer et examiner les personnes/groupes. L'identifiant externe de la
   source et le `sub` OIDC sont deux données distinctes. Associer un compte
   existant seulement sur preuve explicite.
4. Pour confier un groupe local à la source, ouvrir le groupe provisionné dans
   People : lire l'aperçu des ajouts/retraits, confirmer l'empreinte de cet état,
   puis appliquer le changement d'autorité. Un aperçu périmé doit être refait.
5. En mode externe, les membres se gèrent dans la source. Les écrans et API
   natifs People refusent les modifications concurrentes de ces memberships.
6. Pour revenir au mode People, utiliser le transfert explicite prévu dans la
   même interface. Ne pas simplement effacer le lien de provisioning en base.

SCIM applique `active=false`, mises à jour et retraits avec idempotence et
périmètre de source. Une identité externe supprimée puis recréée ne récupère
pas les anciens grants sur son seul nom. Après une panne du fournisseur,
réconcilier son état complet avant de considérer la projection comme actuelle.
La présence d'une claim `groups` dans un jeton n'est pas un import d'annuaire.

Profil livré : discovery `ServiceProviderConfig`, `ResourceTypes`, `Schemas`,
Users/Groups, GET/POST/PUT/PATCH/DELETE, pagination de 200 résultats maximum,
ETag et `If-Match`. Les filtres sont des égalités simples : `externalId` et
`userName` pour Users, `externalId` et `displayName` pour Groups. Pas de Bulk,
tri ni changement de mot de passe. Les corps sont limités à 2 Mio. Une
opération non supportée est refusée explicitement. Vérifier cette discovery
avant de brancher un nouvel annuaire : OIDC seul ne garantit pas son profil SCIM.

## Changer d'IdP ou revenir au précédent

Répéter d'abord le scénario isolé avec un membre, un administrateur, un tiers,
un fichier Drive et un document Docs. La recette Keycloak → Authentik direct
→ Keycloak a été exercée ; aucune qualification Entra n'est déduite de cela.

1. Sauvegarder les quatre bases, l'IdP, les fichiers privés et les stockages au
   point de reprise choisi. Conserver les clients et secrets précédents.
2. Enregistrer les quatre clients du nouvel IdP avec callbacks exacts, PKCE,
   audience et `auth_time`. Vérifier discovery et accès depuis le navigateur
   **et** les conteneurs. Ne pas changer l'issuer du NAS : il n'y en a pas.
3. Ajouter l'issuer approuvé aux consommateurs People et enregistrer les
   associations signées vérifiées vers les mêmes principaux. Traiter les
   subjects pairwise client par client. Une association contradictoire est un
   conflit à résoudre ; elle ne déclenche jamais une fusion automatique.
4. Contrôler la table complète : ancien PK local, principal, organisation,
   ancien issuer/subject, nouveau issuer/subject/client. Inclure les comptes
   de métriques ST et les grants, pas seulement les utilisateurs de login.
5. Depuis People, révoquer les sessions des personnes concernées ; attendre
   l'application des nouvelles révisions. Prévoir la reconnexion des éditeurs.
6. Pendant la courte fenêtre prévue, modifier la configuration privée des
   quatre consommateurs : issuer exact, discovery/endpoints, client/secret,
   paramètres de logout et clés éventuelles. Régénérer les fichiers dérivés
   à partir de l'état privé sauvegardé après modification explicite du nouvel
   issuer ; le générateur refuse volontairement une migration implicite.
7. Relancer uniquement backends/workers/beat concernés, synchroniser annuaire
   et politiques, vérifier les quatre logins et les mêmes UUID/ACL/quotas.
   Ne pas réinitialiser les bases et ne pas recréer les utilisateurs.
8. Tester un retrait et la fermeture de la coédition. Désactiver l'ancienne
   association seulement après succès ; garder la configuration de rollback.

Le retour suit les mêmes étapes, y compris une **nouvelle révocation** des
sessions. Revenir à un ancien issuer ne doit pas ressusciter ses vieux cookies.
Une panne de logout IdP n'empêche pas la révocation applicative ; l'utilisateur
est averti de la session IdP éventuellement restante.

## Diagnostic et reprise d'une panne

Commencer par les services de leur projet, sans changer d'environnement :

```bash
cd /root/Apoze/drive
docker compose ps
cd /root/Apoze/st-deploycenter
make status
```

Si la cible `status` n'existe pas dans une version ultérieure de ST, utiliser
`docker compose ps`. Pour People/Docs, utiliser la commande Compose à deux
fichiers du guide d'installation suivie de `ps`.

Les diagnostics d'administration du paquet `suite_identity` montrent la
révision et les dates de vérification ; ils sont en lecture seule pour éviter
une correction manuelle qui accorderait des droits. Les commandes suivantes
réutilisent exactement la synchronisation des workers :

```bash
python manage.py suite_sync_directory
python manage.py suite_sync_policy
python manage.py check --tag security
```

Exécuter dans le backend concerné, avec son environnement privé. Une liste
partielle, une révision périmée ou une réponse non conforme est rejetée sans
remplacer l'instantané valide. Après rétablissement de People/ST, une lecture
complète et les politiques actuelles rétablissent les accès sans réimporter
les comptes. Ne pas contourner une panne en augmentant arbitrairement la durée
de fraîcheur ou en faisant d'un worker un utilisateur universel.

Un conteneur de coédition « Up » peut héberger un compilateur arrêté : vérifier
le endpoint HTTP interne de collaboration et un vrai échange entre deux
sessions. Les sorties `dist`, Next et emoji sont propres au conteneur. Ne pas
les rendre exécutables via un chmod récursif des sources ou secrets.

Ne pas coller des logs contenant des callbacks OAuth, headers, cookies ou URLs
signées dans un ticket. Conserver les détails privés et ne partager que le
statut, le service, la révision et la classe d'erreur.

## Accès natif de secours

Chaque application dispose d'un compte local d'administration distinct, sans
association à un principal de la suite. Les identifiants générés sont dans
`/root/Apoze/drive/data/suite-local/recovery-accounts.json` (0600), à conserver
avec la sauvegarde des secrets et à consulter uniquement sur le serveur.

Accéder à `http://192.168.10.123:<port-api>/admin/login/` avec le compte de
l'application. La connexion native ne dépend pas de l'IdP. Elle autorise
l'administration Django et **n'accorde pas l'accès aux API utilisateur**.
Ne pas associer ce compte au principal d'une personne ou le partager avec le
compte NAS. Fermer sa session native après la réparation.

Sur une autre installation, créer le compte par la commande Django native
`python manage.py createsuperuser` dans chaque backend, avec un mot de passe
fort saisi interactivement. Drive/ST/Docs utilisent `admin_email` comme login
administratif ; People utilise `sub`. Ne pas passer le mot de passe en argument.
La procédure de récupération reste possible depuis le serveur si People ou
l'IdP est indisponible ; elle suppose l'accès d'exploitation à ce serveur.

## Sauvegarde et restauration

Conserver ensemble :

- dumps PostgreSQL des quatre applications, des bases Keycloak et les rôles
  nécessaires ; exports/configurations des IdP candidats ;
- les checkouts aux révisions Apoze publiées, leurs locks et wheels ;
- fichiers privés d'environnement, clés, comptes de secours et configuration
  S3/IAM ; accès 0700/0600 sur leur archive ;
- buckets/versions Docs et Drive, métadonnées SeaweedFS et volumes physiques ;
- snapshot NAS et correspondance des chemins/espaces, via les mécanismes du
  NAS. Les credentials SMB de Drive ne sont pas supposés administrateurs ZFS.

Pour un point de reprise cohérent, suspendre les nouvelles écritures et les
éditeurs durant la capture coordonnée. Un `pg_dump` ne contient pas les octets
S3/NAS. Une archive à chaud du répertoire SeaweedFS sans cohérence du filer et
des volumes n'est pas une sauvegarde qualifiée.

Exemple de dump privé, depuis le serveur, sans afficher le mot de passe :

```bash
umask 077
mkdir -p /chemin/prive/sauvegarde-suite
docker exec drive-postgresql-1 sh -c \
  'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > /chemin/prive/sauvegarde-suite/drive.pgdump
```

Appliquer la même méthode à ST ; People et Docs sont les bases `people` et
`docs` du conteneur `suite-local-suite-postgres-1`, utilisateur PostgreSQL natif.
Les répertoires privés et les snapshots de stockage doivent être associés au
même manifeste daté. Les sauvegardes et preuves privées de ce chantier sont
conservées sous `/root/Apoze/drive/data/suite-local/backups/2026-09-08/`, hors
des artefacts publics. Le manifeste distingue les dumps avant migration,
ceux restaurés pendant la recette et l'état final après nettoyage.

Pour exercer une restauration, créer une base **isolée**, restaurer avec
`pg_restore --no-owner --no-privileges --exit-on-error`, puis comparer les clés
primaires et associations conservées, groupes et overrides. Restaurer aussi
un document et ses versions dans un bucket distinct, comparer les hashes et
métadonnées, et vérifier la relecture. Ne jamais tester `--clean` sur la base
active. La recette du 8 septembre a restauré les quatre bases et cinq versions
d'objets Docs ; ses bases/bucket de test ont été supprimés après comparaison.

Avant une vraie remise en service : conserver la révision actuelle des
révocations, réconcilier avec l'autorité encore en service, révoquer les anciennes
sessions et renouveler les secrets compromis. Un ancien dump n'est pas une
instruction de rétablir des accès retirés depuis. Les projections doivent
retrouver une révision complète et des politiques fraîches avant de servir
les utilisateurs ; ne pas forcer une ancienne révision dans un diagnostic.

Un rollback applicatif conserve les schémas additifs et les données. Restaurer
les images/configurations compatibles sauvegardées, les associations vérifiées
et l'issuer prévu ; ne pas inverser arbitrairement les migrations contenant
l'état d'identité. Les tags locaux `drive:suite-before-rollout` et
`st-deploycenter:suite-before-rollout` sont des repères de cette exécution,
pas des images publiées ni un remplacement de la sauvegarde des sources.

## Nettoyage et limites du lot

Les fixtures appartiennent à un manifeste de recette. Pour Drive S3, passer
par corbeille puis suppression définitive native et vérifier la purge. Pour
le NAS, supprimer uniquement les chemins synthétiques explicitement créés.
Pour Docs, supprimer le document et ses pièces jointes de recette, y compris
les versions temporaires. Supprimer les téléchargements locaux de ces tests.

Sur le S3 versionné Drive existant, la suppression native appelle
`Storage.delete` : les anciennes versions et marqueurs peuvent rester dans
le bucket. Le nettoyage de recette vérifie donc aussi `ListObjectVersions`
et retire uniquement les versions sous les préfixes des UUID synthétiques
recensés. Ce chantier ne change pas la politique générale de rétention du S3
Drive et ne purge jamais les versions de fichiers préexistants.

Les projets `suite-identity-qa` et l'Authentik de qualification sont distincts
de `drive`, `st-deploycenter` et `suite-local`. Leur arrêt/nettoyage n'autorise
pas un prune global. Garder les volumes persistants et les sauvegardes utiles.

Ce lot livre Docs autonome avec SSO/groupes/navigation. Le rangement des
Documents Docs dans les espaces Drive, les exports interapplications et un
quota commun à toutes les applications restent des chantiers distincts.

## Recyclage borné du worker People local

Conserver cet override avec les fichiers People/Docs locaux :

```sh
docker compose --env-file data/suite-local/compose.env \
  -f ../people/compose.suite-local.yaml \
  -f ../docs/compose.suite-local.yaml \
  -f docker/suite/people-worker-resources.yaml up -d --no-deps people-worker
```

Les enfants Celery sont recyclés après leur tâche au-delà de 384 Mio ou
2 000 tâches. La concurrence reste à deux et la file native est conservée.
L'override évite qu'une rétention mémoire de plusieurs jours bloque les
compilations de la suite ; aucune tâche active n'est tuée pour libérer la RAM.
