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

### TC7 — Générateurs et suivi Drive publiés

Fetch/push : `https://github.com/Apoze/drive.git`, branche
`codex/transfers-chat-integration`, SHA distant vérifié
`0bb739940e6e2962000bd79148325cdc38e21a20`.
Base du lot : même dépôt/branche, `e1d553950d0f48ebb691df345a7675fa7501f440`.
Amont : `https://github.com/suitenumerique/drive.git`, fetch-only, push désactivé.
Aucun PR ni fusion ; base/head/URL de PR sans objet.
Gates : compilation et limites natives, recettes consignées, Python compile,
gitlint, changelog sous 80 colonnes, absence de print backend et diff propres.

## Calendars et invitations Chat — 11 septembre 2026

Validation : invitations réelles initiale/mise à jour/annulation, concurrence,
refus d’accès et carte chiffrée desktop/520 px. Builds natifs et gates ciblées.

- `origin` https://github.com/Apoze/calendars.git : branche `codex/chat-calendar-integration`,
  base vérifiée `Apoze/calendars` `codex/suite-messages-calendars`, SHA distant `37a48575c356d3d7ddd60a5c5231b62f446bf1fa`.
  Amont https://github.com/suitenumerique/calendars.git : lecture seule, push désactivé.
- `origin` https://github.com/Apoze/messages.git : branche `codex/transfers-chat-integration`,
  base vérifiée `Apoze/messages` `codex/transfers-chat-integration`, SHA distant `658784164a38e80ca34424708b64436ffec8dc0d`.
  Amont https://github.com/suitenumerique/messages.git : lecture seule, push désactivé.
- `origin` https://github.com/Apoze/synapse.git : branche `codex/suite-chat`,
  base vérifiée `Apoze/synapse` `codex/suite-chat`, SHA distant `baf94145a2d663ba91a0b31b1720c62ceedc2bb0`.
  Amont https://github.com/element-hq/synapse.git : lecture seule, push désactivé.
- `origin` https://github.com/Apoze/element-web.git : branche `codex/suite-chat`,
  base vérifiée `Apoze/element-web` `codex/suite-chat`, SHA distant `c8eae3da943322519495653738de6bcbb909722d`.
  Amont https://github.com/element-hq/element-web.git : lecture seule, push désactivé.

Aucune PR créée, aucune base/head de PR ni fusion. Publication Drive du suivi
et des générateurs sur `https://github.com/Apoze/drive.git`, branche
`codex/transfers-chat-integration` (base homonyme, amont
`https://github.com/suitenumerique/drive.git` fetch-only, push désactivé).

- Suivi/générateurs Drive vérifiés sur
  `https://github.com/Apoze/drive.git` `codex/transfers-chat-integration` :
  `f94f0ee369cda6dcd8a5ae29f86023bf243066ec`.

## Projects et cartes Chat — 11 septembre 2026

Recette native : création concurrente/rejeu, suppression sans recréation,
partage de tableau et de tâche chiffrés, brouillon conservé, refus par compte
et retrait ST en 22,2 secondes. Interfaces desktop/520 px examinées.
Builds natifs, TypeScript Element complet et linters ciblés réussis.

| Dépôt fetch/push | Branche publiée | SHA distant vérifié | Base du lot |
| --- | --- | --- | --- |
| https://github.com/Apoze/projects.git | codex/chat-projects-integration | 934908cff2fa03a8afb14d27dd4c74a651ca5999 | Apoze/projects codex/suite-projects, 994cb1442b7b8ea1d192d84149c1fbdc0e4b1894 |
| https://github.com/Apoze/synapse.git | codex/suite-chat | 9133b0fe36523d4183ac199dea497694934709eb | Apoze/synapse codex/suite-chat, baf94145a2d663ba91a0b31b1720c62ceedc2bb0 |
| https://github.com/Apoze/element-web.git | codex/suite-chat | 31caf901756da3053edd129754f04b1a2966f5da | Apoze/element-web codex/suite-chat, c8eae3da943322519495653738de6bcbb909722d |

Amonts fetch-only, push désactivé :
https://github.com/suitenumerique/projects.git,
https://github.com/element-hq/synapse.git,
https://github.com/element-hq/element-web.git.
Aucune PR ni fusion ; base/head/URL de PR sans objet.

Images déployées : Projects `9355af9741a4ee0b0962bb3c58d6b8b35b62e908d66cf35c57b5265d498311ac`,
Synapse `e316bf712abf980573ef9db3a3b3227476e113d2c80572a90efe4cf29f05bafb`,
Element `090c465fa1d8e66270e0f33feb2dd308fefabc4791e7b89afa5302c802439bb2`.
Le générateur et le suivi Drive utilisent la branche
`codex/transfers-chat-integration` de https://github.com/Apoze/drive.git,
base du lot `f94f0ee369cda6dcd8a5ae29f86023bf243066ec`.
Amont https://github.com/suitenumerique/drive.git : fetch-only, push désactivé.

