> Archive historique déplacée le 8 septembre 2026 depuis `PLANS_dev_features.md`.
> Ce chantier est clôturé. Les statuts, branches et consignes ci-dessous
> décrivent son état passé et ne sont pas des instructions actives.
> Aucun de ces fichiers ne doit déclencher une reprise automatique.

# Chantier Clos - Push-Ready Branch Cleanup

## Statut final

- `done` historique local nettoye
- `done` commit snapshot supprime de la pile finale
- `done` pile locale splittee en commits coherents et publiables
- `done` `CHANGELOG.md` aligne sur les changements user-visible
- `done` worktree propre
- `done` branche declaree push-ready sans push

## Pile finale verifiee

- `41d7774b` `🐛(preview) keep mount preview closed after dismiss`
- `87e19896` `✨(backend) add mount runtime capability contracts`
- `352d6275` `♻️(frontend) harden preview and shared runtime flows`
- `15b9a775` `✨(explorer) converge drive and mount browse flows`
- `59d450cf` `🧪(e2e) add LAN browse regression coverage`
- `56bd2d85` `📝(changelog) document LAN browse cleanup`
- `d788db6c` `🔧(gitignore) ignore local handoff artifacts`

## Validation finale reverifiee

- `done` `git status -sb`
- `done` `git log --oneline --decorate main..HEAD`
- `done` `gitlint --commits origin/main..HEAD`
- `done` `make lint`
- `done` `make frontend-lint`
- `done` backend aggregate gate
- `done` frontend unit gate cible
- `done` Playwright LAN:
  - `client-folder-navigation-rebind.spec.ts`
  - `context-menu-lan-convergence.spec.ts`
  - `breadcrumbs-layout-lan.spec.ts`
  - `bulk-delete-partial-lan.spec.ts`
  - `trash-restore-partial-lan.spec.ts`
  - `multi-move-partial-lan.spec.ts`
- `done` UI LAN `200`
- `done` API mounts `401` attendu hors session

## Conclusion retenue

- `done` aucun commit `snapshot`, `workspace`, `wip`, `tmp` ou `fixup!`
  parasite dans `main..HEAD`
- `done` le contenu utile de l'ancien snapshot a ete preserve puis splitte
  proprement
- `done` aucun batch actif restant tant qu'il n'y a ni nouveau scope ni
  besoin explicite de publication

## Reprise future

- `done` rouvrir seulement pour:
  - un nouveau scope explicite
  - une regression produit reproductible
  - ou un besoin explicite de push / PR / publication
