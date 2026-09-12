# Publication finale — Transfers et Chat

12 septembre 2026. Serveur/Web LAN et code mobile livrés ; compilation iOS,
recette physique et remise APNs/FCM différées selon le plan. Les SHAs ci-dessous
sont les dernières révisions **de code** publiées, vérifiées par `ls-remote`.
Le commit portant ce bilan ajoute seulement les documents de clôture sur la
même branche de `Apoze/drive` ; son identifiant est celui du commit Git courant.

| Fork origin — fetch/push | Branche de code publiée | SHA vérifié | Amont — fetch-only, push désactivé |
| --- | --- | --- | --- |
| https://github.com/Apoze/drive.git | `codex/transfers-chat-integration` | `af2b5ad702ee28c0f0568167b71376a3b495ee38` | https://github.com/suitenumerique/drive.git |
| https://github.com/Apoze/transfers.git | `codex/suite-transfers` | `7d3f13d9c1d9dccc905521ca5ca2773047c40c5a` | https://github.com/suitenumerique/transfers.git |
| https://github.com/Apoze/synapse.git | `codex/suite-chat` | `24c41ffecdd10f43754d365d41ae135a0e008fb6` | https://github.com/element-hq/synapse.git |
| https://github.com/Apoze/matrix-authentication-service.git | `codex/suite-chat` | `54d12b055bcf322bb3e24d13654ec0267cc11262` | https://github.com/element-hq/matrix-authentication-service.git |
| https://github.com/Apoze/element-web.git | `codex/suite-chat` | `175d54ac1999cc0edb8a2fdec154a7008019e49e` | https://github.com/element-hq/element-web.git |
| https://github.com/Apoze/element-x-android.git | `codex/suite-chat` | `6216f9ffff6b798c4da56a7197cb87c2e6a9ed37` | https://github.com/element-hq/element-x-android.git |
| https://github.com/Apoze/element-x-ios.git | `codex/suite-chat` | `cc69b2e163be7359f34f7dbe253820cbefb926f5` | https://github.com/element-hq/element-x-ios.git |
| https://github.com/Apoze/projects.git | `codex/chat-projects-integration` | `41eb996560e41018b7e655b999fd8cef843d00ec` | https://github.com/suitenumerique/projects.git |
| https://github.com/Apoze/meet.git | `codex/chat-meet-integration` | `bf0415463e17378742effcff072481375ef9c2a0` | https://github.com/suitenumerique/meet.git |
| https://github.com/Apoze/calendars.git | `codex/chat-calendar-integration` | `52b099ec9029b233ea97f56880d3862dcdefaaab` | https://github.com/suitenumerique/calendars.git |
| https://github.com/Apoze/messages.git | `codex/transfers-chat-integration` | `658784164a38e80ca34424708b64436ffec8dc0d` | https://github.com/suitenumerique/messages.git |
| https://github.com/Apoze/st-deploycenter.git | `codex/transfers-chat-integration` | `73f74f01e1cbbc16f78d219fd2468b090415e215` | https://github.com/suitenumerique/st-deploycenter.git |
| https://github.com/Apoze/docs.git | `codex/transfers-storage-capacity` | `d64c753101f6111e46c37a66be843c6bca1811be` | https://github.com/suitenumerique/docs.git |

Bases des derniers lots : même dépôt Apoze et même branche que chaque ligne,
avec les révisions précédentes consignées dans l'historique ci-dessous. Pour
les correctifs finaux Drive, base `Apoze/drive` `codex/transfers-chat-integration`
à `5fc5783855946916d578a7d01187b358dcd21ee8` ; commits de code
`2ae0dc054413ded774f5552d828a10c88491e67c` puis
`af2b5ad702ee28c0f0568167b71376a3b495ee38`.
Aucune PR créée ou modifiée, aucune fusion : base/head/URL de PR sans objet.
Aucune publication vers les dépôts suitenumerique ou element-hq.

Gates : fetch des forks, pas de fixup, absence de print backend suivi, politique
changelog, diff propre et gitlint des plages publiées ; builds/lints et recettes
ciblées consignés dans [validation-final.md](validation-final.md). Les deux refus
locaux de message Git (corps absent puis trop long) ont été corrigés avant commit ;
aucun contournement du hook. Douze forks associés propres au contrôle final.

Le dépôt `https://github.com/Apoze/people.git`, branche
`codex/suite-identity-access-catalogue`, conserve son travail non commité
préexistant à ce chantier ; il n'a pas été absorbé ou publié aveuglément dans
ce lot. La correction mémoire People de ce chantier porte sur les paramètres
d'exploitation suivis dans Drive, pas sur une réécriture de ces fichiers.
Les configurations privées, données, clés, sessions, signatures et archives
restent locales. Aucun binaire de développement ni secret ajouté à Git.

