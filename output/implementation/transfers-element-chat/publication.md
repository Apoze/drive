# Publication Transfers et Chat

Jalon TC3/TC4 publié le 11 septembre 2026. Chat non livré.

| Dépôt origin (fetch/push) | Branche publiée | SHA distant vérifié | Base | Amont fetch-only, push désactivé |
| --- | --- | --- | --- | --- |
| https://github.com/Apoze/docs.git | `codex/transfers-storage-capacity` | `d64c753101f6111e46c37a66be843c6bca1811be` | `Apoze/docs` `codex/projects-storage-capacity` | https://github.com/suitenumerique/docs.git |
| https://github.com/Apoze/messages.git | `codex/transfers-chat-integration` | `4e3bd36410d520aacc01e7021294e6195979afd0` | `Apoze/messages` `codex/projects-notifications` | https://github.com/suitenumerique/messages.git |
| https://github.com/Apoze/st-deploycenter.git | `codex/transfers-chat-integration` | `73f74f01e1cbbc16f78d219fd2468b090415e215` | `Apoze/st-deploycenter` `codex/projects-integration` | https://github.com/suitenumerique/st-deploycenter.git |
| https://github.com/Apoze/transfers.git | `codex/suite-transfers` | `e9bf369c899c7d880cf761f26902894b1f2b312a` | `Apoze/transfers` `main` | https://github.com/suitenumerique/transfers.git |
| https://github.com/Apoze/drive.git | `codex/transfers-chat-integration` | `b178fb6d7dc31eebd66a2b2bbc76f2ebc545778d` | `Apoze/drive` `codex/transfers-chat-integration-plan` | https://github.com/suitenumerique/drive.git |

Aucune PR créée : base/head/URL de PR sans objet. Aucun merge ni action vers
les amonts. Gitlint, absence de fixup/print backend, changelog et contrôles ciblés
passés avant publication. Les SHA ont été comparés à `git ls-remote`.

Forks Chat créées : Apoze/synapse, Apoze/matrix-authentication-service,
Apoze/element-web, Apoze/element-x-android, Apoze/element-x-ios. Leur intégration
reste en cours ; ne pas les confondre avec une solution Chat livrée.

## Jalon fondations Chat — 11 septembre 2026

| Dépôt origin (fetch/push) | Branche publiée | SHA distant vérifié | Base auditée | Amont fetch-only, push désactivé |
| --- | --- | --- | --- | --- |
| https://github.com/Apoze/synapse.git | `codex/suite-chat` | `6b76af95301c9f2273465888c02a6464bbcd136e` | `Apoze/synapse` `develop` | https://github.com/element-hq/synapse.git |
| https://github.com/Apoze/matrix-authentication-service.git | `codex/suite-chat` | `6714d655230a9bb8b29f664f1d22fee57bfc60ce` | `Apoze/matrix-authentication-service` `main` | https://github.com/element-hq/matrix-authentication-service.git |
| https://github.com/Apoze/element-web.git | `codex/suite-chat` | `c0049d08b01a29d20fc0a7f8ba50e352b57bf224` | `Apoze/element-web` `develop` | https://github.com/element-hq/element-web.git |
| https://github.com/Apoze/drive.git | `codex/transfers-chat-integration` | `128107ebd8bed2d8c32d349c0df410547391973a` | `Apoze/drive` `codex/transfers-chat-integration` | https://github.com/suitenumerique/drive.git |

Aucune PR : base/head/URL de PR sans objet. Le diff de publication Element est
évalué depuis son merge-base, car la branche amont develop a avancé après la
release épinglée. Aucun changement de release ni modification des snapshots
amont pour satisfaire artificiellement un contrôle de whitespace.
Le jalon ne clôture pas TC5–TC11 ; les salons gérés et intégrations restent ouverts.

## Jalon salons, médias et administration — 11 septembre 2026

| Dépôt fetch/push | Branche publiée et base du prochain lot | SHA distant vérifié | Amont fetch-only, push désactivé |
| --- | --- | --- | --- |
| https://github.com/Apoze/synapse.git | `codex/suite-chat` | `22b88a19e23aace95f94c3474ba0be085132aa7c` | https://github.com/element-hq/synapse.git |
| https://github.com/Apoze/element-web.git | `codex/suite-chat` | `0f91ba18b2eae0764c915dd2be77e48b0f2db0df` | https://github.com/element-hq/element-web.git |
| https://github.com/Apoze/drive.git | `codex/transfers-chat-integration` | `b2f6efb531e0caabef73f302b050f1462040af76` | https://github.com/suitenumerique/drive.git |

Aucune PR : base/head/URL sans objet. Aucun merge. Gitlint et diff check
passés ; attribut Git des patches respecte leur marqueur de contexte vide.
Les intégrations applicatives et mobiles restent à réaliser.

