# Publication des corrections Messages et Calendars

10 septembre 2026 — publication explicitement demandée par le propriétaire.

| Dépôt fork (`origin`, fetch/push) | Branche publiée | Commit vérifié distant |
| --- | --- | --- |
| https://github.com/Apoze/messages.git | codex/suite-messages-calendars | 124ac4031fc3de411c1ec0ce0e0c01c4c01217d2 |
| https://github.com/Apoze/calendars.git | codex/suite-messages-calendars | fd84ec148e8b657a73c4c2be736e61076a5c3d92 |

Bases rafraîchies avant publication : `Apoze/messages` `main` et
`Apoze/calendars` `main`. Chaque branche contient un commit d'intégration.
Aucune PR créée, aucune fusion demandée ou effectuée ; URL de PR : sans objet.

Sources `upstream`, fetch-only, push configuré `DISABLED` :

- https://github.com/suitenumerique/messages.git
- https://github.com/suitenumerique/calendars.git

Vérification `ls-remote` : commits distants identiques aux commits locaux.
Les deux worktrees publiés sont propres. Les anciennes wheels intermédiaires
0.1.2/0.1.3 ont été retirées ; la wheel verrouillée 0.1.4 est versionnée.

## Contrôles

- Ruff ciblé sur tous les fichiers Python ajoutés/modifiés : réussi.
- Diffs sans erreur d'espacement ; changelogs complétés et lignes < 80.
- Aucun `print(` backend suivi, aucun commit `fixup!` dans les plages.
- Gitlint sur les deux plages base..HEAD : réussi après correction des
  retours à la ligne des messages de commit, avant tout push.
- Recherche de marqueurs de clés privées et jetons dans les fichiers publiés,
  wheel incluse : aucun résultat. Ce n'est pas un audit complet des secrets.
- Recette fonctionnelle précédente réutilisée : voir `validation-final.md`.
  Aucun frontend ou comportement de service n'a été modifié pour publier.
- Deux anciens avertissements de migration Messages passent maintenant par
  le logger natif ; cas avec collision et cas vide exécutés en conteneur
  isolé sans réseau. Assertions existantes adaptées de capsys à caplog.
  La migration déjà appliquée n'a pas été rejouée sur les données LAN.

Le déploiement et sa sauvegarde restent ceux de la recette LAN. La publication
n'a ni redémarré les services ni remplacé les images en cours d'exécution.
Les ajouts finaux concernent la documentation, les diagnostics de migration
et leurs assertions ; ils seront pris lors de la prochaine reconstruction.

## Périmètre préservé

Les changements historiques de `https://github.com/Apoze/drive.git` et les
checkouts Docs/Meet n'ont pas été englobés dans cette publication des deux
forks Messages/Calendars. ST et la préparation Docker restent locaux.
La restauration complète du déploiement exige toujours ces éléments locaux
et la configuration privée, décrits dans le guide d'exploitation.

## Publication complémentaire

Sur demande explicite suivante, les changements Drive, Docs, Meet et ST ont
aussi été publiés : [rapport](../suite-publication/publication.md).
La section précédente décrit uniquement le périmètre du premier push.
