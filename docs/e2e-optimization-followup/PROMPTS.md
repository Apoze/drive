Tu travailles dans le repo `/root/Apoze/drive`.

Tu continues le chantier `e2e-optimization-followup` sur le worktree local
déjà en cours, après validation orchestrator du checkpoint
**Phase 05 GitHub Ready**.

Important:

- Ce prompt est le **premier prompt Git-enabled** de ce follow-up.
- Il t’autorise explicitement à faire:
  - commit
  - push
  - exécution GitHub réelle via `workflow_dispatch`
- Il ne t’autorise **pas** encore à ouvrir une PR.

Mode opératoire obligatoire:

- Continue sur la branche locale déjà en cours; ne crée pas de nouvelle branche
  sans nécessité forte.
- N’annule aucun changement volontaire déjà présent dans le worktree.
- Garde le modèle **one-stack E2E** comme architecture par défaut.
- Ne casse pas le fallback multi-stack existant dans `Makefile`,
  `compose.yaml` et `src/frontend/apps/e2e/scripts/loopback-proxies.js`.

Lis d’abord impérativement:

- `AGENTS.md`
- `docs/e2e-optimization-followup/plan.md`
- `docs/e2e-optimization-followup/implementation-todo.md`
- `docs/e2e-optimization-followup/execution/index.md`
- `docs/e2e-optimization-followup/execution/current-status.md`
- `docs/e2e-optimization-followup/execution/checkpoints/README.md`
- `docs/e2e-optimization-followup/execution/checkpoints/phase-05-github-ready.md`
- `docs/env_freeze_report.md`

Contexte validé par l’orchestrator:

- Phases 0 à 5 GitHub Ready sont validées.
- Le chemin GitHub de contrôle `workers=1` et le chemin expérimental
  `workers=2` sont prêts.
- La politique CI par défaut reste inchangée.
- La vraie Phase 5 peut maintenant être exécutée avec Git/GitHub autorisé.
- La suite doit s’arrêter après la décision explicite `keep/promote` de
  la Phase 5.
- N’ouvre pas la Phase 6 (sharding) dans ce prompt.

Objectif de ce prompt:

- exécuter la vraie **Phase 5** sur GitHub
- mesurer honnêtement l’expérience Chromium PR à `workers=2`
- décider avec preuve si le défaut PR CI doit rester à `1` ou passer à `2`

Travail autorisé maintenant:

- commit des changements du follow-up sur la branche courante
- push de cette branche sur `origin`
- runs GitHub `workflow_dispatch`
- collecte de métriques
- ajustements légers si un défaut mineur de workflow/runbook est révélé
  immédiatement pendant la campagne

Travail interdit:

- ouvrir une PR
- merger quoi que ce soit
- ouvrir la Phase 6
- toucher au sharding
- changer le défaut local
- changer le défaut PR CI sans satisfaire la règle de décision

Étapes obligatoires

1. Vérifier l’état réel:
   - `git status --short --branch`
   - `docker compose ps`
2. Relire les docs ci-dessus, surtout
   `phase-05-github-ready.md`.
3. Faire la préflight Git locale obligatoire avant tout push, conformément à
   `AGENTS.md`:
   - `git fetch origin --prune`
   - vérifier absence de `fixup!` dans la range
   - vérifier absence de `print(` dans `src/backend`
   - exécuter `gitlint --commits origin/main..HEAD`
   - si `gitlint` est absent, l’installer temporairement sous `tmp/`
   - gérer proprement la politique changelog:
     si `CHANGELOG.md` doit être mis à jour pour permettre un push propre, fais
     une entrée minimale et correctement wrapée; ne compte pas sur un futur
     label PR, puisqu’aucune PR n’est ouverte dans cette étape
4. Si la préflight échoue, corriger proprement puis rerun les checks locaux.
5. Faire un ou plusieurs commits propres et gitlint-compliant sur la branche
   courante.
6. Push sur `origin`.
7. Noter le SHA exact qui servira de base à toute la campagne Phase 5.
8. Exécuter la vraie campagne GitHub Phase 5 via `gh` sur ce SHA/branch.
9. Collecter les métriques et décider `keep` ou `promote`.
10. Mettre à jour les docs d’exécution.
11. T’arrêter et demander explicitement la revue orchestrator.

Campagne GitHub Phase 5 à exécuter

- workflow:
  `Frontend Workflow`
