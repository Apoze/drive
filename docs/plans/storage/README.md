# Plans du domaine stockage

[Tous les chantiers](../README.md) ·
[Prochain chantier : identité, accès, People et Docs](../suite/identity-access-catalogue-docs-plan.md).

## Dernier chantier livré localement

- [Espaces unifiés, multi-S3 et administration web](unified-storage-spaces-plan.md)
  — plan canonique du chantier accepté le 5 septembre 2026.
  L'implémentation et la qualification locale sont terminées. Les critères
  de clôture sont dans le plan ; les preuves et limites de déploiement sont dans
  [l'état d'exécution](../../../output/implementation/unified-storage-spaces/current-status.md)
  et la [recette du stack local Keycloak/NAS](../../../output/implementation/unified-storage-spaces/local-environment-validation.md).

## Socle précédent et exploitation

- [Plan initial Drive/ST homelab](../../../output/research/2026-09-04-st-deploycenter-homelab-plan.md)
  — proposition historique, à ne pas utiliser comme état de livraison.
- [Livraison locale du socle Drive/ST](../../../output/implementation/st-deploycenter-homelab-status.md)
  — fonctionnalités, preuves et limites du socle sur lequel reprendre.
- [Guide d'exploitation Drive](../../homelab-storage-operations.md)
  — procédures actuelles d'administration et de reprise.
- [Contrat stockage](../../agent-storage-contract.md)
  — invariants obligatoires pour S3, MountProvider et les flux de fichiers.
- [Plan de parité des aperçus](../../mounts-preview-correction-plan.md)
  — référence spécialisée ; ne pas recréer une seconde liste de corrections.

Les documents historiques conservent leurs chemins pour préserver les liens
des tâches existantes. Les nouveaux plans durables de stockage sont rangés ici.
Les rapports de validation restent sous `output/implementation/` ; les
captures, sessions et secrets de qualification ne sont pas des documents
canoniques et ne doivent pas être publiés.
