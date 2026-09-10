# Espaces unifiés — état d’exécution

Chantier autorisé le 5 septembre 2026, implémenté et qualifié localement le
6 septembre 2026. Lots L0 à L12 clôturés. La pile LAN historique est maintenant activée et sa recette ciblée est terminée
(voir la mise à jour ci-dessous). Aucun commit ou publication de cette implémentation.

- Consolidation Git préalable terminée : [rapport](git-consolidation.md).
- Branche locale des deux dépôts : `codex/unified-storage-spaces`.
- Connexions multi-S3/NAS, coffre, espaces, groupes et accès administrables dans
  Drive ; plafonds applicatifs indépendants, révisions et application dans ST.
- Explorateur commun, documents/viewers/éditeurs, recherche, favoris, partage,
  archives et extraction complète/sélectionnée ; capacités natives explicites.
- Copies et déplacements de fichiers/dossiers dans les quatre directions,
  journal, SHA-256, quotas, reprise et rétention qualifiés.
- Migration répétable et contrôle des droits, mesures de navigation/mémoire,
  scheduler réel et restauration isolée documentés.
- [Recette finale et matrice de capacités](validation-final.md),
  [preuves navigateur](browser-qa/report.md),
  [guide utilisateur/administrateur](../../../docs/unified-storage-spaces.md) et
  [migration](../../../docs/installation/unified-storage-migration.md).

Les sections suivantes sont le journal chronologique : leurs mentions de
travaux « à poursuivre » décrivent l’état au moment du contrôle. Le présent
résumé et la recette finale constituent le statut courant.

## Vérifications ciblées obtenues

- Connexions : deux buckets S3 réels, secrets liés à leur connexion, accès
  administrateur, activation après vérification et publication gouvernée.
- Espaces : restrictions de sous-dossier sur les anciens endpoints Items,
  propriétaire comptable distinct, quota d’espace et plafond global.
- Catalogue NAS : renommage externe, identité conservée, favoris et révocation.
- Migration : deux passages, mêmes UUID/chemins/clés, compteurs non doublés.
- ST : 46 contrôles existants et un contrôle de révision d’instance réussis.
- Copie S3 et rétention NAS : trois scénarios ciblés réussis.
- Migration/coffre/administration : six scénarios ciblés réussis.
- Partage : le plafond lecture seule interdit aussi de déléguer des droits
  d’écriture par accès nommé, invitation ou lien public. Les droits des
  anciennes API de partage sont bornés à l’espace courant.
- Médias : flux multi-S3 authentifié, HEAD, Range et jetons de dossiers publics
  raccordés ; les écritures multipart gouvernées utilisent des conditions
  natives de publication pour fermer la course après le dernier HEAD.
- 50 contrôles ciblés partage/espaces/WOPI/transferts ont réussi, puis le
  scénario supplémentaire de modification de source a également réussi.
- Publication conditionnelle : sept contrôles S3/transfert/copie réussis.
- Renommage S3 gouverné : publication multipart conditionnelle commune,
  relecture SHA-256 et conservation journalisée de l'original. Une version
  immuable peut être nettoyée après rétention ; une clé sans version reste
  conservée. L'ancien effacement WOPI inconditionnel est retiré de ce chemin.
- Politiques : 46 contrôles de compatibilité entitlements/renommage réussis ;
  un scénario Drive couvre organisations distinctes, espace illimité connu,
  lien ST précis et refus à un non-administrateur. Un scénario ST confirme
  la récupération/confirmation de politique sans compte utilisateur fictif.
- Administration durable : trois contrôles sur provider natif passent avec
  panne du broker, reprise de réattribution et perte de réponse de restauration.
  La restauration conserve la source et compte la copie une seule fois.
- Identité comptable : cinq contrôles confirment qu’un Item garde une clé
  d’usage antérieure indépendante de son UUID, y compris après sauvegarde.
- Édition NAS : vingt contrôles WOPI/provider/écriture en flux passent.
  Les contrôles navigateur avec les éditeurs réels restent à effectuer.
- Frontend : TypeScript et ESLint des derniers composants passent. Ruff
  passe sur les changements backend ; Pylint passe après correction d'une
  inférence erronée du retour HEAD de l'APIClient. Preuves navigateur ciblées disponibles dans [le rapport](browser-qa/report.md).

Les migrations nouvelles sont appliquées aux bases éphémères des contrôles
automatisés et aux bases dédiées `driveqa` / `stqa` de qualification isolée. La qualification Docker du socle utilise encore les
anciennes images ; la base de développement partagée n’a pas été migrée.

Référence : [plan canonique](../../../docs/plans/storage/unified-storage-spaces-plan.md).

## Références de publication S3

La publication utilise les conditions natives documentées par AWS, sans
assimiler ETag et checksum. Un S3 compatible doit respecter ce contrat ;
la collision a été contrôlée sur les deux buckets de qualification.

- [Écritures conditionnelles](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html).
- [Suppressions conditionnelles](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-deletes.html).

Les migrations 0040/0041 étendent le journal de déplacement et ses états.
Les migrations 0042/0043 conservent les demandes d'administration et leur lien
vers les publications/restaurations. Aucune
nouvelle migration n’a été appliquée à la base partagée ou à la fixture de
production ; les contrôles éphémères et la nouvelle qualification isolée utilisent ce schéma.

## Reprise — qualification web du 5 septembre

- Administration : racine NAS, inventaire, propriétaire nommé, restauration
  asynchrone et lien exact vers le quota ST contrôlés dans Chromium.
- Import S3 : URL gouvernée rattachée à l’adresse de l’API, y compris lorsque
  l’interface utilise une autre origine ; import et aperçu texte réussis.
- Accessibilité : la désactivation du glisser-déposer ne désactive plus les
  liens/dossiers ; le catalogue ne présente plus « Mount » comme auteur.
- Navigation NAS : retour clavier vers le catalogue commun « Espaces ».
- Dates du catalogue : valeurs persistées au lieu de la date de rendu.
- Quotas : 413 gouverné traduit et orienté vers la libération d’espace ou
  l’administrateur, indépendamment du fournisseur de stockage.
- Contrôles : 17 backend upload/S3, quatre espaces, dix frontend
  adaptateurs/fil d’Ariane réussis. Vérifications additionnelles en cours.