## Jalon TC6 — fichiers privés et catalogue, 11 septembre 2026

| Fork publiée (fetch/push) | Branche | SHA distant vérifié |
| --- | --- | --- |
| https://github.com/Apoze/drive.git | `codex/transfers-chat-integration` | `2289b164cbb5b3215e11bf9448f2aaccc8b949ed` |
| https://github.com/Apoze/element-web.git | `codex/suite-chat` | `eb8d8d677f7cd9d40861135765306f601e1ddce6` |
| https://github.com/Apoze/synapse.git | `codex/suite-chat` | `d78b6cbcf59143be5661abf1e89b4c813319be91` |

Dépôts officiels fetch-only, push désactivé :
https://github.com/suitenumerique/drive.git,
https://github.com/element-hq/element-web.git,
https://github.com/element-hq/synapse.git.
Bases de publication : branches existantes respectives des forks Apoze indiquées.
Aucune PR (base/head/URL sans objet), aucune fusion, aucun envoi upstream.
Fetch, gitlint, diff-check, changelog et absence de fixup vérifiés ; types/lints
ciblés et vrais parcours décrits dans le journal. Ce jalon ne clôt pas TC0–TC12.

## TC6 — Chat et Transfers, 11 septembre 2026

| Fork fetch/push | Branche et base du prochain lot | SHA distant vérifié |
| --- | --- | --- |
| https://github.com/Apoze/drive.git | `codex/transfers-chat-integration` | `e1d553950d0f48ebb691df345a7675fa7501f440` |
| https://github.com/Apoze/transfers.git | `codex/suite-transfers` | `209cd32d1938cef147070416a40df517bbaa51e6` |
| https://github.com/Apoze/element-web.git | `codex/suite-chat` | `7a3449a0c1b258ffa35b6192a0e2755b565a6127` |

Amonts fetch-only, push désactivé :
https://github.com/suitenumerique/drive.git,
https://github.com/suitenumerique/transfers.git,
https://github.com/element-hq/element-web.git.
Aucune PR (base/head/URL sans objet), aucune fusion ni écriture amont.
Gates locaux et scénarios réels consignés dans le journal ; TC7–TC12 ouverts.

## TC7 — Serveur Meet et contexte Chat, 11 septembre 2026

| Dépôt de publication | Branche | SHA vérifié sur GitHub |
| --- | --- | --- |
| `https://github.com/Apoze/meet.git` | `codex/chat-meet-integration` | `cdf982cfd6865208ca327319d190d937b86f785f` |
| `https://github.com/Apoze/synapse.git` | `codex/suite-chat` | `bef5be47e0864b9bc6135e0be9e6c103c2e2f6b4` |

Bases de ce lot : `Apoze/meet` `codex/messages-calendars-sdk`
`71eff781c4764ef53107acfc4cc66a8359016ea6` ; `Apoze/synapse`
`codex/suite-chat` `d78b6cbcf59143be5661abf1e89b4c813319be91`.
Origines fetch/push : URLs Apoze ci-dessus. Amonts fetch-only, push désactivé :
`https://github.com/suitenumerique/meet.git` et
`https://github.com/element-hq/synapse.git`.
Aucun PR, aucune fusion ; base/head/URL de PR sans objet.

Validation : Ruff natif ciblé ; build proxy Meet avec TypeScript ; vrais
parcours SSO, concurrence/rejeu, deux navigateurs WebRTC et retraits actifs
ST/groupe People ; erreur d’accès visible ; gitlint, diff et changelog.
Element et Drive TC7 restent à publier après leur dernier contrôle visuel.

### TC7 — Element Web publié

- Dépôt fetch/push : `https://github.com/Apoze/element-web.git`.
- Branche : `codex/suite-chat`, SHA distant vérifié
  `508bef4847a2ff020e8ba2a886c79062057b5413`.
- Base du lot : `Apoze/element-web` `codex/suite-chat`,
  `7a3449a0c1b258ffa35b6192a0e2755b565a6127`.
- Amont fetch-only, push désactivé :
  `https://github.com/element-hq/element-web.git`.
- Aucun PR ni fusion ; base/head/URL de PR sans objet.
- Contrôles : TypeScript de l’intégration, lints natifs ciblés, build complet
  final à 2,5 Gio/Node 1024 Mio, SSO/invitation E2EE, carte fermée et capture
  desktop/520 px ; gitlint, changelog et diff propres.

Le commit Drive qui porte ce suivi publie le générateur des liaisons,
le proxy borné et le worker de compilation avec leurs guides. Le chantier
complet reste en cours : Calendars, Projects/bot, mobiles et exploitation.
