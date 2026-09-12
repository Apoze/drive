# Journal Transfers et Chat

## 10 septembre 2026 — démarrage

Lecture AGENTS, plan complet, ADR identité et contrat stockage. Préflight
Compose et inventaire Git : intégrations existantes démarrées ; People et Grist
seuls arbres applicatifs avec changements antérieurs. Aucune restauration ou
réinitialisation. Création de la branche Drive depuis le plan publié.

Création des cinq forks prévues sous Apoze, sans écriture vers les amonts.
Transfers part du SHA inspecté ; composants Element/Synapse des références
figées du plan. Branches dédiées ; aucun merge ni PR.

Préflight mobile : serveur Linux, KVM présent, outils mobiles absents du PATH.
Question du domaine durable Matrix envoyée avant toute création de compte.
Le développement Transfers reste indépendant de cette décision.

## Transfers — fondations et première recette réelle

Images natives, bucket privé dédié et trois clés par consommateur ; aucun
remplacement des bases existantes. Sauvegarde privée préalable des métadonnées.
Adaptateur commun d'identité embarqué sous forme de wheel reproductible.
Correction du cookie CSRF propre à l'application et composition du calendrier
Celery pour conserver les synchronisations People/ST.

Analyse clamd des chunks déchiffrés, limite explicite compatible avec le scanner
partagé ; fichiers confidentiels conservés sans clé côté serveur. Conservation
des lignes de fichiers tant que la suppression S3 n'est pas confirmée.
Quotas ST utilisateur/organisation/instance sur les réservations chiffrées.

Recette réelle : standard 32 Mio, confidentiel vide et EICAR bloqué. Le premier
passage a corrigé le refus API des fichiers vides. Le test de session unique a
révélé un verrou PostgreSQL sur jointure nullable, corrigé par verrou du seul
transfert. Recette concurrente en cours. Métadonnées GET sans consommation,
POST explicite, cookie HttpOnly borné ; aucun prétendu accusé de sauvegarde.

### Sessions, quotas et invitations

Acquisition concurrente one-shot 204/410, GET neutre et reprise S3 validés.
Deux admissions concurrentes sous quota ST presque plein : 201/403 ; allocation
temporaire exacte retirée et fichier réservé purgé. Finalize conserve une
empreinte immuable et l'identité du brouillon ; rejeu réel sans doublon.
Une recette HTTP/S3/clamd réutilisable réside dans Apoze/transfers,
`scripts/qa/suite-transfers.py` ; les secrets restent en entrée privée.

Nouvelle invitation privée reçue réellement par Messages via le MTA LAN,
journal marqué sent. Extraction des seules mécaniques SMTP/journal partagées
avec Projects ; intentions Transfers distinctes, pas de clé de déchiffrement.
Panne logique du calendrier Celery diagnostiquée sur les âges de politique :
Django écrasait la première composition. Définition regroupée dans les settings,
rafraîchissement automatique désormais observé ; purge également reprogrammée.

L'UI affiche la capacité restante, les envois incertains et leur confirmation
avant renvoi. ST reçoit une exemption organisationnelle explicite pour les seuls
fichiers standard trop grands pour clamd, désactivée par défaut ; qualification
en cours. L'audit frontend a demandé deux mises à jour de dépendances, ajoutées
avant le prochain build. Les contrôles mobiles/Chat et échanges Drive restent à faire.

## TC3 — administration et parcours navigateur

- Rejeux add-file, complete-upload et finalize validés par la recette réelle.
- Administration Django réutilisée : consultation sans clés ni mutation brute,
  actions contrôlées, aperçu signé cinq minutes et révision du transfert.
- Prolongation propriétaire limitée aux durées natives depuis création ;
  aucune réouverture d’un lien clos ou d’une session one-shot engagée.
- Recette HTTPS : administrateur refusé avant attribution explicite, aperçu,
  changement de responsable puis retour, ancien aperçu refusé, ancien
  propriétaire exclu. Droit administrateur de recette retiré en fin de test.
- Navigateur Chromium réel : upload, scan clamd, téléchargement via service
  worker, comparaison exacte du contenu téléchargé réussie.
- Corrigé STATIC_ROOT incohérent dans les images de production.
- Corrigé statut HTTP du fallback SPA Caddy ; ressource statique absente
  conserve son 404. Validation HTTP du nouveau runtime encore à terminer.
- Le chantier global reste incomplet ; TC4 et la partie Matrix restent à faire.

## Suite de TC3 et début TC4 — 10 septembre 2026

- Administration native : aperçu signé, changement de responsable et retour,
  rejet d’un aperçu périmé et isolement de l’ancien propriétaire vérifiés.
- Chromium : upload standard, analyse, création du lien, téléchargement et
  contenu comparé. Catalogue et page destinataire inspectés visuellement.
- ST Web : politique de scan et budgets utilisateur/organisation réglés ;
  autorité affichée et propagation observées. Messages : remise SMTP réelle.
- Révocation : 4,2 s jusqu’au refus, URL déjà émise expirée à 40,3 s.
- Plafond réel de 20 Gio : échec initial dû aux 32 volumes du S3 partagé ;
  allocation native automatique avec réserve de 5 %, puis réussite en 165,3 s
  upload/download/digest/nettoyage. Budgets temporaires remis à 20 Go.
- TC4 : code de lecture privée par blocs, version observée, import serveur
  avec journal des parties, copie confidentielle navigateur, sélecteur natif
  multiple et export PDF explicite. Build réussi ; recette TC4 à poursuivre.
- Aucun commit/push d’implémentation à ce stade. Chat/mobile toujours à faire.

## TC1/TC5 — Chat isolé, 11 septembre 2026

- Jalon Transfers publié sur cinq forks Apoze ; SHA vérifiés dans publication.md.
- Déployé Synapse 1.160.0 / MAS 1.24.0 / Element Web 1.12.27 sur
  `chat-qa.invalid`, HTTPS LAN 8954/8955. Domaine permanent toujours attendu.
- Deux parcours OIDC natifs approuvés explicitement dans People ; localparts
  issus du UUID durable. Recherche par nom et invitation privée réussies.
- Échange chiffré aller-retour entre deux navigateurs : déchiffrement réel et
  type filaire `m.room.encrypted` vérifiés. Aucun contenu utilisateur utilisé.
- Retrait ST : anciens jeton et sync refusés en 22,6 s ; zéro session MAS
  OAuth/navigateur active pour la personne révoquée, après restauration du droit.
