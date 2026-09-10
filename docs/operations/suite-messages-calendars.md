# Messages et Calendars — exploitation LAN

État au 10 septembre 2026 : intégration LAN fonctionnelle et recette réalisée.
Sauvegarde finale : `data/messages-calendars-backups/20260910T130928Z/`.
Le suivi canonique est le
[plan Messages/Calendars](../plans/suite/messages-calendars-integration-plan.md).

## Services et accès

Messages : `http://192.168.10.123:8900`.
Calendars : `http://192.168.10.123:8930`.
Projet Docker : `suite-mail`. PostgreSQL est partagé avec `suite-local`, avec
trois bases/rôles distincts `messages`, `calendars`, `caldav`.
Le script Drive conserve son périmètre. ST reste lancé séparément.

Depuis `/root/Apoze/drive` :

```sh
python3 docker/suite/mail_operations.py start
python3 docker/suite/mail_operations.py status
python3 docker/suite/mail_operations.py stop
```

Le statut contrôle API, People/ST, files entrantes et d'invitations, erreurs
de livraison, S3, Redis, index, SMTP, antispam et antivirus. Les compteurs
n'exposent ni adresses ni contenu. Une file vieillissante, une projection
dépassant 90 secondes ou une sonde `ok: false` nécessite une investigation.
Le délai SMTP tient compte du contrôle initial natif Postscreen.
Messages doit conserver ses dix tâches périodiques et une file
`search_pending_threads` qui se vide ; un OpenSearch sain ne suffit pas.

Configuration persistante privée : `data/messages-calendars-local/`.
Ne pas l'afficher, la publier ou supprimer ses clés. Régénération idempotente :

```sh
python3 docker/suite/prepare_mail.py \
  --state data/messages-calendars-local \
  --suite-settings data/suite-local/settings.json
```

La préparation ne démarre rien. Elle conserve les secrets et refuse un
changement implicite d'IdP/organisation. `restart: unless-stopped` conserve
le démarrage après redémarrage Docker, sauf arrêt explicite du service.

## Sauvegarde cohérente

```sh
python3 docker/suite/mail_operations.py backup
```

La commande crée un répertoire daté privé sous
`data/messages-calendars-backups/`. Elle conserve les images exactes, sources
locales des deux forks (y compris modifications non commitées), configuration,
clés et trois dumps PostgreSQL, puis le volume natif SeaweedFS. Les écrivains
du projet mail sont arrêtés pendant la copie des données puis redémarrés dans
un `finally`, même si la sauvegarde échoue. Drive, IdP, People et ST continuent.

Un `manifest.json` final et ses empreintes identifient une sauvegarde complète.
Si Docker a remplacé un index OCI sans changer l’image exécutée, le script
compare le digest du manifeste de plateforme avant d’utiliser le nouvel index.
Un tag différent sans cette preuve fait échouer la sauvegarde avant tout arrêt.
Un répertoire interrompu ne doit pas être utilisé. L'archive contient des
données et secrets : accès local privé, copie externe chiffrée selon la
politique de sauvegarde du serveur. Prévoir la place pour images et blobs.

Redis ne fait pas autorité et n'est pas restauré. OpenSearch est reconstructible.
Les messages SMTP sont remis au MDA durable pendant la transaction SMTP ;
le transport Postfix restant élimine la copie déjà livrée.

## Restauration isolée et lecture de contrôle

```sh
python3 docker/suite/mail_operations.py restore-isolated \
  --path data/messages-calendars-backups/<date>
```

La commande vérifie les empreintes et restaure dans un **nouveau** projet
`suite-mail-restore-<identifiant>`, réseau Docker interne, aucun port publié,
aucun worker, API ou SMTP en service. Les images manquantes sont rechargées
depuis l'archive. Le stockage attend son état prêt avant les lectures.

Les signatures/session Django sont renouvelées ; les champs chiffrés sont
réencryptés sans perdre les clés DKIM ou métadonnées. Les anciennes sessions
sont supprimées, canaux et associations IdP désactivés, projections invalidées.
Les anciens envois et invitations en attente sont explicitement bloqués.
Les bases restaurées conservent les UUID et les contenus.

La commande lit un mail avec pièce jointe via le stockage natif, vérifie son
empreinte, lit un objet S3 disponible et un événement par le backend SabreDAV.
`verification.json` conserve les compteurs sans contenu. Une base vide affiche
zéro ; ce n'est pas une preuve de lecture d'un contenu absent.

La restauration n'est pas promue automatiquement sur le LAN. Avant une remise
en accès : réconcilier les identités, groupes et politiques avec People/ST
**actuels**, recréer/renouveler les canaux machine autorisés, vérifier les accès
retirés, reconstruire l'index et décider explicitement du sort des envois
bloqués. Ne pas relancer de vieux jetons ou files Redis.

Pour reconstruire les droits depuis les autorités vivantes dans cet isolat :

```sh
python3 docker/suite/mail_operations.py verify-authorities \
  --path data/messages-calendars-restore/suite-mail-restore-<identifiant>
```

Cette étape attache temporairement People/ST au réseau interne, sans SMTP,
workers ou exposition publique, puis les détache dans un `finally`. Elle ne
réactive pas les anciens canaux/sessions. La preuve de recette comprend un
droit de groupe retiré depuis la sauvegarde, effectivement retiré après
réconciliation. Les comptes de récupération restent distincts des droits métier.

Après inspection :

```sh
python3 docker/suite/mail_operations.py remove-restore \
  --path data/messages-calendars-restore/suite-mail-restore-<identifiant>
```

Seuls le projet, les volumes et le répertoire de cette restauration sont
supprimés. Aucun prune global, aucune restauration sur une base LAN existante.