- Refus NAS : la réservation d’un nouveau fichier ne crée plus son entrée
  de catalogue ; trois contrôles natifs et une vérification navigateur passent.
- Erreurs d’import : motif visible sans survol ; un serveur refusant le fichier
  après 100 % d’envoi ne produit plus une icône de réussite. Trois contrôles
  du composant passent et le motif de quota est visible dans Chromium.
- Copies S3 : API `mode=copy`, comptabilité supplémentaire et reprise sans
  recopie validées. Migration 0044 appliquée aux tests et à `driveqa`,
  uniquement. Copies S3 ↔ NAS et NAS ↔ NAS raccordées aux journaux existants,
  avec contrôle SHA-256, protection contre écrasement et reprise de publication.
- Sélecteur commun de destination raccordé aux actions de copie des fichiers ;
  parcours Chromium S3 → NAS puis NAS → S3 terminés sans erreur réseau.
  Les transferts de dossiers, déplacements entre familles et nettoyage
  complet restent en cours dans L9.
- Racines NAS : correction du filtre de droits pour un grant `/` sur une
  racine non vide (`/documents`), contrôlée sans accorder d’écriture au lecteur.
- Validation : 12 contrôles transferts/publications, quatre espaces et
  23 contrôles frontend existants réussis ; TypeScript et Pylint ciblés passent.

## Copies de dossiers — reprise du 5 septembre

- Manifeste persistant `StorageCopyEntry` (migration 0045), dossiers vides,
  publication native sans fusion dans un dossier existant et réutilisation
  des journaux de fichiers.
- Quatre couples S3/NAS contrôlés : refus de quota puis reprise des seuls
  fichiers interrompus, sans seconde charge ni nouvelle copie des éléments
  terminés. Onze scénarios de transfert réussis.
- Sélection multiple : même sélecteur de destination dans la barre commune ;
  dossiers accessibles depuis le menu de copie.
- Chromium + workers dédiés : dossier NAS copié vers S3, historique terminé,
  aucun échec réseau. Migration 0045 appliquée seulement à `driveqa` et tests.
- 25 contrôles frontend, TypeScript, ESLint et Pylint ciblés passent.
- À poursuivre : déplacements entre familles, résolution de publications
  conflictuelles, nettoyage, antivirus multi-S3, puis qualification finale.
  Le backend JCOP de la dépendance utilise encore `default_storage` ; son
  routage doit être adapté et ses callbacks liés à la version analysée.

## Antivirus et lectures S3

- Le stockage Django par défaut route les lectures de clés Item vers leur
  connexion réelle ; les assets sans Item gardent le comportement existant.
- Les lectures sont des flux S3, y compris pour l’encodeur multipart JCOP,
  sans téléchargement implicite dans un fichier S3 en mémoire.
- Les nouveaux rapports antivirus des emplacements explicites sont liés
  à la connexion, à la clé et à la version. Un rapport périmé est ignoré.
- Les copies du moteur commun vers S3 déclenchent l’analyse configurée,
  avec les états et règles d’accès déjà utilisés par les imports Drive.
- 47 contrôles ont passé immédiatement ; le dernier ancien double de test
  d’administration a été ajusté, puis quatre contrôles ciblés passent, dont
  envoi multipart borné et refus d’un résultat périmé.
- Les anciens jobs S3 `s3_copy` restent récupérables ; toutes les nouvelles
  copies, y compris S3 → S3, utilisent désormais le moteur commun.
- La résolution explicite d’une copie vérifiée malgré une source modifiée
  est raccordée à l’API et à l’historique. Deux contrôles ciblés passent ;
  les droits sont revérifiés après relecture du contenu de destination.

## Reprise : déplacements natifs et conflits de dossiers

- Le journal de déplacement NAS accepte deux vues autorisées d'une même
  connexion. Le fichier lie sa réservation au job dans la transaction de
  publication ; son index et son quota sont confirmés ensemble.
- Contrôle d'identité/version avant et après renommage ; une version différente
  observée à la reprise reste en conflit. Les dossiers réutilisent le manifeste
  et la substitution de quotas du moteur natif existant.
- Migration additive `0046` : les liens NAS nouveaux se rattachent à la référence
  persistante et à leur créateur. Les anciens liens indexés sont rattachés avant
  un déplacement ; un index manquant exige un inventaire. La consultation
  retrouve une vue actuellement partageable du créateur, sinon retourne 410.
- Un dossier temporaire créé avant perte de son identité n'est jamais adopté
  ou supprimé par supposition. La reprise explicite conserve son intention et
  crée un nouveau temporaire ; le manifeste expose le nombre de rétentions.
- L'historique permet de consulter le manifeste paginé et d'agir sur les fichiers
  en conflit avant de reprendre leur parent. Le serveur filtre le propriétaire
  avant de lire le manifeste ou d'appliquer une action.
- Contrôles : 18 scénarios de transferts et provider réussis, dont perte de
  publication, perte d'identité du temporaire, substitution sous quota plein,
  conservation de références/partages et révocation. Les 7 contrôles historiques
  de création/consultation des liens NAS passent aussi. Types TS, ESLint ciblé
  et Pylint ciblé passent. Migration `0046` appliquée uniquement à `driveqa`.

## Nettoyage de source S3 après transfert

- Le scheduler reprend aussi les transferts en nettoyage, par lots bornés.
  Après rétention et vérification de destination, seule la version S3 immuable
  capturée peut être supprimée. Les connexions et droits des deux emplacements
  sont revérifiés ; une source sans version reste explicitement conservée.
- Le contrôle sur un bucket SeaweedFS avec versioning activé valide rétention,
  révocation du droit source, nouvelle version externe au même chemin et perte
  de réponse après suppression. La reprise conserve la nouvelle version et
  termine le journal sans double charge. Le contrôle de verrou
  d'édition passe également après ajout de sa garde.
- Les copies de dossiers acceptent un nom choisi dans le sélecteur commun.
  Modifier la destination ou le nom d'un job encore actif est refusé.
  Les quatre contrôles de copie de dossiers passent ; une nouvelle copie NAS
  vers S3 sous un autre nom passe aussi dans le navigateur avec le worker réel.
- Historique détaillé et sélecteur vérifiés sur ordinateur et mobile ; correction
  de la mise en page étroite, sans erreurs réseau ou JavaScript observées.

## Déplacements ordinaires et verrous entre vues

