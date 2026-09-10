# Publication de la suite sur les forks Apoze

10 septembre 2026 — autorisation explicite et permanente du propriétaire.
État : préparation des commits et validation avant publication.

| Dépôt fork (origin, fetch/push) | Branche à publier | Base de validation |
| --- | --- | --- |
| https://github.com/Apoze/drive.git | codex/messages-calendars-integration | Apoze/drive main |
| https://github.com/Apoze/docs.git | codex/docs-drive-native-documents | Apoze/docs main |
| https://github.com/Apoze/meet.git | codex/messages-calendars-sdk | Apoze/meet main |
| https://github.com/Apoze/st-deploycenter.git | codex/messages-calendars-integration | Apoze/st-deploycenter main |

Sources upstream, toutes fetch-only avec push désactivé :
https://github.com/suitenumerique/drive.git,
https://github.com/suitenumerique/docs.git,
https://github.com/suitenumerique/meet.git,
https://github.com/suitenumerique/st-deploycenter.git.
Aucune publication, PR ou fusion vers ces dépôts n'est autorisée.
Aucune PR ou fusion des branches des forks n'est comprise dans cette livraison.
URL de PR : sans objet.

## Périmètre

Tous les changements implémentés présents dans ces quatre checkouts sont inclus,
avec les plans, guides, migrations, SDK versionnés et rapports exploitables.
Les scripts de préparation des déploiements suite sont dans Apoze/drive.
Les adaptations Docs n'avaient pas encore de fork : Apoze/docs a été créé.
La branche Docs conserve sa base qualifiée v5.6.1 ; les 18 commits plus récents
présents sur Apoze/docs main ne sont pas intégrés implicitement.

Les secrets, données, sauvegardes privées, sessions Playwright et captures QA
restent locaux. Les captures PNG de browser-qa et .playwright-cli sont ignorées
explicitement. Les wheels intermédiaires non utilisées sont retirées ; les
versions réellement verrouillées par chaque application sont suivies.
Le plan Grist reste en pause ; publier sa documentation ne relance pas Grist.

## Validation de publication

Les recettes métier déjà réalisées sont conservées dans les rapports stockage,
identité, Docs/Drive, Meet et Messages/Calendars. Pas de nouveau full E2E.

- Ruff ciblé sur les fichiers Python modifiés/ajoutés des quatre applications.
- Formatage natif des fichiers backend concernés, sans migration de données.
- ESLint ciblé sur les quatre frontends et le serveur de collaboration Docs.
  Ce dernier utilise son conteneur et ses dépendances, distincts du frontend.
- Test Drive réel ciblé du routage des entitlements People/ST : 1 succès,
  via le lanceur natif bin/pytest, base de test isolée.
- Helper d'assertion ST : correspondance imbriquée acceptée, divergence refusée,
  aucune sortie des données avec le mode debug historique.
- Vérification des marqueurs de secrets, notamment dans les wheels et les
  rapports JSON ; aucun secret détecté par ces contrôles ciblés.
- Changelogs à jour, lignes < 80 sauf liens seuls, aucun print backend suivi.
- Diffs sans erreur d'espacement ; absence de fixup et gitlint avant push.

Les changements nécessaires pour passer les contrôles sont limités aux imports,
formatages, documentation, suppression des impressions de debug ST et garde
explicite de l'identifiant de destination dans le déplacement Docs. Les essais
hors lanceur natif ou avec les dépendances du mauvais conteneur ont échoué à
la préparation et ne sont pas comptés comme des validations réussies.

## Règle permanente

AGENTS.md des quatre dépôts et le guide du tracker Drive enregistrent désormais
la publication des travaux implémentés vers Apoze après validation, sans
redemander une autorisation déjà donnée. Les protections des données, le refus
des pushes upstream et les limites des actions de fusion restent en vigueur.
Cette règle est une instruction de travail, pas un hook Git automatique.
