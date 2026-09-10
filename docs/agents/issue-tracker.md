# Issue tracker: GitHub

Les specs et tickets de ce dépôt vivent dans GitHub Issues pour
`Apoze/drive`.

Utiliser `gh` avec `--repo Apoze/drive` pour créer, lire, commenter,
labelliser et fermer les issues.

Les pull requests ne constituent pas une surface de triage.

## Frontière ST Deploy Center

Les modifications implémentées dans `/root/Apoze/st-deploycenter` sont
commitées puis poussées sur `https://github.com/Apoze/st-deploycenter.git`,
après validation. Autorisation permanente du propriétaire du 10 septembre 2026.
Respecter le style du projet ; conserver les secrets et données locales hors Git.

Ne jamais publier, pousser ou ouvrir une pull request vers le dépôt officiel :
il reste en lecture seule.

## Publication par un skill

Quand un skill demande de publier dans le tracker, créer une issue dans
`Apoze/drive`.

Quand un skill demande un ticket, le lire avec ses commentaires et labels.

Les dépendances entre tickets utilisent les dépendances natives GitHub quand
elles sont disponibles, sinon une ligne `Blocked by: #<n>`.
