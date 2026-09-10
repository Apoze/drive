# Installation locale — identité commune, People et Docs

État au 8 septembre 2026 : **installation LAN livrée et qualifiée**. [Décisions](../adr/0003-suite-durable-identity-and-access.md) ·
[Exploitation](../operations/suite-identity-access.md) ·
[Suivi](../../output/implementation/suite-identity-access-catalogue/current-status.md).

## Implantation et versions

| Application | Dépôt local | Source de référence | Version retenue |
| --- | --- | --- | --- |
| Drive | `/root/Apoze/drive` | [Apoze/drive](https://github.com/Apoze/drive), fork spécialisé ; [suitenumerique/drive](https://github.com/suitenumerique/drive) en lecture | État local avec les changements stockage conservés et le socle ajouté |
| ST | `/root/Apoze/st-deploycenter` | [Apoze/st-deploycenter](https://github.com/Apoze/st-deploycenter), [source officielle](https://github.com/suitenumerique/st-deploycenter) en lecture | État local avec politiques et métriques migrées |
| People | `/root/Apoze/people` | [suitenumerique/people](https://github.com/suitenumerique/people), publication désactivée | v1.25.4, `e2188b1a116b6c27d30be93868bfe458cf5ccd4f` + adaptations locales |
| Docs | `/root/Apoze/docs` | [suitenumerique/docs](https://github.com/suitenumerique/docs), publication désactivée | v5.6.1, `3c1275c88da39abb71e045c7deaba3844ca9ac49` + adaptations locales |

Les adaptations locales sont nécessaires : les seuls tags officiels ne
contiennent pas ce socle. Conserver les quatre checkouts, les fichiers non
suivis et leurs patches lors d'un déplacement du serveur. La livraison locale
ne constitue pas une publication GitHub.

| Usage LAN | Adresse |
| --- | --- |
| Drive / API | `http://192.168.10.123:3000` / port 8071 |
| ST / API | `http://192.168.10.123:8960` / port 8961 |
| People / API | `http://192.168.10.123:3001` / port 8072 |
| Docs / API | `http://192.168.10.123:3002` / port 8073 |
| Coédition Docs / médias privés | ports 4444 / 8084 |
| Issuer OIDC commun | `http://192.168.10.123:8083/realms/drive` |
| S3 Drive | port 9000, configuration existante conservée |
| S3 Docs | `http://docs-s3:8333`, réseau Docker interne seulement |

People et Docs partagent un PostgreSQL 16 avec bases/rôles distincts et un
Redis 7.4 avec bases logiques distinctes. Les images PostgreSQL, Redis, Nginx
et SeaweedFS sont figées par digest dans leurs fichiers Compose. Le service
S3 Docs est SeaweedFS 4.46 ; son volume est `suite-local_docs-s3`. Les caches
Next et sorties de compilation de collaboration sont des tmpfs propres à
chaque conteneur. Ne pas sauvegarder ces caches à la place des données.

## Redémarrer l'installation existante

Le script historique reste réservé à Drive :

```bash
cd /root/Apoze/drive
bash run_env_local.sh
```

Il relance sa pile complète. Pour une simple mise à jour de code, préférer les
recréations ciblées ci-dessous. ST reste démarré séparément avec sa commande
native, qui transmet l'UID/GID de l'opérateur :

```bash
cd /root/Apoze/st-deploycenter
make start
```

People et Docs utilisent leur projet persistant commun :

```bash
cd /root/Apoze/drive
docker compose --env-file data/suite-local/compose.env \
  -f /root/Apoze/people/compose.suite-local.yaml \
  -f /root/Apoze/docs/compose.suite-local.yaml up -d
```

Ne jamais ajouter `-v` à un arrêt de cette installation. Ses bases, secrets
et volume S3 doivent survivre aux recréations de conteneurs. Les anciens
Keycloak restent disponibles pour le retour arrière ; les quatre applications
actives utilisent l'issuer Drive commun.

## Secrets et fichiers privés

Répertoire canonique : `/root/Apoze/drive/data/suite-local`, accès 0700,
fichiers sensibles 0600. Il contient `settings.json`, `compose.env`, les
fichiers d'environnement et credentials dérivés People/Docs, les credentials
S3 d'installation et les comptes natifs de secours. Ne jamais le versionner,
le servir par HTTP ou en recopier le contenu dans un rapport.

Drive conserve ses paramètres privés dans `env.d/development/common.local`
et ses secrets dans `data/storage-secrets/suite`. ST utilise
`env.d/development/backend.local` et `data/suite-secrets`. Le compte NAS
existant reste indépendant de l'identité humaine et n'est pas copié vers Docs.

Le générateur crée les secrets une seule fois. Il refuse une modification
implicite d'hôte, d'issuer ou d'organisation d'une installation existante.
Il peut régénérer les fichiers dérivés à partir des paramètres privés conservés :

```bash
cd /root/Apoze/drive
python3 docker/suite/prepare_local.py \
  --host 192.168.10.123 \
  --issuer http://192.168.10.123:8083/realms/drive \
  --organization-id a9caecae-4ba5-41f7-b447-58049718cbbd \
  --state data/suite-local --people /root/Apoze/people --docs /root/Apoze/docs \
  --activate
```

**Nouvelle installation :** commencer sans `--activate`. Renseigner et vérifier
les quatre `policy_service_id` ST avant activation. La clé/secret du client
Drive existant doit être repris depuis sa configuration privée ; ne pas
remplacer son secret par celui généré pour un nouveau client. Le générateur
n'administre pas à distance l'IdP et ne modifie pas automatiquement les fichiers
privés Drive/ST.

Après démarrage du stockage et du backend Docs :

```bash
python3 docker/suite/provision_docs_storage.py --state data/suite-local
```

Cette commande initialise le bucket et vérifie création, lecture, remplacement
de métadonnées et lecture de deux versions. Sa sonde est supprimée. Les secrets
voyagent par stdin, pas dans les arguments du processus. Pour un autre S3,
qualifier ces capacités avant d'y déplacer les documents ; aucune désactivation
du versionnement ou du statut de sécurité ne remplace cette vérification.

## Clients OIDC et contrat générique

Chaque application dispose d'un client confidentiel distinct. Sur cette
installation : `drive`, `apoze-st`, `apoze-people`, `apoze-docs`. Pour chacun :

1. Authorization Code, PKCE S256, scopes `openid email profile`.
2. Callback exact `http://192.168.10.123:<port-api>/api/v1.0/callback/` et
   retour de logout exact `/api/v1.0/logout-callback/`. Aucun wildcard.
3. Issuer exact et endpoints issus de sa discovery approuvée, JWKS/RS256,
   validation `aud`, `azp`, `iss`, `exp`, `iat`, `auth_time`, nonce et state.
4. `max_age=900` ; fournir `auth_time`. Dans Keycloak récent, rattacher le scope
   standard `basic` aux nouveaux clients. Ce réglage Keycloak sert à fournir
   une claim OIDC standard ; aucun branchement applicatif sur sa marque.
5. Pour l'API Bearer d'une application, le jeton d'accès doit avoir sa propre
   audience et des scopes. Un ID token et le jeton d'un autre client sont
   refusés. Docs utilise les sessions natives pour son API navigateur.
6. Désactiver la fusion par email et la création OIDC automatique :
   `OIDC_FALLBACK_TO_EMAIL_FOR_IDENTIFICATION=false`, `OIDC_CREATE_USER=false`,
   et `DJANGO_OIDC_CREATE_USER=false` pour People/Docs.

L'email peut être absent. Les groupes transmis en claims ne remplacent pas
l'autorité People. Un fournisseur aux subjects pairwise fonctionne par
associations explicites par client ; aucun rapprochement par le nom/email.

## Bootstrap et activation sur des données existantes

Effectuer une sauvegarde avant toute association. L'UUID d'organisation vient
de ST ; ne pas créer une organisation homonyme pour faire correspondre un SIRET.
Conserver les UUID des utilisateurs Drive/ST dans le manifeste vérifié. Le
bootstrap People accepte un JSON via stdin, jamais des secrets en arguments :

```bash
docker exec -i suite-local-people-1 python manage.py suite_bootstrap \
  < /chemin/prive/manifest-verifie.json
docker exec -i suite-local-people-1 python manage.py suite_bootstrap --apply \
  < /chemin/prive/manifest-verifie.json
```

Le manifeste contient `organization_id`, `organization_name`, `consumers`,
`principals`, `groups`. Chaque consommateur donne `audience`, `issuers`,
`read_key`, `mutation_key`. Chaque principal donne son `id` durable, son `name`,
son éventuel statut d'administrateur initial et ses identités vérifiées
`{app, issuer, subject}`. Chaque groupe donne son UUID `id`, son `name` et la
liste des UUID `members`. Voir la commande People
`src/backend/suite_directory/management/commands/suite_bootstrap.py` pour les
validations et le test de bootstrap associé. Un replay ne rétablit pas des
droits retirés depuis l'import initial.

Associer chaque compte local existant avec `suite_bind_identity` : d'abord
simulation, puis `--apply`, en conservant le PK local. La commande accepte les arguments `--user-id`, `--principal-id`,
`--organization-id`, `--issuer` et `--subject`. La simulation est le défaut ;
`--apply` effectue l'association. Ne jamais réutiliser le subject d'un autre
client sans preuve. Dans ST, `suite_bind_metric_account` associe
séparément le compte de métriques au principal, en conservant overrides et
historique. Le formulaire du compte ST propose aussi cette liaison avec
confirmation explicite. Ne jamais associer un compte sur une égalité d'email.

Créer/configurer les services et souscriptions ST depuis son administration :
`config.suite_app_id` vaut `drive`, `st`, `people` ou `docs`. Les services LAN
sont respectivement 2, 9, 7 et 8. Conserver le service Drive et sa clé existante.
Chaque service possède sa propre clé machine et sa politique, par groupe ou
personne. Ici, le groupe « Membres de la suite » ouvre Drive/People/Docs et
« Administration de la suite » ouvre ST ; les quotas Drive existants restent
inchangés. Le quota de recette est de 20 000 000 000 octets.

Configurer les quatre consommateurs avec :

| Réglage | Valeur/rôle |
| --- | --- |
| `SUITE_IDENTITY_ENABLED` | `true` seulement après migration préparée |
| `SUITE_APP_ID`, `SUITE_ORGANIZATION_ID` | application et UUID ST explicites |
| `SUITE_OIDC_ISSUER` | issuer commun approuvé |
| `SUITE_DIRECTORY_URL` | People `/api/v1.0/suite-directory/` |
| `SUITE_DIRECTORY_TOKEN_FILE` | clé de lecture propre au consommateur |
| `SUITE_POLICY_URL`, `SUITE_POLICY_SERVICE_ID` | ST `/api/v1.0/suite-policy/`, service associé |
| `SUITE_POLICY_TOKEN_FILE` | clé machine du service ST |
| `SUITE_CATALOGUE_URL` | ST `/api/v1.0/suite-catalogue/` |
| `SUITE_LOGOUT_URL`, `SUITE_LOGOUT_TOKEN_FILE` | endpoint People et clé de mutation |
| `SUITE_IDENTITY_REQUEST_URL` | People `/api/v1.0/suite-identity-requests/` |

Les URLs serveur utilisent un nom accessible depuis le conteneur ; les URLs
publiques du catalogue et les callbacks utilisent l'origine LAN. Les fichiers
privés générés contiennent les valeurs effectives. Ne pas placer ces clés dans
le frontend. Les workers et le beat doivent recevoir le même environnement
que leur backend ; conserver un seul ordonnanceur par application.

Après activation, exécuter une première synchronisation sur chaque backend :

```bash
python manage.py suite_sync_directory
python manage.py suite_sync_policy
python manage.py check --tag security
```

Puis vérifier les diagnostics et le login depuis les quatre applications.
Une identité inconnue peut rester en attente d'approbation : ce refus est
normal jusqu'au rattachement vérifié dans People.

## Reconstruire le paquet commun

Depuis Drive, avec `uv` disponible :

```bash
python3 docker/suite/package_identity.py \
  --st /root/Apoze/st-deploycenter --people /root/Apoze/people --docs /root/Apoze/docs
```

La commande reconstruit une wheel reproductible, la copie dans les quatre
répertoires `src/backend/vendor`, actualise leurs locks et inscrit son SHA-256.
Construire ensuite les images natives ; ne pas monter la source du paquet
commun à la place de la dépendance installée sur le LAN.

```bash
docker build --target backend-development --build-arg DOCKER_USER=1000 \
  -t drive:backend-development /root/Apoze/drive
docker build --target backend-development --build-arg DOCKER_USER=1000 \
  -t apoze/people:identity-dev /root/Apoze/people
docker build --target backend-development --build-arg DOCKER_USER=1000 \
  -t apoze/docs:identity-dev /root/Apoze/docs
```

ST suit son build Compose natif avec l'UID/GID de l'opérateur. Après changement
de wheel Drive, recréer aussi ses volumes anonymes de venv, exclusivement sur
les processus applicatifs :

```bash
ENV_OVERRIDE=local docker compose up -d --no-deps --renew-anon-volumes \
  app-dev celery-dev celery-beat-dev
```

Les frontends et le serveur de collaboration suivent leurs Dockerfiles natifs
et les images nommées dans les fichiers Compose. Leur recette de build et les
patches locaux doivent accompagner le transfert des quatre checkouts.


Builds natifs des trois processus frontend ajoutés :

```bash
docker build -f /root/Apoze/people/src/frontend/Dockerfile \
  --target frontend-dev -t apoze/people:identity-frontend-dev /root/Apoze/people
docker build -f /root/Apoze/docs/src/frontend/Dockerfile \
  --target impress-dev -t apoze/docs:identity-frontend-dev /root/Apoze/docs
docker build -f /root/Apoze/docs/src/frontend/servers/y-provider/Dockerfile \
  --target y-provider-development -t apoze/docs:identity-collaboration-dev /root/Apoze/docs
```

## Rejouer la qualification isolée

Les helpers de recette vivent dans `docker/suite`, dans le checkout Drive
isolé. Ils ne lisent pas les credentials LAN. Depuis ce checkout :

```bash
python3 docker/suite/prepare_qa.py --host 192.168.10.123 \
  --people /root/Apoze/people --docs /root/Apoze/docs \
  --st /root/Apoze/st-deploycenter-worktrees/suite-identity-access
docker compose -f data/suite-identity-qa/compose.json up -d
python3 docker/suite/prepare_authentik_qa.py --host 192.168.10.123
docker compose -f data/suite-authentik-qa/compose.json up -d
```

Les ports 19100–19190 et les volumes des projets de recette doivent être
libres. Les quatre backends utilisent les images construites précédemment.
Migrer leurs bases de recette, puis préparer les associations et politiques
avec les commandes natives décrites dans la section bootstrap. Créer les trois
principaux synthétiques nommés `alice`, `bob`, `outsider`, le groupe
`Qualification editors` (Alice/Bob), les quatre consommateurs et leurs
souscriptions ST. Les subjects Keycloak viennent des identités effectivement
créées dans son realm de recette, jamais d'une adresse email.

Le fichier privé `data/suite-identity-qa/fixture-private.json` conserve
`organization_id` et `principals: [{id, name}, ...]` correspondant à ces trois
principaux. Il sert à préserver ces mêmes comptes pendant la bascule. Les
credentials générés sont dans les répertoires privés de recette. Après le
bootstrap, relancer `prepare_qa.py` avec les mêmes arguments et
`--enable-identity`, puis recréer les consommateurs et synchroniser.

Pour préparer Authentik et exercer son vrai provisioning :

```bash
python3 docker/suite/configure_authentik_qa.py --host 192.168.10.123
```

Ce helper est propre à la qualification : il prépare clients, identités et
source SCIM, sans ajouter de dépendance Authentik au code métier. Effectuer le
transfert d'autorité du groupe dans People après aperçu, puis régénérer la
recette avec `--enable-identity --idp authentik`. Révoquer les sessions et
recréer les consommateurs comme dans la procédure de bascule. Qualifier les
parcours V1–V12 utiles, puis revenir avec `--idp keycloak` et une nouvelle
révocation. Les preuves de l'exécution initiale restent dans la sauvegarde
privée ; ne pas rejouer aveuglément leurs scripts de mutation sur le LAN.

Après conservation des preuves, arrêter uniquement ces deux projets avec
`down --volumes`. C'est l'état laissé à la livraison du 8 septembre ;
`drive`, `st-deploycenter` et `suite-local` restent démarrés.
