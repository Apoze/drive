# Projects — publication des forks Apoze

Les remotes officiels sont en lecture seule, avec push désactivé. Aucune PR,
aucune fusion et aucune écriture vers les dépôts `suitenumerique/*`.
Les branches de chantier restent les branches publiées ; les anciennes branches
principales ne sont pas présumées contenir les précédentes intégrations.

| Dépôt cible (origin, fetch/push) | Branche publiée | Base de validation | Commit vérifié |
| --- | --- | --- | --- |
| [projects](https://github.com/Apoze/projects) | `codex/suite-projects` | `main` | `994cb1442b7b8ea1d192d84149c1fbdc0e4b1894` |
| [st-deploycenter](https://github.com/Apoze/st-deploycenter) | `codex/projects-integration` | `codex/messages-calendars-integration` | `0911be42842b2dd579ac5973e6642b17cc902365` |
| [docs](https://github.com/Apoze/docs) | `codex/projects-storage-capacity` | `codex/docs-drive-native-documents` | `11f99d4de0725fe558d5abda525f54f6b9a2d306` |
| [messages](https://github.com/Apoze/messages) | `codex/projects-notifications` | `codex/suite-messages-calendars` | `d394b6df7d60b5f463d97f6b68750dd09927203d` |
| [Drive](https://github.com/Apoze/drive) | `codex/projects-integration` | `codex/projects-integration-plan` | Commit de livraison contenant ce rapport ; SHA vérifié après push |

Sources officielles, remotes `upstream` fetch-only :

- <https://github.com/suitenumerique/projects.git>
- <https://github.com/suitenumerique/drive.git>
- <https://github.com/suitenumerique/st-deploycenter.git>
- <https://github.com/suitenumerique/docs.git>
- <https://github.com/suitenumerique/messages.git>

PR base/head/URL : sans objet, aucune PR créée. Les bases du tableau sont celles
utilisées pour les contrôles locaux, dans les forks Apoze correspondants.
Contrôles : fetch des forks, ancêtre de base, absence de fixup et de `print(`
backend suivi, changelogs, gitlint, diff propre, secrets locaux absents des
fichiers candidats, validation ciblée et comparaison SHA local/distant.
People conserve ses modifications préexistantes ; Meet et Calendars n’ont pas
été modifiés dans ce chantier. Aucun travail implémenté ici n’est laissé local.
