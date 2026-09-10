# Messages et Calendars — journal d'exécution

Plan canonique : [intégration LAN](../../../docs/plans/suite/messages-calendars-integration-plan.md).
Début : 10 septembre 2026. État : **en cours, non livré**.

## MC0 / MC1 — préparation

- Pile initiale : 43 conteneurs en cours d'exécution, dont les 16 services
  Drive. Espace disponible : 103 Go ; mémoire disponible : environ 11 Go.
- Branche Drive : `codex/messages-calendars-integration`. Modifications
  préexistantes conservées et inventoriées ; aucun commit ni nettoyage.
- Baseline privée : `data/messages-calendars-baseline/20260910T054257Z` :
  états et diffs des cinq dépôts, conteneurs, dumps People/ST et configurations.
- Forks créés sur instruction du propriétaire :
  `https://github.com/Apoze/calendars` et `https://github.com/Apoze/messages`.
  Checkouts : `/root/Apoze/calendars`, `/root/Apoze/messages`.
  `origin` de chaque checkout : URL HTTPS de son fork Apoze (fetch/push).
  `upstream` : `https://github.com/suitenumerique/calendars.git` et
  `https://github.com/suitenumerique/messages.git`, fetch-only, push désactivé.
  Branches locales : `codex/suite-messages-calendars`. Aucune modification
  locale publiée, aucune PR créée et aucune écriture vers les amonts.
- Réutilisation retenue : PostgreSQL 16 existant avec bases/rôles distincts ;
  Redis isolé pour le nouvel ensemble ; S3 privé distinct sur service compatible.
- Domaine mail : `mail.apoze.test`. Interfaces prévues Messages `:8900`,
  Calendars `:8930`, sous réserve du contrôle de disponibilité avant démarrage.

## MC2 / MC3 — socle en cours

- Images natives construites dans les deux forks ; dépendance commune identité
  0.1.2. Calendars utilise `/venv`, hors du bind mount de développement.
- Projet Docker `suite-mail` isolé : deux API, deux interfaces, workers,
  synchronisation, Redis, OpenSearch, S3, CalDAV et MTA privé démarrés.
- Migrations Django des deux applications et schéma SabreDAV appliqués.
  Correction du réseau PostgreSQL (`suite-local_default`) et initialisation
  explicite du schéma DAV ; le script SQL doit échouer dès une erreur.
- Interfaces LAN : Messages `http://192.168.10.123:8900`, Calendars `:8930`.
  Domaine `mail.apoze.test`. Garde d'envoi LAN ajoutée au transport Messages.
- Consommateurs People, politiques ST et clients OIDC enregistrés. Les entrées
  ST restent masquées jusqu'à qualification ; aucune application existante arrêtée.
- Synchronisation réelle People/ST : 23 comptes dans chaque application.
  Preuves OIDC signées vérifiées dans Chromium pour deux comptes et trois
  clients (People, Messages, Calendars), puis quatre associations explicites.
  Aucune association par correspondance d'adresse e-mail.
- Connexion réelle du compte de test existant : `/users/me/` répond 200 dans
  Messages et Calendars. `can_access=true` dans Calendars.
- Calendars : raccordement initial des principaux personnels aux UUID People,
  suppression de la création implicite d'identités par `mailto:`, adaptation
  du client Web, vérification CSRF des écritures DAV à cookie et contrôle
  d'accès ST sur toutes les opérations DAV. Canaux globaux désactivés en mode
  suite en attendant le raccordement des délégations bornées.
- Vérifications exécutées : checks Django des deux apps et syntaxe PHP des
  trois classes modifiées. Après initialisation SQL, chargement réel de
  l'interface agenda sans les erreurs DAV 500 initiales.

## MC4 / MC5 / MC6 — preuves intermédiaires

- Deux boîtes de recette ont été créées par association explicite avec les
  principaux People existants. Les deux comptes se connectent réellement aux
  deux interfaces ; aucun compte n'a été associé à partir d'un email.
- Envoi réel depuis le composeur Web, avec petite pièce jointe : émission et
  réception vérifiées. Seconde livraison avec worker arrêté : réservation
  entrante durable, état en attente, puis réception confirmée après reprise.
  La migration Messages 0036 lie le reçu à la livraison entrante effective.
