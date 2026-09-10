# Visio Apoze — manifeste du déploiement LAN

8 septembre 2026. Source : https://github.com/Apoze/meet.git, `main`,
`9a3d588907e94d725ebf24576156c141e90892fd`.
Source officielle https://github.com/suitenumerique/meet.git en lecture seule.
Aucune PR, aucune publication d'image ni action sur le dépôt officiel.

| Service | Référence locale | Image exécutée |
| --- | --- | --- |
| backend | `apoze/meet:core-backend` | `sha256:564d57d6cc7a03466d1dba69578e7178819798532c5729804e6d0483097b987c` |
| worker | `apoze/meet:core-backend` | `sha256:564d57d6cc7a03466d1dba69578e7178819798532c5729804e6d0483097b987c` |
| beat | `apoze/meet:core-backend` | `sha256:564d57d6cc7a03466d1dba69578e7178819798532c5729804e6d0483097b987c` |
| redis | `redis:7.4-alpine@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf` | `sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf` |
| livekit | `livekit/livekit-server:v1.13.6@sha256:e37d68f172556d02aa77968b9fc55ef481468c0315fa38e4fa6c56ce72e3a815` | `sha256:e37d68f172556d02aa77968b9fc55ef481468c0315fa38e4fa6c56ce72e3a815` |
| proxy | `apoze/meet:core-frontend` | `sha256:2016243419bca85f5af95db4c3c9a96dc989343468a6ad77d5ef31ad6c3ea52e` |

Les digests des bases Python, Node, Nginx, Redis et LiveKit figurent dans le
Dockerfile et `compose.suite.yaml` du commit livré. Les images applicatives
sont construites localement, sans envoi vers un registre public.

- Racine : `/root/Apoze/meet`, projet Compose `meet-local`.
- Configurations : `/root/Apoze/drive/data/meet-local/`, privées 0700/0600.
- Secrets : `settings.json`, `backend.env`, `keys/*` ; aucune valeur ici.
- TLS : CA locale et certificat serveur dans `tls/`. Clé CA non montée dans
  le proxy ; seuls certificat serveur/clé serveur y sont accessibles.
- PostgreSQL : `suite-local-suite-postgres-1`, rôle/base dédiés `meet`.
- Redis : volume `meet-local_redis`, indépendant des quatre applications.
- Contrôle média : `control/verified`, worker/beat dédiés, sans Docker socket.
- Application : https://192.168.10.123:8443 ; WSS sur 8444 ; UDP 7882,
  TCP 7881. LiveKit HTTP 7880 et backend HTTP 8000 restent privés.
- ST : service Visio 10, visible, politique initiale « Membres de la suite ».
- People : consommateur `meet`, deux bindings Keycloak confirmés ; 23 comptes
  projetés, deux groupes. Un administrateur local de récupération distinct.
- Métadonnées de recette finales : aucune salle/admission conservée.
- Sauvegarde Meet : `data/meet-backups/20260908T165358Z/` avec SHA-256.
- Sauvegardes intégrées People/ST/Keycloak :
  `data/meet-execution/integrated-suite-backup/` ; baseline M0 conservée.
- Projets `meet-idp-qa` et `meet-authentik-qa`, deux bases/tests et leurs
  volumes retirés ; configurations temporaires et tokens navigateur supprimés.
- 42 conteneurs actifs : 36 préexistants conservés et les six Meet ci-dessus.

Le certificat public et l'exposition Internet ont été différés par le
propriétaire. La recette HTTPS utilise la confiance de la CA locale dans les
navigateurs du serveur ; aucune configuration des appareils personnels n'est
revendiquée. Consulter les guides installation/opérations avant leur utilisation.
