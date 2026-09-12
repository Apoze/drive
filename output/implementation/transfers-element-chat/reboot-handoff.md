# Reprise Transfers et Chat après augmentation de RAM

Point au 12 septembre 2026, avant redémarrage demandé par le propriétaire.
**Chantier en cours ; le plan TC0–TC12 n'est pas terminé.**
Le redémarrage sera effectué par le propriétaire, puis il relancera l'agent.
Ne pas confondre ce point de reprise avec une livraison finale.

## Vérifications avant de continuer

1. Vérifier la RAM réellement reconnue, Docker et l'espace libre. Avant
   redémarrage : disque 65 Gio libres ; la limite rencontrée était la RAM.
2. Restaurer les services auparavant démarrés à partir de la liste privée
   `tmp/transfers-chat-qa/before-vm-reboot-services.json` (70 conteneurs).
   Plusieurs services Drive/ST et Authentik QA ont `restart=no`. Ne pas
   supposer que le démarrage de Docker remonte toute la pile. Préserver
   leurs conteneurs, configurations et volumes ; aucun `down -v`, prune ou
   changement d'environnement. Drive LAN : `bash run_env_local.sh` ; ST :
   `make start` dans son dépôt, conformément à `docs/env_freeze_report.md`.
   Vérifier les autres stacks et remettre les conteneurs existants nécessaires
   en route. Ne pas recréer une nouvelle base Keycloak ni les accès NAS.
3. Les sources en cours sont persistées, non encore publiées pour le lot bot.
   L'état Git des cinq dépôts concernés est enregistré dans
   `tmp/transfers-chat-qa/before-vm-reboot-git.json`. Respecter aussi les
   modifications People/Grist étrangères à ce lot. Grist reste en pause.
4. Aucun navigateur de recette ni compilation ne reste actif. Le worker
   BuildKit `apoze-suite` a été arrêté après les compilations réussies.

## Dernier lot publié

Projects : création de carte native, partage de carte/tableau chiffré, brouillon,
rejeu sans doublon et refus d'accès qualifiés. Les applications sont publiées ;
le générateur/suivi Drive a aussi été publié :

- https://github.com/Apoze/drive.git — `codex/transfers-chat-integration`,
  `b511ac14cfe928b9b7beda990d4dabc252fa3b21`.
- https://github.com/Apoze/projects.git — `codex/chat-projects-integration`,
  `934908cff2fa03a8afb14d27dd4c74a651ca5999`.
- https://github.com/Apoze/synapse.git — `codex/suite-chat`,
  `9133b0fe36523d4183ac199dea497694934709eb`.
- https://github.com/Apoze/element-web.git — `codex/suite-chat`,
  `31caf901756da3053edd129754f04b1a2966f5da`.

Amonts fetch-only/push désactivé : `https://github.com/suitenumerique/drive.git`,
`https://github.com/suitenumerique/projects.git`,
`https://github.com/element-hq/synapse.git`,
`https://github.com/element-hq/element-web.git`. Aucune PR ni fusion ;
base/head/URL de PR sans objet. Voir `publication.md` pour les autres lots.

## Bot : code et état présents

- Synapse : `synapse/apoze_suite/bot.py`, garde de session personnelle dédiée,
  clé de gestion distincte de lecture/envoi, présence par droit direct de
  membre uniquement. Pas de promotion admin ni admission implicite par groupe.
  Le bot est exclu du roster humain Calendars.
- MAS : `apoze_suite::technical_session` utilise uniquement les informations
  natives de session validées. Pas de preuve OIDC fabriquée ; les sessions
  personnelles humaines restent interdites. Modifications compilées/déployées
  dans MAS avant l'arrêt du 11 septembre.
- Projects : `suite-chat-notifications.js`, actions publiques/privées séparées,
  migration `20260911000200_suite_chat_notifications`, journal natif réutilisé,
  opt-in utilisateur/tableau/salon, reçu Matrix stable et incertitude bornée.
  UI dans `SuiteChat.jsx`, composants Cunningham existants.
- Element : entrée Notifications Projects dans le menu Projects du salon,
  ouverture du SDK natif sans polling de carte pour ce mode.
- SDK bot : `Apoze/synapse/contrib/apoze/notifications-bot/`, Rust Matrix 0.18.0
  verrouillé, stockage SQLite E2EE chiffré, aucune journalisation de contenu.
  Le paquet JS ancien examiné n'est pas livré.
- Drive : provision/générateurs/guide du bot, restauration Projects isolée
  désactivant les nouveaux canaux, limite de recyclage People séparée.