- trigger:
  `workflow_dispatch`
- branche/ref:
  la branche poussée à l’étape 6
- surface de comparaison:
  - contrôle:
    `phase5_ci_experiment=chromium-pr-workers1-control`
  - expérience:
    `phase5_ci_experiment=chromium-pr-workers2`

Ordre recommandé:

- alterne contrôle et expérience sur le **même SHA**:
  1. control-1
  2. experiment-1
  3. control-2
  4. experiment-2
  5. control-3
  6. experiment-3
  7. control-4
  8. experiment-4
  9. control-5
  10. experiment-5

Utilisation GitHub attendue:

- utilise des commandes non interactives `gh`
- exemple indicatif:
  - `gh workflow run .github/workflows/drive-frontend.yml --ref <branch> -f phase5_ci_experiment=chromium-pr-workers1-control`
  - `gh workflow run .github/workflows/drive-frontend.yml --ref <branch> -f phase5_ci_experiment=chromium-pr-workers2`
- surveille chaque run jusqu’à conclusion:
  - `gh run watch <run-id> --exit-status`
- récupère ensuite les détails utiles:
  - `gh run view <run-id> --json ...`
  - ou `gh api` si nécessaire pour les jobs/étapes détaillés

Règle de décision à appliquer strictement

- promouvoir Chromium PR CI à `workers=2` seulement si:
  - `5/5` runs expérience sont verts
  - aucun nouveau flake n’apparaît
  - aucun OOM / bootstrap failure / infra abort
  - le comportement des artifacts reste correct
  - la médiane de la durée du job PR-équivalent à `workers=2`
    est au moins `15%` plus rapide que la médiane contrôle à `workers=1`
- sinon:
  - garder le défaut PR CI à `workers=1`

Métriques à collecter

- pour chacun des 10 runs:
  - run id / URL GitHub
  - SHA
  - type:
    `control` ou `experiment`
  - conclusion finale
  - durée murale du job PR-équivalent uniquement
  - durée des étapes:
    - `Start Docker services`
    - `Wait for Keycloak to be ready`
    - `Run ... e2e tests`
  - résultat Playwright:
    passes / failures / skips / retries / signature de flake
  - résultat infra:
    OOM / timeout / bootstrap issue / cancellation
  - statut des artifacts sur échec/annulation

Artefacts de reporting obligatoires

- maintiens à jour:
  - `docs/e2e-optimization-followup/execution/index.md`
  - `docs/e2e-optimization-followup/execution/current-status.md`
- crée ou mets à jour:
  - `docs/e2e-optimization-followup/execution/checkpoints/phase-05-live.md`
- crée aussi un fichier de données:
  - `docs/e2e-optimization-followup/execution/data/phase-05-live.tsv`

Le fichier `phase-05-live.tsv` doit contenir au minimum les colonnes:

- ordinal
- mode
- run_id
- run_url
- sha
- job_name
- conclusion
- job_wall_time_s
- start_docker_s
- keycloak_wait_s
- e2e_step_s
- playwright_summary
- infra_notes
- artifact_notes

Le checkpoint `phase-05-live.md` doit contenir au minimum:

- ce qui a été poussé
- la range git et le SHA mesuré
- le résultat de la préflight git locale
- le tableau synthétique des 10 runs
- les médianes contrôle vs expérience
- la décision explicite:
  - `keep workers=1`
  - ou `promote workers=2`
- les risques résiduels
- ce que toucherait la suite immédiate
- une recommandation claire:
  - ready for PR prep
  - keep current policy and stop
  - stop and redesign

Important:

- si un blocage GitHub auth/permissions te empêche d’exécuter la campagne,
  arrête-toi, documente le blocage précisément, et n’invente pas de résultat
- si un défaut mineur de workflow est révélé avant d’obtenir une campagne
  valable, tu peux le corriger, refaire les checks locaux nécessaires,
  recommitter, repush, puis recommencer la campagne Phase 5 sur le nouveau SHA
- reste rigoureux sur les secrets:
  ne jamais afficher de token, cookie ou header; masque toute valeur sensible
  en `***`

Quand tu as terminé:

- mets à jour les docs d’exécution
- résume précisément ce qui a été fait et mesuré
- arrête-toi
- demande explicitement la revue orchestrator
- n’ouvre pas de PR
- ne lance pas la Phase 6

Commence maintenant.
