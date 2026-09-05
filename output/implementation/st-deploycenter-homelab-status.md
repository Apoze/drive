# Drive / ST Deploy Center — état de livraison locale

Actualisé le 5 septembre 2026. Ce relevé remplace les anciens états de travail.

L’intégration Drive/ST est implémentée et fonctionne en qualification Docker
isolée. Les quotas virtuels, les accès directs NAS, la reprise des écritures,
l’administration ST et le packaging ont été exercés ensemble. Le déploiement
sur l’infrastructure réelle et les autres applications de la suite ne sont
pas livrés : les paramètres NAS, IdP, domaines et messagerie restent inconnus.
Ce document ne déclare pas l’ensemble des 13 lots terminé ni une production
réelle qualifiée.

## Dépôts et changements

Branche locale dans les deux dépôts :
`codex/st-deploycenter-homelab-complete`. Aucun commit, push, PR ou déploiement
public. Les changements utilisateur préexistants sont conservés.

| Dépôt | Base locale | Dépôt officiel, lecture seule |
| --- | --- | --- |
| `https://github.com/Apoze/drive.git` (`origin`, fetch/push) | `main`, `4086ae6733d78aa1d7e7bcfc30e01672e4d06a38` | `https://github.com/suitenumerique/drive.git` (`upstream`, push désactivé) |
| `https://github.com/Apoze/st-deploycenter.git` (`origin`, fetch/push) | `main`, `7e8542ace7708ac20b1056b03cdc0e010f8778fc` | `https://github.com/suitenumerique/st-deploycenter.git` (`upstream`, push désactivé) |

Les modifications portent principalement sur les modèles/migrations,
`core/services/storage_*`, les producteurs S3/NAS et endpoints associés,
le contrat DeployCenter, l’administration et les formulaires de quotas, puis
les images, manifestes et guides homelab. Le shell explorateur existant est
conservé. La vérification TypeScript a aussi révélé une copie de buffer du
worker ZIP trop largement typée : elle crée désormais un ArrayBuffer
transférable contenant exactement la vue binaire, sans assertion de type.

## Fonctionnement livré

- ST porte les plafonds organisation, utilisateur, backend/namespace, espace
  et utilisateur/backend ; les exceptions personnelles restent sous le
  plafond commun. Identités UUID sans faux SIRET, ancien contrat conservé.
- Connexion NAS, espace visible, droits et propriétaire de la charge sont
  distincts. Plusieurs authentifications NAS et vues sont possibles ; les
  aliases physiques correctement configurés ne doublent pas les compteurs.
- S3 reste du stockage Django/S3 natif. Les montages passent par MountProvider.
  Un même budget Drive additionne les deux familles de stockage.
- Les écritures réservent leurs octets, publient puis comptabilisent de façon
  idempotente. Les opérations ambiguës gardent leur réservation et leur
  journal ; aucun timeout n’est interprété comme une absence de publication.
- Les remplacements NAS conservent l’original ; les restaurations écrivent
  vers un nouveau chemin, sous les droits et quotas applicables. Le nettoyage
  vérifie les identités natives et la rétention des copies privées.
- Les modifications directes NAS sont rapprochées par inventaire de
  métadonnées complet, stagé en base et appliqué par lots de 500. Un scan
  incomplet ne libère pas les charges. Renommage/recréation et remplacement
  externe conservent une attribution cohérente, y compris entre deux lots.
- Les racines, chemins voisins, liens et alias de casse sont contrôlés.
  Une racine configurée avec une casse ambiguë bloque l’activation des
  écritures jusqu’à correction ; l’extraction d’archives reste fermée par
  défaut selon le contrat de durcissement existant.
- Les dossiers sont déplacés par le worker : HTTP 202, intention durable,
  journal lié avant publication native, statut réservé au demandeur,
  reprise sans double déplacement. L’interface attend le résultat.
- Les compteurs, réservations, conflits, jobs et capacités sont consultables
  dans l’administration Drive, sans édition brute des journaux. ST expose les
  exceptions et le nombre de politiques effectivement appliquées.
- La maintenance permet de modifier les racines/propriétaires puis de
  reclassifier avant reprise des écritures. La fusion historique de comptes
  est refusée en gouvernance active ; résoudre ces identités avant activation.
- Setup Docker exclusif à la création : une nouvelle exécution conserve
  configuration et secrets. ST propose `--dry-run`, une rotation explicite de
  clé et un refus des instances/clefs incohérentes.

## Preuves réalisées, avec des données synthétiques