- Correction du sel de chiffrement manquant et des permissions du fichier
  de configuration S3 lu par l'utilisateur du conteneur. Buckets créés.
  Un seul ordonnanceur Celery : le worker natif inclut déjà Beat.
- Création d'un agenda personnel et d'agendas de boîte depuis les interfaces
  authentifiées. La création sur HTTP LAN exige une alternative à
  `crypto.randomUUID`, disponible seulement en contexte sécurisé.
- Calendriers et partages utilisent les UUID People/boîte ; le chemin retourné
  est celui de l'instance du destinataire, pas celui du propriétaire.
  Un utilisateur sans claim email peut utiliser son agenda de boîte.
- Invitation réelle depuis un agenda de boîte : PUT/édition DAV puis un mail
  émis et un mail reçu dans Messages. Correction du détecteur de principal
  MAILBOX SabreDAV qui cherchait encore une URI fondée sur l'email.
- Migration Messages 0037 : intention d'envoi liée à l'acteur, son époque
  d'authentification et ses droits actuels, revérifiés dans les workers.
  Échange Calendars → Messages lié à une preuve utilisateur ; la clé seule
  ne donne pas le droit d'envoyer comme une boîte. Déduplication des retries
  de soumission par Message-ID et empreinte de l'enveloppe/contenu.
- Projection périodique des partages Messages avec échéance héritée des
  contrôles People/ST, sans prolonger leur validité. Les principaux, lectures
  et invitations DAV masquent les partages expirés. Qualification négative
  de la révocation encore à exécuter. Partage manuel des agendas de boîte
  interdit en mode suite : Messages conserve l'autorité.
- Canal inverse Messages → Calendars créé avec scopes lecture/écriture
  d'événements, UUID d'acteur et preuve vérifiée. Recette RSVP encore en cours.
  Tokens CalDAV/ICS personnels liés à l'époque d'authentification ; leur
  révocation après changement d'IdP reste à qualifier.
- Catalogue et déconnexion commune ajoutés aux deux interfaces ; builds
  frontend passés. Recette transversale pas encore terminée.
- Les fixtures, téléchargements et captures privés restent sous
  `tmp/messages-calendars-qa/`. Leur nettoyage est obligatoire avant clôture.

## Reste du chantier

MC2/MC3/MC5 sont partiels, pas validés comme lots complets. Restent notamment
les groupes et budgets/quotas, qualification du transport complet et des
invitations/réponses/annulations, pièces jointes Drive/Docs, Meet réel,
recette catalogue/navigation, opérations/restauration, preuve Authentik et
nettoyage de recette. Les associations de boîtes/UUID fonctionnent ; elles
ne suffisent pas à déclarer les lots fonctionnels complets.
Ne pas assimiler les connexions ou les interfaces visibles à une intégration
livrée. WAN et Grist restent hors exécution.

## Qualification réelle complémentaire — 10 septembre

- RSVP depuis Messages : liste des agendas 200, action 200, tâche réussie ;
  le participant apparaît ACCEPTED dans l'événement de l'organisateur.
- Lien RSVP public : GET sans aucune mutation ; clic explicite accepté ;
  lien d'une séquence précédente refusé 409 après modification de l'événement.
- Messages migration 0038 : droits People et directs séparés, projection dans
  les ACL natives. Retrait réel d'un membre People : Sender hérité supprimé,
  Viewer direct conservé, tentative d'envoi depuis cette boîte refusée 403.
- Paquet commun 0.1.3 : signal transactionnel après import des membres,
  nécessaire car le bulk import ne déclenche pas m2m_changed ; le chemin
  sans changement de révision réconcilie également les droits.
- Interface Messages : ajout/édition/retrait de groupes People ; modification
  de rôle effectuée dans Chromium. Correction du résolveur de configuration
  qui omettait SUITE_IDENTITY_ENABLED et masquait cette interface.
- Client CalDAV Basic réel : lecture 200, modification d'une invitation 204,
  puis suppression du canal et lecture refusée 401. Le champ chiffré natif
  transforme les scalaires en chaînes : comparaison d'époque normalisée.
  La délégation d'une invitation issue d'un canal vérifié est bornée par
  l'échéance People/ST ; aucun header fourni par le client n'est repris.
