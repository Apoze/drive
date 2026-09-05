# Espaces de stockage unifiés, multi-S3 et administration web

Date : 5 septembre 2026.
Statut : plan détaillé, implémentation non commencée.
Responsable d'exécution : Codex dans cette tâche, après instruction de démarrage.

Ce document décrit le chantier suivant le socle Drive/ST homelab. Il ne
déclare pas ses fonctionnalités déjà disponibles. Il constitue le point de
reprise pour l'implémentation et son suivi, sans lancer de migration, modifier
de service, créer de ticket ni publier de changement.

Lecture rapide : [cible](#1-résultat-attendu),
[modèle](#4-modèle-cible-et-décisions-de-conception),
[administration](#5-répartition-drive--st-et-administration-web),
[quotas](#6-quotas-et-capacités-physiques),
[migration](#10-migration-de-linstallation-existante),
[lots](#11-lots-dimplémentation),
[validation](#12-validation-minimale-mais-suffisante),
[suivi](#15-suivi-et-reprise-par-codex).

## 1. Résultat attendu

L'utilisateur ouvre la page normale de Drive et accède à ses espaces
« Personnel », « Famille », « Équipe » ou « Archives ». Il n'a plus à choisir
entre une page S3 et une page Montages. Le type de stockage, les serveurs,
les buckets et les comptes techniques relèvent de l'administration.

L'administrateur peut, depuis le Web :

- connecter plusieurs stockages S3 et plusieurs connexions MountProvider ;
- tester, activer, mettre en maintenance et désactiver une connexion ;
- créer des espaces personnels ou partagés et choisir leur destination ;
- limiter les accès à une racine ou à certains sous-dossiers ;
- attribuer les droits aux utilisateurs et groupes ;
- choisir qui porte la consommation, indépendamment de qui voit le fichier ;
- définir les quotas applicatifs dans ST et suivre leur application ;
- suivre les inventaires, transferts, conflits et restaurations.

Exemple cible :

| Espace visible | Destination administrative | Attribution |
| --- | --- | --- |
| Personnel | S3 principal, racine logique personnelle | Utilisateur |
| Famille | Connexion NAS, dossier `/famille` | Budget commun |
| Archives | Deuxième connexion S3 | Budget commun ou propriétaire fixe |
| Documents privés | NAS, `/users/<UUID Drive>` | Utilisateur |

Un utilisateur peut accéder à plusieurs espaces et leur consommation reste
soumise à son quota global lorsqu'il en est le propriétaire comptable.
Plusieurs espaces peuvent utiliser la même connexion. Un espace a une seule
destination d'écriture déterministe ; ce chantier ne répartit pas un même
fichier automatiquement entre plusieurs serveurs.

## 2. Point de départ vérifié

| Élément | Existant | Écart à traiter |
| --- | --- | --- |
| Exploration | Shell graphique commun, parcours Items et Mounts distincts | Catalogue, navigation et commandes communs |
| Connexions | Registre MountProvider en configuration | Gestion persistante et web, plusieurs S3 |
| Espaces | `StorageSpace` associé à un backend du registre MountProvider | Espaces indépendants de la famille de stockage |
| S3 | `default_storage`, bucket configuré globalement | Routage durable par connexion et objet |
| Quotas | Réservations, budgets communs S3/NAS, ressources ST | Espaces S3 et budgets par connexion S3 |
| Comptabilité S3 | Identité d'Item, scope global `backend:s3` | Localisation et scopes explicites, migration des compteurs |
| Administration | Quotas ST, modèles Django Drive | Parcours produit complet pour connexions et espaces |
| NAS externe | Inventaire, identités natives, rapprochement | Intégration au catalogue commun |
| Reprise | Journaux S3/NAS et déplacements de dossiers | Transferts entre espaces et familles |

Sources de code à réexaminer au démarrage :

- `src/backend/core/models.py` : Item, StorageBackend, StorageSpace,
  StorageGrant, StorageUsage, StorageReservation et StorageMoveJob ;
- `src/backend/core/services/storage_spaces.py`, `storage_inventory.py`,
  `storage_quota.py`, `storage_s3_write.py`, `storage_mount_write.py`,
  `storage_tree_transfer.py`, `storage_recovery.py` ;
- `src/backend/core/api/viewsets.py`, `core/urls.py`, `core/admin.py` ;
- `src/backend/drive/settings.py`, `core/services/s3_streaming.py`,
  `core/services/regular_storage_copy.py`, `core/signals.py` ;
- `src/frontend/apps/drive/src/features/explorer/`, `features/mounts/`,
  `features/drivers/` et `pages/explorer/` ;
- dépôt local ST : `/root/Apoze/st-deploycenter`, notamment les resolvers
  d'entitlements, comptes de ressources et composants `StorageOverrides`.

Le [rapport du socle](../../../output/implementation/st-deploycenter-homelab-status.md)
reste la référence de livraison antérieure. Les modifications de ce socle
sont locales et non committées : ne pas les écraser ni les confondre avec
les changements du présent chantier.

## 3. Invariants et périmètre

### 3.1 À préserver

- S3 utilise Django Storage/S3 ; il ne devient pas un MountProvider.
- MountProvider conserve ses providers et son contrat de capacités.
- Aucun contenu entier en mémoire ; flux, pagination et traitements bornés.
- WOPI PutFile lit le corps une seule fois, sans déclencher de parsing DRF.
- Autorisation côté serveur sur exploration, recherche, aperçu, édition,
  liens publics, transferts et administration.
- Les quotas NAS et Drive restent indépendants. Un compte NAS ne représente
  pas les utilisateurs applicatifs.
- Les alias physiques ne doublent pas les compteurs d'un même périmètre.
- Une publication incertaine conserve son journal et ses réservations.
- Aucun déplacement physique implicite lors de la migration du modèle.
- Style actuel de Drive, shell AppExplorer, Collabora et ONLYOFFICE conservés.
- Aucun secret dans les réponses de lecture, URLs, journaux ou captures.

### 3.2 Inclus dans la livraison

Catalogue d'espaces, plusieurs connexions S3, administration web courante,
attribution et quotas communs, exploration unifiée, références durables,
recherche de métadonnées commune, transferts entre stockages, migration,
reprise, documentation et qualification ciblée.

Les fonctionnalités existantes de fichiers doivent être raccordées ou
explicitement limitées par une capacité réelle. Une absence de raccordement
réalisable n'est pas une limite acceptable pour déclarer le chantier terminé.

### 3.3 Frontières explicites

- Le setup Docker, la première identité administrateur, l'IdP, TLS et les
  clés maîtresses restent des opérations d'amorçage hors interface.
- Le matériel NAS réel et les domaines réels demandent une qualification
  distincte. Ils ne bloquent pas la construction du produit sur fixtures.
- L'accès direct NAS est conservé ; Drive ne peut intercepter ses écritures.
- Un bucket connecté sert aux objets gérés par Drive. L'exposition arbitraire
  de tous les objets préexistants d'un bucket, ou leur modification directe
  par d'autres clients, n'est pas assimilée à l'inventaire NAS : elle demande
  un chantier d'import et de rapprochement S3 distinct.
- Pas de réplication, RAID applicatif, mirroring, bascule automatique ni
  agrégation trompeuse de capacités. Plusieurs S3 signifie plusieurs
  destinations utilisables, pas plusieurs copies automatiques d'un fichier.
- La découverte de quotas natifs ZFS, les anciens orphelins/versions S3,
  la fusion de comptes gouvernés et les autres applications de la suite
  restent les limites documentées du socle.
- Le journal d'activité des Items ne devient pas un journal d'audit global.
  L'ADR `docs/adr/0001-product-activity-journal-not-audit.md` reste applicable.

## 4. Modèle cible et décisions de conception

### 4.1 Vocabulaire

| Concept | Responsabilité |
| --- | --- |
| Connexion de stockage | Destination technique, configuration, référence de secret et capacités |
| Namespace physique | Identité de données communes à plusieurs connexions ou vues |
| Espace virtuel | Racine exposée, nom produit, droits et règle d'attribution |
| Élément Drive | Item persistant géré par Drive, notamment sur S3 |
| Entrée montée | Ressource externe exposée par MountProvider, sans devenir automatiquement un Item |
| Référence de ressource | Identifiant applicatif utilisé par le catalogue, les favoris et les opérations |
| Propriétaire comptable | Utilisateur ou budget commun portant les octets |

Étendre le vocabulaire de `CONTEXT.md` pendant l'implémentation. Enregistrer
les décisions de modèle dans une ADR dédiée ; ne pas réécrire l'ADR activité.

### 4.2 Connexions et localisations

Faire évoluer `StorageBackend` en connexion utilisable par les deux familles,
sans recréer une seconde table concurrente de connexions. La connexion porte
une famille `s3` ou `mount`, une configuration validée propre à cette famille,
un namespace et des états explicites.

Configuration S3 : endpoint, bucket, région si nécessaire, mode d'adressage,
préfixe éventuel, référence de secret, configuration TLS et capacités validées.
Configuration MountProvider : provider existant, paramètres autorisés et
référence de secret. Les détails du provider restent internes à son adapter.

Une localisation S3 associe durablement l'Item à une connexion et une clé
d'objet. Le bucket/périmètre d'une connexion utilisée ne change pas sous les
pieds des fichiers : une nouvelle destination demande une nouvelle connexion
ou une opération explicite de migration.

Réutiliser les clés `item/<UUID>/...` existantes lors de la migration.
Les nouveaux objets utilisent une convention déterministe respectant le
préfixe configuré. Renommer un espace ne réécrit pas ses objets.

Les journaux et uploads en cours conservent la destination et la génération
de configuration nécessaires à leur reprise. Ils ne relisent pas aveuglément
le nouveau stockage par défaut après une rotation ou un changement de réglage.

Django expose un registre de stockages et la création d'une instance à partir
de sa configuration. Réutiliser ces mécanismes après vérification de la
version installée, sans modifier globalement `default_storage` à chaque
requête. Voir la [documentation Storage de Django](https://docs.djangoproject.com/en/5.2/ref/files/storage/).

### 4.3 Racines des espaces

- S3 : racine logique d'Items et connexion de destination. Les dossiers
  restent des objets de l'arbre applicatif, pas des chemins NAS fictifs.
- MountProvider : racine native normalisée et protégée par les contrôles
  existants contre traversée, symlinks, reparse points et alias.
- Espace personnel : propriétaire comptable explicite, attribution d'accès
  explicite et racine isolée. Le choix du stockage est administratif.
- Espace partagé : propriétaire fixe, budget commun ou attribution au créateur.
- Nouvelle arborescence : héritage de la destination de l'espace parent.
  Un changement de destination est un transfert, jamais une simple édition.

L'appartenance aux espaces et la localisation physique sont distinctes.
Plusieurs vues autorisées d'une même ressource ne créent pas plusieurs copies.
Les recouvrements sont signalés dans l'administration avant activation.

### 4.4 Identités, index et droits

Conserver les UUID des Items. Pour les entrées montées, réutiliser l'identité
logique déjà rapprochée par l'inventaire ; compléter la référence persistante
pour les dossiers, favoris et liens lorsque nécessaire. Ne pas identifier un
fichier uniquement par son chemin : renommage et remplacement sont différents.

Le catalogue expose une référence opaque commune. Sa résolution vérifie
l'espace, l'utilisateur et les droits actuels avant d'appeler l'adapter S3 ou
MountProvider. Un identifiant natif ou un chemin technique n'est pas un droit.

Réutiliser `StorageUsage` pour la comptabilité. Les métadonnées d'exploration
ne doivent pas créer de faux usages pour des dossiers ni transformer tous les
fichiers NAS en Items. Ajouter uniquement les données persistantes manquantes
pour l'index et les références ; pas de second registre de contenus concurrents.

Séparer les droits de gestion d'espace, lecture, écriture et partage de
l'attribution comptable. Le propriétaire comptable n'obtient pas de nouveaux
privilèges implicites. Les anciens propriétaires d'espaces conservent leurs
droits grâce à des grants explicites créés lors de la migration.

Les droits effectifs combinent les limites de l'espace, les droits du fichier
et les capacités du stockage. Une permission de fichier ne contourne pas
une restriction de l'espace. Les restrictions sur un sous-dossier ne donnent
pas la liste de ses voisins ; seuls les ancêtres nécessaires sont traversables.

Le partage d'un fichier peut constituer une autorisation limitée à ce fichier
pour un destinataire sans accès général à l'espace, si la politique de l'espace
permet ce partage. Les liens publics utilisent la même borne, restent
révocables et ne permettent aucune découverte des autres fichiers.

## 5. Répartition Drive / ST et administration web

### 5.1 Autorités

Drive possède connexions, espaces, droits sur les fichiers, état des opérations
et consommation observée. ST possède les plafonds applicatifs et leur révision.
Il ne stocke pas les secrets NAS/S3 et ne devient pas un explorateur de fichiers.

Les écrans Drive renvoient vers le réglage ST du bon espace ou utilisateur.
Les identités de ressources sont synchronisées avec des libellés lisibles.
Pas de deuxième formulaire écrivant des quotas locaux concurrents à ST.
Une indisponibilité ST est visible ; elle ne rétablit pas un quota infini.

### 5.2 Parcours administrateur dans Drive

1. **Connexions** : lister état, dernière vérification et espaces associés.
   Ajouter une connexion, saisir ses paramètres, tester, puis activer.
2. **Secrets** : remplacer un secret sans relire l'ancien ; tester la nouvelle
   génération, puis invalider proprement les caches et sessions concernés.
3. **Espaces** : choisir connexion, racine, nom et règle d'attribution ;
   prévisualiser les recouvrements et l'impact avant activation.
   Créer une racine absente depuis ce parcours lorsque les droits techniques
   l'autorisent ; pas de passage obligatoire par un terminal NAS.
4. **Accès** : rechercher utilisateurs/groupes, accorder les droits et
   prévisualiser ce qu'un utilisateur pourra voir, sans contourner ses droits.
5. **Quotas** : afficher utilisé, réservé, plafond et synchronisation ST ;
   accéder au réglage ST exact et revenir à l'espace.
6. **Opérations** : inventaire, maintenance, reclassification, transfert,
   erreurs, reprise et restauration autorisée vers une nouvelle destination.
7. **Désactivation** : interdire les nouvelles admissions, présenter les
   dépendances et refuser la suppression d'une connexion encore référencée.

Les changements courants sont pris en compte par web et workers sans édition
manuelle de fichier ni redémarrage global. La base porte une génération de
configuration ; les caches ne mélangent pas utilisateurs, connexions ou secrets.

Après import, chaque connexion a une source de configuration unique. Une
connexion conservée sous gestion externe est indiquée comme telle et ne peut
être réécrite silencieusement par le formulaire. Le passage sous gestion web
est explicite ; un ancien fichier ne reprend pas autorité au redémarrage.

### 5.3 Sécurité de la configuration

Réserver les connexions techniques et secrets à l'administrateur d'instance.
Un administrateur d'organisation gère uniquement ses espaces et ressources
autorisées. Réutiliser les rôles existants si leur portée est suffisante.

Préférer un chiffrement authentifié avec une bibliothèque maintenue déjà
installée, ou le gestionnaire de secrets existant s'il couvre l'écriture web.
La clé maîtresse reste montée hors base et hors interface. Une indisponibilité
de clé bloque l'utilisation concernée ; aucun stockage en clair de secours.
Documenter sauvegarde et rotation conjointes des secrets et clés.

Les tests de connexion sont bornés, réservés aux administrateurs techniques
et ne renvoient aucun identifiant sensible. Le homelab exige l'accès aux IP
privées : définir des destinations/réseaux autorisés plutôt qu'interdire
aveuglément le LAN. Refuser les schémas non prévus, chemins de secrets libres,
redirections et destinations hors politique, notamment les métadonnées cloud.
Vérifier TLS et proposer une autorité privée administrée, pas un contournement
global de la validation des certificats.

Prévoir protection CSRF selon l'authentification utilisée, validation serveur,
contrôle d'organisation et erreurs expurgées. Journaliser seulement l'action
administrative, son acteur, sa ressource et son résultat, sans secret ni contenu.

## 6. Quotas et capacités physiques

### 6.1 Périmètres

| Budget | Portée cible |
| --- | --- |
| Instance Drive | Plafond total de l'application, toutes organisations et familles |
| Organisation | Plafond commun de ses données |
| Utilisateur | Octets imputés à l'utilisateur dans tous ses espaces |
| Stockage/namespace | Données canoniques du périmètre, alias dédupliqués |
| Espace | Ressources comprises dans sa racine logique ou native |
| Utilisateur/stockage | Allocation de l'utilisateur sur ce périmètre |

Le plafond d'instance est distinct d'un plafond d'organisation. Dans le homelab
à une organisation, ils peuvent couvrir les mêmes données, mais leur sens
reste explicite. Ajouter ce scope dans le contrat ST si absent ; le migrer
à illimité sans modifier silencieusement les plafonds d'organisation existants.

Réutiliser le moteur de réservations et l'ordre déterministe des verrous.
Réserver dans tous les budgets applicables avant la croissance. Les limites
ne sont pas une somme d'allocations garanties : un plafond commun peut limiter
des quotas personnels plus élevés ou suralloués. L'interface explique ce cas.

Un même objet compte une fois dans un budget donné, même exposé par plusieurs
vues. Des espaces imbriqués peuvent chacun imposer un plafond sans doubler
le compteur d'organisation. Une modification par un lecteur devenu éditeur
ne change pas le propriétaire comptable du contenu existant.

### 6.2 Migration et synchronisation

Remplacer le scope S3 implicite par des identités explicites. Si une limite
`backend:s3` existe, la conserver comme budget de l'ancien stockage S3 lors
du rattachement, avec correspondance ST stable. Ne jamais l'effacer ni
l'appliquer arbitrairement à chaque nouvelle connexion.

Inclure espaces S3 et couples utilisateur/S3 dans découverte, métriques,
révisions et accusés d'application ST. Préserver exactement la convention
de l'interface ST : zéro historique illimité et blocage de croissance séparé.
Tester suppression d'une exception et retour à l'héritage.

Afficher la fraîcheur des compteurs et le statut de synchronisation. Une
réponse ancienne ne remplace pas une politique plus récente. La création d'un
espace produit son identité ST avant de prétendre que son quota est réglable.

### 6.3 Capacité extérieure

La capacité native connue limite les écritures mais ne remplace pas les
quotas Drive. Afficher séparément octets logiques, réservations applicatives,
copies temporaires et capacité remontée par le serveur.

Une capacité inconnue est « inconnue », pas infinie. S3 ne doit pas recevoir
une fausse capacité calculée depuis un bucket vide. Les alias ne permettent
pas d'additionner deux fois un même disque. Un plafond administratif supérieur
à une borne native fiable est signalé ou refusé selon la nature de cette borne,
sans présenter un espace libre instantané comme un quota permanent.

Les modifications NAS directes sont rapprochées périodiquement. En cas de
dépassement, conserver les données et refuser les nouvelles croissances Drive.

## 7. Interface commune d'accès aux ressources

Placer le choix S3/MountProvider dans la résolution de ressource côté backend.
Réutiliser les modules existants derrière cette interface ; ne pas encapsuler
tout le code dans un nouveau framework de stockage.

Contrat commun nécessaire :

- liste paginée des espaces visibles et état de chaque espace ;
- exploration d'une ressource, ancêtres et enfants ;
- référence stable, nom, type, taille, date, état et capacités autorisées ;
- création, import, renommage, suppression et restauration ;
- aperçu, téléchargement, édition et partage via liens autorisés ;
- lancement et consultation d'opérations asynchrones ;
- recherche de métadonnées et références de favoris/récents.

Des routes `/spaces/`, `/resources/` et `/storage-operations/` sont une
direction de nommage, à ajuster aux conventions du dépôt au lot L1. Le contrat
ne doit demander ni marque de provider ni bucket au frontend utilisateur.
Les endpoints techniques historiques restent des adaptateurs de compatibilité
tant que des liens, sessions d'éditeur ou clients SDK les utilisent.

La recherche commune utilise les métadonnées déjà présentes ou inventoriées,
avec pagination et filtrage des droits avant comptage et réponse. Elle ne
parcourt pas tous les NAS à chaque frappe. Ne pas exposer un résultat, un
nombre de résultats ou un extrait concernant un espace inaccessible.

Le rafraîchissement d'un dossier NAS peut consulter le provider ; les grandes
listes utilisent un index ou une pagination adaptée. Éviter le tri en mémoire
d'un dossier entier à chaque page. Publier la date de fraîcheur et distinguer
un résultat vide, un inventaire incomplet et un stockage indisponible.

## 8. Explorateur et parité fonctionnelle

Conserver `AppExplorer.tsx`, `AppExplorerInner.tsx` et les templates existants.
Faire converger ItemsBrowseExplorer et MountBrowseExplorer vers une source
commune de ressources et de commandes ; supprimer les duplications seulement
après raccordement. Aucun deuxième shell ni refonte graphique.

La page normale devient le point d'entrée des espaces autorisés. Un espace
personnel peut être ouvert par défaut. Les espaces partagés restent visibles
même si l'utilisateur n'en est pas le créateur : supprimer la dépendance du
catalogue au seul filtre historique `is_creator_me`.

| Parcours | Résultat cible |
| --- | --- |
| Navigation | Espaces nommés, arbre et fil d'Ariane communs |
| Création/import | Destination héritée de l'espace, progression existante |
| Aperçu/édition | Route de ressource commune, viewers existants et flux bornés |
| Recherche | Tous les espaces autorisés, filtre d'espace facultatif |
| Favoris/récents | Références des deux familles, résolution après renommage |
| Partage | Même parcours, droits bornés à la ressource et à la politique d'espace |
| Corbeille | Ressources récupérables ; distinction explicite d'une suppression définitive |
| Déplacement | Sélecteur de destination commun et suivi asynchrone |
| Erreurs | Quota, droits, synchronisation et indisponibilité compréhensibles |
| Mobile/clavier | Navigation, formulaires, focus et annonces accessibles |

Évaluer explicitement téléchargement de dossier, archives, extraction,
conversion, création de documents, miniatures, antivirus, WOPI, Collabora,
ONLYOFFICE, sélection multiple et glisser-déposer pour les deux familles.

L'extraction reste interdite si le provider n'est pas durci. Ne pas simuler
versions, corbeille ou verrouillage si la capacité manque. Réutiliser les
copies NAS conservées pour une restauration contrôlée lorsque possible ;
une suppression irréversible doit être présentée comme telle avant action.

Les anciennes routes `/explorer/mounts/...` redirigent vers une référence
résolue et autorisée. Ne pas supprimer les endpoints de liens publics ou
éditeurs pendant des sessions actives. Les anciens favoris, liens et accès
SDK font partie de la migration et de la recette.

## 9. Transferts et changement de stockage

### 9.1 Distinction des opérations

- Même ressource physique exposée par un alias : aucune copie ni libération
  de quota ; détecter le cas et refuser un déplacement sur soi-même.
- Même namespace avec déplacement natif sûr : réutiliser le journal existant.
- Connexions/familles différentes : copie en flux, publication validée,
  bascule logique puis nettoyage conditionnel de la source.
- Copie explicite : nouvelle ressource, charge et droits de destination.
- Déplacement explicite : continuité de la référence logique si elle est
  persistante ; changement de localisation seulement après publication sûre.

### 9.2 Journal durable

États minimaux : en attente, réservation, copie, vérification, publication,
nettoyage de source, terminé ; plus conflit, échec récupérable et annulé.
Étendre les journaux et mécanismes de reprise existants avant d'ajouter un
nouveau moteur de tâches. Les dossiers ont un manifeste paginé par fichier.

Conserver identités source/destination, versions observées, tailles, références
de quotas et étapes accomplies. Les essais répétés ne recopient pas un objet
déjà confirmé et ne suppriment jamais un fichier recréé au chemin source.

Pour S3 compatible, ne pas supposer qu'un ETag est une somme de contrôle de
contenu : le cas multipart est documenté par
[AWS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html).
Vérifier longueur, version/marqueur de publication et checksum quand
disponible ; sinon calculer en flux et relire la destination si nécessaire
avant une suppression irréversible. Une source modifiée pendant la copie
déclenche un conflit, y compris par un client NAS externe.

La vérification suivie d'une suppression par chemin ne suffit pas contre une
écriture externe concurrente. Utiliser une opération native conditionnée à
l'identité/version, ou une mise à l'écart sûre et contrôlée. Si le provider
ne peut garantir ce nettoyage, conserver la source et présenter le transfert
comme publié avec nettoyage en attente ; ne pas déclarer un déplacement
complètement terminé ni supprimer une source dont l'identité est incertaine.

### 9.3 Comptabilité, droits et sessions

Réserver la destination et les besoins temporaires sans libérer prématurément
la source. Un déplacement sans croissance logique peut être admis sous un
quota utilisateur plein si le moteur prouve la substitution atomique de la
charge ; la capacité physique temporaire et le budget de destination restent
nécessaires. Une copie supplémentaire consomme bien des octets supplémentaires.

Revérifier les droits et la politique juste avant publication et suppression.
Définir la nouvelle attribution selon la règle de destination et présenter
son impact. Les sessions d'édition actives empêchent la bascule du document
jusqu'à fermeture ou expiration confirmée du verrou ; pas d'ancien token
continuant à écrire dans un stockage devenu obsolète.

Préserver les références internes et liens lors d'un déplacement lorsque
leurs permissions restent valides. Les droits de destination priment :
ne pas élargir un partage ni déplacer silencieusement des droits incompatibles.
Présenter les liens concernés avant le transfert et révoquer explicitement
ceux qui ne peuvent subsister. L'ancien endpoint ne révèle pas la nouvelle
destination à un ancien destinataire révoqué.

Une annulation avant publication nettoie uniquement les objets temporaires
identifiés. Après publication, terminer ou réparer l'opération durable ; ne
pas simuler une annulation en supprimant aveuglément la destination.

## 10. Migration de l'installation existante

### 10.1 Préparation et simulation

1. Établir un état Git et documentaire de départ sans réinitialiser les
   changements locaux. Vérifier les services et les schémas réellement actifs.
2. Inventorier connexions du registre, Items, racines, grants, espaces,
   scopes ST, réservations, liens publics, favoris et opérations actives.
3. Produire une simulation sans écriture : correspondances de ressources,
   orphelins, ambiguïtés, volumes et politiques qui changeraient.
4. Sauvegarder ensemble bases Drive/ST, configuration, clés, S3 et NAS.
   Qualifier la restauration dans un environnement isolé.

### 10.2 Migration additive et idempotente

1. Ajouter les champs/tables nécessaires sans retirer les anciens contrats.
2. Créer la connexion représentant le S3 historique et rattacher les Items,
   sans changer UUID, clé, contenu, liens ou métadonnées d'édition.
3. Convertir le registre MountProvider en connexions persistantes avec
   correspondance stable. Les secrets peuvent conserver leurs références
   externes ; un import dans le coffre applicatif est une opération dédiée.
4. Rattacher les racines d'Items existantes à des espaces compatibles avec
   leurs droits. Ne pas forcer un arbre partagé multi-créateurs dans un espace
   personnel qui couperait les accès. Isoler les cas ambigus dans le rapport.
5. Préserver les UUID des espaces NAS et transformer leurs droits implicites
   en grants explicites. Conserver les namespaces physiques déjà qualifiés.
6. Initialiser références montées et métadonnées nécessaires au catalogue.
7. Recalculer les scopes par lots, rapprocher les compteurs et migrer les
   identités de ressources ST avec conservation des limites et révisions.

Les opérations longues utilisent des commandes/jobs reprenables, pas une
migration SQL contenant des appels réseau non bornés. Une seconde exécution
ne crée ni nouvel espace ni nouvelle charge pour les mêmes données.

### 10.3 Activation contrôlée

1. Activer d'abord lecture et comparaison sur la qualification isolée.
2. Prévoir une fenêtre sans nouvelles écritures pour la bascule réelle.
3. Drainer les tâches, sessions d'édition et autorisations d'upload anciennes
   ou attendre leur expiration ; traiter les publications incertaines.
4. Comparer droits, tailles et budgets avant/après ; résoudre les ambiguïtés.
5. Basculer ensemble web, worker et scheduler vers les nouveaux producteurs.
6. Activer le catalogue commun, vérifier une écriture sur chaque famille,
   les quotas ST et les liens historiques, puis ouvrir les utilisateurs.

Pas de double écriture sur ancien et nouveau modèle. Un drapeau transitoire
peut choisir l'interface, mais ne doit pas permettre deux autorités de droits
ou de comptabilité. Retirer les chemins morts après qualification.

### 10.4 Retour arrière

Avant nouvelles écritures, revenir au chemin compatible si le schéma et les
références le permettent. Après écritures sur plusieurs destinations, une
ancienne image ignorant ces destinations n'est plus un rollback sûr.
Utiliser alors une correction compatible ou la restauration cohérente
documentée. Ne jamais effacer une connexion pour « revenir au S3 par défaut ».

## 11. Lots d'implémentation

Tous les lots ci-dessous sont **à faire**. Un lot terminé exige son résultat
observable, son contrôle ciblé et la mise à jour du suivi en section 15.
Les dépendances indiquent l'ordre technique, pas une demande de délégation.

### L0 — État de reprise et inventaire des parcours

Dépendance : aucune.

- Lire les contrats, le présent plan et le rapport du socle ; vérifier le Git
  local et les services des deux dépôts sans redémarrage inutile.
- Cartographier tous les lecteurs/producteurs S3 et MountProvider, y compris
  jobs, proxy, uploads signés, conversion, antivirus et éditeurs.
- Relever bibliothèques de secrets disponibles et contrôles d'administration.
- Capturer les mesures de référence de navigation et transfert sur fixtures.

Sortie : carte des appels, données à migrer, risques concrets et fixtures
retenues. Aucun changement de stockage réel.

### L1 — Modèle, vocabulaire et contrat de ressources

Dépendance : L0.

- Définir schéma exact connexions/localisations/espaces/références et
  constraints ; préciser les racines logiques S3 et namespaces communs.
- Arrêter le contrat commun, les droits et les règles de partage/transfert.
- Écrire l'ADR et les migrations additives ; réutiliser les modèles existants.

Sortie : un Item et une entrée montée se résolvent par le contrat commun sans
changer leurs octets ni accorder de droits supplémentaires.

### L2 — Connexions persistantes et gestion des secrets

Dépendance : L1.

- Construire validation, coffre/références de secrets, import du registre,
  test de connexion, génération de configuration et invalidation des caches.
- Ajouter les endpoints administratifs avec portée d'instance/organisation.
- Conserver un amorçage local minimal et les références de secrets existantes.

Sortie : deux connexions utilisant des comptes distincts restent isolées ;
rotation et échec de test ne rendent aucun secret lisible et ne cassent pas
une opération déjà journalisée.

### L3 — Routage S3 multiple de bout en bout

Dépendances : L1, L2.

- Résoudre stockage/client/bucket/clé par localisation durable.
- Raccorder tous les parcours identifiés en L0, y compris reprise et
  nettoyage des multipart, URLs, proxy interne, WOPI et conversions.
- Vérifier CORS, signatures, URLs publiques et accès internes par connexion ;
  ne pas réutiliser le client ou la signature d'un autre endpoint.

Sortie : deux S3 indépendants servent des fichiers et éditions corrects ;
changer la destination des nouvelles créations ne déplace pas les anciennes.

### L4 — Espaces, droits et catalogue commun

Dépendances : L1, L2, L3.

- Généraliser les espaces, rattacher les racines et séparer droits/charge.
- Exposer découverte, exploration et résolution des ressources des deux
  familles ; appliquer les droits aux liens et endpoints historiques.
- Compléter l'inventaire de métadonnées et les références nécessaires.

Sortie : utilisateur personnel, lecteur de sous-dossier et groupe partagé
voient exactement leurs ressources, indépendamment du protocole.

### L5 — Quotas complets et contrat ST

Dépendances : L3, L4.

- Généraliser scopes, réservations et audits aux espaces/connexions S3.
- Ajouter le plafond d'instance et préserver les limites historiques.
- Synchroniser les ressources nommées dans ST, leurs métriques et ACK.
- Raccorder les quotas à chaque producteur, pas seulement à l'upload web.

Sortie : plafonds simultanés S3/NAS, exceptions et concurrence cohérents,
y compris lorsque ST est indisponible ou le NAS a été modifié directement.

### L6 — Migration répétable et mode de comparaison

Dépendances : L4, L5.

- Fournir simulation, backfill reprenable, contrôles d'intégrité et rapport
  de droits/quotas ; conserver les identifiants et liens historiques.
- Tester une base représentative : arbres partagés, Items à la corbeille,
  utilisateurs sans créateur, alias NAS et politiques déjà appliquées.

Sortie : deux passages donnent le même résultat ; aucune copie de contenu,
perte d'accès autorisé ou augmentation de privilèges inexpliquée.

### L7 — Explorateur unifié et compatibilité de navigation

Dépendances : L4, L6.

- Utiliser la page normale et le shell existant pour tous les espaces.
- Unifier routes, arbre, breadcrumbs, commandes, import et progression.
- Retirer la séparation Montages de la navigation produit ; conserver les
  redirections et liens compatibles.

Sortie : un même parcours utilisateur explore et modifie S3 et NAS sans
choix de backend ni perte de sélection/navigation.

### L8 — Recherche, favoris, partage et parité des fichiers

Dépendances : L5, L7.

- Unifier recherche de métadonnées, favoris/récents et références partagées.
- Raccorder les viewers et tous les parcours de la matrice de section 8.
- Vérifier révocation, accès partiel, vieux liens et éditeurs actifs.

Sortie : tableau de capacités renseigné, chaque fonctionnalité réalisable
raccordée ; les restrictions natives sont visibles et appliquées au serveur.

### L9 — Transferts entre espaces et stockages

Dépendances : L5, L6, L8.

- Étendre les opérations durables pour copies/déplacements inter-stockages,
  manifestes de dossiers, contrôles d'intégrité et reprise.
- Ajouter estimation/impact, destination autorisée, progression et conflits
  dans les composants non bloquants existants.
- Couvrir les modifications externes, annulations, réservations et liens.

Sortie : S3→S3, S3→NAS et NAS→S3 fonctionnent ; une coupure entre publication
et nettoyage ne perd aucun contenu ni ne double la charge finale.

### L10 — Administration web utilisable

Dépendances : L2, L5, L8, L9.

- Livrer les parcours connexions, espaces, accès, inventaire, maintenance,
  opérations et restauration décrits en section 5.
- Ajouter les liens contextuels vers ST et les libellés de ressources.
- Prévoir validation, confirmation d'impact, états asynchrones, erreurs,
  clavier, mobile et traductions existantes.

Sortie : après amorçage, un administrateur connecte un second stockage,
attribue un espace et configure son quota sans fichier ni console Django.

### L11 — Exploitation et performance

Dépendances : L6, L9, L10.

- Vérifier scheduler, reprise, caches, requêtes SQL et parcours de grands
  dossiers ; supprimer N+1, listes complètes et scans interactifs inutiles.
- Borner concurrence, mémoire, temps des tests de connexion et files de jobs.
- Documenter sauvegarde/restauration de toutes les destinations et du coffre,
  rotation, désactivation, rétention, capacité et diagnostic.

Sortie : état exploitable depuis le Web, limites mesurées et restauration
isolée cohérente. Aucune promesse d'optimisation sans mesure de référence.

### L12 — Recette finale et bascule documentée

Dépendances : L0 à L11.

- Exécuter la matrice minimale ci-dessous et les linters/types nécessaires.
- Corriger les échecs du chantier ; distinguer les erreurs préexistantes.
- Actualiser guides, architecture, contrat stockage et changelog produit.
- Retirer le code transitoire inutile ; conserver la compatibilité nécessaire.
- Rédiger le rapport final : livré, preuves, migration, limites et paramètres
  requis pour l'infrastructure réelle.

Sortie : critères de section 14 satisfaits en qualification. L'ouverture
réelle reste identifiée séparément si les paramètres d'infrastructure manquent.
Pas de commit, push, PR ou publication sans instruction explicite.

## 12. Validation minimale mais suffisante

Réutiliser les fixtures et tests du socle. Ajouter des scénarios aux frontières
modifiées, pas une suite par helper. Les contrôles ci-dessous sont des
scénarios regroupés ; ils peuvent couvrir plusieurs assertions utiles.

| Scénario | Preuve attendue |
| --- | --- |
| V1 — Migration | Simulation, deux exécutions, mêmes identités/contenus/droits/limites |
| V2 — Connexions | Deux S3 et deux comptes NAS isolés ; rotation sans fuite |
| V3 — Autorisation | Espaces privés/partagés, sous-dossiers, groupes, révocation et lien public |
| V4 — Quotas | Concurrence, instance/organisation/utilisateur/espace, alias, dépassement externe |
| V5 — Transfert/reprise | Directions S3/S3 et S3/NAS, coupure, source modifiée, destination pleine |
| V6 — Parcours fichier | Upload, lecture, aperçu, édition texte/WOPI et suppression/restauration |
| V7 — Navigateur | Explorateur et administration, recherche, favoris, quotas ST, mobile/clavier |
| V8 — Exploitation | Vrai scheduler, restauration isolée, audit sans écart, absence de fuite de secrets |

Pour V4, vérifier la suppression d'exception ST, les messages de limite et
l'absence de double charge lors d'une vue ou d'un transfert. Pour V5, injecter
la panne au point dangereux entre publication et suppression, pas seulement
avant que le job ait commencé. Pour V6, conserver les gardes WOPI lecture
unique et extraction fermée quand non autorisée.

Validation frontend/backend ciblée conformément à `AGENTS.md`, adaptée à la
demande de tests minimes : lint des zones touchées, types et tests concernés,
puis un parcours Chrome réel avec vue mobile. Pas de campagne E2E générale
trois navigateurs ni de répétition des suites réussies sans nouvelle raison.

Mesures courtes avant/après : requêtes par page, latence de navigation,
mémoire lors d'un fichier dépassant les buffers et durée de reprise. Utiliser
le même environnement et des volumes représentatifs. La mémoire ne doit pas
croître avec la taille du fichier ; la navigation ne doit pas scanner tous
les stockages ni tous les descendants d'un espace.

## 13. Risques et traitement prévu

| Risque | Traitement |
| --- | --- |
| Appel S3 restant sur le stockage global | Carte des producteurs L0, vérification à deux destinations L3 |
| Migration coupant un partage existant | Simulation des droits, espaces compatibles et cas ambigus bloqués |
| Alias ou préfixes comptés deux fois | Namespace qualifié, identité canonique, audit des scopes |
| Secret ou destination technique exposés | Réponses filtrées, coffre, droits techniques, contrôle des logs |
| Copie réussie suivie d'une panne | Journal durable, reprise idempotente, suppression conditionnelle |
| Document édité pendant une bascule | Verrou/session vérifiés, transfert différé et tokens revalidés |
| NAS modifié hors Drive | Identités natives, versions, inventaires complets, conflits explicites |
| Recherche lente ou révélant un espace privé | Index de métadonnées, pagination et filtrage d'autorisation serveur |
| Ancienne image utilisée après multi-S3 | Compatibilité documentée ou restauration cohérente |
| Nouvelle UI cachant une fonction perdue | Matrice de parité et contrôles de parcours |

## 14. Définition de terminé

- [ ] Tous les espaces autorisés apparaissent dans l'explorateur normal.
- [ ] Aucun parcours quotidien ne demande de choisir S3 ou MountProvider.
- [ ] Plusieurs connexions S3 et MountProvider fonctionnent simultanément.
- [ ] Chaque ressource conserve une localisation et une identité explicites.
- [ ] Administration courante possible sur le Web après amorçage.
- [ ] Connexions et secrets restent réservés aux administrateurs autorisés.
- [ ] Droits de dossier, groupes, partage et attribution sont séparés et sûrs.
- [ ] Quotas communs et par espace/stockage appliqués à tous les producteurs.
- [ ] Capacités physiques et quotas applicatifs restent distingués.
- [ ] Recherche, favoris, navigation et viewers couvrent les deux familles.
- [ ] Transferts, panne et reprise qualifiés sans perte ni double charge.
- [ ] Migration idempotente, liens historiques et retour arrière documentés.
- [ ] Scheduler et restauration vérifiés en environnement isolé.
- [ ] Matrice de parité et scénarios ciblés documentés avec leurs preuves.
- [ ] Guides actualisés et limites restantes déclarées explicitement.
- [ ] Statut local distingué de l'ouverture sur le NAS/IdP réels.

« Terminé » signifie ces critères vérifiés, pas seulement une interface
commune devant deux comportements encore incompatibles.

## 15. Suivi et reprise par Codex

| Lot | Statut | Preuve / remarque |
| --- | --- | --- |
| L0 | À faire | Inventaire de départ au lancement de l'implémentation |
| L1 | À faire | Modèle et contrat |
| L2 | À faire | Connexions et secrets |
| L3 | À faire | Routage multi-S3 |
| L4 | À faire | Espaces et droits |
| L5 | À faire | Quotas et ST |
| L6 | À faire | Migration |
| L7 | À faire | Explorateur |
| L8 | À faire | Parité et fonctions transversales |
| L9 | À faire | Transferts |
| L10 | À faire | Administration |
| L11 | À faire | Exploitation/performance |
| L12 | À faire | Recette et documentation |

À chaque reprise : lire ce tableau, le dernier rapport d'exécution et le diff
réel ; continuer le premier lot incomplet dont les dépendances sont satisfaites.
Ne pas repartir de zéro ni relancer les contrôles déjà probants sans motif.

Les futurs rapports d'exécution seront placés sous
`output/implementation/unified-storage-spaces/`, avec un état courant unique
et des preuves expurgées. Ne pas créer de sessions/secrets dans `docs/`.
Conserver ce plan comme référence de périmètre, corriger ses décisions si
le code impose un ajustement et tracer la raison dans le rapport.

Les paramètres du NAS, des S3 et de l'IdP réels seront recueillis avant leur
raccordement, au moyen des écrans sécurisés ou fichiers privés appropriés.
Aucun secret n'est demandé dans la conversation. Leur absence ne bloque
pas l'implémentation ni les contrôles synthétiques des lots L0 à L12.

## 16. Documents associés

- [Index des plans stockage](README.md).
- [Architecture actuelle](../../architecture.md).
- [Contrat stockage et flux](../../agent-storage-contract.md).
- [Exploitation actuelle Drive](../../homelab-storage-operations.md).
- [Plan de parité des aperçus](../../mounts-preview-correction-plan.md).
- [Contrat de test local](../../WorkDone/e2e/test-execution-contract.md).
- [Contrat navigateur](../../qa-browser-testing-contract.md).
- [Vocabulaire de domaine](../../../CONTEXT.md).
- [ADR du journal d'activité](../../adr/0001-product-activity-journal-not-audit.md).
- ST : `/root/Apoze/st-deploycenter/docs/homelab.md` et
  `/root/Apoze/st-deploycenter/docs/homelab-changes.md`.

Les guides opérationnels décrivent l'existant jusqu'à leur mise à jour pendant
l'implémentation. Le présent plan décrit la cible ; il ne remplace pas ces
procédures par anticipation.
