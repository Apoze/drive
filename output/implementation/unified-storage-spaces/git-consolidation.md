# Consolidation Git avant le chantier

Date : 5 septembre 2026.

Autorisation : consolidation sur main, nettoyage des branches et création de la branche du chantier demandés explicitement par l’utilisateur.

| Dépôt de publication | main consolidé | Anciennes branches archivées |
| --- | --- | --- |
| https://github.com/Apoze/drive.git | `cfa564e0` | 2 |
| https://github.com/Apoze/st-deploycenter.git | `71a6572` | 43 |

Les deux dépôts ne contenaient plus que `main` après la publication atomique. La branche `codex/unified-storage-spaces` a ensuite été créée et publiée dans chacun. Aucun force-push de main ; chaque suppression de branche vérifiait son SHA attendu.

Les tags `archive/2026-09-05/…` conservent les pointes exactes de toutes les anciennes branches GitHub. Les branches ST divergentes ne sont pas fusionnées : leur contenu historique reste consultable et récupérable sous ces tags. Le socle homelab et les huit commits du journal d’activité local Drive sont intégrés dans main. Le worktree du journal d’activité est conservé.

Dépôts officiels fetch-only : https://github.com/suitenumerique/drive.git et https://github.com/suitenumerique/st-deploycenter.git ; push désactivé. Publication directe sur les deux dépôts Apoze, aucune PR créée (base/head/URL de PR : sans objet).

Validation : 39 tests backend, 19 tests frontend, types Drive, Ruff/Pylint des chemins intégrés, gitlint de la plage, absence de print backend Drive et diff-check. Les preuves précédentes du socle ST restent celles de son rapport de qualification.

La fusion préserve les deux historiques Django par `0036_merge_storage_activity`. Une erreur de métadonnées après conversion ne supprime plus une publication gouvernée confirmée ; scénario de régression inclus.

Les secrets et configurations locales, sessions de navigateur et artefacts de qualification restent exclus. Sauvegardes locales des références, historique et diff sous tmp/unified-storage-preflight dans chaque dépôt.

## Références archivées

### Apoze/drive

| Branche ancienne | SHA conservé | Tag |
| --- | --- | --- |
| `codex/block-drive-uploads-quota-172` | `a8a93fb86271556b6e515c40c3be9ec3e7731ae3` | `archive/2026-09-05/codex/block-drive-uploads-quota-172` |
| `codex/catchup-behind-prep-20260727` | `57a65ec153e078026e0b5643f83285fd0c95488c` | `archive/2026-09-05/codex/catchup-behind-prep-20260727` |

### Apoze/st-deploycenter