- Les identifiants affichés pour les clients CalDAV utilisent désormais le
  principal durable ; build frontend à requalifier. Travail Meet commencé
  sur la branche locale codex/messages-calendars-sdk d'Apoze/meet, sans push.

Ces preuves ne clôturent aucun des lots encore incomplets : quotas, groupes
sur agendas personnels, SMTP/filtrage, Drive/Docs, exploitation, second IdP et
nettoyage restent notamment à exécuter.

## Attribution personnelle et Meet — 10 septembre

- Migration Messages 0039 appliquée : propriétaire d'allocation explicite et
  boîte principale unique par personne. Les deux boîtes de recette sont
  attribuées aux personnes People déjà vérifiées. Aucun nouveau compte IdP.
- Correction du formulaire/admin API de création personnelle : sélection
  d'une personne People ; plus de get_or_create par email en mode suite.
  La recherche permet aussi les personnes sans email et sans boîte préalable.
  Build frontend réussi, recette de création web encore à exécuter.
- Calendars migration 0004 : contact mail applicatif séparé du profil IdP,
  projeté depuis la boîte principale avec échéance de la source Messages.
  Envoi des agendas personnels par Messages en mode suite ; qualification
  de ce parcours encore à faire.
- Meet SDK : contrôle de l'origine réelle et de la fenêtre popup ; retour au
  seul parent ayant intégré le bouton, corrélation CSPRNG et format vérifié.
  Le middleware core-only bloquait creation-callback ; ce blocage a été retiré
  pour le parcours autorisé, sans activer les fonctions expérimentales.
- Calendars utilise le SDK natif en iframe, contrôle origine/fenêtre/délai,
  et construit le lien sur l'origine configurée. Test Chromium : création,
  retour du lien, fermeture popup ; vérification DB : salle réelle, accès
  restricted, un propriétaire. Quelques essais antérieurs ont également
  créé des salles : les recenser et nettoyer en fin de recette.
- Images Meet backend/frontend reconstruites et services ciblés redémarrés.
  Aucun push de https://github.com/Apoze/meet.git et aucun changement vers
  https://github.com/suitenumerique/meet.git (fetch-only).

## Qualification complémentaire et préparation quotas

- Création d'une boîte personnelle supplémentaire dans Chromium : 201,
  propriétaire People sélectionné, aucune association par email. Fixture
  `mc-allocation-temp` à nettoyer. Le propriétaire d'allocation est indépendant
  des lecteurs de boîte ; l'unicité de la boîte principale est imposée en base.
- Invitation depuis l'agenda personnel : PUT 201, deux copies Messages
  (émetteur/destinataire), intention d'envoi liée à l'acteur, reçu de livraison
  confirmé. La boîte principale fournit l'adresse, sans changer le profil IdP.
- Deuxième recette Meet depuis Calendars : succès, sans script de diagnostic.
  La fenêtre revient avec la salle créée puis se ferme. L'interface Calendar
  n'a pas encore enregistré un événement incluant ce lien (reste à qualifier).
- Syntaxe PHP et checks Django passent. Linters ciblés Messages/Calendars
  passent ; migrations alignées avec les modèles. Isolation des principaux
  DAV par organisation renforcée ; régression DAV de ce changement à refaire.
- ST : extraction de l'exposition de politique de stockage déjà utilisée par
  Drive ; Messages réutilise la même forme (instance, organisation, compte,
  ressources, révision). Un override de boîte ne peut pas dépasser le budget
  d'organisation. Contrôle d'admission atomique dans Messages **pas encore
  implémenté** : cette préparation ST ne vaut pas une gestion des quotas livrée.

### Point de reprise quotas

