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