- Quotas natifs : deux uploads concurrents de 2 Mio sous plafond de 3 Mio,
  résultats 200/403 ; download/digest, purge et upload asynchrone vide réussis.
- Miniatures natives conservées : PNG synthétique de 91 294 octets facturé
  93 433 octets avec miniatures ; thumbnail authentifiée 200 et purge intégrale.
- Tampon HTTP dans tmpfs privé plafonné à 384 Mio, réservé à l'instance ;
  deux uploads simultanés maximum. Les refus ne libèrent pas prématurément
  une réservation dont la purge n'est pas confirmée.
- MAS : erreurs attente/refus/indisponibilité distinguées, build Rust réussi.
  Jeton machine réutilisé selon sa durée native, sans nouvelles sessions à
  chaque synchronisation. Aucune bibliothèque OAuth ou E2EE maison ajoutée.
- En cours : seconde connexion avec Authentik isolé, sauvegarde/récupération
  native des clés, puis gouvernance des groupes/salons et intégrations UI.
- Chat non publié et chantier non terminé : TC5 partiel, TC6–TC12 ouverts.

### TC5 — Bascule IdP et durcissement du journal (11 septembre)

Authentik a été démarré dans son environnement isolé préexistant. Un fournisseur
et un utilisateur réservés à cette recette ont été ajoutés. Le couple signé a
été approuvé explicitement dans People : même MXID, même salon, récupération
native du secret de sauvegarde et lecture de l’ancien message chiffré réussies.
Le journal MAS compare désormais UUID et empreinte issuer/sub. Sa migration
conservatrice termine les anciennes sessions ; le refus du jeton et l’absence
de sessions OAuth/navigateur actives ont été vérifiés via les API natives.
Les preuves et secrets de récupération restent privés. Nettoyage final requis.

Le dernier propriétaire actif ne peut pas abandonner un autre propriétaire
sans droit Chat. La règle native interdisant de rétrograder un propriétaire
égal a empêché le nettoyage immédiat de ce seul changement de recette : le
second utilisateur reste propriétaire du salon QA jusqu’au nettoyage final.

### TC5 — Salons gérés et révocation native

Recettes réelles passées : cumul groupe modérateur/direct membre ; retrait de
la seule appartenance People conservant le rôle membre ; suppression du dernier
droit provoquant leave natif et refus des messages/événements. Le cache initial
sync a été corrigé après détection d’une ancienne réponse de salon rejoint.
Le contrôle reproductible `contrib/apoze/check_room_revocation.py` vérifie les
lectures et les sync classique/sliding avec deux vrais jetons de recette.

Perte externe du dernier groupe responsable : ancien propriétaire bloqué,
reprise ordinaire refusée, administrateur du groupe People `suite-administrators`
accepté et propriétaire natif transféré. L’accès administrateur temporaire du
second compte a été retiré dans le finally de la recette. Intentions et fin de
reprise sont consignées dans le journal applicatif, sans clés de chiffrement.
Le salon QA appartient désormais au second compte ; le premier en est sorti.
Le groupe QA reste à nettoyer en fin de chantier (appartenances QA supprimées).

### TC6 — Préparation du build Web

Écran d’accès en composants natifs, avec FR/EN, en cours. L’installation des
packages a abouti ; le contrôle TypeScript a trouvé une incompatibilité du SDK
Matrix publié (`unknown` dans le bundle WASM), corrigée par patch pnpm versionné
et garde d’objet avant sérialisation. TypeScript passe après reconstruction des
packages locaux. La tentative d’export navigateur n’a pas été validée : le
navigateur s’était fermé sur pression mémoire. À reprendre après compilation.
Le build Docker natif a aussi révélé un ancien chemin de checkout SDK dans le
script de version ; résolution du package de l’application et version npm
ajoutées. Image complète en cours, aucune recette UI annoncée comme réussie.

## 2026-09-11 — Paramètres Element et responsabilité des médias

- Navigation réelle vers Paramètres du salon → Rôles : adoption avec le groupe
  People de recette et propriétaire direct enregistrée ; rôles et sauvegarde
  visibles dans les composants natifs. Capture privée `chat-room-access.png`.
- API d’administration des salons hors appartenance et réattribution des médias
  implémentées. Recette réelle via `chat_media_admin_real.py` : accès ordinaire
  refusé, quota insuffisant refusé, aperçu obsolète refusé, attribution atomique,
  ancien responsable privé de purge. Purge finale et restauration People/ST OK.
- Premier contrôle TypeScript dans un conteneur limité à 1600 MiB interrompu
  par cette limite (137). Il ne constitue pas une validation. Relance isolée
  après arrêt temporaire des seuls services Authentik de recette et du navigateur.

## 2026-09-11 — Recette administration Web et panne de purge

- Recherche d’un salon depuis les paramètres de compte, rôles et journal visibles.
- Réattribution réelle depuis l’UI vers « Recette Chat Deux », confirmation puis
  suppression via aperçu destructif. Le fichier synthétique est supprimé.
- Capture étroite révèle le `min-width: 580px` des paramètres natifs : correction
  responsive commune en construction. Ne pas valider avec le seul scrollWidth.
- Panne réelle limitée au dossier miniature d’un PNG de recette (permissions
  root, restaurées dans finally) : purge 503, quota intégral conservé, puis
  reprise 200 et quota initial retrouvé. Aucun fichier résiduel de ce test.
- Capacités Matrix v11 contrôlées via HTTP, création v12 refusée. Pusher non
  configuré et payload complet refusés ; pusher de recette natif enregistré
  avec données opaques. Révocation de ce pusher encore à vérifier.
- Authentik QA temporairement arrêté de nouveau pendant le build responsive ;
  il doit être redémarré après ce build. Keycloak et pile métier restent actifs.

## 2026-09-11 — Administration et révocation qualifiées

- Image responsive `13dd167124c710367b380b51de7852fb2f654431d2430840dc2468c6759a263d`
  déployée. À 520 px, panneau 392 px et actions 368 px, sans contenu coupé.
  Capture privée `chat-storage-responsive-fixed.png` inspectée visuellement.
- Pusher QA natif enregistré, payload complet refusé ; retrait ST réel du
  principal de recette principal : ancien token refusé et pusher natif supprimé
  en 11,1 s. Grant ST restauré, la session révoquée n’est pas réactivée.
- Réglage `apoze.qa` de passerelle et groupe administrateur temporaire retirés.
  Fichiers médias des recettes d’administration, navigateur et purge nettoyés.
