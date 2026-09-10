# Socle identité, accès et catalogue — état livré

**8 septembre 2026 : L0–L11 terminés et qualifiés localement.**
[Plan](../../../docs/plans/suite/identity-access-catalogue-docs-plan.md) ·
[Validation V1–V12](validation-final.md) · [Manifeste](delivery-manifest.json) ·
[Journal historique](execution-journal.md).

## Résultat actif

Drive, ST, People et Docs utilisent le Keycloak Drive existant et les mêmes
principaux durables. People porte les groupes ; ST porte l'accès applicatif
et les quotas. Docs est utilisable avec partage, coédition, médias privés et
export. Le NAS et les stockages Drive existants sont conservés.

| Lot | État | Résultat |
| --- | --- | --- |
| L0 | Vérifié | Sources/configurations/bases initiales sauvegardées ; travail isolé avant activation. |
| L1 | Vérifié | Contrat durable, associations explicites, migrations additives, collisions refusées. |
| L2 | Vérifié | People persistant, organisation homelab, groupes et administration Web bornée. |
| L3 | Vérifié | Projections paginées/versionnées, retrait et reprise, fraîcheur bornée. |
| L4 | Vérifié | Drive raccordé ; S3/NAS, WOPI, jobs, métriques et grants conservés. |
| L5 | Vérifié | ST : comptes stables, politiques, refus et quota test de 20 Go conservé. |
| L6 | Vérifié | Docs persistant, coédition réelle, groupes, médias privés, export et révocation. |
| L7 | Vérifié | Catalogue des quatre apps, SSO commun, administration et déconnexion. |
| L8 | Vérifié | Profil SCIM entrant, reprise d'autorité explicite, replay et suspension. |
| L9 | Vérifié | Keycloak → Authentik direct → Keycloak, mêmes données et anciens cookies refusés. |
| L10 | Vérifié | Activation LAN, éditeurs S3/NAS sauvegardés, redémarrages et nettoyage. |
| L11 | Vérifié | Restaurations, secours, guides, manifestes, qualification retirée et clôture locale. |

## État d'exploitation

- 36 services actifs : Drive 16, ST 7, People/Docs 13 ; aucun unhealthy.
- Annuaire et politique frais dans les quatre apps ; 23 principaux projetés.
- Même utilisateur principal Drive ; une seule saisie pour les quatre logins.
- Quota test : **20 000 000 000 octets**, usage **59 471 422 octets** après
  nettoyage, identique à l'avant-recette. Aucun quota global Docs annoncé.
- Docs S3 privé dédié 4.46, versionné et persistant ; l'ancienne version 4.12
  du stockage Drive reste inchangée. Écart motivé dans l'ADR et la validation.
- Quatre comptes natifs de secours vérifiés sans IdP, API de contenu refusée.
- Projets QA/Authentik et leurs volumes supprimés ; fichiers de test, versions
  et téléchargements nettoyés. Groupes LAN restaurés après les retraits.

Les tests sont ciblés sur les comportements et les parcours Chromium utiles.
Les délais observés, linters, types, preuves de conservation et limites exactes
figurent dans la [validation finale](validation-final.md).

## Reprise et livraison des sources

- [Installation et relance](../../../docs/installation/suite-identity-and-docs.md).
- [Administration, IdP, incident et restauration](../../../docs/operations/suite-identity-access.md).
- Sauvegardes privées : `/root/Apoze/drive/data/suite-local/backups/2026-09-08/`.
- Les sources effectives sont `/root/Apoze/drive`, `/root/Apoze/st-deploycenter`,
  `/root/Apoze/people`, `/root/Apoze/docs`. Les worktrees Drive/ST du chantier
  sont synchronisés ; leurs chemins et les HEAD sont au manifeste.
- Le socle est dans `src/packages/suite-identity`, installé via wheel/locks
  natifs. Les quatre checkouts et les fichiers nouveaux font partie de la
  livraison ; les seuls HEAD Git ne contiennent pas ces changements locaux.
- Publication : aucune. Aucun commit, push, ticket ou PR de cette livraison.

Aucune action d'implémentation restante dans ce périmètre. Pour une évolution,
partir des guides et de l'état actif, jamais d'une instruction de reprise du
journal historique. Les prochains lots possibles sont le rangement Docs/Drive
ou l'ajout de Grist ; ils nécessitent leur propre cadrage.