- Le point d'entrée commun choisit maintenant le mécanisme natif et sert aussi
  les nouvelles tentatives. Les mouvements ordinaires dans un espace S3 ont un
  job et une transaction unique pour arbre, partage hérité, activité et état
  final ; aucun octet n'est recopié. Le contrôle d'interruption puis de reprise
  passe, ainsi que le refus d'un mouvement dans son propre sous-arbre.
- `Item.move` protège les opérations actives de tous ses descendants, pas
  seulement les métadonnées du dossier source.
- Les verrous d'édition NAS utilisent la référence persistante commune aux
  vues et conservent la compatibilité des anciens verrous par chemin. Un
  déplacement natif vérifie les verrous de son sous-arbre par lots de cache
  sous la garde exclusive de namespace. L'ouverture WOPI référence l'entrée
  déjà observée avant de créer sa session.
- Contrôles : les 35 scénarios passent après correction de la fixture alias
  (une seconde vue partageable permet légitimement au créateur de conserver
  son partage). Les 2 scénarios natifs ont été relancés avec des vues source
  et destination explicites ; les contrôles Ruff/Pylint ciblés passent.
- Glossaire enrichi et ADR 0002 ajoutée pour la séparation entre référence
  commune, stockage natif, droits et attribution. La compatibilité des références
  lors d'un déplacement entre familles reste à implémenter et qualifier.

## Favoris, récents et vues superposées

- Les favoris/récents NAS se rattachent maintenant au couple utilisateur et
  ressource ; l'espace mémorisé est une préférence de navigation, pas l'autorité
  du favori. Supprimer cet espace conserve le favori si une autre vue autorisée
  permet ensuite de retrouver la ressource.
- Recherche, favoris et récents sélectionnent une vue actuellement autorisée
  avant pagination. Les vues superposées n'ajoutent plus de doublons et un
  déplacement ne fait plus disparaître le favori de l'ancien espace.
- Migration `0047` : fusion des anciennes lignes par vue en conservant tout
  favori actif et la visite la plus récente. Contrôle de migration réel réussi,
  incluant suppression de la vue préférée après fusion. Huit contrôles ciblés
  de catalogue, espaces et mouvements natifs passent ; Pylint ciblé passe.

## Qualification SMB, reprise planifiée et sélecteur de déplacement

- Samba réel, données synthétiques isolées : remplacement du secret par un
  mot de passe invalide refusé malgré la session précédente, puis reconnexion
  après restauration. Déplacement entre vues avec référence conservée, copie
  SMB→S3 rejouée sans doublon et compteurs concordants.
- Le véritable Celery Beat a repris deux déplacements dont la livraison
  initiale avait été volontairement supprimée, dont un après arrêt/redémarrage
  de Beat. Les contrôles des parents et des quotas passent. Beat est arrêté
  après qualification ; les environnements persistants ne sont pas activés.
- Les menus de déplacement, la sélection multiple et les deux points d'entrée
  du glisser-déposer utilisent maintenant le sélecteur commun en mode unifié.
  Les racines du catalogue exposent leurs capacités réelles au panneau latéral.
- Correction d'un défaut découvert au navigateur : le contrôleur NAS retenait
  les éléments sélectionnés sans ouvrir leurs fenêtres Renommer/Déplacer/
  Supprimer. Une action explicite pilote désormais la bonne fenêtre.
- Navigateur : déplacement SMB réellement terminé depuis le sélecteur commun
  sur ordinateur ; ouverture/annulation Renommer/Supprimer/Déplacer sur mobile,
  sans erreur réseau ni JavaScript. Captures dans `browser-qa/`.
- Les alias de connexion du même namespace peuvent effectuer un déplacement
  natif si la connexion source atteint la destination et si les deux connexions
  confirment la même identité de dossier. Les chemins de bases différents sont
  traduits ; une fausse correspondance est refusée avant publication.
- La récupération périodique des mouvements natifs repasse par le job et ses
  contrôles de droits/configuration. Une destination désactivée après publication
  laisse une opération récupérable, sans valider sa charge silencieusement.
- Les déplacements entre familles physiques différentes et leur compatibilité
  complète de références restent ouverts. Le chantier n'est pas terminé.

## Restauration et téléchargement public NAS

- Sauvegarde PostgreSQL de la base synthétique, restauration dans une autre
  base isolée et restauration séparée de la clé du coffre. Les cinq connexions
  natives répondent, les secrets sont déchiffrables, les journaux sont conservés
  et les compteurs concordent. Sans la clé, le déchiffrement est refusé.
  Ce contrôle restaure les métadonnées et le coffre ; les stockages natifs
  synthétiques sont restés en place pendant l'exercice.
- L'API publique NAS sert maintenant GET/HEAD et Range avec le lecteur natif,
  confinement des chemins, pièce jointe et cache désactivé. Elle réévalue le
  partage et ses droits actuels. Les liens inconnus/révoqués et les sorties de
  racine sont refusés ; aucun ticket d'édition n'est créé pour le lecteur public.
- La page publique propose le téléchargement annoncé par les capacités,
  ouvre les fichiers des dossiers partagés, pagine et traduit ses messages.
  Une réponse tardive ne remplace plus le dossier choisi entre-temps.
- Huit contrôles ciblés des liens publics passent. Le navigateur mobile sans
  session a téléchargé le fichier SMB synthétique et vérifié ses octets, sans
  erreur HTTP/JavaScript (`public-download-mobile.png`). Les aperçus publics
  spécialisés et les déplacements entre familles restent à terminer.


## Déplacement de fichier NAS vers S3

- Le journal `mount_s3_transfer` réutilise la publication multipart native S3,
  la vérification SHA-256 et la substitution de quotas. Aucun Item provisoire
  n'est exposé pendant la copie. Après vérification, la source NAS est renommée
  vers un fichier privé de rétention, puis la localisation et la charge sont
  basculées dans une transaction unique.
- Le nouvel Item reprend l'UUID de la ressource NAS. Favoris, visites, route
  commune et liens publics de fichier suivent cette identité. Les droits de
  partage et de la destination sont réévalués ; la nouvelle copie S3 passe
  par l'analyse antivirus avant consultation. La ressource NAS antérieure est
  conservée comme référence historique, marquée absente.