## Bot Projects, reprise VM et menu natif — 12 septembre 2026

| Fork fetch/push | Branche | SHA distant vérifié |
| --- | --- | --- |
| https://github.com/Apoze/drive.git | codex/transfers-chat-integration | 70da48d0bd0d08ef479b337d6bd722480c4e616e |
| https://github.com/Apoze/projects.git | codex/chat-projects-integration | 2b8be7928b8a3a87c2b04cb35fe2ed278c2e797b |
| https://github.com/Apoze/synapse.git | codex/suite-chat | b0742d17206df494d9b33ba4ef300c95ffa55054 |
| https://github.com/Apoze/matrix-authentication-service.git | codex/suite-chat | 54d12b055bcf322bb3e24d13654ec0267cc11262 |
| https://github.com/Apoze/element-web.git | codex/suite-chat | 5c5bbfafa3762f8d58eecd7282de6e90232815d2 |

Amonts fetch-only, push désactivé :
https://github.com/suitenumerique/drive.git,
https://github.com/suitenumerique/projects.git,
https://github.com/element-hq/synapse.git,
https://github.com/element-hq/matrix-authentication-service.git,
https://github.com/element-hq/element-web.git.
Bases : précédents SHA publiés des mêmes branches. Aucune PR ni fusion ;
base/head/URL de PR sans objet. Diffs/changelogs/gitlint contrôlés ; lints
ciblés, compilations natives et recette réelle consignés dans le journal.
Le chantier global reste ouvert.

## Domaine durable et premiers lots mobiles — 12 septembre 2026

| Fork fetch/push | Branche | SHA distant vérifié | Amont fetch-only |
| --- | --- | --- | --- |
| https://github.com/Apoze/synapse.git | `codex/suite-chat` | `cb6e31da501234cc7007a6b8c5c5f6525fc9d459` | https://github.com/element-hq/synapse.git |
| https://github.com/Apoze/drive.git | `codex/transfers-chat-integration` | `0c6b2632021b9aff3613c9b2c8fe6a7ca91d74a0` | https://github.com/suitenumerique/drive.git |
| https://github.com/Apoze/element-x-android.git | `codex/suite-chat` | `c4329d98733be765af5c84ded84d9e0b647ed6ce` | https://github.com/element-hq/element-x-android.git |
| https://github.com/Apoze/element-x-ios.git | `codex/suite-chat` | `947013ede8ef8c75071605b546fe71729cc4cbba` | https://github.com/element-hq/element-x-ios.git |
| https://github.com/Apoze/meet.git | `codex/chat-meet-integration` | `bf0415463e17378742effcff072481375ef9c2a0` | https://github.com/suitenumerique/meet.git |
| https://github.com/Apoze/calendars.git | `codex/chat-calendar-integration` | `52b099ec9029b233ea97f56880d3862dcdefaaab` | https://github.com/suitenumerique/calendars.git |
| https://github.com/Apoze/projects.git | `codex/chat-projects-integration` | `e186496c236f3451293051b076c8e50996bda325` | https://github.com/suitenumerique/projects.git |

Bases mobiles auditées : `Apoze/element-x-android` `develop` et
`Apoze/element-x-ios` `develop` ; autres bases : branches déjà publiées du tableau.
Aucune PR (base/head/URL sans objet), aucune fusion, aucun push amont.
Android compilé et testé sur émulateur ; iOS préparé, sans Xcode disponible.
Les actions fichiers mobiles et la clôture du chantier restent en cours.

Incident de procédure Meet : le fetch limité à `main` n'avait pas créé la ref
locale de la branche publiée. Gitlint a d'abord échoué sur cette ref absente ;
le push a été lancé trop tôt. Le contrôle sur le SHA précédent explicite
`cdf982cfd6865208ca327319d190d937b86f785f` a ensuite réussi. Pour les lots
suivants, résoudre/fetcher la branche exacte avant le contrôle et ne lancer
aucun push dans une boucle indépendante du résultat de la gate.

### Partage système mobile — jalon supplémentaire

| Fork fetch/push | Branche | SHA distant vérifié |
| --- | --- | --- |
| https://github.com/Apoze/element-x-android.git | `codex/suite-chat` | `1c740f104bf8de571327b09354c27ed2c4e71008` |
| https://github.com/Apoze/element-x-ios.git | `codex/suite-chat` | `9ce5bdd0141d0ad08109f0e3a7328163500f3765` |
| https://github.com/Apoze/transfers.git | `codex/suite-transfers` | `4bcbcecf4c578f6148b4d38a72a7988a7abb71b2` |

Bases : branches publiées du jalon précédent. Amonts `element-hq/element-x-android`,
`element-hq/element-x-ios` et `suitenumerique/transfers`, fetch-only et push
désactivé, URLs complètes dans les tableaux précédents. Aucune PR ni fusion.
Android réel qualifié ; iOS non compilé. Lots suivants encore ouverts.