### Compilations terminées le 12 septembre

- Bot : `apoze/projects-bot:suite-local`, image
  `sha256:507abbc09079f636bfcae3cfae390551fb5396fea23cf2e8bc87915ba13c5970`.
- Projects : `apoze/projects:suite-local`, image
  `sha256:c3f3e4ad63595abd6ee4328ae213166eaf0c363635428c2e57cd5d461e071785`.
- Synapse : `apoze/synapse:suite-local`, image
  `sha256:1bc1924c33b69aea4f25fce04dd4122dec6c5603a8f59e1d252d70ec72d387d0`.

**Ces trois dernières images ne sont pas encore déployées.** La migration
Projects du bot n'a pas encore été appliquée. Element doit encore être compilé
avec l'entrée Notifications Projects ; sa dernière image active est antérieure.
Lints ciblés Projects/Synapse/Element passés avant le redémarrage ; les deux
erreurs de compilation Rust (API JSON et reçu `.response.event_id`) corrigées,
compilation native réussie. Pas de recette E2EE du bot encore effectuée.

### Identité et données de recette

- Bot People : `21f2f754-e036-42b1-9a26-4ecf54085f00`, appareil
  `APOZE_PROJECTS_BOT`, aucun binding IdP humain. Droit ST Chat accordé.
  Session et clés privées sous `data/chat-qa/bot/`, métadonnées privées dans
  `data/chat-qa/settings.json`. Ne jamais imprimer ces fichiers.
- `bot_auth_probe.py` a validé réellement le compte/appareil du bot par
  l'API Matrix native et le refus d'une session personnelle humaine créée
  pour la recette. Cette dernière session a été révoquée dans le `finally`.
- Main et second utilisateur QA ont un login Projects natif fonctionnel ;
  leur preuve expire après 15 minutes. Helpers privés
  `projects_native_login.py` et `projects_second_native_login.py`.
- Le second sujet Projects a été vérifié cryptographiquement et approuvé dans
  People (`projects_second_bind.py`), puis ajouté au tableau de recette par
  l'API native. La carte UI existante est suivie par le premier utilisateur.
  État/restauration : `projects-chat-fixtures.json`, champs
  `bot_second_membership`, `bot_subscription_before`. Aucun commentaire de
  recette bot ni aucune souscription Chat n'a encore été créé.
- Sauvegarde DB avant migration bot :
  `tmp/transfers-chat-qa/projects-before-bot.dump`.
- Toutes les fixtures précédentes restent pour TC12 : voir journal et
  fichiers privés existants. Ne pas supprimer l'espace NAS préexistant.

## Prochaine action concrète

1. Après restauration de la pile, refaire le préflight RAM ; conserver le
   worker de build limité et fermer les navigateurs pendant les compilations.
2. Déployer les images Synapse/Projects construites, attendre leur santé et
   vérifier la migration native Projects. Compiler/déployer Element.
3. Démarrer `projects-bot` depuis `data/chat-qa/compose.json` ; diagnostiquer
   et corriger toute erreur native de sync/E2EE. Le bot ne doit rejoindre
   que les salons dans lesquels le responsable l'active explicitement.
4. Recette réelle minimale : UI desktop/520 px, activer le bot et une
   destination pour le premier QA ; commentaire du second utilisateur sur
   la carte suivie ; vérifier notification chiffrée déchiffrable et lien
   Projects. Tester replay après perte d'accusé, retrait et redémarrage
   avec les mêmes clés. Garder une vérification réexécutable ciblée.
5. Publier le lot validé sur les forks Apoze seulement, après les gates.
6. Continuer TC6 restant, TC8/TC9 code Android/iOS, TC10 Sygnal/push, puis
   TC11 restauration isolée et TC12 nettoyage/publication finale.

Le nom durable Matrix reste demandé au propriétaire, sans réponse à ce stade.
`chat-qa.invalid` reste une identité jetable ; ne pas inventer le domaine final.
Pas d'appareil mobile, pas de Mac/Xcode ni SDK Android installés constatés ;
le code mobile reste à livrer même si la recette physique est différée.

## Garde-fou RAM appliqué

Un enfant People inactif retenait 1,8 Gio après plusieurs jours. Recyclage
Celery natif après vérification sans tâche active, puis application de
`docker/suite/people-worker-resources.yaml` au seul worker People.
Concurrence deux ; recyclage après tâche à 384 Mio ou 2 000 tâches.
La configuration active inclut cet override ; le conserver à la reprise.
Le code People modifié par d'autres travaux n'a pas été touché.
