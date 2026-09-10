# Installer Visio dans la suite Apoze

Livraison du 8 septembre 2026 : cœur Meet, People/ST/OIDC, sans enregistrement.
Application locale : https://192.168.10.123:8443.

Le [guide canonique du fork Apoze/meet](https://github.com/Apoze/meet/blob/main/docs/apoze/meet-core-operations.md)
décrit le client OIDC, les bindings People, la politique ST et les commandes
`prepare.py`, `provision_local.py` et `manage.py`. Sources locales :
`/root/Apoze/meet`. Configuration privée : `data/meet-local/` dans Drive.
Le script de démarrage Drive reste indépendant et inchangé.

Six services Meet utilisent la base/rôle dédiés `meet`, PostgreSQL partagé et
un Redis propre. HTTPS 8443, WSS 8444, médias 7882/UDP et 7881/TCP sur le LAN.
Aucune exposition Internet. Les postes doivent faire confiance à la CA locale
avant d'utiliser micro/caméra ; certificats publics différés à la demande du
propriétaire. Aucun contournement des restrictions du navigateur.

Voir le [manifeste de déploiement](../../output/implementation/meet-visio-core-integration/deployment-manifest.md)
et la [validation finale](../../output/implementation/meet-visio-core-integration/validation-final.md).
