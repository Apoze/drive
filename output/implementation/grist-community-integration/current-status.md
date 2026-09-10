# Grist Community — EN PAUSE

8 septembre 2026, sur demande du propriétaire.
[Plan canonique et état détaillé de pause](../../../docs/plans/paused/suite/grist-community-integration-plan.md).

**Ne pas reprendre ce chantier sans nouvelle demande spécifique du propriétaire.**
Les autorisations antérieures d’exécution sont suspendues. Ne pas considérer
ce document comme une tâche à poursuivre automatiquement.

## Avancement réel

- G0 : fork et sauvegardes préparés ; workflows désactivés, adaptation à finir.
- G1 : builds Community et outillage réussis ; aucune qualification runtime.
- G2/G3/G5 : code local partiel d’identité, projection People, politique ST,
  OIDC et gardes HTTP/WebSocket ; non validé fonctionnellement.
- G4 et G6–G11 : non réalisés. Aucun Grist déployé ni code publié.
- TypeScript production : réussi (18,26 s).
- ESLint ciblé : échec, 14 erreurs de style restantes après autofix.
- Aucun test comportemental Grist effectué.

## État conservé

- Checkout `/root/Apoze/grist`, branche `codex/suite-community-integration`,
  modifications non commitées ; branche locale `main` également conservée.
- Base `690c8dfdd32046a4de2558eb812c704ea5619229`.
- `origin` : https://github.com/Apoze/grist.git (fetch/push), distante `main`.
- `upstream` : https://github.com/gristlabs/grist-core.git (fetch-only,
  push désactivé). Aucun push du chantier, aucune PR ni écriture officielle.
- GitHub Actions **désactivé sur Apoze/grist**, à laisser ainsi pendant la pause.
- Images conservées : `apoze/grist:community-base`, `apoze/grist:build`.
- Sauvegardes privées : `data/grist-execution/baseline/` et
  `data/grist-execution/pause-20260908/` dans Drive ; ne pas publier.
- Journaux privés : `data/grist-execution/` dans Drive.
- Les 36 conteneurs existants sont actifs ; aucun conteneur Grist présent,
  aucun build/test Grist en cours lors du contrôle de pause.

## Reprise conditionnelle

Aucune prochaine action d’implémentation autorisée actuellement.
Après demande explicite seulement, suivre la section 0 du plan : réinventorier
l’environnement et le travail local avant de reprendre G1/G2/G3/G5, puis les
lots restants. Les tests et la publication finale restent à réaliser.