## Historique des publications intermédiaires

Les phrases « chantier ouvert/non livré » ci-dessous décrivent chaque jalon
à sa date ; l'état courant est celui de l'en-tête et du rapport final.

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

### Message mobile vers Projects — 12 septembre 2026

| Fork fetch/push | Branche | SHA distant vérifié | Amont fetch-only, push désactivé |
| --- | --- | --- | --- |
| https://github.com/Apoze/projects.git | `codex/chat-projects-integration` | `41eb996560e41018b7e655b999fd8cef843d00ec` | https://github.com/suitenumerique/projects.git |
| https://github.com/Apoze/element-x-android.git | `codex/suite-chat` | `159caac2ddee6b1214219b9eecf7affee20abc0e` | https://github.com/element-hq/element-x-android.git |
| https://github.com/Apoze/element-x-ios.git | `codex/suite-chat` | `6323c5087069eb001141a940421d18802ba94da7` | https://github.com/element-hq/element-x-ios.git |

Bases : versions précédemment publiées des mêmes branches, fetch explicite.
Aucune PR ni fusion ; base/head/URL de PR sans objet. Gitlint et diff contrôlés.
Android : APK, ordre des actions et envoi chiffré réels. Projects : parseur,
lint, build, SSO et création réels ; retour mobile corrigé après observation.
iOS : code raccordé, sans compilation macOS/Xcode disponible. Les premières
lignes de messages de commits locaux ont été remises en forme après un échec
gitlint ; aucun historique distant n'a été réécrit.

Publication précédente Transfers vérifiée :
`b654926d25662c7ed3a59b66a61a8d2de08c585e` sur
https://github.com/Apoze/transfers.git, branche `codex/suite-transfers`.
Le contrôle navigateur sans intention a abouti après réauthentification ; le
premier essai rencontrait une session expirée. Amont
https://github.com/suitenumerique/transfers.git : fetch-only, push désactivé.

### Reprise SSO du Web mobile — 12 septembre 2026

- Fork fetch/push : https://github.com/Apoze/element-web.git.
- Branche publiée : `codex/suite-chat`, base précédente `5c5bbfafa3762f8d58ecd7282de6e90232815d2`.
- SHA distant vérifié : `175d54ac1999cc0edb8a2fdec154a7008019e49e`.
- Amont : https://github.com/element-hq/element-web.git, fetch-only, push désactivé.
- Aucune PR ni fusion ; base/head/URL de PR sans objet.

Build, lint ciblé, connexion MAS Android Chrome et vérification du device avec
la clé native réussis. Le Web restaure les événements chiffrés. La lecture du
fichier dans ce navigateur mobile n'est pas qualifiée. Element Web considère
le mobile non pris en charge : ce parcours reste un secours, pas le transport
nominal des pièces jointes Element X. I93 et le chantier global restent ouverts.

### Reprise Transfers — 12 septembre 2026

- Fork fetch/push : https://github.com/Apoze/drive.git.
- Branche publiée : `codex/transfers-chat-integration` ; base de ce lot
  `6d249e7cf031589ebff684111eb1196c0b05d4de`.
- SHA distant vérifié : `276d4287393d6a97413e023c11c33cd99ee5bab1`.
- Amont : https://github.com/suitenumerique/drive.git, fetch-only, push désactivé.
- Aucune PR/fusion ; base/head/URL de PR sans objet.
- Ruff, compilation, gitlint et diff : passés. Sauvegarde, restauration,
  relecture S3/API et autorités actuelles : qualifiées. Instances isolées
  retirées ; archives privées conservées. Le chantier global reste ouvert.

### Reprise Chat durable — 12 septembre 2026

- Fork fetch/push : https://github.com/Apoze/drive.git.
- Branche publiée : `codex/transfers-chat-integration` ; base de ce lot
  `276d4287393d6a97413e023c11c33cd99ee5bab1`.
- SHA distant vérifié : `db413c1215fd31f312659b1ac8a62674653d01d5`.
- Amont : https://github.com/suitenumerique/drive.git, fetch-only, push désactivé.
- Aucune PR/fusion ; base/head/URL de PR sans objet.
- Compilation/Ruff/gitlint/diff passés. Restauration durable, revalidation de
  4 comptes et déchiffrement natif des 5 messages et du média 32 Mio qualifiés.
- Les instances isolées sont retirées ; pile active et archives préservées.
