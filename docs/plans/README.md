# Plans de chantier

Un plan décrit le travail demandé ; sa présence n’autorise pas son exécution.
Les rapports de livraison sont conservés séparément sous
[`output/implementation/`](../../output/implementation/).

[Roadmap de la suite Apoze](suite/roadmap.md) : vue courte des chantiers
restants, options et travaux en pause, dont l'intégration de ClipSync.

## Publication des travaux livrés

- [Publication Drive, Docs, Meet et ST sur les forks Apoze](../../output/implementation/suite-publication/publication.md)
  : changements implémentés publiés le 10 septembre 2026.
- Autorisation permanente : publier les prochains travaux implémentés après
  validation, sur les forks Apoze uniquement ; secrets et données restent locaux.

## Suite — Transfers et Chat livrés sur le LAN

- [Transfers et Chat Apoze — serveur, web et mobile](suite/transfers-element-chat-integration-plan.md)
  : lots TC0–TC12 livrés dans le périmètre courant le 12 septembre 2026.
  Transfers, Synapse/MAS/Element Web, intégrations Drive/Docs/Meet/Calendars/
  Projects/Messages, quotas, révocation, bot E2EE et restauration qualifiés.
  Android compilé et testé sur émulateur ; code iOS livré. Compilation iOS,
  signature/distribution, téléphones et remise APNs/FCM différés (§14).
  [État courant](../../output/implementation/transfers-element-chat/current-status.md),
  [validation](../../output/implementation/transfers-element-chat/validation-final.md)
  et [publications Apoze](../../output/implementation/transfers-element-chat/publication.md).

## Suite — Projects livré sur le LAN

- [Projects — intégration complète à la suite Apoze sur le LAN](suite/projects-integration-plan.md)
  : plan du 10 septembre 2026, lots **P0–P9 terminés**. Identité durable
  Node/People/ST, rôles et révocation, stockage privé et quotas, Drive/Docs,
  notifications Messages, restauration et publication sur les forks Apoze.
  Recette réelle R0–R6 et [guide d’exploitation](../operations/suite-projects.md).
  [État courant](../../output/implementation/projects-integration/current-status.md).

## Suite — messagerie et agendas livrés sur le LAN

- [Messages et Calendars — messagerie et agendas intégrés sur le LAN](suite/messages-calendars-integration-plan.md)
  : livré le 10 septembre 2026, **MC0–MC10 terminés sur le LAN**.
  Lots MC0–MC10 : identité/People/ST, boîtes et groupes, quotas,
  transport mail interne, invitations aller-retour, Drive/Docs et Meet,
  exploitation et recette minimale. [Validation](../../output/implementation/messages-calendars/validation-final.md).
  Corrections publiées sur les forks Apoze Messages/Calendars ;
  [publication](../../output/implementation/messages-calendars/publication.md).
  WAN explicitement différé.

## Suite — documents natifs livrés sur le LAN

- [Docs dans Drive — documents natifs, classement et droits unifiés](suite/docs-drive-native-documents-integration-plan.md)
  : livré localement le 9 septembre 2026, **D0–D9 vérifiés**.
  Documents vivants dans les espaces S3/NAS, droits délégués, migration,
  quotas, exports et reprise ; ancien explorateur Mes fichiers rétabli.
  [Validation finale](../../output/implementation/docs-drive-native-documents/validation-final.md).

## Suite — Visio livré sur le LAN

- [Meet / Visio — cœur de visioconférence intégré à la suite](suite/meet-visio-core-integration-plan.md)
  : livré le 8 septembre 2026 sur `Apoze/meet` `main` ; audio, vidéo, écran,
  chat, People/IdP, accès ST et droits de réunion. Sans enregistrement,
  transcription ou IA. [Validation finale](../../output/implementation/meet-visio-core-integration/validation-final.md).

## Chantiers en pause

- [Index des chantiers en pause](paused/README.md).
- [Grist Community intégré à la suite Apoze](paused/suite/grist-community-integration-plan.md)
  : mis en pause le 8 septembre 2026 sur demande du propriétaire. Fork et
  builds préparés, intégration partielle non validée et non déployée.
  **Aucune reprise sans demande spécifique du propriétaire.**

## Suite — socle livré localement

- [Socle commun d’identité, d’accès et de catalogue — Drive, ST, People et Docs](suite/identity-access-catalogue-docs-plan.md)
  : plan exécuté et qualifié le 8 septembre 2026. People comme source initiale
  des groupes, SCIM optionnel, Docs et bascule Authentik vérifiés.
  [Validation finale](../../output/implementation/suite-identity-access-catalogue/validation-final.md).

## Chantier précédent — stockage livré localement

- [Index des plans de stockage](storage/README.md).
- [Espaces unifiés, multi-S3 et administration web](storage/unified-storage-spaces-plan.md)
  : périmètre historique accepté ;
  [recette de l’environnement local avec Keycloak et NAS](../../output/implementation/unified-storage-spaces/local-environment-validation.md).

## Recherches et archives

- [Inventaire de La Suite et recherches antérieures](../../output/research/README.md).
- [Rapport du socle Drive/ST précédent](../../output/implementation/st-deploycenter-homelab-status.md).
- [Description historique de la livraison Drive/ST, PR 177](../../output/implementation/archive/pr-177-description.md).
- [Ancien plan de clôture navigation/aperçus LAN](../../output/implementation/archive/lan-browse-cleanup-2026-07-05/plan.md)
  et [rapport historique](../../output/implementation/archive/lan-browse-cleanup-2026-07-05/report.md)
  : anciens fichiers racine rangés en archives ; aucune reprise automatique.
  L'[ancien prompt](../../output/implementation/archive/lan-browse-cleanup-2026-07-05/historical-prompt.md)
  est conservé uniquement pour l'historique.
- [Nettoyage Docker avant le chantier identité](../../output/operations/2026-09-06-docker-cleanup.md).

Les plans stockage sont déjà rangés par domaine et les recherches par date.
Leurs chemins sont conservés pour les liens des tâches existantes. Les anciens
plans spécialisés E2E, aperçus et rattrapage restent aux chemins canoniques
routés par `AGENTS.md` : ils ne sont pas des lots du chantier identité.