- APNs/FCM ne sont pas validés par ce test : il qualifie l’inscription et la
  suppression natives. Aucune notification mobile réelle n’a été envoyée.
- Réapparition d’un OOM global à 04:45 : second Chrome de recette fermé.
  Correction d’exploitation I52 : builder BuildKit dédié et borné, qualification
  en cours. Les services métier ont conservé leur état démarré.

## TC6 — premiers échanges Chat/Drive, 11 septembre 2026

- Jalon administration publié : Synapse 22b88a19e, Element 0f91ba18b2,
  Drive b2f6efb5 ; identités complètes dans publication.md.
- Fenêtre `/sdk/chat` ajoutée au sélecteur Drive existant ; session Drive
  conservée, principal People comparé côté API, source privée et versionnée.
- Lecture réelle 32 Mio S3 et 32 Mio NAS : SHA-256 attendus ; export PDF Docs
  réussi ; absence de session et compte différent refusés. Aucune donnée créée.
- Menu natif d’ajout Element et action Enregistrer dans Drive en développement.
  Import réutilise les jobs/reprises/quota Drive ; E2EE reste dans le client.
- Lints ciblés réussis après corrections ; construction/recette UI à poursuivre.

### Recette navigateur TC6 (avant les derniers correctifs de présentation)

- Sélection Drive 32 Mio : données privées copiées dans la confirmation native
  d’Element. Upload local 36 octets et second upload 32 Mio réussis ; événements
  `m.room.encrypted` observés. Premier essai 32 Mio échoué avant publication,
  sans diagnostic enregistré à cet instant ; non reproduit au second essai.
- Retour natif Enregistrer dans Drive : job
  `c8ad3ba4-b764-474b-83d3-2e07ac05ab5f`, ressource
  `393ffc0e-ed97-42ab-bc1e-97b18b64d626`, 32 Mio, empreinte identique à la source.
  Fixture propre `tc-chat-return-real.txt`, à nettoyer en TC12.
- Médias QA à nettoyer : `lRMgICtsWMAaTZLJBRaTpleT` (36 octets),
  `eqMQzmMWIliQySZfFmkznZUz` (32 Mio). Suivi privé dans
  `tmp/transfers-chat-qa/chat-drive-roundtrip.json` ; aucune clé dans ce journal.
- Lien Docs sélectionné et confirmé, source toujours soumise aux droits Drive.
  Carte native Compound ajoutée après constat visuel d’une longue URL peu lisible.
- CORS autorise désormais explicitement `X-Suite-Principal` ; le vrai préflight
  navigateur puis les appels authentifiés ont été vérifiés.
- Docs frontend redémarré pour son cache ; HTTP 200 confirmé. Sa recompilation
  recrée un cache important. Authentik QA serveur/worker temporairement arrêtés
  pour libérer la mémoire de compilation : les restaurer après le build.

### TC6 — dernière image et contrôle de session

- Build final borné réussi ; image Web `75edd1dabef58674abf7cd89d54c69ee4a9fed663b10dc9da1b70866d2ef3bd1`
  déployée. Transfers, Chat et Authentik QA restaurés et sains ; builder arrêté.
- TypeScript complet, stylelint et lints ciblés passent. Aucun test complet
  supplémentaire lancé pour ces corrections localisées.
- Un contrôle artificiel remplaçait le token après un renouvellement tout en
  gardant son échéance future : le SDK le traite comme révoqué et déconnecte.
  Cette injection n'est pas une preuve d'expiration normale. Reconnexion native
  et récupération des clés effectuées ; recette avec expiration réelle en cours.
- Le point d'entrée Drive exige aussi l'activation de l'identité Suite ; aucun
  rapprochement sur le sujet de connexion d'une installation autonome.

### TC6 — échanges Drive et reprise réseau qualifiés

- Nouveau transport ArrayBuffer : copie 32 Mio puis upload natif réussi,
  événement chiffré ; identité du contenu déjà confirmée par le retour Drive.
- Dialogue de droits réel et lien Docs confirmé. Carte Compound lisible à
  520 px et sur grand écran ; bouton Ouvrir dans Drive natif, aucun aperçu
  serveur d'une URL privée. Correction du libellé null dans le dialogue commun.
- Le contrôle par arrêt du SDK était invalide (il ferme aussi son moteur Rust).
  Après rechargement natif, vraie coupure réseau du navigateur ; ancien token
  constaté expiré par HTTP 401. Retour réseau : OAuth token 200, upload 401,
  whoami 200 puis upload 200. L'envoi reprend sans modifier les états du SDK.
- Catalogue serveur : session native voit les neuf services ST avec leurs
  décisions différentes (Drive/Docs autorisés, Projects/Calendars refusés pour
  cette personne de recette). Anonyme 401, réponse privée sans cache. Menu Web
  à qualifier dans la prochaine image. Chat jetable demeure caché du catalogue
  général tant que son identité durable n'est pas choisie.
- TypeScript complet repassé après ajout du menu catalogue. Fichiers de recette
  conservés pour les derniers parcours ; inventaire privé actualisé dans
  `chat-drive-final-evidence.json` et `chat-drive-media-final.json`.

### TC6 — catalogue Web qualifié, 07:01 UTC

- Image `6afe80b5aa89d975d972b491a0c06f96ef48f7d7b70cc610e47a71df44e51a30`,
  construite depuis Element `eb8d8d677f` avec tous les services démarrés.
- Menu natif Applications de la suite, décisions ST respectées (Projects
  désactivé, Drive actif), dialogue lisible sur desktop/520 px. Échap ferme
  le catalogue ; activation Drive ouvre l'application puis ferme le dialogue.
- Carte Drive activée au clavier : bon chemin de ressource, aucun partage créé.
- Synapse/Element sains ; Transfers, Drive et Authentik QA toujours démarrés.
  Builder arrêté, navigateur revenu en ligne et moteur natif restauré.
- Cinq médias propres à la recette restent dans le salon ; manifeste complet
  `chat-drive-final-evidence.json`, nettoyage final TC12 toujours requis.

### TC5 — panne réelle d'autorité, 07:07 UTC

- URL ST changée uniquement dans la configuration privée du Synapse de recette,
  vers un port fermé ; aucun service People/ST métier arrêté. Snapshot conservé.
- Token natif renouvelé avant le test ; 200 jusqu'à expiration de la décision,
  puis 503 à 80 secondes. Aucune mutation d'échéance ou de projection en base.
- Configuration d'origine restaurée dans finally, Synapse redémarré et même
  token de nouveau admis (200). Trace privée `chat-authority-proof.json`.
