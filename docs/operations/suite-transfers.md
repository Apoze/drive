# Transfers — exploitation LAN

État : Transfers et Chat livrés sur le LAN le 12 septembre 2026. Références : [plan](../plans/suite/transfers-element-chat-integration-plan.md)
et [preuves](../../output/implementation/transfers-element-chat/validation-final.md).

## Démarrage et mise à jour

Depuis `Apoze/drive`, avec les services communs et ST déjà démarrés :

```sh
python3 docker/suite/provision_transfers_local.py --register-current-keycloak
python3 docker/suite/prepare_transfers.py
docker compose -f data/transfers-local/compose.json build transfers frontend
docker compose -f data/transfers-local/compose.json up -d
```

Le premier argument adapte uniquement l'inscription du client à l'IdP local
actuel. L'application utilise OIDC et les associations People ; un autre IdP
se configure avec les mêmes redirections et associations explicites. Ne pas
remplacer l'issuer d'un état existant sans procédure de migration des identités.
Le script de démarrage Drive est conservé ; ces services se gèrent séparément.

Interface : `https://192.168.10.123:8950`. Stockage signé : port 8952.
Importer **uniquement** `data/transfers-local/tls/ca.crt` dans les magasins de
confiance des appareils LAN. Ne jamais diffuser `ca.key` ou `server.key`, ni
neutraliser les vérifications TLS. La CA n'est pas montée dans le proxy.
La préparation conserve les secrets existants ; récupérer une génération TLS
incomplète avant de la relancer. Prévoir le renouvellement avant expiration.

La fiche Transfers est active et visible dans ST. Autoriser les
utilisateurs/groupes voulus avec les règles existantes. Les inscriptions neuves restent fermées.
Les quotas utilisateur/organisation se règlent dans l'administration native ST.
20 Go décimaux par défaut ; `0` signifie sans limite à ce niveau, jamais une
capacité physique infinie. Les octets chiffrés, brouillons et purges en attente
comptent dans les réservations. Le plafond par fichier clair est 20 Gio : son
admission exige aussi la place pour l'enveloppe chiffrée.

Le compte d'administration technique Transfers se délègue explicitement :

```sh
docker compose -f data/transfers-local/compose.json exec transfers   python manage.py suite_admin UUID_PEOPLE
```

Ajouter `--revoke` pour retirer ce rôle. L'interface native `/admin/` emploie le
SSO de la suite ; les actions de gouvernance demandent un aperçu confirmé.
Ne pas utiliser un compte local ou une mutation brute des modèles pour contourner
People/ST.

## Garanties et limites visibles

- Standard : clé reçue par Transfers, analyse antivirus avant publication.
  Le scanner partagé accepte 60 Mio. L'exemption ST des fichiers plus grands
  est désactivée par défaut ; une infection ou erreur n'est jamais exemptée.
- Confidentiel : clé conservée dans le navigateur et fragment du lien. Aucun
  scan serveur promis ; les mails ne contiennent pas cette clé.
- Source Drive/NAS privée, export Docs PDF explicite plafonné à 25 Mio. Une
  copie reçue a ses propres droits et ne suit pas les révocations de la source.
- Retour Drive : blocs de 25 Mio, journal et quotas natifs, nom sans écrasement.
  Spool privé `data/transfer-intakes`, monté dans Drive app et worker, UID 1000,
  mode 0700 ; fichiers 0600, suppression après publication ou abandon.
  Budget spool 100 Gio, réserve disque libre 5 Gio, abandon inactif après 1 h.
  Ne jamais effacer le spool d'un job actif. Pendant la confirmation finale de
  publication, une annulation peut être refusée : consulter le résultat.
- L'accès unique est réclamé par POST ; ouvrir un aperçu GET ne le consomme pas.
  Le navigateur gagnant peut reprendre le téléchargement jusqu'à l'expiration
  de sa session. Une copie déjà téléchargée ne peut pas être rappelée.
- Reconnexion : conserver l'onglet Transfers pour garder la clé/le brouillon en
  mémoire. Une fermeture de cet onglet n'est pas une sauvegarde des clés.

## Supervision et reprise

```sh
docker compose -f data/transfers-local/compose.json ps
```

