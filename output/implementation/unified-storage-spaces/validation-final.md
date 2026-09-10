# Recette des espaces unifiés — 6 septembre 2026

Note opérationnelle : les anciens conteneurs de qualification décrits ci-dessous
ont été supprimés lors du [nettoyage Docker demandé par le propriétaire](../../operations/2026-09-06-docker-cleanup.md).
Leurs commandes historiques de relance ne s’appliquent plus. L’environnement
habituel Drive/ST est resté démarré ; les anciennes bases ont été archivées.

Qualification locale sur données synthétiques. Les preuves antérieures et les
mesures sont détaillées dans [l'état d'exécution](current-status.md) et le
[rapport navigateur](browser-qa/report.md). Les lots L0 à L12 sont clôturés localement dans le tableau du plan.

## Périmètre de parité

| Parcours | S3 | MountProvider |
| --- | --- | --- |
| Catalogue, arbre, recherche, favoris et récents | Connexion explicite, grants bornés | UUID inventoriés, mêmes pages et commandes |
| Import et création | Écriture S3 gouvernée | Écriture native gouvernée, création ODF/OOXML |
| Aperçu privé | Viewers existants, accès routé | Même shell, contrat de preview et flux natifs |
| Images et miniatures | Routage vers le bon bucket | URLs d'aperçu natives selon capacités |
| Texte et éditeurs | Texte, Collabora, ONLYOFFICE | Texte, Collabora, ONLYOFFICE ; conflits externes |
| Conversion | Producteur S3 explicite | ONLYOFFICE, copie transformée et source conservée |
| Antivirus | Routage et callbacks liés à l'objet/version | Pas de verdict du pipeline S3 pour les fichiers NAS externes ; contrôle antivirus du NAS distinct |
| Archives | ZIP, extraction ZIP/TAR complète ou sélectionnée | Même destination commune ; extraction soumise au durcissement |
| Téléchargement | GET/HEAD/Range, ZIP de dossiers | GET/HEAD/Range, ZIP de dossiers |
| Partage public | Sous-arbre autorisé et liens historiques | Lecture/téléchargement, dossiers ZIP, révocation et déplacements |
| Suppression/restauration | Corbeille et capacités S3 existantes | Rétention et restauration contrôlée ; pas de fausses versions natives |
| Copies/déplacements | Quatre directions, UUID et journaux | Quatre directions, protection des modifications externes |
| Administration | Connexions, espaces, grants, maintenance | Connexions, racines, inventaire, accès, reprise |
| Quotas | Instance/organisation/utilisateur/namespace/espace | Mêmes budgets, indépendants de la capacité physique |

Les pages publiques conservent leur contrat de lecture/téléchargement ; elles
ne fournissent pas de session d'édition anonyme. Les formats non reconnus et
les fonctions sans capacité réelle restent indisponibles, côté UI et serveur.
L'accès direct NAS reste possible et ne passe pas par les producteurs S3 de
Drive. La migration ne transforme pas les fichiers NAS en Items.

## Scénarios vérifiés

| Critère | Preuve |
| --- | --- |
| V1 Migration | Simulation, deux passages, mêmes UUID/clés/droits ; groupes, corbeille et créateur absent ; plafonds historiques conservés |
| V2 Connexions | Plusieurs S3, comptes/partages SMB distincts, alias, coffre, rotation et contrôle des destinations |
| V3 Autorisation | Privé/partagé/sous-dossier, groupes réels, révocation, liens publics et absence de découverte des voisins |
| V4 Quotas | Réservations, concurrence, scopes cumulés, exception ST et retour à l'héritage, dépassement externe |
| V5 Transfert | Quatre combinaisons de fichiers/dossiers, panne après publication, modification source, rétention et nettoyage successif |
| V6 Fichiers | Import, création, texte, viewers, vrais Collabora/ONLYOFFICE, conversion NAS, archives/extraction, suppression/restauration |
| V7 Navigateur | Administration Drive/ST, quotas, catalogue, recherche/favoris, bureau/mobile, formulaires et clavier |
| V8 Exploitation | Vrai scheduler, restauration isolée DB/coffre/S3 avec VersionIds, audit sans écart, lectures à mémoire bornée |

Les mesures avant/après figurent dans « Navigation et mémoire mesurées » du
rapport courant : SQL/latence d'une page sur 2 000 entrées et mémoire comparée
sur des fichiers de 16/128 Mio. Les copies natives restent bornées ; les archives
ajoutent leur plafond explicite de métadonnées et un spool disque.

La restauration physique S3 a conservé les quatre versions originales de deux
objets dans deux buckets sur un réseau séparé de la source arrêtée. La restauration
NAS via rétention est qualifiée. Une restauration NAS transparente de toutes les
identités demande les snapshots du serveur réel ; un simple miroir d'inodes ou
une réimportation S3 changeant les VersionIds ne suffit pas.

## Déploiement réel et Git

Le code reste local, non committé et non publié, sur `codex/unified-storage-spaces`
dans les deux dépôts. La consolidation Git préalable est décrite dans
[son rapport](git-consolidation.md). Cette recette ne raccorde pas les serveurs,
domaines ou identités réels de l'opérateur.

- Drive : `https://github.com/Apoze/drive.git` (`origin`, fetch/push) ;
  `https://github.com/suitenumerique/drive.git` (`upstream`, fetch-only).
