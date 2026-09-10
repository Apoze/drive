# Docs dans Drive — état courant

**Implémenté, activé et qualifié sur le LAN le 9 septembre 2026.**
Plan : [D0–D9](../../../docs/plans/suite/docs-drive-native-documents-integration-plan.md).
Rapport : [validation finale](validation-final.md).
Historique : [journal d’exécution](execution-journal.md).

- Intégration native active dans Drive et Docs ; migrations additives appliquées.
- « Mes fichiers » retrouve le socle AppExplorer historique, ses filtres,
  menus, aperçu, sélection et navigation, avec espaces S3/NAS et Docs natifs.
- 43 services actifs ; Keycloak, NAS, People, ST, Office et Meet conservés.
- Recette réelle terminée : coédition/révocation, quotas, exports PDF,
  dossier mixte S3–NAS–S3, ZIP, disparition/récupération d’ancre et invitations.
- Bascule isolée Keycloak–Authentik–Keycloak et restauration cohérente vérifiées.
- Données de recette purgées : zéro document, média, version ou réservation
  active. Journaux terminaux et témoins d’idempotence conservés.
- Quota du compte de test : 20 Go. Projets QA et volumes éphémères supprimés.
- Branches locales Drive/Docs : `codex/docs-drive-native-documents`.
  Modifications locales conservées ; publication distincte de cette livraison LAN.

Wheel identité 0.1.1 :
`29ce377994e58bb751c4c7ec2523b9850e60062310ae0d2fb9f0243f8a14f067`.
Images et santé : [manifeste final](deployment-final.json).
Aucun lot fonctionnel restant dans ce périmètre ; Grist reste en pause.
