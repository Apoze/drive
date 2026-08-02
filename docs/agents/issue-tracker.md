# Issue tracker: GitHub

Les specs et tickets de ce dépôt vivent dans GitHub Issues pour
`Apoze/drive`.

Utiliser `gh` avec `--repo Apoze/drive` pour créer, lire, commenter,
labelliser et fermer les issues.

Les pull requests ne constituent pas une surface de triage.

## Frontière ST Deploy Center

Les modifications nécessaires dans `/root/Apoze/st-deploycenter` restent
locales. Elles doivent être minimales, respecter le style actuel du projet et
être décrites de façon à pouvoir être proposées ultérieurement comme ticket
au dépôt officiel `suitenumerique/st-deploycenter`.

Ne jamais publier, pousser ou ouvrir une pull request vers le dépôt officiel
sans instruction explicite.

## Publication par un skill

Quand un skill demande de publier dans le tracker, créer une issue dans
`Apoze/drive`.

Quand un skill demande un ticket, le lire avec ses commentaires et labels.

Les dépendances entre tickets utilisent les dépendances natives GitHub quand
elles sont disponibles, sinon une ligne `Blocked by: #<n>`.
