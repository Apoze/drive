# Exploitation homelab : Drive et ST Deploy Center

Le manifeste `compose.production.yaml` construit les images locales, utilise
PostgreSQL, Redis et un S3 SeaweedFS privé, et publie uniquement le proxy sur
`127.0.0.1:8970`. ST possède son propre manifeste et ses propres volumes dans
le dépôt `Apoze/st-deploycenter` ; son proxy écoute sur `127.0.0.1:8967`.
Placer ces deux adresses derrière le reverse proxy HTTPS de l'hôte.

Ce profil est prévu pour un hôte Docker. Il ne fournit pas de haute disponibilité
ni de fournisseur d'identité. Les domaines, l'IdP et le NAS de l'opérateur sont
à renseigner et à qualifier avant une ouverture aux utilisateurs. La validation
locale porte sur des données synthétiques, avec de vrais PostgreSQL, S3 et SMB.

## Installation vierge

Dans le dépôt Drive :

```sh
python3 docker/homelab/prepare.py
docker compose -f compose.production.yaml build
```

Le script crée uniquement les fichiers absents. Une seconde exécution conserve
les secrets et les réglages manuels. Les fichiers privés doivent être lisibles
par l'UID 1000 ou le groupe 0 des services, sans accès pour les autres utilisateurs
de l'hôte. Ne pas placer de secret directement dans un manifeste ou dans Git.

Configurer `env.d/production/backend.local` : origine HTTPS, UUID organisation
ST, identifiant du service Drive dans ST et endpoints OIDC. L'IdP doit fournir
un `sub` stable ; conserver `organization_id` avec `OIDC_STORE_CLAIMS` lorsqu'il
est fourni. `STORAGE_ORGANIZATION_ID` est le rattachement explicite de repli d'une
instance à organisation unique. Ne pas activer le rapprochement par e-mail pour
remplacer une identité OIDC différente.

Renseigner les fichiers `secrets/oidc_client_secret` et `secrets/st_service_key`
dans ce même dossier. La clé de service est commune au service enregistré dans
ST et à Drive ; elle est distincte du secret du client OIDC. Sa rotation demande
la mise à jour des deux applications puis leur redémarrage. Les autres secrets
sont générés par `prepare.py`.

Dans ST, exécuter `python3 docker/homelab/prepare.py`, puis configurer
`env.d/production/backend.local` depuis son exemple. Voir `docs/homelab.md`
dans ce dépôt pour le bootstrap complet. Ses secrets
attendus sont `database_password`, `django_secret_key`, `oidc_client_secret`.
Son entrée `secret_entrypoint.py` charge les références de fichiers ; un
`compose exec backend python manage.py ...` la contourne. Utiliser `compose run`
pour les commandes, ou appeler explicitement l'entrée lors d'un `exec`.

```sh
# Dans le dépôt ST, une fois la configuration privée renseignée :
docker compose -f compose.production.yaml build
docker compose -f compose.production.yaml run --rm backend python manage.py migrate --noinput
docker compose -f compose.production.yaml up -d
```

Le bootstrap ST `bootstrap_homelab` attend `--organization-id`, `--drive-url`,
`--operator-url` et `--service-key-file`. Monter ce dernier en lecture seule
dans le conteneur pour cette commande. Les options `--user-limit` et
`--organization-limit` sont en octets ; elles s'appliquent à la création.
Une seconde exécution ne remplace pas les quotas ni les activations existantes.
`--rotate-service-key` est nécessaire pour remplacer une clé déjà enregistrée.
`--admin-email` rattache un utilisateur ST qui s'est déjà connecté avec l'IdP.
La sortie contient les identifiants de l'organisation, de l'opérateur et du
service, jamais la clé.

Revenir dans Drive pour préparer son stockage puis démarrer l'application :

```sh
docker compose -f compose.production.yaml run --rm backend python manage.py migrate --noinput
docker compose -f compose.production.yaml run --rm backend python manage.py storage_inventory --ensure-bucket --initialize-items --all-backends --check --verify-items
docker compose -f compose.production.yaml run --rm backend python manage.py config_preflight
docker compose -f compose.production.yaml up -d
docker compose -f compose.production.yaml ps
```