- Le 502 initial pendant le redémarrage est distinct du 503 d'autorité attendu.
  Aucun test de panne encore actif.

## TC6 — Chat et Transfers, recette réelle du 11 septembre 2026

- Démarrage natif corrigé : import différé du sélecteur Forward évite le cycle
  des composants de timeline/audio ; le login natif se charge à nouveau.
- HTTPS/COOP/CSP : routes SDK seules avec opener, routes ordinaires isolées ;
  authentification native séparée et reprise après expiration réelle validées.
- Confidentiel 101 Mio : transfert `60edb249-ece8-4fd4-b610-b4f172c76a37`,
  carte native chiffrée et fichier téléchargé de même SHA-256 :
  `f1753a034bbd26e9458921b121c32d4750b9f7e5ef8adbbb337dcc96283ef40a`.
  Le fragment de clé ne figure pas dans le contenu Matrix transmis en clair.
- Retour dont le principal diffère ignoré par le receveur réel.
- Transfers vers Chat : `fa29cf64-b59a-4607-886c-9127dc508a72`, 36 octets ;
  sélection native au clavier, même instance du SDK et carte chiffrée.
- Pièce jointe Matrix vers Transfers : `cab93cb4-8633-41cd-9fa0-39d37a043fb3`,
  36 octets, retour confirmé au salon et carte chiffrée.
- Fixture créée avant correction du contrat finalisé, non partagée :
  `c9814da2-7be5-4d5f-9b9d-abaa0a4869cb`. Ces quatre transferts et les
  fichiers locaux de 101 Mio doivent être supprimés lors de TC12.
- Captures desktop : carte, relais et sélecteur lisibles. Le sélecteur à
  520 px débordait ; largeur bornée corrigée, validation finale en cours.

- Image finale Element :
  `09d15ff54e2ec1327f0406d510c2436a5b3052a0d85888f75d5d90bbce2df6f2`.
  Image finale Transfers frontend :
  `f8e16c3398b9a8f40fbf7633b7fb4a23ff14a1ad5379c771505df17da0441d20`.
- Correction I63 validée : sélecteur entièrement visible à 520 px ; annulation
  depuis Transfers ferme le sélecteur et, dans le sens Chat → Transfers,
  ferme la confirmation. Dans les deux cas, le formulaire reste ouvert.
- Aperçu natif « Forward message », bouton Send visible et Escape vérifiés
  à 520 px ; aucune régression de la sélection native conservée.
- TypeScript complet Element/Transfers, oxlint, stylelint, eslint ciblés et
  constructions des deux images réussis. Builder arrêté après déploiement.

## TC7 — Meet : première recette native (11 septembre 2026)

- Modèle et migration `0029_room_chat_context` appliqués sur Meet, après
  sauvegarde native de sa base/configuration. Services backend/worker/beat
  redémarrés sans arrêter les autres applications.
- Le compte synthétique principal a suivi le vrai SSO Meet. Son sujet
  pairwise a été vérifié séparément (signature, issuer/audience, nonce et
  UserInfo), puis explicitement associé dans People ; aucun repli email.
- Deux POST simultanés authentifiés créent la même salle
  `4d49f803-2ab3-45de-b22f-ea032ee4d829`, slug `bvt-qzpz-oue`.
  Le renommage conserve ce slug.
- Fermeture, anciennes demandes de création, réouverture par comparaison
  de génération puis rejeu après une seconde fermeture : PASS. La salle
  reste fermée au terme de ce contrôle.
- Lecture privée de contexte : responsable reconnu, non-membre exclu,
  mauvaise clé refusée et taille de lot excessive refusée. Bail <= 5 s.
- La recette SSO a révélé le détachement COOP de la fenêtre Meet : I69 retire
  la dépendance à `popup.closed`. Nouvelle image en construction ; invitation
  finale et appel/révocation actifs restent à qualifier avant publication TC7.
- Les grants Meet des deux comptes de recette sont suivis dans
  `tmp/transfers-chat-qa/meet-chat-grants.json` pour restauration au nettoyage.

Preuves privées : `meet-concurrent-create.private.log`,
`meet-lifecycle.private.log`, `chat-context-final-runtime.private.log`.

### TC7 — Appel et révocation réellement observés

- Invitation native confirmée dans Chat, carte affichée ; lecture d’état
  par le SDK Matrix. Route anonyme : 401 ; contexte machine public : 404.
- Deux comptes avec sessions Meet natives dans des contextes navigateur
  distincts : deux participants LiveKit actifs, chacun avec deux pistes.
  Chaque client rend deux vidéos 1280×720, `readyState=4`, pistes vivantes,
  et un élément audio distant. Médias synthétiques Chrome, pas de matériels
  physiques ni d’enregistrement.
- Retrait ST Chat : appel existant coupé à **27,2 s**, admission révoquée
  `authority_expired`. Liste Meet native 200, salle liée 403 et absente de la
  liste. Grant ST initial restauré dans le `finally` de la recette.
- Groupe People : ajout temporaire du second compte, invitation Matrix
  acceptée par son SDK natif authentifié, puis vrai préappel/connexion Meet.
  Le retrait du groupe expulse ce participant à **11,9 s** ; le responsable
  reste actif dans la même réunion. Groupe de recette revenu à l’état vide.
- Le second client Chat n’avait pas de récupération disponible : aucun reset
  de ses clés ni historique annoncé comme récupéré. L’acceptation d’invitation
  par l’API native teste l’appartenance, pas sa vérification cryptographique.
- Le responsable a refermé la salle après le contrôle. L’API de grants Meet
  a refusé la tentative d’ajout de droits locaux sur cette salle (400).
- Les captures ont montré une hiérarchie visuelle à améliorer : I71 emploie
  un titre et des boutons secondaires natifs. I73 corrige l’erreur API prise
  pour une attente d’admission dans le composant Lobby commun.

Preuves privées : `meet-chat-revocation.json`, `meet-group-revocation.json`,
`meet-two-video.private.log`, `meet-final-access-and-close.private.log`.
Le dernier ajustement Lobby/visuel est encore à contrôler avant publication.

### TC7 — Finition et compilation bornée

- La carte Meet est retrouvée après nouvelle connexion/récupération native :
  événement `$VZlRxysIVOqpY6rQqbk-rMk_-LDzd73RT_1CPmTlCW0`, type réseau
  `m.room.encrypted`, métadonnées absentes du contenu réseau en clair.
  L’état affiché provient de Meet et indique la fermeture effective.
