# Projects — exploitation LAN

Projects : <http://192.168.10.123:8940>. Sources :
<https://github.com/Apoze/projects>, branche `codex/suite-projects`.
Contrat et suivi : [plan d’intégration](../plans/suite/projects-integration-plan.md).
Le profil conserve Drive, Docs, Meet, Messages, Calendars, People, ST et l’IdP
existants. Le script de démarrage Drive ne démarre pas Projects ni ST.

## Administration depuis le Web

| Besoin | Interface |
| --- | --- |
| Identifier une personne ou approuver une association IdP | People, administration des identités de la suite |
| Créer un groupe et gérer ses membres | People |
| Autoriser l’application | ST, souscription Projects, règles utilisateurs/groupes |
| Limiter le stockage | ST, Projects, budgets organisation/utilisateur et overrides des comptes projet |
| Attribuer des droits de contenu | Projects, tableau/projet, **Accès directs et groupes** |
| Voir l’usage ou transférer la facturation | Projects, paramètres du projet, **Stockage et quotas du projet** |
| Autoriser la création de projets et reprendre un espace orphelin | Projects, **Mon compte → Réglages → Connexion à la suite et notifications**, administrateur |
| Examiner/reprendre une notification en erreur | Même panneau ; la reprise est réservée à l’administrateur |

Les droits directs et ceux des groupes se cumulent. Retirer un groupe ne retire
pas un droit direct. Un propriétaire ne peut pas supprimer le dernier
responsable actif. La récupération administrative concerne uniquement les
espaces sans responsable actif ; elle conserve IDs, historique et facturation.
Le responsable de facturation est une personne People, distincte de l’auteur
qui ajoute une pièce jointe. Son départ ne transfère pas implicitement le quota.
Le transfert affiche l’usage résultant et exige une confirmation actualisée.

ST conserve sa convention : **zéro ou absence de plafond = illimité**.
Utiliser **blocage de croissance** pour interdire les nouveaux fichiers.
Une baisse sous l’usage bloque les admissions sans supprimer l’existant.
Les limites instance, organisation, responsable et projet se cumulent.
Les réservations et miniatures comptent ; un échec de suppression ne libère
pas les octets avant confirmation S3. Les suppressions parentes sont collectées
par lots, avec un délai de grâce de dix minutes pour les opérations abandonnées.

La session s’appuie sur OIDC, une association explicite People et des décisions
ST fraîches. Aucun rapprochement par email, groupe ou rôle issu des claims.
Les preuves d’authentification durent au plus quinze minutes ; les décisions
ST et snapshots au plus 90 secondes. Les sockets sont revérifiées toutes les
quinze secondes. Une panne durable ferme les accès. Une modification des grants
reconnecte actuellement les sockets de l’instance ; les clients autorisés se
réabonnent. Cette solution est destinée à une instance LAN.
Les brouillons de commentaires restent dans le `sessionStorage` du navigateur
courant, par utilisateur et carte/commentaire, jusqu’à confirmation d’écriture.
Ils ne sont pas partagés entre appareils ; le navigateur doit autoriser ce stockage.

## Fichiers et notifications

Dans une carte : **Ajouter depuis Drive**, puis lien ou copie ; **Enregistrer
dans Drive** choisit un dossier S3/NAS et un nom. Une copie devient indépendante.
Un lien conserve les droits Drive ; son titre est visible aux membres du tableau.
Pour Docs, le lien ouvre le document vivant ; une copie est un export PDF
explicitement autorisé. Aucun accès public ou partage supplémentaire implicite.
Les liens Drive/Docs sont conservés lors d’une duplication de carte/tableau.

Pièce jointe et transfert : **25 MiB maximum** ; le sélecteur de transfert
conserve la limite minimale native d’un octet. Uploads, copies et duplications
passent l’admission commune : ClamAV, quotas atomiques et publication privée.
Sharp est borné à 40 mégapixels et cinq secondes pour les transformations.
Le profil n’active pas les imports externes, webhooks, tableaux publics ou les
écrans d’upload d’avatars/fonds désactivés dans la référence native retenue.
Les médias utilisateur ne sont jamais exposés par un bucket public.
Une copie de tableau matérialise les fichiers séquentiellement ; le tableau
incomplet est masqué et retiré en cas d’échec ou d’abandon. Attendre son résultat
avant de relancer une duplication complète.

Les notifications natives restent dans Projects. Une affectation, ou un
commentaire destiné à un abonné, produit une intention durable vers Messages.
Le destinataire est résolu par UUID People et boîte principale active.
L’expéditeur `projects@<domaine-LAN>` est une adresse de service sans réponse.
Le mail contient un texte générique et un lien soumis aux droits Projects.
Pas de contenu de carte ni d’adresse libre dans l’API machine ; aucun envoi WAN.
Une boîte absente est signalée ; créer la boîte principale puis reprendre.

Messages utilise le MTA existant et journalise sa décision par UUID et Message-ID.
Une panne certaine peut être réessayée sans nouvelle remise pour le même UUID.
Une réponse SMTP incertaine nécessite une vérification de Messages puis une
confirmation explicite : aucune garantie « exactement une fois » n’est possible
si l’accusé SMTP a été perdu. Les droits sont revérifiés avant une nouvelle
émission. Un mail déjà remis ou un téléchargement terminé ne peut pas être rappelé.

## Démarrage et configuration

Depuis `/root/Apoze/drive` :