- Une publication interrompue après la mise à l'écart de la source est reprise
  sans nouvelle copie. La désactivation de la destination bloque la reprise.
  La source privée reste restaurable depuis l'administration et n'est nettoyée
  qu'après rétention, contrôles des droits, configuration et intégrité de la
  destination. Le nettoyage périodique repasse par le propriétaire du journal.
- Un test à quota plein vérifie l'interruption, les droits, l'identité, le
  favori, le lien public, Range, la révocation du partage et le nettoyage.
  Les 26 contrôles ciblés de transferts/publication/liens passent. Après la
  correction SMB ci-dessous, le scénario ciblé repasse ; Ruff et Pylint passent.
- SMB réel : la première qualification a révélé le refus du renommage avec
  le flux de lecture encore ouvert. Le flux est désormais fermé avant la
  publication finale ; un test l'impose. Le journal interrompu a été repris
  sans recopier. Un second fichier a ensuite été déplacé depuis le sélecteur
  web jusqu'à la rétention, sans erreur réseau ou JavaScript.
- Le téléchargement public mobile du premier fichier passe après sa bascule
  en S3 ; son ancien UUID ouvre le lecteur texte S3 dans la route commune.
  Captures : `move-smb-s3-picker.png`, `move-smb-s3-completed.png`,
  `moved-resource-bookmark.png`, `public-download-mobile.png`.
- Restent ouverts : sens S3→NAS, déplacement NAS→autre namespace physique,
  dossiers entre familles, vues S3 superposées et les autres finitions du plan.
  Aucun de ces points n'est déclaré livré par ce contrôle de fichier NAS→S3.


## Retours S3 vers NAS et administration des liens

- Les fichiers S3→NAS utilisent le writer natif protégé : vérification du flux,
  publication sans remplacement et substitution de quota. Après publication,
  l'Item laisse place à une ressource native du même UUID, dans la transaction
  comptable. Les octets S3 restent journalisés ; aucun Item supprimé ne peut
  déclencher leur purge ordinaire. Seule une version S3 immuable est nettoyée.
- Une interruption après publication native se reprend sans nouvelle copie.
  Un éditeur délégué conserve le propriétaire comptable du fichier lorsque la
  destination attribue au créateur ; son quota personnel nul n'est pas débité.
  Les favoris, liens publics explicites et anciennes URL de fichier suivent
  l'identité dans les deux sens. Les favoris NAS migrés sont retirés pour ne
  pas réapparaître après une suppression du favori en S3.
- Les déplacements S3→S3 et NAS→S3 utilisent une clé propre au journal lors
  d'une copie physique. Revenir sur un stockage ne remplace pas une ancienne
  source retenue. Les journaux existants gardent leur clé enregistrée ; un
  changement de vue dans le même stockage conserve l'objet sans copie.
- Les liens persistants sont listables et révocables depuis la ressource
  courante ; les liens NAS peuvent aussi être créés depuis cette fenêtre.
  Le panneau S3 existant inclut ses anciens liens NAS. Un lecteur ne voit que
  ses propres liens ; partager un sous-dossier ne permet pas de partager son
  parent accessible uniquement pour la navigation.
- Validation : 28 contrôles transferts/liens/provider passent, dont les deux
  sens avec reprise à quota plein et le retour dans un ancien bucket. Les
  dix contrôles frontend existants des fenêtres de partage passent. Pylint
  des services/API modifiés : 10/10. Liens Web qualifiés sur mobile, sur la
  ressource déplacée et dans la fenêtre de partage S3 habituelle.
- SMB réel : retour du fichier synthétique depuis S3 vers le NAS via le
  sélecteur web réussi, sans erreur navigateur. Le lien public initial reste
  téléchargeable et l'ancienne URL Item ouvre le lecteur natif. Captures :
  `move-s3-smb-picker.png`, `move-s3-smb-completed.png`,
  `moved-item-bookmark.png`.

Ces contrôles portent sur des fixtures isolées. La parité dossiers,
les namespaces NAS distincts, les vues S3 superposées et la qualification
complète du plan restent ouverts. Aucun déploiement réel supplémentaire.


## Fichiers entre NAS distincts et inventaire pendant une reprise

- Le service `storage_native_transfer.py` réunit les déplacements vers un
  filesystem, depuis S3 ou un autre namespace natif. Le writer, la réservation,
  la vérification de destination et le nettoyage sont partagés. Le journal
  conserve séparément la source native privée et la publication de destination.
- UUID, lien public et favori suivent le fichier vers le nouveau namespace ;
  la source est mise à l'écart et vérifiée avant la transaction comptable.
  Une destination désactivée bloque la reprise. La source reste restaurable
  dans l'administration et une restauration crée une copie soumise au quota.
- Un inventaire après publication interrompue ne doit pas adopter les octets
  de destination comme un nouveau fichier : les chemins des mouvements
  encore réservés sont exclus de la comptabilité et de l'index jusqu'à
  résolution du journal. Cela évite une double charge temporaire. La reprise
  NAS→S3 accepte aussi l'absence constatée de sa source lorsque sa copie privée
  journalisée est toujours vérifiée, sans adopter un remplacement externe.
- Vérifications : 21 scénarios transferts/administration passent ; après le
  contrôle supplémentaire d'inventaire, les deux scénarios NAS→NAS et NAS→S3
  repassent. Pylint des nouveaux services et de l'inventaire : 10/10.
- Navigateur réel : déplacement entre deux partages SMB distincts, utilisant
  deux authentifications, réussi depuis le sélecteur commun. Le lien public
  initial télécharge toujours le fichier sur mobile. Aucune erreur HTTP/JS.
  Captures : `move-smb-independent-picker.png`,
  `move-smb-independent-completed.png`.
- Liens publics : création/révocation sur mobile et révocation après passage
  en S3 qualifiées. La fenêtre de partage remplace temporairement le lecteur
  pour rester accessible au clavier et à la souris. Les URL porteuses de
  secrets sont masquées dans les captures.

Le chantier reste en cours : dossiers déplacés entre stockages, vues S3
superposées, autres parcours de parité et qualification finale du plan.


## Contrôles de cohérence après ce lot

- `make lint` et `make frontend-lint` passent. Les nouveaux services non suivis
  par le sélecteur Git de Pylint ont aussi été vérifiés explicitement.