- Panneau Meet desktop/520 px : titre natif, action principale de réouverture
  et retour secondaire ; aucun débordement. Le refus d’un non-membre affiche
  l’erreur et ne lance plus une attente d’admission fictive.
- Worker abaissé à 2,5 Gio : premier essai arrêté par le cgroup. Tas Node
  abaissé ensuite à 1024 Mio : compilation complète réussie, limites réelles
  vérifiées et paramètres persistés dans le nœud Buildx. Pas de nouvel OOM
  global après les incidents déjà consignés ; navigateurs fermés pendant
  les dernières compilations. Aucun service métier arrêté pour le build.
- Image finale Element avant publication :
  `e0fecad2bc638dcdacb497226ec30cdc4f45e52aebf8e1debc4caf144a34c7d5`.
- Images serveur qualifiées : Synapse
  `f38c60ebfb90027448754714ced787d80e3107a008c45a16c8b051a54d18bd3c`,
  Meet backend
  `70904cd32605e92ada45f49da10ef945ff7479446d22fa6cd634a0d1648dfbbc`,
  Meet proxy
  `b3555427acfaf149ed28f9b4e1162f49d6c5c5a15f50d855e9251d5a27d33e0f`.

- En-tête compact Element requalifié dans la vraie image à 520 px : bouton
  Meet sur une ligne, nom du salon visible avec troncature native, aucun
  débordement ; nom accessible complet conservé. Invitation chiffrée retrouvée
  et état fermé toujours correct. Captures finales relues.

## TC7 Calendars — recette en cours (11 septembre 2026)

- Branche de travail Calendars : `Apoze/calendars`
  `codex/chat-calendar-integration`, base `codex/suite-messages-calendars`.
- Migrations additives `0007_chat_event_handoff` et
  `0008_chat_write_receipt` appliquées. Sauvegardes privées préalables des
  DB Calendars/CalDAV et des paramètres : `tmp/transfers-chat-qa/`.
- Sujet OIDC par client Calendars vérifié (signature/issuer/audience/nonce
  et UserInfo), puis association explicite People du compte synthétique.
  Login natif et recette API/browser, aucun jeton ou preuve OIDC inventé.
- Refus 403 mauvais principal et salon absent. Deux sauvegardes natives
  concurrentes : 200/200, un seul UID `b235be9d-bf0c-44c0-8143-d1c633d87e94`.
  Invitation reçue dans la boîte du second compte et copie envoyée distincte.
  Modification native avec ETag : même UID.
- Second compte : groupe People réactivé pour ce lot, nouvelle connexion
  Matrix native et `joinRoom` natif. Ses clés n’ont pas été réinitialisées.
  Le groupe contient actuellement ce second membre (à restaurer vide).
- Formulaire UI desktop/520 px inspecté : participant autorisé prérempli,
  choix du calendrier, confirmation d’envoi. Aucun débordement horizontal.
- Création UI `c1742106-f20d-4023-b923-0f3198e67a49`, carte
  `$FDXgFkOgN5G77KmpBmmlW8wUtl3ZyZTg2C2yX7-9BmQ` confirmée
  `m.room.encrypted`. Ouverture native, titre modifié, réouverture avec
  le titre courant, suppression 204 et ancien lien 404. Rejeu de création
  après nouvelle connexion native : 200, événement toujours absent.
- Mail initial et annulation reçus. Le changement de titre seul n’avait
  pas envoyé de mise à jour : cause native identifiée, correction I78 en
  cours de construction/recette. Ne pas annoncer ce point qualifié encore.
- Build Element borné réussi via esbuild natif, un worker, Node 1024 Mio
  et Go 512 Mio. Image déployée de cette recette :
  `98eca21123e15a7e125f743e0c6785c40bbffba1c0049843733a841291654cfa`.
  Derniers ajustements date lisible/caption/erreurs restent à reconstruire.
- Rien de ce sous-lot Calendars n’est publié à cette étape. Les lots
  Projects/bot, mobile, restauration et nettoyage final restent à faire.

### Calendars — qualification finale

- Correction I78 qualifiée : titre et URL Meet actualisés reçus dans Messages,
  message `9a0fe690-4d81-449f-8dfe-75391c596902`. Sauvegarde identique :
  aucune ligne d’invitation supplémentaire. Aucune répétition SMTP induite.
- Retrait réel ST Calendars et salon non-membre : 403 ; règle d’origine
  restaurée dans un `finally`. Deux préparations simultanées : un seul UID.
- Check réel réutilisable : `Apoze/calendars/contrib/check_chat_handoff.py`.
  Utilise la session native privée et un UID de recette existant ; concurrence
  et séparation des comptes réussies. Aucun test du contenu des fichiers code.
- TypeScript Element complet, build Calendars natif et lints ciblés réussis.
  Minification finale : pic 2321 Mio, worker arrêté après le build.
- Dernière carte native relue à 520 px, date lisible et aucun débordement.
  APIs natives Matrix Calendar/Meet répondent après le redéploiement final.
- Images finales : Element
  `79e11beb312be963039be79c0fbc94311511c09df36434cbcf91163f1c9282ae`,
  Synapse `e604261fa403a1455a12fcd0ff0bfa2fca7fdb3ef26ffe4fa5a54231e0a2febf`,
  Calendars frontend
  `c411a5d86a2a11197eae1c794cbee1d8415e1332625d0bb9a939a6ea9aa3d8c2`,
  CalDAV `0816faa925bb01d71f753b5fa043d95d832b6ecbf58b243805d4cd2e30c611e2`.

## TC7 Projects — implémentation et recette en cours

- Base propre `Apoze/projects` `codex/suite-projects`, nouvelle branche
  `codex/chat-projects-integration`. Sauvegarde DB/configuration avant
  migration privée : `tmp/transfers-chat-qa/projects-before-chat*`.
- Identité OIDC Projects vérifiée séparément (signature, issuer, audience,
  nonce et UserInfo), association People approuvée du compte synthétique ;
  login natif réussi. Règles ST des deux comptes conservées avant modification
  dans `projects-chat-grants.json`.
- Projet/tableau/liste de recette créés via API natives, privilège admin
  temporaire restauré immédiatement. IDs dans `projects-chat-fixtures.json`.
- Première compilation CRA : OOM limité au cgroup 2,5 Gio. Correction I81 :
  tas Node 1536 Mio, minificateurs séquentiels, sourcemaps production retirées.
  Compilation native suivante réussie en 45,66 s, image déployée saine.