- ST : `https://github.com/Apoze/st-deploycenter.git` (`origin`, fetch/push) ;
  `https://github.com/suitenumerique/st-deploycenter.git` (`upstream`, fetch-only).
- Aucun push, PR ou merge de cette implémentation ; aucune PR base/head à annoncer.

L'amorçage réel et la bascule suivent les guides
[espaces](../../../docs/unified-storage-spaces.md),
[migration](../../../docs/installation/unified-storage-migration.md) et
[restauration](../../../docs/installation/backup-restore.md).
Les frontières de section 3 du plan restent applicables : import arbitraire S3,
OpenZFS, réplication, anciens orphelins/versions et autres applications de la Suite.


## Contrôles finaux et reproduction

- `make lint` : Ruff et Pylint, succès ; Pylint des modules ajoutés aussi vérifié.
- `make frontend-lint` et `yarn tsc --noEmit` dans l’application frontend : succès.
- Jest ciblé : anciennes modales ZIP/extraction, shell montages, preview,
  contrôleur/lecteur d’archives et traductions. Les dépendances des fixtures
  isolées ont été ajustées ; les parcours réels sont qualifiés dans Chromium.
- Pytest ciblé : `test_storage_file_transfer.py`, `test_archive_security_limits.py`,
  `test_storage_migration.py`, `test_services_item_exports.py` et
  `test_api_mount_share_links_public_browse.py`, en complément des contrôles
  du socle déjà consignés. Les relances ont suivi les changements ou échecs.
- Aucune migration de modèle manquante ; `git diff --check` propre dans les
  deux dépôts. Schéma QA 0049, base partagée volontairement non migrée.

Pour rejouer les tests backend, utiliser le contrat de test du dépôt et
`docker compose run --rm --no-deps app-dev pytest -q <scénarios>` avec la
configuration `Test` et les origines définies par ce contrat. Le profil de
qualification a explicitement évité le démarrage de services partagés et la
campagne générale trois navigateurs. Les contenus, sessions et secrets des
fixtures restent hors des artefacts publics.

## Reprise finale après interruption — 6 septembre

La reprise a vérifié les critères du plan et les journaux existants, puis ajouté
la compilation de production des deux frontends et une nouvelle qualification
des interfaces. Aucun lot fonctionnel L0–L12 n'a été retrouvé interrompu.

- Builds Next.js Drive et ST réussis, export statique compris. Le build Drive
  a révélé un import global `react-virtualized` qui chargeait inutilement son
  composant Table et produisait un avertissement React 19 sur `findDOMNode`.
  Les deux composants PDF importent maintenant directement AutoSizer et List.
  Le nouveau build passe sans cet avertissement, sans nouvelle dépendance.
- ESLint frontend réussi ; deux tests PDF existants réussis. Les 27 scénarios
  du test de transfert avec reprise passent également sur les sources finales.
- Chromium, contexte neuf : administration Drive, ouverture du quota ST du bon
  espace, imports PDF synthétiques S3 et NAS via les menus visibles, rendu des
  deux pages et navigation par miniatures. Aucune erreur HTTP/JavaScript.
- Mobile 390 × 844 : sélection dans une archive, choix de destination,
  confinement du focus et fermeture par Échap réussis, sans débordement.
- Après ces imports : zéro transfert/tâche d'administration en attente et zéro
  écart comptable. Les deux interfaces répondent HTTP 200.
- L'index des plans et le contrat stockage n'annoncent plus une implémentation
  « en cours ». Le rapport navigateur identifie clairement ses étapes anciennes.

Les premières tentatives navigateur ont nécessité le renouvellement des seules
sessions synthétiques expirées. Un script renseignait ensuite un champ caché
avant le chargement du contexte de dossier ; le scénario final passe par
« Importer → Importer des fichiers », sans rechargement de page. L'instrumentation
temporaire a été retirée et aucune modification du layout n'a été conservée.

Preuves : [PDF S3](browser-qa/resume-s3-pdf.png),
[PDF NAS](browser-qa/resume-mount-pdf.png),
[dialogue mobile](browser-qa/archive-selected-mobile.png).
Journaux locaux : `/tmp/drive-unified-final-build2.log`,
`/tmp/st-unified-final-build.log`, `/tmp/drive-unified-resume-lint.log`,
`/tmp/drive-unified-resume-pdf-test.log`,
`/tmp/drive-unified-resume-transfer.log`,
`/tmp/drive-unified-resume-browser11.log`,
`/tmp/drive-unified-resume-mobile.log`.

### Interfaces locales conservées après la task

Les interfaces de qualification sont désormais lancées dans les conteneurs
`drive-unified-qa-ui` et `st-unified-qa-ui`, avec `--init` et redémarrage
`unless-stopped`. Elles utilisent les sources et dépendances locales existantes,
sur les mêmes origines isolées `http://127.0.0.1:8980` et
`http://127.0.0.1:8987`. Elles ne dépendent plus d'un terminal actif de la task.

Pour les relancer après un arrêt volontaire :

```sh
docker start drive-unified-qa-ui st-unified-qa-ui
```

Pour les arrêter :

```sh
docker stop drive-unified-qa-ui st-unified-qa-ui
```

Les API, workers et données restent ceux de la qualification isolée. Il ne
s'agit pas d'une installation des nouvelles images sur le NAS/IdP de l'opérateur.
Les règles de publication et la procédure de bascule ci-dessus restent valables.
