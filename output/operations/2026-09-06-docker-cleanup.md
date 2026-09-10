# Nettoyage Docker du 6 septembre 2026

Nettoyage explicitement demandé par le propriétaire avant le futur chantier
identité/People. Aucune implémentation du socle ni installation Authentik.

## Résultat

| Mesure | Résultat |
| --- | --- |
| Espace libre avant | 87.98 Go |
| Espace libre après | 238.73 Go |
| Gain net mesuré sur la partition | 150.75 Go |
| Conteneurs supprimés | 93 : 69 déjà arrêtés et 24 anciens services de qualification |
| Volumes inutilisés supprimés | 747 |
| Réseaux inutilisés supprimés | 11 |
| État final Docker | 22 conteneurs actifs, 16 images utilisées, 16 volumes utilisés, cache de construction nul |
| Récupérable selon Docker après prune | 0 octet dans les quatre catégories |

Les Go ci-dessus sont décimaux. Les compteurs de Docker et le gain physique
sur la partition sont des mesures distinctes ; leurs valeurs ne sont pas
additionnées pour estimer le gain net.

## Périmètre et précautions

Les 24 services supplémentaires provenaient des essais clôturés : configuration
avec `identity-qualification.invalid`, interfaces sur ports de boucle locale,
ou conteneurs de restauration/QA. Leur rôle a été rapproché des rapports
[de qualification](../implementation/unified-storage-spaces/validation-final.md)
et [de retour à l’environnement habituel](../implementation/unified-storage-spaces/local-environment-validation.md).

Avant suppression des volumes détachés contenant des bases ou des objets,
22 archives privées ont été créées et vérifiées, pour environ
121.0 Mo compressés. Elles restent dans
`tmp/docker-cleanup-2026-09-06/preserved-detached-data/`, hors Git, avec accès
restreint et manifeste d’empreintes SHA-256. Les données des stockages NAS et
les répertoires montés depuis l’hôte n’ont pas été supprimés.

Prune exécuté par catégorie : conteneurs arrêtés, tous volumes inutilisés,
toutes images inutilisées, réseaux inutilisés et totalité du cache du builder.
Chaque phase a terminé avec un code de retour nul.

## Vérifications

- Les 16 services Drive et 6 services ST habituels restent démarrés.
- Identifiants des conteneurs, images, montages, dates de démarrage et compteurs
  de redémarrage inchangés pour ces 22 services ; aucun état malsain.
- Interfaces Drive/ST, découvertes OIDC des deux IdP actuels et découvertes
  Collabora/ONLYOFFICE : HTTP 200 avant et après nettoyage.
- APIs utilisateur anonymes Drive/ST : HTTP 401 attendu avant et après.
- `storage_inventory --check --verify-items` : réussite ; aucun écart de
  compteurs ou de tailles S3, aucune opération active ni backend non prêt.
- Aucun volume détaché restant ; aucune image inutilisée ni cache restant.

Ces contrôles valident le nettoyage et la continuité des services. Ils ne
constituent pas une nouvelle campagne complète de connexion/édition/navigateur.
Les détails d’exécution assainis restent dans `tmp/docker-cleanup-2026-09-06/`.

Les anciens conteneurs de qualification ont été retirés : leurs anciennes
commandes `docker start` ne s’appliquent plus. Une nouvelle qualification devra
recréer son environnement isolé si nécessaire.
