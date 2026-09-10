# Projects — journal d’exécution

## 2026-09-10 — P0

- Plan entièrement relu, contrats identité et stockage consultés.
- Pile existante active ; aucun Projects ni données Projects existants.
- Port 8940 libre ; 66 Gio libres avant construction.
- Drive part de `0db5237b` sur `codex/projects-integration`, pas du main ancien.
- Fork https://github.com/Apoze/projects créé ; checkout `/root/Apoze/projects`
  sur `codex/suite-projects`, base `7858be2a22ca87cacd6ff5d67a149aa06cb11b6b`.
- Amont https://github.com/suitenumerique/projects.git en lecture seule,
  push désactivé. Aucun service existant arrêté.
- People contient des travaux antérieurs non commités, préservés.
- P1 en cours : construction native et socle de configuration persistante.

## P1/P2 — socle natif en qualification

- Fork, DB `projects`, consommateur People, service ST et client OIDC créés.
  Catalogue masqué ; une seule autorisation de recette, pas d’ouverture globale.
- Image Node 22.21.1 construite avec les lockfiles ; migrations réelles réussies.
  Seeds désactivés en mode suite. Montage de code provisoire pour l’itération,
  à retirer au build de livraison.
- Synchronisation réelle : 23 comptes People projetés, aucun rapprochement par
  email ; bornes ST indépendantes, transactions PostgreSQL et staging paginé.
- Correction Knex : conserver le wildcard `*` lors du snake_case des colonnes.
  Cause de l’erreur SQL 42601 reproduite sur le premier échange réel.
- Correction callback : transmettre le paramètre OIDC `iss` réellement reçu ;
  Keycloak le requiert selon sa discovery. Ne pas inventer ce paramètre.
- Navigateur Chromium : connexion réelle Keycloak → demande People en attente ;
  approbation via formulaire d’administration People ; refus ST explicite ;
  autorisation ciblée → session Projects et page d’accueil. Même ID natif.
- Profil natif sans email utilisé pendant ce parcours.
- Bouton de suite issu du kit Cunningham, messages d’attente/refus visibles.
- Catalogue, logout commun et gardes des tableaux publics ajoutés ; qualification
  finale de ces ajouts en cours, pas encore déclarée réussie.
- Deux contrôles Mocha ciblés passent (preuves/leases ; pagination/purge S3).
  Lint ciblé passe avant les derniers ajouts ; à repasser sur le diff final.
- Aucun autre service arrêté. People antérieur préservé.

Reste obligatoire : groupes/provenance/UI, stockage privé et antivirus/quotas,
transferts Drive/Docs, notifications Messages, opérations/restauration, second
IdP isolé, nettoyage et publication. Ce socle n’est pas la livraison du plan.

### Droits et révocation — preuve réelle

- `tmp/projects-qa/groups.cjs` : cumul direct/groupe, retrait de groupe conservant
  le droit direct, puis nettoyage des attributions de recette : passent.
- `tmp/projects-qa/revocation.cjs` : connexion Socket.IO authentifiée ouverte,
  retrait ST, fermeture socket et HTTP 401 en **38,645 secondes** ; règle ST
  restaurée dans le `finally`.
- Cause racine corrigée : watcher natif employait les collections Socket.IO 2
  alors que le serveur utilise Socket.IO 4 (Map/Set). Aucun nouveau transport.
- P3 n’est pas clos : UI/provenance/pagination et autres parcours restent ouverts.

### Stockage — démarrage P4

- ST : branche `codex/projects-integration` du fork Apoze/st-deploycenter ;
  extension du résolveur et des formulaires existants pour `projects_storage`.
- SeaweedFS : vérifier le rechargement de l’identité dédiée sans arrêt de Docs.
  Référence primaire : https://github.com/seaweedfs/seaweedfs/blob/master/weed/s3api/auth_credentials.go
- Inspection duplication : le contrôleur natif vérifiait le projet destination
  mais pas l’accès au tableau source ; contrôle source ajouté avant copie.

### P4 — fichiers privés, preuve intermédiaire

- Bucket Projects dédié, credentials propres sur le S3 suite 4.46, réseau privé.
  Identité conservée à chaque préparation de la suite. Aucun secret suivi.
- Cause racine S3 : `volume.max=6` était entièrement affecté à Docs ; passage à
  32 emplacements de 1 GiB, même volume persistant/image. Redémarrage du seul
  service `docs-s3` pour appliquer sa capacité ; tous les produits conservés.
  Correction dans Apoze/docs, branche `codex/projects-storage-capacity`.
- Le volume temporaire Docker était créé avec UID root : ownership corrigé
  pour le volume de recette ; l’image crée désormais `.tmp/uploads` avec UID 1000.