- Migration `20260911000100_suite_chat_handoff` appliquée : reçu atomique avec
  l’insertion native. Deux créations API simultanées et rejeu : même carte
  `1861746395682178303`, lien retour Chat présent. Mauvais principal et
  salon non-membre refusés. La recette navigateur et le bot restent à faire.
- Image Element en cours de construction, TypeScript complet et lints ciblés
  déjà réussis. Aucun code Projects de ce sous-lot publié pour le moment.

### Projects — parcours réels qualifiés

- API native : carte `1861746395682178303` supprimée ; rejeu 409
  `suite_chat_deleted` et GET 404, aucune recréation.
- Navigateur : SSO → sélecteur → tableau confirmé → carte chiffrée
  `$eJ9c6rRXsxZst4vk3Z4sYHekYD4zfx8SIIW_ze3nc1M`.
- Message source `$6oQNoIjVcdwExIrrxwvEhVhTG83v_EBosW6xOTjubuw` :
  confirmation explicite, texte prérempli, titre/texte/liste conservés après
  reload, création de carte native `1861748895193761028`, texte et lien
  retour source vérifiés par lecture Projects autorisée. Carte chiffrée
  `$eoX-hb_QRJneWB7XBN_aZBcxcCbp6mQTPrmQEj0T3pQ`.
- Formulaires et cartes relus à 520 px : kit natif, boutons cohérents et
  aucun débordement. Requête de recette initialement trop précoce avant
  réception du postMessage : la prélecture immédiate était vide ; la capture
  suivante et le contenu natif confirment la copie réelle, sans bug produit.
- Révocation ST Projects mesurée à 22,2 s, lecture native 401 ; règle
  restaurée. Un nouveau login natif a renouvelé la session QA arrivée à sa
  durée normale, sans altération de preuve d’authentification.
- Recherche de tâche qualifiée : le tableau sélectionné reste affiché quand
  son nom ne correspond pas au texte recherché dans les tâches.
- `Apoze/projects/contrib/check-chat.mjs` exécuté sur l’opération UI existante :
  concurrence et séparation des comptes réussies. Aucun scan de texte source.
- Bot, mobiles, restauration et nettoyage final restent à réaliser.

### TC7 bot — préparation du 11 septembre (non encore qualifié)

- Générateurs Projects/Chat et suivi Drive publiés : `b511ac14cfe928b9b7beda990d4dabc252fa3b21`.
- Bot technique People `21f2f754-e036-42b1-9a26-4ecf54085f00`, ST Chat
  autorisé, session personnelle MAS native/appareil fixe provisionnés. Aucun
  binding IdP ni rôle admin ; présence dans aucun salon à ce stade.
- Journal natif Projects réutilisé ; opt-in par utilisateur/tableau/salon,
  contrôle avant envoi, reçus stables et état incertain après une heure.
- Sources SDK JS examinées puis écartées (dépendances vulnérables) ; SDK Rust
  Matrix 0.18.0 conservant ses clés, pas de cryptographie réimplémentée.
- Code présent dans Projects/Element/Synapse/MAS/Drive, non encore publié.
  Compilation MAS en cours ; bot/Projects/Element puis recette à poursuivre.

## 12 septembre — reprise VM et bot Projects qualifié

- VM redémarrée : 47 Gio reconnus, 38 Gio disponibles au premier contrôle.
  Script LAN Drive et commande ST exécutés, Authentik QA existant redémarré ;
  les 70 conteneurs précédents sont démarrés, données et identités conservées.
- Images bot/Projects/Synapse/Element déployées, migration native appliquée.
  Bot technique accepté, session personnelle humaine refusée puis révoquée.
- Défaut du déclencheur Projects reproduit ; composition Compound native
  corrigée (I84). Menu clic/clavier et formulaire natif desktop/520 px validés.
- Commentaires Projects natifs, consentement UI, chiffrement/déchiffrement
  réel du navigateur courant ; aucun texte de commentaire dans la carte.
  Deux messages émis avant le nouveau device navigateur restent sans clés
  historiques pour ce device ; aucune réussite de récupération de ces deux
  messages annoncée. Les nouveaux messages sont déchiffrés normalement.
- Accusé volontairement perdu avant Projects : reçu
  `0c8c0abb-885f-4f80-8b4c-bed41822a4c4`, même événement après reprise native
  (`$_O2lGHjOWzv1-y6D_9cFn0UlWxNJreVijm4R315K0-A`), sans doublon.
  Proxy de faute arrêté, configuration d’origine restaurée et bot redémarré.
- Retrait UI du bot : commentaire suivant annulé sans envoi ; réactivation
  UI et nouvelle remise après rotation/redémarrage déchiffrée. Clés publiques
  inchangées. Ancien jeton refusé après cache natif de deux minutes.
- Contrôle API réel réexécutable ajouté dans Projects ; pas de test de
  contenu du code. Nettoyage des fixtures réservé à TC12.
- Nom Matrix durable toujours demandé, en attente ; aucune identité durable
  créée sous un nom provisoire. Suite du chantier et mobiles non terminés.

### 12 septembre — partage système mobile et façade Drive HTTPS

- Android : actions Drive et Transfers ajoutées au menu natif Compound.
  Builds 8 et 9 réussis, test `SuiteContentTest` et lint ciblé réussis.
- Drive : même explorateur et mêmes API privées S3/Provider. Préparation bornée
  existante, puis Web Share depuis un second clic. Aucun relais de fichier
  dans Synapse. Repli explicite vers fichier local ou lien copié.
- L'adresse LAN HTTP ne permettait pas Web Share : ajout de la façade
  `suite-drive-tls`, port 8445, certificat LAN Transfers réutilisé. Callback
  ajouté au client OIDC Drive existant ; anciens callbacks préservés.
- Authentification réelle HTTPS réussie ; identité correspondante 200,
  principal différent 403. Huit checks natifs API-origin passés, TypeScript,
  Ruff, lint ciblé et `nginx -t` réussis.
- Copie S3 `tc-private-source.txt`, 32 Mio, préparée depuis le navigateur,
  remise à l'extension native puis envoyée après choix du salon et confirmation.
  Salon durable : trois événements chiffrés, un média de 33 554 432 octets.
- Ancien transfert standard expiré refusé par la validation de partage.
  Nouveau transfert créé réellement depuis le formulaire, fichier de 39 octets :
  `fe8e794a-dc90-4490-9730-ee858c4498ef`. Son lien est envoyé par le partage natif.
  Salon : quatre événements chiffrés et aucun `m.room.message` en clair.