Le contrôle de quotas Messages reste à coder. Tous les chemins d'écriture
(MIME/draft, réservations MailboxBlob, pièces jointes, file InboundMessage,
ThreadAccess et templates) doivent participer à la même transaction. Une
vérification au seul upload ne couvre ni import ni livraison concurrente.
Préférer un contrôle transactionnel différé PostgreSQL des références natives,
avec budgets ST projetés et compteurs distincts instance/organisation/personne/
boîte ; regrouper les vérifications d'une transaction pour ne pas recompter
chaque pièce du brouillon avant sa transformation finale en MIME. Mesurer
le coût sur une boîte réelle et garder les calculs SQL bornés, sans contenu
chargé en Python. Les quotas ne sont pas déclarés fonctionnels à ce stade.

## Quotas — première admission réelle qualifiée

- Migrations Messages 0040/0041 appliquées : budgets ST et contrôle PostgreSQL
  différé des références boîte, brouillon/MIME, pièce jointe, réservation,
  file entrante, partage de conversation et template. Recompte groupé par
  transaction ; les changements de lecture/livraison sans modification de
  contenu ne déclenchent pas ce travail.
- Politiques ST réelles projetées : instance, organisation, boîte, allocation
  personnelle. Réconciliation toutes les 30 secondes ; politique positive
  périmée après 90 secondes. Pas de quota fondé sur l'espace Docker/S3.
- Recette HTTP réelle : boîte temporaire limitée à 10 octets dans ST ; deux
  uploads concurrents de 8 octets différents → un 201 et un 507 explicite.
  Une seule réservation/8 octets comptabilisés ; suppression de la réservation
  puis compteur revenu à 0. Le jeton CSRF du test vient du endpoint natif
  users/me (CSRF_USE_SESSIONS), pas d'un cookie inexistant.
- Plafond temporaire restauré à 20 Gio pour cette boîte ; budget personnel
  par défaut de 20 Gio ajouté dans ST. Le budget d'organisation reste séparé.
- Les trois contrôles ciblés natifs ST de refus d'accès Drive passent, avec
  configuration Test et identité Suite désactivée pour ces fixtures legacy.
  Un premier lancement Development a échoué sur debug_toolbar/staticfiles,
  puis Test avec l'identité LAN héritée refusait les sessions des fixtures.
- RESTENT : vérifier agrégation personnelle et plafonnement organisation,
  expirations/rollback/imports ; l'archive d'import avant conversion en blobs
  n'est pas encore réservée. Ajouter l'état quota dans l'interface et qualifier
  les erreurs des jobs/SMTP. Ces limites empêchent de clôturer MC4.

### 10 septembre — imports réservés et stockage S3 réellement vérifié

- Migration Messages 0042 appliquée : réservation des archives avant émission
  d'URL ; propriétaire, boîte, taille et parties multipart contrôlés. Les
  archives restent comptées jusqu'à suppression physique ; un import actif ou
  en échec conserve son entrée pour reprise/annulation.
- URL signée bornée par les droits People/ST, Content-Length signé et PUT
  conditionnel. Le navigateur utilise la route LAN du seul bucket d'import.
- Création du canal et liaison de réservation atomiques ; distribution après
  commit ; rejeu du même démarrage retourne le même import. Réévaluation des
  droits du créateur dans le worker et avant chaque message.
- Cause d'échec S3 corrigée : limite de trois volumes inférieure au lot natif
  de sept ; capacité configurée à 32 volumes de 1 GiB, sans préallocation.
- Test HTTP réel : upload 200, écrasement 412, démarrage 202 et rejeu identique ;
  MBOX d'un message terminé, 1 succès, 0 échec. Artifacts privés sous
  `tmp/messages-calendars-qa/archive-*`. Nettoyage final encore requis.