| Branche ancienne | SHA conservé | Tag |
| --- | --- | --- |
| `account_ui` | `654f17c7f7bc73a5a02d652838ba483d3313ca5e` | `archive/2026-09-05/account_ui` |
| `account_webhooks` | `41223aaec5f733fde693bde37c4c5e24e175acd8` | `archive/2026-09-05/account_webhooks` |
| `card_improvements` | `092a68f4c24f8a0a0afbe8b2889ed5b88cd6b0cc` | `archive/2026-09-05/card_improvements` |
| `codex/st-deploycenter-drive-quota` | `76d9bd631c556e7c93a51649c0c790f137248e7b` | `archive/2026-09-05/codex/st-deploycenter-drive-quota` |
| `delete_account` | `9f9667261bcf6a871cbbc328cf864bace6f0936d` | `archive/2026-09-05/delete_account` |
| `domains_split` | `64bc7dae369c73505fe4f74ffeff97a3c32f7d9d` | `archive/2026-09-05/domains_split` |
| `extended_admin` | `a056078f882fd07d425fd2952f5b3ac59927dde4` | `archive/2026-09-05/extended_admin` |
| `external_mgmt_api` | `3e139cd52da7dec9a41682e20504d273a3a9c3ff` | `archive/2026-09-05/external_mgmt_api` |
| `feat/accounts` | `112277d82c7bb09435dd0a6d44a87811ba52e025` | `archive/2026-09-05/feat/accounts` |
| `feat/allow-no-organization-entitlements` | `0a351c91fa1eac18e5f6761a7fed316bfbff0e48` | `archive/2026-09-05/feat/allow-no-organization-entitlements` |
| `feat/cannot-upload-drive-reason` | `e30588c0d876b1e82eb828e1fb7f1aaf87a840d7` | `archive/2026-09-05/feat/cannot-upload-drive-reason` |
| `feat/drive-can-access-always` | `7577dfd5d45c39f62ea0e8db59df0ad7de0c1ecb` | `archive/2026-09-05/feat/drive-can-access-always` |
| `feat/drive-org-quota` | `971898a1bd95ef6b5189d24f7c9ec5db416bf35c` | `archive/2026-09-05/feat/drive-org-quota` |
| `feat/edit-entitlements` | `0712ab26ef6e38af560e9e2dffc68113448b45e7` | `archive/2026-09-05/feat/edit-entitlements` |
| `feat/entitlements` | `11f0fc3643bcff5e39bae3b3a1bd46ab99a203b6` | `archive/2026-09-05/feat/entitlements` |
| `feat/expose-metrics-entitlements` | `27e309b235b1fa12159e0a9626db52001b3e3bb0` | `archive/2026-09-05/feat/expose-metrics-entitlements` |
| `feat/hidden-service-transferts` | `7104cc831708dc32acd7a30a2ce4f9a7584e6971` | `archive/2026-09-05/feat/hidden-service-transferts` |
| `feat/implement-sketches` | `ca7f48297c6c7d8c6885442ea890961bd97c0825` | `archive/2026-09-05/feat/implement-sketches` |
| `feat/messages-card` | `5dd29e5a1ac71d2c36852ab3b3b366990bfd89c9` | `archive/2026-09-05/feat/messages-card` |
| `feat/metrics-dashboard` | `a87de804d2c91af903168cdb906095ba1270f76d` | `archive/2026-09-05/feat/metrics-dashboard` |
| `feat/pc-service` | `1a9b5624abb67b31b7425c9af94668aa06b28dde` | `archive/2026-09-05/feat/pc-service` |
| `feat/post-metrics` | `b1cc2655568767a277513f907115764d9a844f42` | `archive/2026-09-05/feat/post-metrics` |
| `feat/setup-front` | `fed2ace844d8a3659645175cb58aaa5e8a4c2c5f` | `archive/2026-09-05/feat/setup-front` |
| `feat/setup-front-bak` | `8d2d9cd33baf9ed0f81ef4d80a9c73bf4afbeb3f` | `archive/2026-09-05/feat/setup-front-bak` |
| `feat/subscription-operator` | `65e636751e04276effe71de98269a2b80f8b463e` | `archive/2026-09-05/feat/subscription-operator` |
| `fix/perfissues` | `60b646b00f198a5f619efa562865693013e3309d` | `archive/2026-09-05/fix/perfissues` |
| `fix/service-display` | `05c0d0f54714eff9037c0c95e59fcc7e06d2b4f0` | `archive/2026-09-05/fix/service-display` |
| `instance_name` | `39f6653ca69f59feb49dcedc2e2b0f59b444bf90` | `archive/2026-09-05/instance_name` |
| `master_roles` | `ec48cfbd208330bd8a6ae14273b13d3669943618` | `archive/2026-09-05/master_roles` |
| `messages_admin` | `28069e296776c6b8ba07b9a356e169456c0a9bc6` | `archive/2026-09-05/messages_admin` |
| `messages_card` | `ec575709edbb1656f29454003d8f269da71fc496` | `archive/2026-09-05/messages_card` |
| `metrics_api_rename` | `f42b1deb0f578de2f453dc0aafe6b997b66ba1ee` | `archive/2026-09-05/metrics_api_rename` |
| `multiple_operators` | `5167673ec2155030418d0da21f9e5507ce885eb9` | `archive/2026-09-05/multiple_operators` |
| `operatorconfigs` | `b61d10668ffb9b953f22322c9399d00c19f6e789` | `archive/2026-09-05/operatorconfigs` |
| `org_types` | `7382466b4d4a9478f8fa3e36324d935d1a357516` | `archive/2026-09-05/org_types` |
| `population_limits` | `daf2c32598d24985dfaa5fb258e572644fab3ae8` | `archive/2026-09-05/population_limits` |
| `proconnect_api` | `ba931011d11d7a356a9a219d7e92c2dfb6eb171d` | `archive/2026-09-05/proconnect_api` |
| `proconnect_prodx` | `c14268408579039c16452c2a391f2db25fad0050` | `archive/2026-09-05/proconnect_prodx` |
| `ref/subscription-active` | `02e5ec23aaf89acc90e6cd73fd8d4b24f15e5e0a` | `archive/2026-09-05/ref/subscription-active` |
| `renovate/configure` | `e0872eb1c51cf2d5a38a42f6f24414f79e535251` | `archive/2026-09-05/renovate/configure` |
| `service_api_key` | `33923c3582bf605883da0b1789f9f6bcc45cca2a` | `archive/2026-09-05/service_api_key` |
| `services/meet` | `46f527d777d37cf0575b68329a48330ebd2fd441` | `archive/2026-09-05/services/meet` |
| `webhooks` | `9c286a612cea1f98dbe6e104174ac9ec8fed98fd` | `archive/2026-09-05/webhooks` |