```sh
python3 docker/suite/provision_projects_local.py --register-current-keycloak
python3 docker/suite/prepare_projects.py --help
docker compose -f data/projects-local/compose.json build projects
python3 docker/suite/projects_operations.py start
python3 docker/suite/projects_operations.py status
python3 docker/suite/projects_operations.py stop
```

La première commande est idempotente, conserve les credentials et prépare
uniquement Projects. `--register-current-keycloak` est l’adaptateur facultatif
du LAN actuel ; l’application reste OIDC générique. Avec un autre IdP,
enregistrer le client confidentiel, code + PKCE, callback `/oidc-callback`,
configurer issuer/client/secret puis approuver les associations dans People.
Ne pas réinitialiser les identités ou réutiliser un sujet d’IdP pour une autre
personne. Une seconde installation dans la même organisation peut utiliser un
Consumer People distinct et `SUITE_DIRECTORY_APP_ID` correspondant.

État privé, jamais Git : `data/projects-local/` (settings, env, clés et compose).
Préparation des clés Messages conservée aussi dans
`data/messages-calendars-local/`. People, ST, Drive et Messages disposent de
credentials machine distincts ; les lectures et mutations sont séparées.
Les répertoires de configuration et les sauvegardes sont réservés à l’opérateur.
Ne pas afficher les fichiers env, secrets, cookies ou dumps.

PostgreSQL : rôle/base `projects` dans la pile suite. S3 : bucket Projects
privé et identité dédiée sur le service Docs S3, séparés des objets Docs.
SeaweedFS conserve son image épinglée et offre 32 emplacements de volumes,
avec des nouveaux volumes limités à 1 GiB pour ce LAN. Le stockage Drive/NAS
reste sous le contrôle de Drive, sans migration de ses fichiers.
ClamAV est le service existant de la pile mail ; aucune seconde pile mail.

`status` donne la santé applicative, l’âge de l’annuaire, l’expiration des
politiques, les écritures/mails en attente, le disque temporaire et S3/ClamAV.
Un échec de dépendance produit un état non prêt. Les logs d’exploitation privés
restent dans le dossier d’état ; les erreurs applicatives utilisent des codes
stables sans contenu de fichier ou credentials. Pour reconstruire après un
changement, utiliser le compose généré, jamais les montages de sources de recette.

Récupération de l’administrateur, opérateur serveur uniquement :

```sh
docker compose -f data/projects-local/compose.json exec -T projects \
  node db/suite-admin.js <UUID-People-actif>
```

Cette commande promeut un compte People déjà associé ; elle ne crée pas de
mot de passe local et ne contourne ni ST ni l’IdP. Les tâches quotidiennes
s’effectuent ensuite dans les interfaces ci-dessus.

## Sauvegarde, restauration et reprise

```sh
python3 docker/suite/projects_operations.py backup \
  data/projects-backups/<identifiant-unique>
python3 docker/suite/projects_operations.py restore \
  data/projects-backups/<identifiant-unique> \
  --destination data/suite-projects-restore-<identifiant>
python3 docker/suite/projects_operations.py verify-authorities \
  data/suite-projects-restore-<identifiant>
python3 docker/suite/projects_operations.py cleanup-restore \
  data/suite-projects-restore-<identifiant>
```

La sauvegarde exige une image saine sans montage de sources. Elle exporte
images exactes, configuration privée, dump PostgreSQL et inventaire SHA-256
avec les objets privés, en streaming. Projects seul est arrêté pendant le dump
et l’export, puis remis dans son état précédent même en cas d’erreur.
Le manifeste fige les empreintes ; conserver une copie protégée hors du serveur.
Les liens Drive ne recopient pas le NAS : la reprise de leurs cibles exige la
sauvegarde Drive/Docs et le maintien de leurs UUID.

La restauration vérifie les empreintes et crée un réseau interne, des volumes
neufs, aucune publication de port, aucun SMTP/webhook, aucun ancien credential
machine utilisable. Les sessions et transactions OIDC sont supprimées, les
comptes/politiques invalidés et les notifications historiques en attente annulées.
Les fichiers et les correspondances sont conservés.

`verify-authorities` n’accepte que cet isolat sans ports ni réseau externe.
Il attache temporairement People/ST au réseau interne, utilise leurs credentials
**de lecture actuels**, réconcilie puis détache les autorités dans un `finally`.
Il ne réactive pas les anciens jetons, envois ou droits retirés depuis le backup.
La reprise opérationnelle doit renouveler les credentials autorisés, vérifier
les données et les droits puis basculer l’adresse de service explicitement.
Ne jamais lancer l’ancien binaire sur une base ayant reçu un schéma incompatible.

`cleanup-restore` retire seulement les conteneurs/volumes de l’isolat validé ;
les fichiers privés et rapports restent disponibles pour l’opérateur. Aucun prune.
Pour retirer Projects du LAN : fermer sa souscription/son catalogue dans ST et
arrêter Projects seul. Les autres applications restent en fonctionnement.

## Échanges depuis Chat

Le menu Projects du salon partage une tâche ou un tableau par lien chiffré
générique. L’action sur un message texte propose sa copie explicite dans une
nouvelle carte native, avec choix du tableau/liste et lien de retour au salon.
Les détails restent soumis aux permissions Projects ; aucune autorisation
n’est déduite d’un lien Chat. Voir le [guide Chat](suite-chat.md).

La migration `20260911000100_suite_chat_handoff` conserve les reçus même après
suppression d’une carte afin qu’un retry ne la recrée pas. Les sauvegardes
existantes incluent ces tables et les clés privées ; le profil de restauration
isolée désactive explicitement les communications et liens Chat.
