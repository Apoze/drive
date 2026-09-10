> Archive historique déplacée le 8 septembre 2026 depuis `PROMPT_dev_features.md`.
> Ce chantier est clôturé. Les statuts, branches et consignes ci-dessous
> décrivent son état passé et ne sont pas des instructions actives.
> Aucun de ces fichiers ne doit déclencher une reprise automatique.

# Prompt pour `codex dev`

Aucun nouveau batch.

La branche locale `codex/lan-restart-20260321` est au stop-point utile pour
publication.

Etat retenu:

- historique local nettoye et splitte proprement
- worktree propre
- branche push-ready sans push effectue

Pile finale verifiee:

- `41d7774b` `🐛(preview) keep mount preview closed after dismiss`
- `87e19896` `✨(backend) add mount runtime capability contracts`
- `352d6275` `♻️(frontend) harden preview and shared runtime flows`
- `15b9a775` `✨(explorer) converge drive and mount browse flows`
- `59d450cf` `🧪(e2e) add LAN browse regression coverage`
- `56bd2d85` `📝(changelog) document LAN browse cleanup`
- `d788db6c` `🔧(gitignore) ignore local handoff artifacts`

Points fermes et verifies:

- preview mount dismissal
- navigation dossier cliente route-sync
- convergence visible du clic droit `Items/S3` / `MountProvider`
- breadcrumbs/path desktop
- bulk delete partiel Items
- trash restore / hard delete partiel
- multi-move partiel
- compteur du modal hard delete
- pile git propre et publiable

Reference d'execution:

- `report.md`

Regle de reprise:

- n'ouvre rien sans nouveau scope explicite
- ou nouvelle regression produit reproductible
- ou besoin explicite de push/PR/publication

Si tu es relance sans nouveau besoin concret, reponds seulement:

- `DONE`
- branche propre et push-ready
- chantier clos
- reference a `report.md`