- `tmp/projects-qa/files.cjs` : envoi HTTP 200, répétition de la même clé donnant
  le même ID, téléchargement avec empreinte identique, accès anonyme 401, EICAR
  refusé 422. Pièce et carte conservées pour la suite de la recette.
- Contrôle additionnel : SeaweedFS normalisait les clés natives commençant par
  `/`. Le profil suite emploie maintenant des clés relatives, y compris dans le
  journal de réservations, pour que la purge exacte retrouve ses objets.
- Réservation SQL avant chaque écriture, publication/journal atomiques via trigger,
  contrôle People/ST/ACL et plafonds à publication ; collecte bornée des objets
  sans attache après délai de grâce. Réservations jamais libérées sur simple échec.
- ST : test ciblé `test_entitlements_projects.py` passe (1). L’ancien module
  `test_entitlements_messages.py` a des assertions de réponses complètes antérieures
  au contrat `storage_policy` déjà présent avant ce chantier (18 divergences) ;
  ne pas présenter ce module comme passant. Utiliser DJANGO_CONFIGURATION=Test
  et désactiver l’identité uniquement dans ces tests d’entitlements isolés.
- UI en cours : provenance paginée, stockage/responsable dans paramètres projet,
  refus d’upload explicite. Rebuild et contrôle visuel final encore requis.
- Reste P4 : qualifier concurrence/purge/copies, migration responsable et reprise,
  statut/collecte exploitables ; P5–P9 restent ouverts.

### P5 — échanges réels S3/NAS et correction du sélecteur

- `drive-exchange.cjs` : enregistrement S3/Test1 et SMB, rejeu sans nouvelle
  ressource, lien, copie vers Projects et SHA-256 identique : **PASS**.
- Le double `ModalProvider` natif cachait la carte aux lecteurs d'écran.
  Retrait du doublon dans Root ; bouton retrouvé par rôle, aucun ancêtre caché.
- Premier login Drive : montage des requêtes avant auth puis allowlist locale
  configurée avec des URL au lieu de host:port. Gate du sélecteur partagé et
  correction de la configuration LAN/E2E ; retour réel `/sdk/projects` confirmé.
- Copie navigateur complète et Docs PDF restent à terminer.

### P2/P4/P6 — compléments en cours

- Brouillon commentaire conservé dans sessionStorage par utilisateur/carte,
  effacé seulement sur confirmation ; retour à la carte après login, transactions
  OIDC multi-onglets conservées et bornées. Code à qualifier dans le navigateur.
- Recherche membres compatible avec email absent. Vue de statut et reprise des
  notifications dans les paramètres du profil, avec confirmation d'un doublon
  possible uniquement pour les remises SMTP incertaines.
- Notifications natives Projects journalisées ; machine Projects limitée à une
  intention fixe auprès de Messages, qui résout la boîte principale People et
  utilise son transport SMTP LAN. Ni adresse libre, ni HTML/contenu de carte.
  Messages conserve sa décision SMTP par UUID pour rendre les retries HTTP sûrs.
- Affectation native réelle -> notification -> SMTP -> Message reçu : **1 mail**.
  Le premier essai a révélé EMAIL_HOST non chargé dans la configuration Suite
  Messages (localhost au lieu de mta-in) ; cause corrigée, reprise envoyée.
- Une boîte et un grant ST temporaires sont enregistrés dans
  `tmp/projects-qa/mail-fixture.json`. Le premier run les a créés ; les relances
  get_or_create ont remplacé les flags `created` par false : ces objets sont
  bien des fixtures de ce chantier et devront être nettoyés.
- Revue des suppressions natives : archiveOne ne cascade pas les descendants.
  La collecte retire désormais les références de pièces jointes suite dont le
  chemin parent a disparu avant de purger les objets ; qualification à finir.
- Duplication de tableau séquentielle, état privé en cours, nettoyage en cas
  d'arrêt/échec, copie des liens ; déplacement de carte entre projets reprend
  la facturation sous contrainte SQL. Code et recette à finaliser.
- Migrations 008–010 ajoutées. L'opérateur PostgreSQL `?&` était interprété comme
  paramètre Knex : remplacé par jsonb_exists_all. Service revenu healthy sur les
  sources d'itération. Reconstruction finale encore nécessaire.
- `projects_operations.py` et `db/suite-objects.js` ajoutés pour backup streaming
  DB/bucket/image/config et restauration sans réseau extérieur/session/mail.
  Première archive produite avec l'image précédant le correctif migration :
  marquée **usable=false**, explicitement refusée à la restauration. Faire une
  nouvelle sauvegarde après qualification de l'image correcte.

Le chantier reste **NON LIVRÉ** : tests consolidés, Docs, restauration, IdP
isolé, nettoyage, documentation et publication restent à exécuter.