Le backend attend un S3 sain. L'image frontend utilise l'origine du proxy :
aucune compilation avec le domaine public n'est nécessaire. Le proxy interne
renouvelle la résolution DNS Docker après remplacement d'un conteneur. Le proxy
HTTPS externe doit conserver l'hôte public, définir `X-Forwarded-Proto`, accepter
les flux d'upload sans les charger en mémoire et laisser passer les routes
API/WOPI/streaming. Les bases, Redis et les ports internes S3 restent privés.

Le volume `scratch` porte `/tmp` des processus Drive sur disque pour les
conversions et archives volumineuses. Prévoir son espace libre et le traiter
comme sensible. Les fichiers temporaires abandonnés après un arrêt brutal
peuvent être supprimés pendant une maintenance sans worker ni requête active ;
ne pas purger ce volume pendant une conversion.

## Connexions NAS et espaces virtuels

Avec les espaces unifiés activés, utiliser les [écrans de stockage](unified-storage-spaces.md)
pour les connexions S3/NAS, espaces et accès courants. Le registre ci-dessous
reste une source externe compatible ; sa reprise sous gestion web est explicite.
Voir aussi la [migration](installation/unified-storage-migration.md) pour une
installation existante.

`env.d/production/mounts.local` contient les connexions techniques, par exemple :

```json
[
  {
    "mount_id": "nas-principal",
    "display_name": "Stockage familial",
    "provider": "smb",
    "enabled": true,
    "params": {
      "server": "nas.example.net",
      "share": "documents",
      "username": "drive-service",
      "base_path": "/",
      "password_secret_path": "/run/secrets/nas/principal"
    }
  }
]
```

Le mot de passe correspondant reste dans `secrets/nas/principal`, monté en
lecture seule. Ajouter une connexion par authentification NAS, puis redémarrer
les processus Drive qui chargent le registre. Les sessions SMB sont isolées
par connexion et génération de secret.

Dans l'administration Django Drive, créer un `StorageBackend` dont le
`registry_id` correspond au registre et dont l'organisation est l'UUID ST.
Deux connexions qui voient les mêmes fichiers doivent partager explicitement
le même `namespace`. `namespace_root` positionne chaque connexion dans cet
espace commun. Ne pas créer deux namespaces pour deux vues du même stockage.
Cette correspondance physique doit être vérifiée par l'opérateur ; un nom de
serveur ou une taille de volume ne suffit pas à prouver qu'il s'agit du même NAS.

Créer les dossiers NAS nécessaires puis les `StorageSpace` et leurs droits :

- Vue complète : racine `/`, droit accordé à l'utilisateur ou à son équipe.
- Espace personnel : racine `/users/<UUID utilisateur Drive>`, propriétaire
  fixe correspondant à cet utilisateur. Le propriétaire dispose de son espace.
- Dossier partagé : racine dédiée, droits de lecture/écriture/partage explicites.
  Choisir un propriétaire fixe ou une charge commune à l'espace.
- Attribution au créateur : chaque nouveau fichier créé par Drive est imputé
  à son créateur. Un fichier externe sans auteur identifiable nécessite une
  décision d'attribution ; Drive ne lui invente pas un propriétaire.

Utiliser les noms et la casse réelle des dossiers. Les chemins voisins, liens
symboliques, reparse points, noms de transactions et alias de chemins ne sont
pas des chemins d'accès autorisés par un simple préfixe textuel. La présence de
droits NAS pour le compte technique ne donne aucun droit Drive supplémentaire.
Les chemins d'écriture sont contrôlés côté serveur.

L'inventaire ne lit pas le contenu des fichiers. Il rapproche un instantané
complet de métadonnées, par lots de 500, puis traite les absences. Un scan
incomplet ne déclenche pas de suppression d'usage. Une identité logique conserve
sa charge lorsque l'identité native change après remplacement ou restauration.
Les changements de périmètre restent visibles comme conflits d'attribution.

Pour modifier une racine ou son propriétaire après inventaire, utiliser l'action
d'administration de mise en maintenance, modifier les espaces, puis lancer la
reclassification. Les lectures restent possibles ; les écritures reprennent
après réussite. Ne pas modifier directement les compteurs, réservations ou
identités de namespace en base.