- Suite frontend existante : 223 suites ont passé lors du lancement complet ;
  les 13 restantes ont été corrigées pour fournir les nouveaux contextes et
  isoler les adapters inutiles au scénario testé. Leur relance ciblée passe
  (39 contrôles). TypeScript et ESLint des tests modifiés passent.
- 34 contrôles backend ciblés passent avec `docker compose run --no-deps`,
  couvrant les fichiers, espaces, administration, inventaire et liens publics.
- Le wrapper `make test-back` démarre les dépendances partagées. Cette
  invocation a été interrompue, les services qu'elle avait démarrés arrêtés,
  puis le même périmètre exécuté sans dépendances. Ne pas utiliser ce wrapper
  tel quel pour les prochaines qualifications isolées.
- Après une longue relecture de destination, le nettoyage réévalue aussi les
  droits source et destination et le verrou d'édition. Les trois scénarios
  NAS→NAS/S3→NAS passent, dont une révocation pendant le calcul de checksum.

Le versionnement/import des anciens objets S3 et la découverte native ZFS
restent hors périmètre selon la section 3 du plan accepté ; aucune nouvelle
interface de versions S3 n'est requise par ce lot. Les dossiers inter-stockages,
les vues S3, l'administration et les autres qualifications prévues restent
à terminer avant toute conclusion globale.

## Dossiers S3 — extension de L9

- Déplacement entre deux espaces d'une même connexion S3 : changement atomique
  des chemins et de l'attribution, aucune copie d'octets, UUID et clés conservés.
  Le contrôle comprend plusieurs fichiers, un plafond global plein, une limite
  de destination insuffisante et une panne au commit. La réservation agrégée
  réserve uniquement la croissance supplémentaire, sans réserver deux fois
  le premier fichier du dossier.
- Déplacement de dossiers entre connexions S3 et de S3 vers NAS : le manifeste
  borné réutilise les journaux de déplacement des fichiers. Les transferts
  terminés restent visibles et ne sont pas répétés lors d'une reprise.
  La finalisation conserve les UUID des dossiers, les favoris et les liens.
  Un conflit peut donc laisser une partie des fichiers déjà déplacée ;
  l'historique expose les entrées et leurs opérations pour poursuivre.
- Les anciennes adresses publiques de dossiers S3 déplacés vers NAS rejoignent
  leur navigateur public natif ; un ancien lien de sous-dossier reste confiné
  à la racine partagée. Les liens créés sur le dossier temporaire sont conservés.
  La migration additive 0048 retire la contrainte qui empêchait de conserver
  ces deux liens valides pour une même personne ; la création courante réutilise
  un lien existant sous verrou.
- Vérifications : 32 scénarios backend transferts/partages/espaces réussis,
  sept contrôles de la page publique réussis, TypeScript, ESLint ciblé, Ruff
  et Pylint des services concernés passent. Les quatre scénarios de copie
  de dossiers restent couverts. La qualification navigateur S3 inter-buckets
  est obtenue. Le parcours SMB réel, sa reprise après rafraîchissement
  d'inventaire et le lien public historique sur mobile sont aussi qualifiés
  sans erreur HTTP ou JavaScript ; captures examinées visuellement.
- 0048 appliquée uniquement à `driveqa` et aux bases éphémères de tests.
  Aucun changement de schéma dans la base partagée ni les fixtures de production.
- Restent notamment les dossiers dont la source est NAS : finalisation native,
  conservation/relocalisation des journaux de rétention et parité des liens
  publics lorsque le dossier revient vers S3. Le chantier global reste ouvert.

## Dossiers dont la source est NAS — L9, 6 septembre

- Le manifeste réutilise les déplacements de fichiers existants. Chaque dossier
  devenu vide est mis en rétention par le journal de suppression natif ; son
  UUID bascule vers sa destination avec un checkpoint de métadonnées.
  Une reprise après cette mise en rétention ne recopie pas les fichiers.
  Les dossiers vides sont conservés dans la destination.
- Les journaux de rétention suivent les déplacements et suppressions du dossier
  parent, y compris leur source native imbriquée. Le nettoyage autorise toujours
  le périmètre original, puis accède au chemin privé journalisé et vérifie son
  identité, sa version et son checksum. Les dossiers privés ne sont retirés
  qu'une fois les rétentions de leurs enfants nettoyées.
- Les liens publics de dossiers NAS devenus S3 utilisent une pagination SQL et
  vérifient les droits actuels. Les anciens chemins nommés restent reconnus ;
  les nouvelles navigations utilisent des segments UUID confinés au dossier.
- 39 contrôles ciblés backend passent (transferts, espaces, providers natifs,
  partages et administration). Ruff/Pylint des services passent.
- Le contrôle SMB réel a identifié l'absence d'itérateur de dossier dans ce
  provider. `iter_children` utilise maintenant le générateur de la bibliothèque
  SMB et ferme son handle, y compris lors d'un arrêt anticipé. Le contrat
  historique `list_children` garde son ordre déterministe. Les dix contrôles
  du provider SMB passent, dont lecture paresseuse et fermeture du générateur.
- Parcours navigateur obtenus : dossier SMB→S3, dossier entre les deux partages
  SMB indépendants, ancien UUID retrouvé, lien public conservé lors de
  l'aller-retour S3→NAS→S3 et navigation mobile dans son sous-dossier.
  `/tmp/drive-native-trees-browser-recover.log` : aucune erreur HTTP/JS.
  Capture `folder-roundtrip-public-mobile.png` examinée visuellement.
- API et worker dédiés redémarrés après vérification d'absence de transfert
  actif ; aucun redémarrage Samba, aucune nouvelle migration au-delà de 0048.
- Interactions sur les dossiers temporaires S3 conservées : favoris, accès,
  invitations, grants, activité et anciens tokens. Quatre contrôles couvrent
  les familles de déplacement et Pylint passe. Le sidecar de lien est documenté
  dans ADR 0002 ; aucun accès aux octets S3 n'est délégué au Provider API.
  Les limites globales du plan demeurent ouvertes ; ces validations ne
  constituent pas la clôture de L0–L12.

## Espaces S3 imbriqués et isolation des politiques — 6 septembre

- Création administrative d'un espace sur un dossier S3 existant : sélecteur
  paginé, organisations bornées, racine logique immuable et avertissement de
  superposition. Un dossier déjà racine se gère par ses bénéficiaires ; les
  nouvelles allocations imbriquées choisissent un sous-dossier.