- Frontend Messages reconstruit (quotas et taille d'import), services ciblés
  relancés. Les groupes d'agendas personnels, le raccordement Drive/Docs et
  l'exploitation/restauration restent à réaliser ; chantier non livré.

### 10 septembre — agendas personnels et groupes People

- Migration Calendars 0005 et CalDAV 004 appliquées : grants de groupes liés
  aux UUID People, projection complète bornée par l'observation People/ST.
- Les lignes DAV natives conservent les droits directs ; une vue de lecture
  compose ces droits avec les groupes encore valides. Les chemins des agendas
  restent stables pendant une panne/expiration de projection.
- API de partage limitée au propriétaire d'un agenda personnel de la même
  organisation. Les boîtes restent administrées exclusivement dans Messages.
- Test HTTP réel : partage direct lecture + groupe écriture ; PUT 201 puis
  retrait du groupe 200, PUT 403 et GET 200. Un droit de groupe seul en
  disponibilité retourne l'événement sans exposer son titre privé. Même URI
  après retrait du droit direct.
- Interface native de partage complétée par recherche, choix du groupe, rôle
  et retrait ; modification réelle Web observée 200. Inspection visuelle puis
  corrections des noms People, des marqueurs de provenance, des traductions et
  de l'affichage des tailles (réutilisation du formateur Messages).
- Artifacts privés `calendar-group*` et `quotas-groups-ui.cjs` sous le répertoire
  de recette. Fixtures non nettoyées tant que la recette globale continue.
- Restent notamment MC6 (annulation/récurrence/reprise), MC7 Drive/Docs,
  exploitation/restauration MC8 et qualification Authentik/nettoyage MC9.

### 10 septembre — reprise durable des invitations

- Cause racine : l'ancien callback HTTP de SabreDAV pouvait échouer alors que
  l'événement restait enregistré, sans reprise persistante de l'envoi.
- Nouvelle outbox CalDAV (migration 005) engagée dans la même transaction que
  PUT/DELETE. Échec de l'écriture DAV : rollback de l'intention d'envoi.
- Drain via le worker Dramatiq natif, indépendant de la boucle de fraîcheur
  People/ST. Lecture machine dédiée, claims bornés, retry et acquittements.
- Compte, epoch, issuer, accès agenda et droit d'émission de boîte revalidés.
  Migration Django 0006 conserve le MIME exact/Message-ID avant soumission
  Messages ; un acquittement perdu réutilise ces mêmes octets.
- Test réel : API Messages temporairement suspendue, PUT d'une invitation 201 ;
  API remise en service dans le finally du test, outbox livrée automatiquement
  au premier passage du worker. Une entrée REQUEST, non échouée, un événement.
  La recette annulation/récurrence et le rejeu de réception restent à poursuivre.


### 10 septembre — versions d’invitations et échanges de fichiers

- Une mise à jour réelle de l’invitation passe 204, sa copie destinataire reçoit
  SEQUENCE 6 et le nouvel horaire. Rejeu avec ancien ETag : 412. DELETE source
  204 produit une annulation, copie destinataire SEQUENCE 7 / CANCELLED.
- L’acquittement de l’outbox applique les mises à jour aux copies existantes
  par le moteur iTIP SabreDAV natif, sous verrou de la ressource, sans créer
  d’agendas ou accorder de droits implicites au destinataire.
- Messages recherche maintenant la ressource par UID et utilise son ETag.
  Un RSVP tiré du mail antérieur échoue explicitement après annulation ; les
  données courantes, exceptions et propriétés locales ne sont pas écrasées.
- MC7 en cours : transport machine dédié Messages/Drive avec acteur People
  réel, sans jeton IdP ; lectures plafonnées à 25 MiB (API Blob native), copie
  en flux côté Drive, empreinte vérifiée et journal de publication existant.
- Test réel S3 Test1 et NAS SMB : save 201, rejeu même identifiant 201, retour
  dans la boîte Messages 201 avec SHA-256 identique. Source hors droits 404.
  Fixtures `mc-suite-transfer-temporaire.txt` et réservations Blob à nettoyer.
- Sélecteur natif AppExplorer branché au catalogue unifié, choix explicites
  lien privé/copie/export PDF, aucune ouverture automatique des ACL.
  Qualification visuelle et des conflits encore en cours, MC7 non clôturé.
- Restent MC4/MC5/MC6 complémentaires, MC8 reprise/restauration, MC9 second IdP
  et nettoyage, puis documentation finale. Chantier toujours NON LIVRÉ.

### 10 septembre — sélecteur, filtrage et restauration isolée

- MC7 : parcours navigateur Messages → explorateur canonique Drive → copie
  jointe réussi, sélection simple et double clic conservés. Un conflit de nom
  sur S3/NAS laisse le job en échec, sans écraser le fichier existant. Export
  PDF réel du document Docs : 201, 1 302 octets. Fixtures encore présentes.
- Rspamd officiel stable 4.1.5 figé, un worker borné ; contrôle de santé adapté
  au port d'analyse car l'administration est désactivée. ClamAV 1.5.4 figé,
  deux threads, limite d'analyse explicite et refus si analyse incomplète.
- Upload réel : fichier normal 201, signature de test antivirus 422.
  Le contrôle commun couvre maintenant aussi les imports ; un scanner ou quota
  indisponible conserve la possibilité de reprise, y compris dans le runner IMAP.
- Un propriétaire révoqué n'interrompt plus la projection des autres agendas.
  RSVP consulte les droits composés directs/groupes. Linters ciblés et PHP OK.
- `docker/suite/mail_operations.py` fournit démarrage/arrêt/statut, sauvegarde
  complète et restauration isolée. Image locale disparue, modes de répertoires
  extraits et droits du fichier S3 corrigés à la cause ; attente explicite du S3.
- Sauvegarde complète `20260910T100953Z` : images, sources, configuration,
  secrets, trois bases et volume S3. Les autres projets sont restés démarrés.
- Restauration `suite-mail-restore-7a51f0c18c` : réseau interne sans port exposé,
  aucun worker/API/SMTP. Clés de session renouvelées et champs chiffrés
  réencryptés ; canaux, identités et anciennes files désactivés.
- Lecture réelle : un mail, une pièce jointe, une archive S3 et un événement
  SabreDAV ; empreinte MIME identique, accès anonyme refusé. Les fixtures n'ont
  pas de Blob mail déporté S3 ; l'archive d'import vérifie ici la copie S3.
- Guide en cours : `docs/operations/suite-messages-calendars.md`. Restent les
  scénarios complémentaires MC4–MC7, la réconciliation après restauration et
  l'aller-retour Authentik MC9, le nettoyage puis la clôture. NON LIVRÉ.

### 10 septembre — transport SMTP, récurrence et conservation

- SMTP réel : destinataire valide accepté et mail livré une fois ; destinataire
  inconnu refusé 550. Correction racine du préfixe MDA doublé dans la préparation.
- CalDAV réel : PROPFIND/REPORT 207, série hebdomadaire traversant le changement
  d’heure avec exception au bon horaire ; PUT Web 204, ancien ETag 412.
  VALARM et propriété importée conservés ; génération frontend sur copie de
  l’objet, exceptions conservées. Build, oxlint et TypeScript ciblés réussis.
- Abonnement ICS LAN HTTP 200 ; révocation DAV 401 et ICS 404. Réponse HTTP
  temporairement stockée en flux, limite 64 MiB/60 s et mémoire 1 MiB.
- Suppression d’un agenda non vide refusée 409, sans perte d’événement.
  La suppression d’un principal conserve ses agendas tant que leur sort
  n’a pas été traité explicitement ; une boîte avec agendas reste protégée.
- Import terminé oublié via API 204 ; nettoyage différé 90 s pour laisser
  expirer les anciens PUT signés avant de rendre le quota.
- RSVP sur une ancienne invitation annulée : travail refusé 409 par la
  vérification du journal de scheduling, indépendamment de la copie locale.
- MC9 démarré dans le projet `suite-identity-qa` séparé, données synthétiques,
  aucun SMTP sortant. Les projets LAN existants restent actifs.
- NON LIVRÉ : second IdP, recette complémentaire et nettoyage encore en cours.

### 10 septembre — IdP, restauration et corrections de récurrence

- MC9 : aller-retour Keycloak → Authentik → Keycloak réel dans deux projets
  isolés ; mêmes UUID applicatifs, mail chiffré et événement journée entière.
  Messages → Calendars accepte les issuers explicitement approuvés, y compris
  les issuers distincts par application Authentik. Anciennes sessions refusées.
- Retrait People sur session ouverte : boîte, agenda partagé, DAV et ICS
  deviennent inaccessibles. Preuve : `identity-roundtrip.json`. Les projets
  Authentik/identité de recette et leurs volumes ont été retirés.
- Accès de récupération natif créé pour chaque application ; droit natif de
  gestion des ressources affecté au groupe Administration de la suite.
  Deux réservations simultanées : une acceptée, une refusée, statuts visibles
  sur les événements organisateurs. Aucun double créneau sur la ressource.
- Wheel commune 0.1.4, locks et builds Messages/Calendars/Drive/Docs vérifiés.
  Assets `collectstatic` présents dans les images de développement : correction
  du renderer HTML qui échouait alors que les API JSON fonctionnaient.
- Sauvegarde `20260910T114341Z`, restauration isolée : mail, pièce jointe,
  Blob natif S3 et événement relus. People/ST actuels réconcilient un ancien
  accès Sender en Viewer ; aucune ancienne session/canal réactivé, aucun SMTP.
  Preuve : `restoration-readback.json`. Projet restauré supprimé ensuite.
- Antivirus indisponible simulé par pause temporaire : upload refusé 503 ;
  conteneur rétabli dans un `finally`. Fichier non admis.
- Interface : édition d'une occurrence puis des suivantes exécutée réellement.
  Défaut natif trouvé : deux écritures séparées tronquaient avant création et
  réutilisaient COUNT entier. Découpage remplacé par une transaction SabreDAV
  conservant alarmes/propriétés et exceptions futures ; COUNT restant ajusté.
  Requête invalide : 400, original inchangé ; requête valide : 200, 2 occurrences
  restantes. Contrôles ACL/ETag conservés ; bornage à 10 000 occurrences.
- NON LIVRÉ : dernières vérifications transversales, nettoyage et clôture restent
  en cours. La sauvegarde ci-dessus précède la correction du découpage de série.


### Clôture fonctionnelle — 10 septembre, compléments

- Celery Messages : conserver les tâches natives en fusionnant la configuration
  beat avec celle du SDK. La substitution initiale avait supprimé indexation,
  retries et collecte. Dix tâches effectives ; recherche réelle et file vide.
- iTIP activé explicitement : REQUEST, REPLY et CANCEL ont le même METHOD dans
  le MIME et l’ICS ; séquences 1/1/2, une copie expéditeur et une reçue chacune.
  Preuve : `itip-readback.json`. Ancien mail conservé immutable jusqu’au nettoyage.
- Série partagée : réponses concurrentes ACCEPTED/TENTATIVE terminées, lecteur
  refusé 403 ; mise à jour EXDATE propagée, annulation propagée, ancienne
  invitation refusée après suppression de la copie. Les chemins de boîtes se
  lisent via l’instance utilisateur DAV, pas le chemin propriétaire machine.
- Interface Messages : enregistrement d’une pièce jointe vers Drive 201 ; lien
  Docs envoyé, ressource privée refusée 404 au destinataire. Taille nulle d’un
  lien Docs normalisée à zéro (pas de fichier joint), validation du callback.
- Quota Drive : refus réel obtenu en abaissant temporairement la politique ST,
  autorité effective ; politique restaurée dans finally. Une mutation directe
  de la projection locale n’était pas une simulation valide (ST la remplace).
- Mails : brouillon/envoi/Bcc/réponse/recherche/export natifs qualifiés. Transfert
  depuis le navigateur, destinataires valide/inexistant : livré/échoué séparés.
- ClamAV indisponible : upload 503, service rétabli dans finally. EICAR SMTP
  accepté durablement puis mis en quarantaine, aucun Message utilisateur créé.
- Salle Meet : le destinataire arrive en attente d’admission, sans admission
  automatique. Salle qualifiée supprimée au nettoyage.
- Confidentialité : un lecteur reçoit un VCALENDAR sans VEVENT privé (200,
  filtrage natif, et non 403). Résolution de l’adresse participante corrigée
  pour les principaux UUID. Propriétaires/éditeurs conservent les règles natives.
- Suppression des ressources : transaction avec verrou natif de réservation ;
  réservation active refusée, historique entièrement annulé supprimable après
  confirmation. Lecture de comptage `?export` non concluante : ne pas la présenter
  comme une preuve ; le contrôle reproductible utilise REPORT calendar-query.
- Suppression d’une boîte avec agendas par administrateur de domaine : 409.
  Suppression d’agenda de boîte désormais distincte d’un désabonnement DAV :
  autorité Messages admin, identité/organisation vérifiées, garde agenda vide.
- Maintenance ciblée : Django Messages 5.2.17 et Pillow Calendars 12.3.0,
  verrous mis à jour sans changement des autres dépendances. Avis officiels :
  https://www.djangoproject.com/weblog/2026/aug/04/security-releases/
  https://github.com/python-pillow/Pillow/security/advisories/GHSA-pg7v-jwj7-p798
  https://github.com/python-pillow/Pillow/security/advisories/GHSA-whj4-6x5x-4v2j
  Registres SabreDAV/VObject consultés ; cela ne constitue pas un audit de
  sécurité exhaustif de toutes les dépendances du serveur.

Nettoyage encore en cours à ce point : quatre Items Drive purgés, dont Docs
avec binding purged ; fichier NAS supprimé par Provider API (204). Les preuves
finales doivent encore constater disparition des fixtures restantes et sauvegarde.


### Pré-clôture — recette nettoyée

- L’agenda de boîte supprimé depuis l’UI ne réapparaît plus. La sélection
  d’organisateur prend désormais l’adresse de boîte exposée par SabreDAV,
  propriété serveur protégée, au lieu de décoder un UUID comme une adresse.
- Sans aucune boîte ni adresse principale : création UI d’un agenda personnel
  201, rechargement réussi, suppression 204. Les guards de connexion DAV se
  fondent sur le principal durable et ne réclament plus un email absent.
- Les trois boîtes de recette ont été supprimées par l’API native (204), après
  leurs agendas. 53 conversations et 46 blobs supprimés par les mécanismes
  natifs ; aucun échec GC, aucun objet S3 ni multipart restant. Mails, imports,
  événements, dispatches, canaux personnels et groupe People QA : zéro.
- Les projections de quota vides sont retirées lorsque leur allocation métier
  disparaît. Leur ancien timestamp ne doit pas dégrader indéfiniment le statut.
  Le statut vérifie désormais aussi la fraîcheur des budgets effectifs.
- Quatre Items Drive purgés (Docs inclus), fichier NAS supprimé, salle Meet
  qualifiée supprimée ; trois anciens volumes de dépendances inutilisés retirés.
- Catalogue Messages/Calendars ouvert dans ST. Smoke final : catalogue depuis
  trois apps, façades existantes et dossier Drive d’origine vérifiés.
- Nouvelle sauvegarde : Docker 29 remplace parfois l’index OCI d’une image
  inchangée sans recréer son conteneur. Le script vérifie désormais l’identité
  exacte du manifeste de plateforme avant de retenir l’index actuel. Sans
  preuve, il refuse avant d’arrêter les services. Les deux tentatives refusées
  n’ont pas interrompu les écrivains et ne sont pas des sauvegardes complètes.


### Sauvegarde de l’état livré

Sauvegarde complète `20260910T130928Z`, trois bases et blobs, configuration,
sources et images figées. La résolution OCI compare le manifeste de plateforme
exécuté puis conserve l’index inspectable correspondant, sans changer le runtime.
Les lecteurs/écrivains du projet mail ont été rétablis par le script ; aucune
intervention sur Drive, NAS, Keycloak, ST, People, Docs ou Meet.

Les vérifications finales de syntaxe/migrations n’ont trouvé aucune migration
manquante. Le check Calendars interrompu par son remplacement de conteneur a
été relancé seul et a réussi ; cette interruption n’est pas un échec métier.
Le smoke final a été corrigé pour viser ST UI 8960 et ne pas attendre
`networkidle` sur une page Django de diagnostic. Les 11 vérifications passent.


### Clôture — LIVRÉ SUR LE LAN

MC0–MC10 terminés. La sauvegarde nettoyée `20260910T130928Z` est restaurable,
vérification isolée effectuée (bases volontairement vides de fixtures), ancien
contenu de recette et droits restaurés déjà qualifiés dans le précédent isolat.
Les archives de recette devenues inutiles sont supprimées ; aucune action
amont, aucun commit/push/PR de ces développements. Plan, index, contexte,
architecture, installation, guides des deux forks et changelog mis à jour.
Le rapport `validation-final.md` fait autorité sur les anciens points de reprise.
