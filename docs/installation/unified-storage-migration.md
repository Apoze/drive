# Migration vers les espaces unifiés

Cette procédure rattache les métadonnées existantes à des connexions et espaces
explicites. Elle ne copie pas les contenus. Utiliser les mêmes images Drive/ST
et la même configuration privée sur tous les processus de l'installation.
Les commandes ci-dessous concernent le manifeste homelab du dépôt Drive.

## Préparer et simuler

1. Préparer la version ST comprenant les scopes stockage et instance, ainsi
   que la version Drive comprenant les migrations jusqu'à `0049` incluse.
2. Sauvegarder ensemble bases, destinations et configuration selon le
   [guide de restauration](backup-restore.md). Conserver les versions d'images.
3. Monter la clé du coffre, les CA privées et la politique réseau ; vérifier
   `STORAGE_GOVERNANCE_ENABLED=true`. Laisser `STORAGE_UNIFIED_ENABLED=false`
   pendant la préparation. Le script homelab crée la clé uniquement si absente.
4. Appliquer les migrations et demander un rapport sans écriture :

```sh
docker compose -f compose.production.yaml run --rm backend python manage.py migrate --noinput
docker compose -f compose.production.yaml run --rm backend python manage.py storage_unify
```

Le rapport indique les Items/racines non rattachés, espaces implicites,
connexions du registre, liens sans créateur et opérations actives. Résoudre
les racines mêlant plusieurs organisations, liens historiques sans auteur et
providers non compatibles. Ne pas leur attribuer arbitrairement un propriétaire.
Comparer également les quotas déjà appliqués dans ST : le budget historique
`backend:s3` reste celui de l'ancien stockage, pas celui de chaque nouveau S3.

## Fermer les écritures et appliquer

Fermer les sessions d'édition et les nouvelles admissions. Laisser se terminer
les opérations en cours et résoudre leurs publications incertaines. Coordonner
les clients NAS directs si un snapshot cohérent est nécessaire.

Configurer `STORAGE_MIGRATION_MODE=true` dans le fichier privé, puis remplacer
les processus qui acceptent des écritures pour qu'ils appliquent cette barrière.
Arrêter les workers et scheduler avant le backfill ; ne pas supprimer leurs
journaux. Le rapport doit afficher zéro opération active et zéro déplacement
actif. Une réservation en publication ne doit jamais être effacée manuellement.

```sh
docker compose -f compose.production.yaml run --rm backend python manage.py storage_unify --apply
docker compose -f compose.production.yaml run --rm backend python manage.py storage_unify --apply
docker compose -f compose.production.yaml run --rm backend python manage.py storage_unify
```

Le deuxième passage vérifie la répétabilité. Les UUID, arborescences, clés S3,
liens et accès historiques restent conservés. Les propriétaires des anciens
espaces reçoivent des grants explicites ; les compteurs sont rattachés aux
périmètres correspondants sans déplacement d'octets.

La reprise est atomique par racine d'Items, puis par usage comptable. Une racine
interrompue est annulée et reprise entière ; les racines confirmées restent
rattachées. La durée du plus grand arbre détermine donc la fenêtre de maintenance.
Le parcours des métadonnées est borné, mais il ne constitue pas un checkpoint
interne à chaque grand arbre. Tester une copie représentative avant la bascule.

## Contrôler puis ouvrir

Avec les écritures toujours fermées :

```sh
docker compose -f compose.production.yaml run --rm backend python manage.py storage_inventory --all-backends --check --verify-items
docker compose -f compose.production.yaml run --rm backend python manage.py config_preflight
```

Vérifier l'absence d'écart comptable et de ressource non rattachée ; lire un
fichier de chaque connexion. Comparer avant/après un propriétaire, un lecteur,
un groupe, un accès limité à un dossier, une corbeille et un lien public ancien.
Contrôler les budgets globaux, le quota historique S3, les exceptions et la
révision ST effectivement appliquée. Un rapport de comptes cohérent ne remplace
pas cette vérification des droits.

Activer `STORAGE_UNIFIED_ENABLED=true`, retirer `STORAGE_MIGRATION_MODE`, puis
remplacer API, workers et scheduler avec cette configuration commune. Vérifier
l'inventaire périodique et ouvrir l'explorateur normal sur S3 et NAS. Faire un
petit import, une édition et un transfert avec contrôle des compteurs.

Ne pas réutiliser les anciens processus ou sessions d'édition après cette
bascule. Les tokens historiques restent soumis à leurs droits et durées de vie ;
ils ne constituent pas une autorisation de continuer avec une ancienne image.

## Retour arrière

Avant toute écriture multi-connexion, conserver la nouvelle version en
maintenance pour corriger le rattachement. Ne pas inverser les migrations
ou supprimer des usages pour tenter de rétablir des compteurs.

Après des écritures unifiées, une ancienne image limitée au S3 par défaut ne
peut pas servir de retour arrière. Restaurer l'ensemble cohérent bases,
stockages, coffre et images du point de sauvegarde, dans un environnement isolé,
puis vérifier les identités et contenus avant ouverture. Une restauration de
base seule ou un miroir qui renouvelle les VersionIds/inodes ne suffit pas.
