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