## Mises à jour et retour arrière

Sauvegarder avant migration. Construire les images natives dans les forks
`Apoze/messages` et `Apoze/calendars`, vérifier les migrations prévues, puis
mettre à jour seulement les services concernés avec le compose généré.
Les sources bindées du LAN font partie de la version : une ancienne image
avec de nouvelles sources n'est pas un retour arrière.

Un schéma incompatible impose une restauration isolée et une reprise
contrôlée, pas le démarrage d'une ancienne image sur la base migrée. Conserver
la sauvegarde précédente jusqu'à validation. Les dépendances doivent rester
figées ; les bases de signatures ClamAV sont actualisées par Freshclam.

## Filtrage LAN

Rspamd 4.1.5 officiel et ClamAV 1.5.4 sont figés par digest. Interfaces
d'administration et ports de filtrage non publiés. Les vérifications DNS de
délivrabilité publique restent désactivées pour le domaine LAN de test.
ClamAV contrôle mails entrants, imports et transferts de pièces jointes.
Une panne ne vaut jamais verdict sain ; les contenus détectés restent bloqués.
Les limites d'analyse produisent également un refus, pas une validation partielle.

Sources : [image Rspamd](https://github.com/rspamd/rspamd-docker),
[antivirus Rspamd](https://docs.rspamd.com/modules/antivirus/),
[image ClamAV](https://docs.clamav.net/manual/Installing/Docker.html).
La qualification WAN et la délivrabilité Internet restent un chantier distinct.


## Administration courante

- ST : activer séparément Messages et Calendars ; accès des groupes/personnes,
  plafonds application/organisation/personne/boîte. People reste l’autorité des
  groupes ; le contenu d’une boîte n’est pas accessible par le seul rôle ST.
- Messages : administrateur de domaine pour créer les adresses et sélectionner
  le propriétaire People ; paramètres de boîte pour membres/groupes, rôles,
  nom d’affichage et consultation du budget effectif. Viewer lit, Editor édite
  sans envoyer, Sender envoie/répond, Admin gère la boîte. Les droits d’une
  conversation se composent toujours avec les droits de sa boîte.
- Calendars : création avec choix personnel/boîte, partages personnels directs
  ou groupes People. Les agendas de boîtes héritent de Messages : pas de second
  éditeur concurrent des droits. Seul un admin de boîte peut supprimer son
  agenda, après export/déplacement/suppression des événements et livraison des
  invitations en attente. Supprimer une salle requiert l’annulation de toutes
  les réservations actives ; la confirmation supprime aussi l’historique annulé.
- L’adresse d’une boîte native est immutable. Créer une autre adresse et
  transférer explicitement les accès, conserver l’ancienne pour les anciennes
  invitations ; ne pas renommer une adresse par une mutation SQL. Le choix
  `allocation_owner`/`is_primary` existe dans l’administration Django de
  récupération, avec unicité en base. Ne pas le confondre avec l’adresse IdP.
- La récupération Django est réservée à l’opérateur : secrets uniques privés
  du déploiement, aucun compte de démonstration. Son privilège technique peut
  lire du contenu et ne doit pas être attribué à un simple administrateur ST.
- Canaux personnels CalDAV/ICS depuis les paramètres Calendars : rotation,
  révocation, scope, dernière utilisation. Une migration d’IdP impose une nouvelle
  connexion et régénération des canaux personnels ; les UUID métier restent.
  Garder les canaux machine `Suite Messages` / `Suite Calendars` du provisioning.

## Invitations, imports et limites actuelles

Le domaine interne est `mail.apoze.test`. Le transport WAN reste fermé ; une
adresse extérieure n’est pas une promesse d’acheminement Internet. Les états de
livraison sont suivis par destinataire et une panne de filtrage ne vaut pas
acceptation du contenu comme sain.

`CALENDAR_ITIP_ENABLED=true` conserve les METHOD natifs REQUEST/REPLY/CANCEL.
Une réponse dans Messages vérifie la boîte, l’acteur, la séquence et l’occurrence
avant écriture ; les tâches revalident leurs permissions. Les liens RSVP
nécessitent un POST confirmé, pas seulement une visite du lien.

Les pièces jointes sont limitées à 25 MiB, le MIME entrant à 25 MiB, chaque ICS
écrit à 1 MiB ; les réponses DAV sont bornées à 64 MiB et 60 secondes, avec
spool disque après 1 MiB. Les imports réservent les budgets avant publication.
Les enregistrements libérés suivent la collecte native (blobs PostgreSQL/S3,
réservations d’upload et cycle de vie du bucket d’import).

Le découpage « cette occurrence et les suivantes » est atomique : COUNT restant,
exceptions, alarmes et propriétés opaques sont conservés. Un changement de
calendrier dans cette opération est refusé : découper, puis déplacer explicitement.
Pas de notifications navigateur ni de rappels mail promis par un VALARM stocké.

Plafonds de protection actuels : recherche d’historique d’invitation limitée à
1 000 intentions par paire d’adresses, application à 1 000 copies acceptées,
découpage à 10 000 occurrences parcourues. Au plafond, erreur explicite,
jamais approximation silencieuse. Avant un usage dépassant ces bornes, ajouter
une projection UID indexée/pagination, puis qualifier ce volume réel.

Pièces jointes ↔ Drive : S3 et NAS restent des backends distincts derrière les
espaces canoniques. Copie autorisée, quota de destination et collision vérifiés.
Un lien Docs conserve ses ACL ; son envoi ne partage pas automatiquement le doc.
Une invitation Meet donne un lien de salle, pas une admission automatique.