- Débordement réel des boutons à 393 px corrigé ; confirmation de copie
  séparée du navigateur de fichiers. Captures privées conservées dans
  `tmp/transfers-chat-qa/android-drive-copy-*.png` ; capture initiale tronquée
  et screenshot d'un onglet suspendu conservés comme diagnostics, pas preuves.
- Nouveau média et transfert à nettoyer en TC12. Aucun fichier métier supprimé.
- iOS : même entrée navigateur/extension native, code publié sans Xcode.
  Les retours Chat → Drive/Transfers et le message sélectionné → Projects
  restent du code à terminer ; ne pas confondre cette recette avec la clôture.

### I94 — Reprise Transfers — 12 septembre 2026

- Commandes start/stop/status/backup/restore/verify-restore/verify-authorities
  et cleanup-restore ajoutées, sans arrêt des services communs.
- Images exactes, dump et 6 objets S3 (211 812 855 octets) sauvegardés ;
  restauration sur réseau interne, sans ports, workers, mail ou droits hérités.
- Révision People invalidée avec la projection ; rechargement complet puis
  décisions ST actuelles pour 2 comptes. Aucun ancien usage publié vers ST.
- GET API d'un transfert finalisé et empreinte comparés réellement ; refus
  avant revalidation et après fermeture de la copie. Sessions restaurées : zéro.
- Scanner isolé conservé en échec fermé ; liens à accès unique déjà consommés
  non réouverts, invitations anciennes non rejouées. Ruff/compilation ciblés.
- Les copies de diagnostic précédentes ne constituent pas des succès ; seule
  la copie « qualified » prouve l'ensemble du parcours. Chantier global ouvert.

### I95 — Reprise Chat durable — 12 septembre 2026

- Snapshot `chat.zohenhl.ovh`, redémarrage des seuls services Chat.
- Restauration isolée : 13 événements, 1 salon, 1 média, 3 sauvegardes de clés
  et 16 fichiers médias/clés identiques ; aucune session restaurée active.
- Rotation cohérente des secrets internes MAS/Synapse et du client admin MAS.
- Revalidation de 4 comptes via les clés de lecture People/ST ; synchronisation
  native MAS, aucun ancien usage médias publié vers ST. Projection refermée.
- Le login technique de contrôle créait une nouvelle session machine ; clôture
  ajoutée, puis vérification finale des sessions rejouée avec succès.
- Cinq événements issus de la base restaurée déchiffrés par le SDK Matrix du
  client Android Web déjà vérifié. Média restauré de 32 Mio déchiffré par
  `matrix-encrypt-attachment`, empreinte identique à la source. Le premier
  export de recette omettait l'event_id stocké séparément : export rectifié,
  aucun contournement du chiffrement ni changement produit pour ce diagnostic.
- Aucun login humain synthétique ; aucun test d'un nouvel IdP sur cette copie.
  Les clés des clients restent nécessaires à la récupération des contenus E2EE.

Contrôle natif supplémentaire : réaction Android envoyée sur le message de
recette durable, événement reçu par Synapse, puis réaction retirée depuis le
même menu natif ; aucune réaction active de recette restante. Le contrôle ne
prétend pas avoir qualifié visuellement la pastille : elle n'est pas exposée
dans la capture d'arbre accessible utilisée. Aucun correctif UI spéculatif.

Prochaine action : terminer les retours de pièces jointes Element X vers
Drive/Transfers, en conservant le déchiffrement natif et les admissions des
applications cibles. Aucun transport mobile supplémentaire implémenté par
les travaux d'exploitation I94/I95. TC12 et le chantier global restent ouverts.


## I96 — Pièces jointes Element X vers Drive (en cours)

- API `mobile-intakes/<operation>/` limitée à un journal de copie existant,
  challenge SHA-256, preuve récente capturée après accord dans Drive ; droits
  et destination revalidés à chaque requête. Aucun jeton Matrix converti en
  session Drive. Reprise par blocs et publication S3/NAS natives réutilisées.
- Métadonnées reçues en fragment, retirées avant SSO et gardées localement
  pendant une heure. Sélecteur Drive existant, nom/destination et accord
  explicites ; retour dans l'application pour lancer la copie.
- Action native Android et iOS, déchiffrement SDK sur disque temporaire,
  progression, reprise avec le même journal, annulation et lien de résultat.
  Le processus mobile doit rester ouvert ; sa fermeture ne relance aucune
  copie automatiquement, et les réservations abandonnées expirent côté Drive.
- Premier essai Android : défaut découvert dans la découverte d'API, car le
  catalogue LAN donne le frontend 3000 alors que l'API est sur 8071. Correction
  par `mobile_url` HTTPS explicitement configurée dans le catalogue Chat,
  indépendante de l'URL web existante. Générateur et forks mobiles adaptés.
- Android builds 12, 13, 14 réussis ; build 14 installé. Synapse reconstruit
  et redémarré avec les URL mobiles privées LAN. iOS code seulement, aucune
  compilation annoncée. Recette réelle 32 Mio en cours, rien encore qualifié.
- Restent ensuite l'envoi natif vers Transfers (standard/confidentiel), les
  contrôles ciblés restants, le nettoyage TC12 et les publications finales.

- I96 recette Android réelle : SSO Drive, sélection du dossier, nom explicite,
  accord puis retour natif et copie terminée. Ressource
  `fb40f13a-c559-4a60-8a53-b55697d05f56`, espace S3 QA
  `0ecb2ec9-c1ac-4e11-9870-68a37154c968`, 33 554 432 octets,
  SHA-256 identique à la source NAS initiale ; spool serveur nettoyé.
  Capture `mobile-drive-approved.png` inspectée : boutons et formulaire lisibles.

## I97 — Pièces jointes Element X vers Transfers (en cours)

- Même clé de preuve privée par opération, brouillon/chiffrement/multipart
  Transfers existants ; aucune clé Matrix envoyée au serveur. Nouvelle clé AES
  de transfert gardée côté clients, mode standard/confidentiel choisi dans le
  formulaire existant. Grants supprimés à la publication.
- Android/iOS : SDK vers disque, AES-GCM natif par blocs avec AAD/IV/tag du
  format Transfers, S3 HTTPS borné, reprise depuis les parts S3 réelles,
  finalisation puis retour au formulaire existant. UI native contextuelle.
- Formulaire Transfers : autorisation explicite, import de la clé client en
  fragment retiré avant SSO, brouillon idempotent, observation de la fin du
  multipart natif puis finalisation standard/confidentielle habituelle.