### P2–P8 — recette consolidée du 10 septembre

- Popup réel Projects → Drive → copie : PASS ; S3/Test1 et SMB enregistrés,
  relus, copiés et rejoués avec le même ID et SHA. Docs privé : lien et PDF PASS.
- Le sélecteur Messages factorisé fonctionne toujours : copie réelle depuis
  S3 ajoutée à un brouillon Messages ; boîte temporaire commune à la recette.
- Création et édition de commentaire : brouillon conservé après reconnexion,
  retour à la carte et effacement uniquement sur ACK natif WebSocket : PASS.
- UI : doubles providers retirés, largeur mobile et retour à la ligne des
  actions corrigés ; captures inspectées. Groupes ajoutés/retirés via le Web,
  panneau quotas/propriétaire, statut du profil et récupération d'un projet
  orphelin via le Web : PASS. Pas de refonte de l'explorateur.
- Natif : checklist cochée, échéance/minuteur, copie de tableau avec fichiers
  privés et liens, export CSV téléchargé : PASS. Deux utilisateurs réels
  observent la même carte en temps réel ; lecteur refusé en écriture (403),
  fichier privé lisible puis refusé après retrait du grant.
- Déplacement inter-projets : quota projet 1 octet -> 409 ; plafond retiré ->
  déplacement aller/retour avec pièces jointes conservées. ST zéro signifie
  illimité : le premier essai à zéro n'était pas une anomalie d'admission.
- Mail : panne ciblée de la clé Projects, état retry, rétablissement -> sent ;
  un seul Message pour cet UUID, même après rejeu de l'intention. Retrait du
  membre avant reprise -> cancelled sans émission. Appel machine invalide refusé.
- Backup correct puis restauration interne : sessions/transactions supprimées,
  comptes et envois anciens invalidés ; carte/commentaires et fichier SHA relus
  après décisions People/ST actuelles. Nouvelle commande verify-authorities
  qualifiée sur isolat sans ports : un accès retiré après backup reste refusé.
- Keycloak → Authentik → Keycloak dans la restauration QA : mêmes principal,
  user, cartes et fichiers ; ancien JWT Authentik refusé au retour. Compte natif
  sans email. Le sujet Keycloak de recette est opaque (mapper historique),
  donc association sur le sub réellement vérifié, jamais sur le PK interne.
  Le Consumer People QA est distinct ; l'IdP LAN n'a pas changé.
- Contrôles : deux tests Mocha ciblés, test ST Projects, linters ciblés et
  build image ; pas de suite E2E générale. Nettoyage/publication P9 en cours.

- ClamAV indisponible (réseau Projects seul détaché temporairement) : upload
  refusé 422 `suite_scan_unavailable`, réseau restauré dans finally, santé prête.
- Collision de nom Drive avec une nouvelle clé : état failed sans écrasement.
- Nettoyage en cours : deux projets de recette supprimés via API, 18 objets
  marqués deleted par le collecteur natif, zéro écriture en attente. Les seules
  métadonnées orphelines des IDs de recette ont ensuite été retirées.

- Dernière revue de session : après révocation globale, l’ancien SSO IdP
  pouvait encore présenter un auth_time antérieur à l’epoch People. Projects
  demande maintenant une authentification fraîche via OIDC max_age=0 après
  logout explicite ou détection de cet ancien contexte, sans dépendance IdP.

- Déconnexion/reconnexion réelle après l’epoch People : PASS. Le formulaire
  Keycloak peut ne demander que le mot de passe du compte déjà sélectionné ;
  ce comportement natif était la cause du premier timeout de la recette.
- Catalogue Drive → Projects visible. Nettoyage natif : documents Docs purgés,
  objet S3 retiré, NAS retiré, bucket Projects vide ; boîte et quatre mails de
  recette supprimés, blob de copie sans référence collecté.
- Credentials inspectés sans sortie de valeur : aucun secret local dans les
  fichiers candidats. Les cinq dépôts ont passé les contrôles ciblés ;
  commits Projects, ST, Docs, Messages créés. Drive et pushes en clôture.

### P9 — livraison

- Les cinq forks Apoze reçoivent les modifications sur leurs branches de
  chantier, avec gitlint, contrôles ciblés et vérification SHA distante.
- Aucun secret, session navigateur, dump ou fichier de recette dans Git.
- Backup opérationnel propre conservé ; anciennes archives de recette et
  dossiers des restaurations supprimés après leur qualification.
- Administrateur Projects initial et règle du groupe Membres de la suite
  conservés comme configuration opérationnelle ; quotas de recette retirés.
- Le journal historique reste daté : ses mentions « en cours » décrivent les
  étapes intermédiaires. L’état final est celui de current-status.md.