| Contrôle | Résultat |
| --- | --- |
| Boucle HTTPS vérifiée ST → Drive → S3/SMB | Quota utilisateur 17 octets, organisation 23 ; S3 6 + NAS 5 = 11, réservation 0 ; croissance refusée, original préservé |
| Exception d’espace ST | Plafond de 6 octets appliqué ; révision accusée par le vrai worker et persistée dans ST |
| Upload HTTP réel | 6 octets publiés ; autorisation à usage unique, rejeu refusé |
| Déplacement HTTP + Celery | Création du dossier, réponse 202, exécution native, statut 200, nettoyage du dossier de qualification |
| Scheduler réel | `storage_inventory` émis ; `reconcile_storage`, `reconcile_backend` et `synchronize_policy` reçus et terminés par le worker |
| SMB réel | Deux sessions isolées ; partage interdit refusé ; lien vers dossier voisin refusé ; `/ALICE` rapproché avec `/alice` ; mauvaise racine configurée refusée |
| Régression gouvernance | 4 scénarios ciblés passent : concurrence/réservations, vues/droits/reprise, inventaire externe et publication S3 réelle |
| Régression texte/WOPI/S3 | 9 contrôles ciblés passent, dont corps WOPI lu une fois sans accès à `request.body` ni parsing DRF |
| Contrat Drive/ST | 34 contrôles passent ; le test historique de clé absente a été adapté à `api_key_file` et sa relance passe |
| Contrat ST | 16 contrôles ciblés passent ; bootstrap étendu relancé : prévisualisation, conservation, rotation et conflit d’organisation passent |
| Frontend | 11 tests API/driver et 7 tests du worker ZIP passent ; TypeScript Drive/ST passe |
| Navigateur Chrome | ST : ajout/édition/suppression/héritage, mobile ; Drive : dossier NAS, aperçu texte, mobile ; pas d’erreur ni débordement observé |
| Installation répétée | Les deux scripts préservent contenu, secrets et permissions lors d’une seconde exécution |
| Activation finale | Tous les compteurs du rapport `--all-backends --check --verify-items` sont à zéro : écarts, opérations actives, conflits et états non initialisés |
| Schéma | Migrations Drive 0031–0035 et ST 0021–0022 appliquées aux bases de qualification ; `makemigrations --check --dry-run` ne détecte aucun changement |
| Restauration isolée | Dumps Drive/ST, copie du volume S3 à l’arrêt et copie NAS ; nouvelles bases/réseaux/volume ; lectures, propriétaire, quota 11/0, nouvelle écriture et refus de croissance vérifiés |

Ruff passe sur les sources backend modifiées des deux dépôts. Pylint Drive
passe sur ces sources. Pylint ST conserve les diagnostics déjà présents dans
les deux resolvers historiques : ils ont été reproduits sur leur version HEAD
avant modification ; les autres sources modifiées contrôlées passent.
Le lint frontend passe, avec l’avertissement préexistant de `_document.test.tsx`
sur `<head>`. Pas de suite E2E générale ni de contrôle trois navigateurs : les
vérifications restent ciblées, conformément à la demande.

Les traces de validation sont locales sous `/tmp/drive-*.log` et
`/tmp/st-*.log`. Les scripts/captures synthétiques sont sous
`tmp/storage-qualification/`. Ne pas publier ce dossier, ses sessions ou secrets.
Le harness réutilisable de boucle complète est
`docker/qualification/storage_loop.py` ; il demande la fixture isolée documentée.

## Exploitation et réglages

Guide Drive : [homelab-storage-operations.md](../../docs/homelab-storage-operations.md).
Guide ST : `/root/Apoze/st-deploycenter/docs/homelab.md`.
Changements ST : `/root/Apoze/st-deploycenter/docs/homelab-changes.md`.

- Réconciliation : 300 secondes ; inventaire maximal : 900 secondes.
  Variables `STORAGE_RECONCILIATION_INTERVAL_SECONDS` et
  `STORAGE_INVENTORY_MAX_AGE_SECONDS`.
- Écritures actives : 32 par acteur, tous propriétaires/espaces confondus,
  via `STORAGE_MAX_ACTIVE_WRITES_PER_USER`. Réservations d’une heure ; les
  publications incertaines restent retenues jusqu’à rapprochement.
- Copies NAS conservées : 7 jours, `STORAGE_BACKUP_RETENTION_DAYS`.
- Espace libre natif contrôlé par fenêtres pendant la copie temporaire.
  Les fichiers temporaires de conversion/archive utilisent le volume disque
  `scratch`, pas un `/tmp` en mémoire.
- Le cache de politique ST de l’exemple vaut 10 secondes. Pas de repli
  automatique vers une limite infinie si ST ne répond plus ; une croissance
  nécessitant une nouvelle politique échoue jusqu’au rétablissement.

## Runtime laissé disponible

Les services de développement préexistants et leurs bases n’ont pas été
migrés ni remplacés. La gouvernance est activée uniquement dans les fixtures.

- Projet `drive-production` : backend, worker, scheduler, PostgreSQL, Redis,
  SeaweedFS 4.12 épinglé par digest, frontend, edge. Proxy HTTP loopback 8970.
- Projet `st-deploycenter-production` : services de production isolés,
  proxy HTTP loopback 8967.
- Proxies TLS synthétiques : Drive loopback 8969, ST loopback 8968. Samba de
  qualification sans port hôte. Domaines/IdP fictifs, sessions synthétiques.
- Projets de restauration `drive-restore-qualification` et
  `st-restore-qualification` arrêtés après preuve ; volumes conservés.

Ces services servent à la revue locale. Les certificats de qualification et
les sessions sont temporaires ; ne pas transformer ces fixtures en production.

## Limites et suite réelle

Les quotas Drive restent indépendants du NAS. Les mesures SMB de capacité ne
prouvent pas un quota ZFS par dataset ou compte ; une télémétrie native demande
le modèle et l’API du NAS. Les octets logiques, copies privées, blocs physiques,
versions S3 et snapshots ne sont pas interchangeables.

Un client écrivant directement sur le NAS peut dépasser une limite Drive.
Drive observe ensuite ce dépassement et refuse sa propre croissance ; il ne
peut pas réserver atomiquement le disque contre ces clients externes. Les
orphelins/anciennes versions S3 exigent une politique de stockage séparée ;
l’audit des Items n’est pas un inventaire de tous les objets orphelins.

Avant ouverture réelle : renseigner les authentifications NAS et leurs
recouvrements, les racines, le proxy HTTPS, les clients/claims OIDC, puis
qualifier droits et restauration sur cette infrastructure. Aucun secret n’est
à transmettre dans la conversation. Les lots 11–13 (Docs/Grist/équipes,
Messages et autres services) restent des travaux futurs, dépendants des choix
IdP/domaines/IMAP et des services retenus. Leur recette ne peut pas être
remplacée par des services ou comptes de démonstration.