- Maintenance obligatoire avant réattribution d'un arbre existant. La tâche
  sélectionne sa racine la plus profonde par SQL, réattribue les usages par
  lots et conserve le blocage des écritures en cas d'interruption. Les scopes
  des espaces parents/enfants s'additionnent ; les octets ne sont pas doublés
  dans les budgets utilisateur, connexion, organisation ou instance.
- Les grants d'un espace parent restent valables dans ses sous-espaces. Une vue
  désactivée n'efface pas les autres vues autorisées ; les bénéficiaires du seul
  sous-espace n'obtiennent pas ses voisins. Recherche, sous-dossiers de grants
  et liens déplacés suivent les identités logiques plutôt que le seul espace
  comptable. La propriété comptable n'accorde toujours aucun accès.
- Parcours Chromium : création, maintenance, réattribution et lecture depuis
  le parent réussis, sans erreur réseau/JavaScript. Correction du rafraîchissement
  des connexions et quotas après les tâches asynchrones, du libellé de sauvegarde
  et du défilement des formulaires. Captures `s3-nested-root-*.png`.
- Compatibilité de migration préservée, y compris grants historiques sur fichier
  et état de maintenance préexistant. Dix contrôles espaces/migration/politiques
  passent ; 30 autres contrôles transferts/administration/providers passent dans
  la régression précédente. TypeScript, ESLint et Pylint ciblés passent.
- Les quotas ST des connexions S3 historiques utilisent désormais le namespace
  de leur organisation. Les anciennes exceptions `s3` sont traduites dans ce
  périmètre ; une exception explicite au nouveau namespace prime. Le plafond
  global historique `backend:s3` et les plafonds utilisateur-S3 sont conservés
  indépendamment, jamais écrasés par une autre organisation. Rejouer le backfill
  en maintenance pour ajouter les scopes de namespace aux usages déjà migrés.
  Les exceptions visant une connexion/espace étrangère ou retirée sont ignorées.

## Impact avant transfert — L9

- Estimation en métadonnées pour une sélection S3/NAS, bornée à 100 ressources.
  Aucun contenu lu, aucune réservation ni tâche créée. Les sélections qui
  incluent deux fois une référence ou son parent sont refusées.
- Présentation des fichiers/octets connus, croissance du budget global et de
  l'espace de destination, règle d'attribution et liens publics explicites
  concernés (noms bornés, jamais leurs tokens). L'admission réelle reste
  authoritative après les modifications concurrentes.
- Contrôle backend mixte S3/NAS, copie/déplacement, absence de lecture de contenu,
  refus de droits et de doublons réussi. Pylint, TypeScript et ESLint passent.
- Chromium : aperçu puis copie S3→S3 `copie-impact.txt` terminée, sans erreur
  HTTP/JavaScript. Captures `transfer-impact-picker.png` et
  `transfer-impact-completed.png`. Le premier script cherchait l'ancien nom
  source dans l'historique ; la qualification finale cible le nom de copie.
- `make lint` et `make frontend-lint` passent après ces lots ; les nouveaux
  modules sont également vérifiés explicitement par Pylint.

## Navigation et mémoire mesurées — L11, 6 septembre

- Anciennes routes de navigation NAS : pagination SQL de l'index actif et
  capacités de connexion calculées une fois par page. Les routes privées et
  publiques évitent la matérialisation de tous les enfants. Le catalogue
  `/resources` utilisait déjà son index ; le repli historique est maintenant
  borné lui aussi. Les journaux `.drive-txn-` sont exclus défensivement.
- Mesure instrumentée, pages de 20 entrées : 96 → 19 requêtes NAS ; dans un
  dossier de 2 000 entrées, médiane 0,57 → 0,17 seconde. Dix contrôles de
  catalogue/partage passent, dont absence d'énumération physique et un seul
  calcul de capacités par page.
- Route commune S3 : contrôle d'éligibilité WOPI avant construction du client,
  résultat par connexion/génération partagé dans la seule page sérialisée,
  annotations existantes de rôles/favoris/enfants, regroupement des ancêtres,
  grants applicables chargés pour la page et suppression du double calcul des
  actions. Une liste de dossiers ne construit plus vingt clients boto3.