- Android build 15 réussi et installé. Backend/frontend Transfers construits,
  migration 0015 appliquée, services métier redémarrés. Recette en cours.
  Dernières corrections de confidentialité/télémétrie et finalisation restent
  à rebâtir. Aucun lot I96/I97 publié à ce stade.

### I97 — Transfert mobile qualifié, modes standard et confidentiel

12 septembre 2026 : Android 17 installé, copie native de 32 Mio en deux parties
AES-GCM, autorisation par le vrai navigateur, retour et finalisation testés.
Standard `ff30b7cf-689a-47bd-80e2-e06fb6d83d5f` et confidentiel
`ab1625bc-d4b9-4e5f-a1bd-8ca259e9030c` : téléchargement réel, déchiffrement
et SHA-256 identiques au fichier NAS. Clé absente du serveur en confidentiel,
autorisations mobiles effacées à la finalisation. Aucun fichier clair envoyé
au serveur Chat par ce chemin. Le mode standard confie sa nouvelle clé à
Transfers pour le scan prévu par le produit.

Défaut trouvé et corrigé pendant la recette : les boutons d'autorisation et
retour d'un formulaire doivent déclarer `type="button"`. Le premier essai avait
créé un transfert sans titre ; il fait partie du nettoyage. Le formulaire
indique désormais quand terminer le transfert, sans demander un retour inutile.

Autre correction : l'échec S3 d'un fichier ne purge plus les autres fichiers du
brouillon. Contrôle HTTP réel : mauvais vérificateur refusé, accès à un autre
fichier refusé, ETag invalide rejeté et second fichier conservé. Brouillon vide
de ce contrôle supprimé via l'API. Le test ne fabrique aucun octet de données
métier. iOS reprend ce contrat ; fermer après un succès ne supprime pas le fichier
Transfers en attente de finalisation. Source iOS relue, non compilée sans Xcode.

### I98 — Mémoire du SDK mobile bornée avant téléchargement

Le SDK Rust 0.18 charge le média complet avant d'écrire son fichier temporaire :
la mention antérieure « SDK vers disque » ne signifiait donc pas un téléchargement
streaming. Correction : contrôle authentifié de la taille immuable du média
local auprès de Synapse, limite de 100 Mio, avant tout chargement par le SDK.
Le client vérifie ensuite la taille exacte. Aucune confiance dans la seule taille
déclarée par l'événement Matrix. Les copies sortantes restent par blocs de 25 Mio.

Android : build et parcours réels réussis avec ce contrôle. API réelle :
32 Mio / 200, média distant / 400, absent / 404, anonyme / 401. La façade HTTPS
et les listes natives d'endpoints ont été mises à jour. Cette limite suit le
plafond Chat actuel ; ce chemin mobile n'annonce pas la limite Transfers 20 Gio.
Lever cette borne demandera un SDK média réellement streaming. iOS utilise
le même contrôle, avec la réserve de compilation déjà autorisée.


## I99 — Nettoyage final du périmètre livré

12 septembre 2026 : vingt transferts de recette et tous les brouillons du
principal synthétique supprimés par les opérations natives ; purge S3 réelle.
Drive : aucun item de recette restant ; fichiers/dossier NAS retirés via le
provider, journaux de purge traités. Le backend NAS et ses authentifications
préexistants sont conservés. L'espace S3 de recette est désactivé, sans racine ;
ses références de quotas/jobs sont conservées pour audit, sans fichier vivant.

Docs, projet/tableau/cartes et événement CalDAV de recette supprimés ; réunion
Meet fermée et admissions révoquées. Dix-huit messages et treize blobs supprimés,
boîte mail préexistante conservée. Deux personnes suspendues, liens IdP et accès
retirés, groupe de recette supprimé ; quatorze règles ST temporaires retirées.
Deux utilisateurs Keycloak et le fournisseur/utilisateur Authentik exclusivement
créés pour cette recette supprimés ; configuration MAS synchronisée et redémarrée.
Les fiches Transfers/Chat sont désormais visibles dans le catalogue ST.

Dernier salon : refus natif de départ du dernier propriétaire observé et conservé.
L'API admin de purge a également refusé le jeton CLI sans preuve de session MAS ;
aucun contournement ajouté. Purge par le contrôleur de stockage natif Synapse,
pendant une courte maintenance de Synapse et du bot seuls, puis redémarrage.
Contrôle PostgreSQL : zéro salon, événement et média local dans cette instance
neuve, qui ne contenait que la recette. Média de 32 Mio préalablement supprimé
par l'API authentifiée ; usage natif nul. Anciennes sessions MAS révoquées.

Le profil chat-qa, ses conteneurs/volumes, bases et rôles séparés sont supprimés.
Les environnements de restauration ont déjà été retirés après I94/I95. Les
archives de sauvegarde restent privées selon la rétention d'exploitation ;
elles contiennent l'état historique de recette, pas des services actifs.
Aucune suppression des données métier, comptes administrateur ou Grist.

## I100 — Invalidation des autorisations mobiles après restauration

Le nouveau champ Transfers mobile_intake doit être effacé à la restauration,
y compris sur un fichier chargé mais dont le brouillon n'est pas finalisé.
Le helper de restauration invalide désormais tous ces grants ; son contrôle
verify refuse aussi leur présence. Contrôle réel dans PostgreSQL : fichiers
vide en attente et chargé, appel au helper natif, deux grants supprimés ;
transaction annulée, aucun objet S3 écrit, aucune session vivante modifiée.
Le contrôle réutilisable verify conserve cette garantie sans nouveau harnais.

Ruff ciblé réussi. Recettes I96/I97 closes : Android 32 Mio vers Drive S3,
Transfers standard et confidentiel, empreintes identiques ; refus des mauvais
vérificateurs et d'un autre fichier. L'échec multipart conserve les autres
fichiers du brouillon. Android build 18 réussi (17 testé, 18 ne change que les
prévisualisations UI). iOS source livré et relu, non compilé. Les anciennes
mentions « en cours » ci-dessus sont des observations historiques, remplacées
par le rapport final et l'état courant.

Compatibilité I100 : les snapshots antérieurs à la migration mobile exécutent
leur image épinglée sans ce champ. Le helper détecte cette capacité du modèle ;
il continue à invalider sessions/acteurs sans exiger une migration de la
sauvegarde historique. Sur le modèle courant, les deux grants sont bien effacés
et le contrôle PostgreSQL avec rollback a été rejoué après cette adaptation.