## Quotas et capacité

ST définit les limites de Drive, de ses utilisateurs, de ses namespaces,
espaces et couples utilisateur/backend. L'imputation suit le propriétaire du
fichier et les espaces qui le contiennent ; elle ne change pas parce qu'un autre
utilisateur voit ou modifie ce fichier. Plusieurs vues d'un même objet ne le
comptent pas plusieurs fois dans un même périmètre.

Les limites applicatives n'altèrent aucun quota NAS. Les réservations Drive
empêchent deux workers d'admettre simultanément une croissance incompatible
avec un plafond commun. Une exception personnelle reste soumise aux plafonds
de l'organisation et de l'espace. L'interface ST conserve le zéro historique
« illimité » ; le blocage des nouveaux octets est une option séparée. Une
limite abaissée sous l'usage existant conserve les fichiers et autorise les
réductions et suppressions selon les droits.

Les mesures NAS `caller_available_bytes`, `actual_available_bytes` et
`total_bytes` sont celles exposées à la connexion.
Elle ne prouve pas l'existence ni la valeur d'un quota ZFS, d'un dataset ou d'un
compte NAS. Une intégration de télémétrie native demande le modèle/API du NAS.
`private_logical_bytes` mesure les longueurs de fichiers temporaires/conservés
observés ; ce n'est pas une mesure des blocs physiques après compression,
déduplication ou snapshots. Ne pas additionner les capacités de connexions qui
désignent le même espace physique.

Lors d'une sauvegarde NAS, Drive vérifie aussi l'espace disponible pour les
octets temporaires, par fenêtres bornées, lorsque le provider le fournit.
La mesure ne réserve pas le disque contre un autre client NAS ; une panne ou
un refus natif conserve donc toujours l'original et son journal de reprise.

Les accès directs au NAS restent possibles. Ils peuvent dépasser une limite
Drive sans être interceptés. Les inventaires périodiques rapprochent ensuite
ces changements et Drive bloque sa propre croissance. Un inventaire ancien
ou une publication incertaine n'est pas assimilé à un espace libre. La
réconciliation et la synchronisation ST sont programmées toutes les cinq
minutes ; vérifier que worker et scheduler fonctionnent réellement.
`STORAGE_RECONCILIATION_INTERVAL_SECONDS` et
`STORAGE_INVENTORY_MAX_AGE_SECONDS` permettent d'adapter cette fréquence et
l'âge maximal de l'inventaire au temps mesuré sur le NAS. Par défaut, un
inventaire de plus de quinze minutes empêche les écritures gouvernées.

`STORAGE_MAX_ACTIVE_WRITES_PER_USER` limite chaque acteur à 32 écritures
actives par défaut, tous espaces confondus. Les réservations expirent après
une heure ; une publication incertaine reste retenue jusqu’à rapprochement.

Les déplacements de dossiers gouvernés retournent HTTP 202 avec un identifiant
de tâche. L'interface attend leur résultat ; le journal en base permet de
reprendre une publication dont le worker a perdu la réponse. Le statut est
réservé au demandeur et les droits sur la destination sont revérifiés.

## Passage depuis une installation existante

Prévoir une fenêtre sans écritures Drive, conserver une sauvegarde cohérente
et résoudre les fusions d'identités avant activation. La fusion historique de
comptes est refusée en gouvernance active, car elle contournerait l'imputation
des fichiers et des espaces. Arrêter les anciens workers.
Attendre l'expiration des autorisations S3
déjà émises, ou retirer explicitement leurs droits d'écriture avant d'activer
le nouveau chemin d'upload. Un ancien lien signé encore autorisé ne devient
pas soumis aux réservations simplement parce qu'une variable a changé.

Appliquer les migrations, initialiser les Items historiques, inventorier les
connexions et exécuter `--check --verify-items`. Le contrôle échoue sur un
compteur divergent, une opération active, une attribution ambiguë, une
comptabilité non initialisée ou une différence de taille S3. Il ne supprime ni
ne remplace de fichier pour corriger un écart. Les orphelins S3 et les anciennes
versions natives demandent leur propre rapprochement et politique de rétention.

