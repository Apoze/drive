# Meet / Visio — livré sur le réseau local

8 septembre 2026. [Plan exécuté](../../../docs/plans/suite/meet-visio-core-integration-plan.md).
[Validation finale](validation-final.md) · [Manifeste](deployment-manifest.md).

- M0–M8 terminés dans le périmètre LAN accepté : cœur visio, People/ST/OIDC,
  salles et groupes Web, invités admis, contrôle continu, renouvellement,
  sauvegarde/restauration et qualification Authentik isolée.
- Application : https://192.168.10.123:8443 ; lien dans tous les catalogues.
- Deux tests natifs ciblés, linters/build, Chromium + Firefox réels ; aucun full.
  Retrait ST : 35,44 s ; contrôle interrompu : navigateur fermé en 56,35 s.
- Comptes, NAS/S3 et services existants conservés. 42 conteneurs actifs :
  36 préexistants + six Meet. Salles/admissions de recette supprimées.
- Authentik/copie Meet et bases/volumes de test supprimés ; credentials,
  associations/client/politique de qualification et profils privés nettoyés.
- Sauvegarde Meet : `data/meet-backups/20260908T165358Z/`.
  Sauvegardes People/ST/Keycloak intégrés :
  `data/meet-execution/integrated-suite-backup/` ; baseline antérieure conservée.
- Livraison : https://github.com/Apoze/meet.git, branche `main`, commit
  `9a3d588907e94d725ebf24576156c141e90892fd`. Dépôt propre, seule branche `main`.
  https://github.com/suitenumerique/meet.git reste fetch-only/push désactivé.
  Aucune PR ni publication officielle ; Actions du fork désactivées.
- Limite de déploiement convenue : pas d'Internet ni certificat public. La CA
  est approuvée dans les profils de recette ; les appareils de l'utilisateur
  doivent lui faire confiance avant utilisation micro/caméra.
- Grist reste en pause. Aucun chantier supplémentaire lancé.