- Même fixture et instrumentation mémoire, hors debug toolbar : 147 → 7
  requêtes à chaud (167 → 27 à froid avec les compteurs d'accès historiques),
  environ 7–9 → 0,10–0,14 seconde à chaud. Mémoire Python par page :
  environ 245 Mo → 0,55 Mo. Dossiers de 20 et 2 000 enfants, trois mesures.
  Ce sont des mesures de qualification locale, pas une latence de production.
  Les fixtures S3 de cette mesure sont annulées par transaction.
- 74 contrôles WOPI/espaces passent : fichiers non pris en charge sans client,
  cache limité à la génération, sessions sans utilisateur, droits imbriqués.
- Flux synthétiques de 16 puis 128 Mio : mémoire Python S3 27,39 puis
  27,33 Mo, NAS 1,060 puis 1,056 Mo. Envoi multipart S3 suivi d'une relecture
  SHA-256 ; relecture SHA-256 NAS. Bucket et fichiers temporaires supprimés
  après contrôle. Ces mesures qualifient les primitives de flux, indépendamment
  de l'admission des quotas déjà contrôlée par les scénarios de transferts.
- Les manifestes de dossiers sont insérés par lots de 100, avec unicité SQL
  par tâche/source pour la reprise. Les références déjà chargées ne sont plus
  résolues individuellement une seconde fois ; droits et readiness restent
  vérifiés. Sept scénarios de dossiers passent après cette optimisation.

## Nettoyage après déplacements successifs — L9

- Vérification commune de la destination courante par UUID, sous les verrous
  d'édition et de namespace : relecture SHA-256 et identité native actuelle,
  puis revalidation de l'accès et de la localisation. Un déplacement suivant
  entre familles ne bloque plus définitivement la collecte de la première
  source. Une version S3 encore utilisée comme fichier courant n'est jamais
  supprimée ; seules les versions sources immuables capturées sont collectées.
- Les droits d'écriture sur la source historique restent exigés, y compris
  grants d'un espace S3 parent. Les sauvegardes NAS suivent leur journal privé
  même quand leur parent est supprimé. Contenu modifié, droits révoqués ou
  édition active : conservation et état de nettoyage en attente.
- 31 contrôles transferts/espaces passent. Un scénario NAS→S3→NAS avec parent
  source mis en rétention vérifie que la première sauvegarde est collectée
  après délai sans effacer la nouvelle destination. Les checks de quota,
  panne, révocation pendant checksum et suppression S3 rejouée passent.
- Aucun nouveau déploiement, commit ou publication. Parité fonctionnelle,
  restauration physique complète et recette finale restent ouvertes.

## Éditeurs réels et groupes locaux — L8/L10, 6 septembre

- Collabora 26.04 : ouverture, modification, sauvegarde et relecture DOCX sur
  S3 explicite et NAS local. Les marqueurs saisis dans Chromium sont présents
  dans les deux fichiers et l'audit comptable ne trouve aucun écart.
- ONLYOFFICE 9.2.1 : même parcours sur les deux familles. Le premier PutFile
  NAS a été refusé avec un inventaire âgé de 1 451 secondes (limite 900) car
  le scheduler de qualification était arrêté. Après inventaire, reprise et
  relecture réussies ; aucune protection de fraîcheur désactivée.
- Les deux éditeurs sont isolés, exposés seulement sur 127.0.0.1:8982/8983.
  API/worker recréés avec leurs volumes virtuels Python d'origine ; les anciens
  conteneurs arrêtés sont conservés. Le runtime utilise actuellement ONLYOFFICE.
  Le beat dédié est relancé avec l'intervalle de production de 300 secondes,
  uniquement pour la tâche de rapprochement stockage (ancien test : 10 s).
- Les images d'éditeurs ont quelques 404 d'assets/traductions facultatifs :
  Collabora, icônes et index d'extensions ; ONLYOFFICE, traduction française
  d'un plugin. Les sauvegardes et relectures réussissent. Ces réponses vendor
  ne sont pas masquées dans les journaux privés de qualification.
- Correction de `common.back` affiché littéralement sur la page WOPI NAS.
- L'ancienne propriété `User.teams` était un stub vide. Les groupes Django
  existants fournissent maintenant les principals stables `group:<id>`.
  Leurs noms sont recherchables/paginés dans les accès d'espace ; le lien vers
  l'administration des utilisateurs ouvre la gestion web des groupes.
- Les groupes ne changent pas l'imputation des octets. Le changement de nom
  conserve les grants ; la révocation d'appartenance invalide les caches de
  droits S3 et NAS lorsqu'un utilisateur est revalidé. Les administrateurs
  délégués recherchent leurs groupes et ceux déjà accordés à leur espace.
  Les claims OIDC arbitraires ne deviennent pas automatiquement des groupes.
- Vingt et un contrôles groupes/espaces/WOPI passent, Pylint 10/10,
  TypeScript et ESLint ciblés passent. Chromium : création du groupe,
  rattachement d'Alice via l'administration utilisateur, recherche du groupe
  dans Drive et attribution en lecture de « Edition NAS ». Refus d'écriture
  et révocation contrôlés aussi sur les vraies données synthétiques.
- Copies actuelles des bases Drive/ST et du coffre réalisées ; restauration
  de la base Drive dans `driveqa_restore` réussie. La qualification physique
  complète de cette nouvelle livraison reste à terminer. Le volume S3 de
  développement partagé fait 43 Go pour 40 Go libres : ne pas le recopier
  aveuglément ni toucher aux fixtures nommées production. Utiliser une fixture
  de restauration physique bornée et distincte.

## Révocation durable, restauration S3 et création/conversion NAS — 6 septembre

- Migration 0049 : nonce nullable des liens Items. Les URLs historiques restent
  inchangées jusqu'à une révocation explicite. La publication d'un déplacement
  supprime les tokens montés devenus incompatibles et renouvelle le nonce S3 ;
  réactiver ensuite le partage ne réactive pas l'ancienne URL. La navigation et
  le transport de fichiers vérifient tous deux le token courant. Le retour NAS
  vers S3 ne régénère pas un ancien token supprimé. Les liens compatibles sont
  conservés, y compris lors d'un déplacement ordinaire au sein d'un espace.
- Contrôle de révocation durable réussi ; 39 autres contrôles espaces,
  transferts et tokens passent. La migration des favoris utilise désormais ses
  modèles historiques pendant le contrôle de suppression sous ancien schéma.
- Restauration physique S3 bornée : deux buckets, deux versions par objet,
  stockage SeaweedFS dédié arrêté puis copié vers un autre volume et réseau.
  Base Drive restaurée séparément, coffre restauré à part, source inaccessible
  depuis le réseau de restauration. Quatre VersionIds et SHA-256 conservés,
  UUID/clés/grants/scopes inchangés, audit comptable sans écart. Le contrôle
  échoue sans clé du coffre. Les fixtures ont été corrigées pour rattacher
  explicitement leurs usages après leur construction directe en base.
- Création de documents NAS depuis le même formulaire de formats que S3 :
  modèles ODF/OOXML existants, publication gouvernée et collision refusée,
  sans créer d'Item S3. Le champ de nom du formulaire a un nom accessible.
- Conversion des formats historiques NAS via le moteur ONLYOFFICE existant :
  copie transformée dans un dossier voisin, journal de copie et reprise,
  empreinte du résultat distincte de l'observation source, nouvelle vérification
  des droits et de la source avant publication. Le convertisseur lit son token
  WOPI hors verrou exclusif ; token à courte durée et supprimé à la fin.
  Le nombre d'essais de conversion est borné avant nouvelle tentative explicite.
- Chromium a créé « Creation NAS web.odt » puis lancé la conversion de
  « legacy.doc ». La vraie sortie ONLYOFFICE DOCX contient le marqueur attendu,
  le DOC reste présent et les quotas sont cohérents. Aucun échec HTTP Drive ni
  erreur JavaScript sur les parcours réussis. Les premiers scripts ont été
  corrigés après découverte d'un champ sans label et de deux actions Convertir
  (barre de sélection et menu contextuel), sans masquer les erreurs produit.
- Une conversion S3 explicite ne retombe plus sur une racine du stockage par
  défaut si le parent source n'est pas utilisable. TypeScript passe ; cinq
  contrôles groupés création/conversion/copies passent. Les vérifications
  finales et la parité des archives restent ouvertes.

## Archives, parité et recette finale — 6 septembre

- ZIP unifié depuis une sélection S3/NAS, vers S3 ou NAS ; manifeste borné,
  empreinte et permissions revérifiées, publication par le journal de copie.
  Les chemins de dossiers renommés pour l'archive restent cohérents avec leurs
  descendants. Les originaux et leurs partages restent inchangés.
- Extraction ZIP/TAR complète ou sélectionnée depuis le menu et le lecteur
  d'archives, avec le même sélecteur de destination. Nouveau dossier, refus des
  chemins dangereux/liens/collisions, garde NAS conservée, admission par fichier.
  Répertoire ZIP limité avant allocation (32 Mio), tailles TAR contrôlées avant
  décompression des corps, spool disque après 8 Mio et passes de 20 entrées.
  Un répertoire racine TAR `./` est accepté sans contourner les chemins sûrs.
- Chaque fichier extrait possède son journal ; un arrêt après publication et
  avant progression ne crée pas de doublon. Les enfants se reprennent via leur
  extraction parente. Les validations fonctionnent dans les quatre directions.
- Export ZIP des dossiers natifs et S3 par flux bornés. Filtrage des descendants
  autorisés, fermeture des flux S3 et revalidation avant lecture. Les liens
  publics de dossiers NAS, y compris déplacés vers S3, téléchargent un ZIP limité
  au sous-arbre partagé et restent soumis à la révocation.
- Chromium réel : création de ZIP NAS, extraction NAS, téléchargement de dossier
  ZIP et relecture exacte des octets ; extraction de `a.txt` seule depuis un ZIP
  NAS vers S3, sans `b.txt`. Audit comptable sans écart après ces opérations.
  Liens publics de dossiers NAS et NAS→S3 téléchargés sans session sur mobile.
- Vue mobile 390×844 : sélection dans l'archive, destination, formulaire complet,
  focus dans la modale et fermeture Échap vérifiés. Captures inspectées. Correction
  du libellé de taille du lecteur et distinction entre taille de l'archive source
  et taille décompressée ; le champ nomme maintenant le nouveau dossier.
- 37 contrôles transferts/archives passent ; 13 contrôles bornage et création/
  extraction passent après ajout du garde ZIP/TAR. Sept contrôles publics et
  dossiers déplacés passent. Les derniers contrôles de sécurité complètent ces
  scénarios sans relancer une campagne générale.
- Migration : deux passages vérifiés avec arbre partagé, groupe, fichier sans
  créateur, corbeille et ancien quota S3. Identités, clés, accès lecture/écriture,
  état de suppression et plafonds conservés ; trois contrôles passent.
- Lint backend suivi et nouveaux modules non suivis passent à 10/10 (migrations
  générées exclues de Pylint conformément au runner du dépôt). Les tests de
  modales ont été adaptés à leurs nouvelles dépendances ; ancien parcours et
  raccordement du lecteur restent couverts. Types et lint frontend passent.
- Douze navigateurs des anciennes qualifications sont arrêtés ; environ 17 Go
  de mémoire libérés. Aucun service partagé de données ni fixture de production
  n'a été supprimé. La qualification reste sur les ports isolés.
- Guides utilisateur/administrateur et migration ajoutés ; architecture, contrat
  stockage, exploitation, changelog et documentation ST mis à jour. Les dernières
  vérifications finales sont enregistrées ci-dessous et les lots sont clôturés.


## Clôture locale — 6 septembre

Reprise finale également effectuée : builds de production Drive/ST, imports PDF
réels via les menus, administration/quota ST et contrôle mobile. Les interfaces
QA sont maintenant conservées dans des conteneurs indépendants du terminal.
Le correctif des imports PDF, les preuves et commandes de relance figurent dans
la [recette finale](validation-final.md#reprise-finale-après-interruption--6-septembre).

- `make lint` : Ruff et Pylint réussis ; nouveaux modules Python contrôlés aussi
  séparément, à 10/10. Migrations générées exclues de Pylint comme dans le runner.
- `make frontend-lint` et TypeScript : réussis. Scénarios frontend ciblés des
  modales, montages, lecteur d'archives et traductions réussis après adaptation
  des fixtures de composants, sans masquer d'échec produit.
- Migration : trois contrôles avec groupe, corbeille et créateur absent.
  Archives : 37 contrôles de transfert, puis 13 contrôles de bornage/raccordement
  et 12 de sécurité finale. Export/migration/public : 26 contrôles réussis ;
  sept contrôles des exports publics natifs et après déplacement passent.
  Ces groupes se recouvrent : ils ne doivent pas être additionnés.
- `makemigrations --check --dry-run` : aucun changement manquant. Les migrations
  restent non appliquées à la base de développement partagée ; la base de
  qualification utilise le schéma 0049. Aucun avertissement de schéma partagé
  n'a été résolu en migrant silencieusement cette base.
- API/worker/scheduler de qualification redémarrés sur les sources finales,
  files de transferts et d'administration vidées, audit comptable sans écart.
  Les deux connexions de source du test de restauration physique, désormais
  hors ligne, sont désactivées dans la seule base QA ; la restauration isolée
  et ses fichiers restent conservés.
- `git diff --check` propre dans Drive et ST. Documents d'amorçage ST corrigés
  pour refléter les forks Apoze réellement configurés et leur upstream sans push.
- Le NAS/IdP/domaines réels, OpenZFS, import arbitraire S3, réplication et autres
  applications restent hors de cette ouverture locale, conformément au plan.
# Mise à jour de l'environnement habituel — 6 septembre 2026

La pile LAN a maintenant été relancée avec le script Drive original, inchangé,
et ST séparément. Keycloak historique, NAS réel, espaces unifiés et politiques ST
sont raccordés. La conservation des identités a été vérifiée après une seconde
relance. Après autorisation de l'opérateur, les plafonds de l'organisation et du
compte de test sont à 20 Go. Imports, aperçus, téléchargements, copies/déplacements
S3↔NAS et sauvegardes Collabora/ONLYOFFICE passent sur cette pile. Le défaut de
résolution de ST depuis les workers est corrigé dans Compose. Les fichiers,
versions et copies de secours de ces essais ont été supprimés ; les 158 Items et
15 586 247 860 octets historiques sont retrouvés, sans écart de compteurs ni
opération active. Voir le [rapport local](local-environment-validation.md).