Après résolution des écarts, activer `STORAGE_GOVERNANCE_ENABLED` sur **tous**
les producteurs, workers compris, puis effectuer un petit upload S3 et une
sauvegarde NAS. Vérifier usage, réservation nulle et accusé d'application ST.
Ne pas mélanger des producteurs anciens et nouveaux contre les mêmes données.

## Récupération et copies conservées

`STORAGE_BACKUP_RETENTION_DAYS` vaut 7 par défaut. Les anciennes copies NAS
restent privées, référencées par leur journal et leur identité native. Le
nettoyage vérifie cette identité ; une copie modifiée par un accès NAS conserve
une nouvelle période de rétention. Une issue ambiguë garde sa réservation.

```sh
docker compose -f compose.production.yaml run --rm backend python manage.py storage_inventory --pending
docker compose -f compose.production.yaml run --rm backend python manage.py storage_inventory --recover --cleanup
```

Pour récupérer une copie conservée, utiliser `--restore <UUID opération>` avec
`--actor <UUID superutilisateur actif>`, `--space <UUID espace autorisé>` et
`--destination <nouveau chemin virtuel>`. L'administrateur doit aussi avoir les
droits d'écriture de cet espace. La restauration passe par les quotas et refuse
une destination déjà existante. Ne pas manipuler les `.drive-txn-*` à la main.

## Sauvegarde, restauration et mise à jour

Sauvegarder ensemble les bases Drive/ST, les objets S3, les fichiers NAS, la
configuration privée et l'état nécessaire à l'IdP. Une copie de PostgreSQL
seule n'est pas une sauvegarde des fichiers. Les copies de récupération Drive
ne remplacent pas une sauvegarde indépendante.

Pour une sauvegarde simple sur un hôte : arrêter les admissions et workers,
attendre/réconcilier les opérations actives, produire les dumps PostgreSQL
(`pg_dump -Fc`), arrêter S3 pour copier son volume complet, et prendre un
snapshot cohérent du NAS. Les accès directs NAS doivent être coordonnés avec
ce snapshot. Protéger et chiffrer les archives selon l'outil de sauvegarde de
l'opérateur. Redis contient notamment les sessions et tâches : sa perte exige
une reconnexion et la reprise des tâches durables.

Restaurer d'abord sur des volumes **et réseaux Docker distincts**. Réutiliser
les identités de bases, namespaces, utilisateurs et secrets nécessaires, puis
rapprocher les fichiers restaurés par inventaire. Contrôler `--check
--verify-items`, une lecture S3, une lecture NAS, une nouvelle sauvegarde, un
refus de quota et la révision ST. Ne jamais lancer deux schedulers restaurés
sur les services de production pendant ce contrôle.

La qualification locale a restauré les deux bases et un volume S3 dans des
projets Docker distincts, puis les fichiers NAS synthétiques dans une autre
racine. Contenus, imputation, compteur commun et nouvelle sauvegarde ont été
vérifiés. La restauration de l'IdP et du NAS réel reste à qualifier sur le
matériel de l'opérateur.

Pour mettre à jour : sauvegarder, construire les images, arrêter les producteurs,
appliquer les migrations avec la nouvelle image, vérifier les comptes, puis
redémarrer web/worker/scheduler ensemble. Le rollback d'un schéma ou d'une
publication de stockage demande une restauration cohérente ; ne pas seulement
redémarrer une ancienne image sur une base modifiée. Conserver les digests
d'images et la révision Git avec chaque sauvegarde.

## Vérifications courtes

Les scénarios ciblés résident dans `test_storage_quota.py`,
`test_storage_s3_governance.py`, `mounts/test_virtual_provider.py` et
`mounts/test_smb_governance_protocol.py`. Ils couvrent les transactions réelles,
le rejeu d'upload, les conflits, la reprise et l'isolation. Le harness
`docker/qualification/storage_loop.py` vérifie la boucle TLS ST/S3/SMB sur
l'environnement synthétique. Voir le dossier d'implémentation pour l'état des
preuves et les derniers contrôles ; ne pas utiliser ses identités de test en
production.