Vérifier API, frontend, worker et beat. Les synchronisations People/ST et quotas
s'exécutent périodiquement ; une autorisation trop ancienne ferme les accès.
Ne pas allonger la fraîcheur pour masquer un ordonnanceur arrêté. Les journaux
restent privés : ils peuvent inclure des références techniques sensibles.
La purge conserve les objets/réservations incertains jusqu'à la reprise S3.
L'administration expose la reprise de nettoyage ; ne pas libérer un quota à la
main avant d'avoir confirmé la suppression effective. Les imports interrompus
reprennent les parties déjà confirmées dans le journal.

## Sauvegarde et restauration

Les commandes dédiées préservent les services communs et les autres apps :

```sh
python3 docker/suite/transfers_operations.py status
python3 docker/suite/transfers_operations.py stop
python3 docker/suite/transfers_operations.py start
python3 docker/suite/transfers_operations.py backup data/backups/transfers-DATE
python3 docker/suite/transfers_operations.py restore data/backups/transfers-DATE \
  --destination data/suite-transfers-restore-DATE
python3 docker/suite/transfers_operations.py verify-restore \
  data/suite-transfers-restore-DATE
python3 docker/suite/transfers_operations.py verify-authorities \
  data/suite-transfers-restore-DATE --transfer UUID_TRANSFERT_FINALISE
python3 docker/suite/transfers_operations.py cleanup-restore \
  data/suite-transfers-restore-DATE
```

`backup` archive les images exactes avant l'interruption, puis arrête la façade
publique S3 et les écrivains Transfers. Il capture le dump PostgreSQL, les objets
S3 terminés, leur empreinte et la configuration privée. Les services initialement
actifs sont redémarrés même en cas d'échec. Un montage de sources dans l'image
est refusé : construire la version réellement utilisée avant de la sauvegarder.
La sauvegarde contient des secrets et les clés des transferts standard ; la
protéger comme les données vivantes. Les clés confidentielles restent chez les
utilisateurs. Le journal privé ne doit pas être publié.

`restore` vérifie les empreintes puis crée PostgreSQL, S3, Redis et l'API sur un
réseau interne, sans port publié, worker, ordonnanceur, SMTP ni accès au NAS.
Les anciennes sessions et credentials machine sont invalidés ; les droits
People/ST sont fermés et leur cache de révision supprimé pour imposer une
projection complète. Les invitations anciennes ne peuvent pas repartir ; un
lien à accès unique déjà réclamé reste consommé. Les autorisations mobiles
des fichiers en attente ou déjà chargés sont également supprimées. Les parties multipart non
finalisées ne sont pas sauvegardées : leurs uploads restaurés sont abandonnés,
avec journal de purge conservé. Les objets terminés sont relus par empreinte.

`verify-authorities` raccorde temporairement uniquement People et ST au réseau
interne avec des credentials de lecture. Il ne publie aucune métrique ancienne
vers ST. L'option `--transfer` qualifie un transfert finalisé, non expiré,
accessible selon les droits actuels : refus avant revalidation, lecture via
l'API et comparaison du fichier, puis refus après fermeture de la projection.
Le transfert de recette doit autoriser un téléchargement sans réclamer une
session à accès unique. Le vérificateur utilise le script courant ; l'import
et la vérification des objets utilisent celui figé dans la sauvegarde.
`cleanup-restore` retire uniquement les conteneurs et volumes du projet isolé ;
les fichiers privés restent conservés pour diagnostic. Il ne nettoie jamais la
pile active.

Recette du 12 septembre 2026 : 6 objets (211 812 855 octets) restaurés et relus,
2 comptes revalidés, lecture API d'un transfert finalisé identique, anciennes
sessions absentes et accès refermé après vérification. Aucun mail ni usage ST
réinjecté. Les copies de recette sont ensuite retirées.

La promotion en production reste volontairement séparée de la qualification :
restaurer les sauvegardes People/ST cohérentes si nécessaire, relire leurs droits
actuels, reconfigurer les credentials et origines, puis réadmettre la pile.
Pour une copie retour Drive active, sa base et son spool ont leur propre point
cohérent ; cette sauvegarde Transfers ne les remplace pas. Pour une mise à jour,
prendre ce point avant les migrations, figer la nouvelle image et effectuer un
parcours ciblé. Après migration incompatible, le retour exige la restauration
du point complet ; remettre seulement une ancienne image ne suffit pas.
