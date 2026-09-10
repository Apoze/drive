# Docs dans Drive — documents natifs, classement et droits unifiés

Date : 8 septembre 2026.
Statut : **implémenté, activé et qualifié sur le LAN le 9 septembre 2026**.
Autorisation actuelle : exécution complète demandée par le propriétaire,
avec tests minimaux et conservation de la pile existante.

Ce fichier est le plan canonique et le suivi du chantier. L'agent doit le
mettre à jour à chaque lot terminé et avant toute interruption. Une case
cochée signifie « implémenté et vérifié », jamais « code écrit seulement ».
Les choix ci-dessous décrivent le périmètre implémenté ; les preuves datées
figurent dans le suivi et le rapport final.

Lecture de reprise : [suivi](#1-suivi-et-reprise),
[résultat](#2-résultat-à-livrer), [architecture](#4-architecture-retenue),
[migration](#8-migration-des-documents-existants),
[lots](#10-exécution-de-a-à-z), [tests](#11-validation-minimale),
[clôture](#13-définition-de-terminé).

## 1. Suivi et reprise

| Lot | Objet | État | Preuve / prochaine action |
| --- | --- | --- | --- |
| D0 | État réel, sources et sauvegarde initiale | Vérifié | Sources, patches, bases, objets versionnés Docs et configuration sauvegardés ; zéro document existant. |
| D1 | Modèle documentaire et contrat d'accès | Vérifié | Modèles, migrations, ADR et contrats alignés ; PostgreSQL et migrations check réussis. |
| D2 | Délégation Docs/Drive et coédition autorisée | Vérifié | Délégation, commentaire/coédition, révocation 10,5 s, panne et bascule IdP réelle vérifiés. |
| D3 | Migration préparée et répétable | Vérifié | Cycle riche isolé avec descendants/ACL/invitation/corbeille et rejeux ; migration LAN de zéro document appliquée avec reçus privés. |
| D4 | Création, partage et cycle de vie communs | Vérifié | Création des deux Web UI, partages, invitation SMTP, déplacement/copie et purge réels. |
| D5 | Quotas des documents et exports vers Drive | Vérifié | Refus 413 puis reprise du brouillon ; PDF S3/NAS relus ; comptabilité remise à zéro après purge. |
| D6 | Parcours Web dans Drive et Docs | Vérifié | Ancien socle Mes fichiers rétabli et enrichi ; filtre réel, NAS, clavier/mobile et Office vérifiés. |
| D7 | Dossiers mixtes S3/NAS et opérations en lot | Vérifié | Dossier mixte S3–NAS–S3, ZIP, ancre renommée/disparue et récupération ; 21/201 Docs : 20/22 requêtes. |
| D8 | Bascule locale et exploitation | Vérifié | Images et clés déployées ; restauration isolée avec versions/médias/droits/quotas identiques ; guide livré. |
| D9 | Recette ciblée, nettoyage et livraison | Vérifié | 43 services actifs ; recette nettoyée, aucun job de recette inachevé ; rapport et index alignés. |

**État courant :** intégration activée sur le LAN le 9 septembre 2026.
La pile Keycloak/People/ST/Meet et les connexions S3/NAS sont conservées.
**Clôture :** D0–D9 vérifiés. Aucun travail fonctionnel restant dans ce périmètre.
Le [rapport final](../../../output/implementation/docs-drive-native-documents/validation-final.md)
référence les preuves et précise l’état Git local. Le journal conserve les
états historiques ; ils ne remettent pas la livraison actuelle en attente.
**Blocage identifié pendant la rédaction :** aucun pour préparer le chantier.
**Décisions produit encore nécessaires :** aucune pour le périmètre ci-dessous.
Les destinations des anciens documents non rapprochables seront présentées
dans l'aperçu de migration ; aucun propriétaire ou partage ne sera deviné.

Règles de suivi :

1. Lire ce plan, le contrat stockage et les changements intervenus depuis le
   dernier point de reprise. Ne pas relancer les lots déjà prouvés sans motif.
2. Après chaque lot, noter date, fichiers/révisions utiles, résultat du contrôle,
   éventuel écart et prochaine commande ou action concrète.
3. Utiliser les états `À faire`, `En cours`, `Bloqué`, `Vérifié` et
   `Livré`. Un blocage précise sa cause, les données préservées et la reprise.
4. Les preuves volumineuses vont, au début de l'exécution, dans
   `output/implementation/docs-drive-native-documents/`. Conserver un journal
   court ici ; ne pas créer un second plan concurrent ou recopier les logs.
5. Les sauvegardes, secrets, profils navigateur et identifiants de tests vont
   dans les emplacements privés ignorés. Le rapport public reste expurgé.
6. Une interruption ne vaut pas livraison. Avant d'arrêter, indiquer les jobs
   encore actifs, les migrations appliquées et l'état des services concernés.
7. Ne reprendre ni Grist ni un autre chantier par déduction. Ne pas déléguer
   automatiquement ce plan à des sous-agents.

### Journal du chantier

| Date | Étape | Résultat | Suite |
| --- | --- | --- | --- |
| 2026-09-08 | Préparation | Inspection du code local, des deux prototypes officiels et du rangement des plans. Rédaction uniquement. | Attendre l'autorisation d'exécuter D0–D9. |
| 2026-09-08 | D0 | Exécution autorisée. Branches locales `codex/docs-drive-native-documents` dans les deux checkouts. Sauvegardes privées sous `data/docs-drive-native-documents/baseline/`, manifestées et hachées. Docs : 0 document, 0 accès, 0 invitation. Aucun service arrêté. | D1, raccordement inactif jusqu'à qualification. |
| 2026-09-08 | D1/D2 | Modèles additifs et rôles commentateur ; ADR 0004 ; transport privé borné et preuves d'identité ; filtrage SQL des placements ; droits et médias Docs sans repli vers les ACL historiques. Contrôles ciblés : 4 PostgreSQL Drive, 1 PostgreSQL Docs, 1 contrat identité isolé. Migrations non appliquées aux bases LAN ; paquets runtime non remplacés ; intégration désactivée. | Achever D2 puis D3–D9. Ce socle ne constitue pas une livraison. |
| 2026-09-08 | D2/D4 | Listes Docs accueil/favoris/enfants/tous/recherche déléguées ; projection durable sans réseau sous verrou SQL, reprise de création, rejet des acquittements anciens ; commandes titre/corbeille/restauration/favoris/liens. Cinq scénarios Drive et trois Docs réussis sur bases isolées. Correction du parent direct après déplacement et notification des descendants ; garde contre suppression du pointeur avant purge native. | Achever partages, invitations, déplacements, copies et reprise UI ; D3/D5–D9 restent nécessaires. Aucun changement de configuration LAN ni activation. |
| 2026-09-08 | D4, reprise | Reçus de commande, clé d'idempotence et lecture de statut sans réexécution ; suppression rejouée une seule fois, statut inaccessible à un autre acteur. Migration additive Drive 0053 préparée, non appliquée sur le LAN. Parent direct également vérifié par le test existant de déplacement et d'activité de fichiers. | Raccorder les clés et le polling dans l'UI ; journaliser contenu initial/import et quota avant activation. 42 conteneurs en fonctionnement ; aucune bascule effectuée. |
| 2026-09-08 | D2/D4/D6, partages | Partages individuels/groupes délégués depuis les endpoints Docs, UUID People traduits vers les références locales Drive, pages internes bornées, héritage non modifiable depuis l'enfant et journal d'activité Drive. Commentateur et origine dossier affichables dans les composants Docs existants. Six scénarios Drive et quatre Docs vérifiés progressivement, lint ciblé et typage frontend avec les types Vitest réussis. | Invitations/demandes d'accès, notifications, récents et cycle de vie complet restent ouverts. La liste de membres frontend conserve son fonctionnement exhaustif par pages ; qualifier sa charge avec la recette UI. Aucun test navigateur du raccordement activé à ce stade. |
| 2026-09-08 | D5 | Quotas logiques du propriétaire, réservations et journaux de contenu/pièces jointes ; édition publique anonyme sans usurpation du propriétaire ; antivirus, réduction comptable et purge après confirmation, versions natives et médias partagés préservés. Écriture conditionnelle vérifiée sur le S3 Docs réel avec nettoyage intégral de l'objet de test. | Transferts de budgets, exports et recette LAN restent ouverts. |
| 2026-09-08 | D4/D5, imports | Préparation privée jusqu'à confirmation du contenu ; intention taille/digest et réservation initiale durables ; reprise des octets privés par le créateur réauthentifié et nettoyage des versions temporaires. Routes Web de commande/statut Drive et reprise Docs préparées. Huit scénarios Drive et sept Docs réussis sur PostgreSQL isolé. | Abandon explicite, clés/polling UI, invitations, mouvements/copies et D3/D6–D9 à terminer. Migrations Drive 0056 et Docs 0046 préparées seulement, aucun changement de configuration LAN. |
| 2026-09-08 | D6, création Web | Ouverture Docs séparée des viewers binaires, métadonnées/taille/date dans Drive, page de création Docs avec sélecteur paginé et clé persistée par utilisateur. Neuf scénarios backend Drive, deux régressions catalogue existantes, typages/lints frontend et sept cas de dispatch d'ouverture réussis. Contrôle Chromium bureau/mobile avec APIs simulées : dossier en lecture seule, répétition de clé après 503 et reprise après rechargement ; course de session/configuration corrigée. | Imports, menus Drive, sous-documents/reprises, partages complets, transferts et export encore incomplets. Aucune recette du raccordement réel et aucune activation. Rapport : `output/playwright/docs-native-create/report.md`. |
| 2026-09-08 | D4/D5, abandon | Abandon rejouable d'une création encore privée ; réservation conservée jusqu'à suppression native des versions puis règlement, sans supprimer un document actif. Route et bouton Docs ajoutés. Deux scénarios PostgreSQL dédiés passent ; tombstone de purge révisionné après perte d'acquittement. | Inclure le bouton dans la prochaine recette UI ; imports, sous-documents/reprises, mouvements/copies, D3/D7/D8/D9 restent ouverts. |
| 2026-09-08 | D4/D6, imports et reprise | Conversion initiale Yjs stable ; imports avec destination, sous-documents avec clé persistée, annulation avant réception et liste serveur des préparations. Invitations historiques intégrées conservées au login. Contrôles ciblés PostgreSQL, conversion, schémas et typages passent. UI import/reprise/annulation contrôlée avec APIs simulées, sans écriture LAN. | Achever D3, invitations, transferts/export, menus Drive et D7–D9. Le convertisseur doit être reconstruit avant activation. Suivi détaillé dans `output/implementation/docs-drive-native-documents/current-status.md`. |
| 2026-09-09 | D4/D6, invitations et demandes | Invitations explicites centralisées, reprise après erreur, expiration/nonce, révocation et envoi incertain testés. Jeton retiré avant le routeur ; acceptation et nettoyage vérifiés en Chromium simulé. Demandes Docs acceptées par commande Drive stable, notifications aux responsables actuels paginées (droits directs/groupes/hérités), sans ACL native. Migrations Drive 0057 et Docs 0047 seulement sur bases de test. Journal de notifications atomique avec la demande et reprise périodique sans renvoi incertain. | Menus de création depuis Drive raccordés au dossier courant, contrôlé dans Docs ; finir dossiers mixtes et qualification SMTP/UI réelle ; migration, copies/export, activation et recette réelle restent à faire. Intégration LAN toujours inactive. |
| 2026-09-09 | D2/D4–D7, reprise | Déplacements/ordre et quotas Docs, copies avec médias/descendants et reprises, inclusion dans les dossiers mixtes, réattribution lors d'un renommage natif, sélecteur de classement avec impact, actions mixtes et parcours commentateur corrigés. Tests ciblés PostgreSQL et localfs réussis ; détails dans le statut de reprise. | Poursuivre archives PDF, liens contextuels, récupération d'ancre, migration complète, qualification navigateur puis activation/restauration/recette D8–D9. Pile LAN conservée, intégration inactive. |

| 2026-09-09 | D2/D4–D7, finalisation | PDF isolé réel vérifié ; ZIP mixtes et téléchargements directs raccordés ; révision des Docs après finalisation de dossiers ; reprise de copie privée malgré édition ultérieure ; manifeste de 201 Docs réduit de 1 823 à moins de 30 requêtes. Liens contextuels S3/NAS, session protégée CSRF et révocation vérifiés en tests ciblés. | Finir la qualification Web/contextes/exports, migration apply/resume, bascule et restauration D8–D9. Raccordement toujours inactif sur le LAN. |

| 2026-09-09 | D0–D9, clôture LAN | Recette réelle, restauration et bascule IdP terminées ; explorateur historique rétabli avec S3/NAS/Docs ; purge intégrale des objets synthétiques, 43 services actifs. | Rapport final et guide d’exploitation livrés. Travail conservé localement, aucune publication distante de ce chantier. |

## 2. Résultat à livrer

Dernier contrôle du 9 septembre : remplacement/absence/panne d'ancre testés
avec Provider localfs et PostgreSQL isolé ; refus d'IO sous transaction vérifié.
Suppressions groupées des propriétaires et cascade de compte refusées sans
perte de droits. Recherche commune filtrée par espace corrigée et testée.
Ces contrôles ne constituent pas une activation ni une recette NAS LAN.

Un utilisateur ouvre son explorateur Drive habituel et y retrouve les fichiers
S3/NAS et les documents Docs. Il peut créer un document, l'ouvrir dans Docs,
le partager, le déplacer, le dupliquer, le mettre à la corbeille et le
restaurer. Les mêmes règles s'appliquent depuis Drive, depuis l'accueil Docs,
par une URL Docs enregistrée et dans une session de coédition déjà ouverte.

### Inclus

- Documents Docs vivants dans les dossiers Drive et dans les espaces adossés
  à MountProvider, dont le NAS actuel ; aucun deuxième explorateur.
- Titre, emplacement, arborescence des sous-documents, favoris, récents,
  recherche par titre, partage et cycle de vie cohérents.
- Rôles individuels et groupes People, héritage du dossier et restrictions
  d'espace ; conservation du rôle **commentateur** de Docs.
- Création depuis Drive et Docs ; les deux entrées passent par le même flux.
- Coédition, commentaires, historique et pièces jointes Docs existants
  conservés ; reprise d'une ancienne URL sans recréer le document.
- Migration de l'existant avec aperçu, conservation des propriétaires, groupes,
  liens et invitations ; aucune remise à zéro des données pour faciliter le lot.
- Copie réelle d'un document et de ses sous-documents ; export PDF vers un
  dossier S3 ou NAS autorisé. Les autres formats ne sont exposés que si
  l'export natif de la version Docs retenue les prend réellement en charge.
- Application des budgets aux documents intégrés, sans double comptage de
  leurs exports ni attribution fictive de leurs octets au NAS.
- Paramétrage courant et opérations utilisateur depuis le Web ; installation,
  secrets et sauvegardes via les mécanismes d'exploitation existants.
- Déploiement sur le LAN actuel, sauvegarde/restauration et courte recette
  réelle avec nettoyage des seuls objets de test.

### Frontières explicites

- Docs reste le moteur documentaire. Le contenu Yjs, les versions et les
  pièces jointes restent dans son stockage privé ; aucun fichier `.docs`
  artificiel, aucun document Office factice dans le NAS.
- Un document classé dans un dossier NAS est visible dans **Drive**. Il ne
  devient pas éditable en ouvrant ce dossier depuis un client SMB. Un export
  PDF placé sur le NAS est, lui, un fichier ordinaire accessible directement.
- Aucun remplacement de Collabora/ONLYOFFICE, aucun changement du format des
  fichiers existants, aucune synchronisation bidirectionnelle PDF/DOCX ↔ Docs.
- Aucun Find, Grist, chat, IA, enregistrement Meet, IdP supplémentaire permanent
  ou nouvelle infrastructure d'authentification dans ce lot.
- Pas de moteur universel de connecteurs ni de réservation globale pour toutes
  les futures applications. Le raccordement se limite à Docs et Drive.
- Exposition Internet, DNS et certificats publics restent différés. Conserver
  les accès LAN et ne pas ouvrir de nouveaux ports au routeur.

## 3. Point de départ vérifié

### 3.1 Livré avant ce plan

Le [socle identité](identity-access-catalogue-docs-plan.md) a livré Docs,
Drive, ST, People, les groupes, le catalogue et le changement d'IdP. Son
[rapport](../../../output/implementation/suite-identity-access-catalogue/validation-final.md)
précise que les documents Docs ne sont pas encore classés dans Drive.
Meet est [livré séparément](meet-visio-core-integration-plan.md).

Au moment de la rédaction, 42 conteneurs sont actifs, dont les 16 services du
projet Drive et les 6 services Meet. C'est un constat de services démarrés,
pas une nouvelle recette de fonctionnement. Aucune relance n'a été faite.

| Dépôt local | Base constatée | Précaution |
| --- | --- | --- |
| `/root/Apoze/drive` | `cfa564e048c1c7a5ad74c713c3c4fd57bb708850` | Nombreuses modifications antérieures, notamment stockage et identité ; le SHA seul ne représente pas le code exécuté. |
| `/root/Apoze/docs` | `3c1275c88da39abb71e045c7deaba3844ca9ac49` | 33 entrées de modifications locales au relevé ; identité, groupes et collaboration déjà adaptés. |

Identités Git constatées :

- Drive `origin` : `https://github.com/Apoze/drive.git`, lecture/écriture.
- Drive `upstream` : `https://github.com/suitenumerique/drive.git`, lecture
  seule, URL de push désactivée.
- Docs `origin` local : `https://github.com/suitenumerique/docs.git`, lecture
  seule, URL de push désactivée. Ce checkout n'est pas configuré pour publier
  sur une fork Apoze. Vérifier l'existence d'`Apoze/docs` avant de préparer
  sa publication ; ne jamais pousser les adaptations sur le dépôt officiel.

La branche de rédaction est `codex/plan-docs-drive-native-documents` dans
`Apoze/drive`. Son nom ne signifie pas que les modifications précédentes lui
appartiennent. Ne pas réinitialiser ou nettoyer les worktrees au démarrage.

### 3.2 Points de raccordement locaux

Chemins Drive relatifs à ce dépôt ; chemins Docs relatifs à `/root/Apoze/docs`.
Ils sont des points de lecture identifiés, pas une obligation de tous les modifier.

| Domaine | Points de départ |
| --- | --- |
| Ressources et arbre Drive | `src/backend/core/models.py` : `Item`, `ItemAccess`, `Invitation`, `StorageResource`, `StorageSpace`, `StorageGrant`. |
| API commune et capacités | `src/backend/core/api/storage_resources.py`, `api/viewsets.py`, `services/storage_resources.py`, `services/storage_access.py`, `services/storage_spaces.py`. |
| Quotas et opérations | `services/storage_quota.py`, `storage_copy_job.py`, `storage_folder_copy.py`, `storage_item_tree_move.py`, `storage_tree_transfer.py`, `storage_transfer_impact.py`, `tasks/item.py`. |
| Explorateur commun | `features/explorer/components/app-view/AppExplorer.tsx` et `AppExplorerInner.tsx`, sous `src/frontend/apps/drive/src/`. |
| Adaptateurs et parcours | `features/storage/api.ts`, `ResourceCollection.tsx`, `StorageTransferModal.tsx`, `features/drivers/types.ts`, `implementations/StandardDriver.ts`, création et partage existants. |
| Identité et délégation | `src/packages/suite-identity/suite_identity/access.py`, `api_authentication.py`, `resource_server.py` ; exemple d'utilisation dans `src/backend/wopi/services/access.py`. |
| Docs : données et accès | `src/backend/core/models.py`, `core/choices.py`, `core/api/permissions.py`, `serializers.py`, `viewsets.py`, `core/external_api/`. |
| Docs : collaboration | `core/services/collaboration_services.py`, `src/frontend/servers/y-provider/src/api/collaborationBackend.ts`, `servers/hocuspocusServer.ts`. |
| Docs : interface | `src/frontend/apps/impress/src/features/docs/doc-share/`, `doc-management/`, `docs-grid/`, `doc-header/`, pages de création et d'édition. |
| Installation existante | Drive `docker/suite/prepare_local.py`, `package_identity.py`, `provision_docs_storage.py`, [installation](../../installation/suite-identity-and-docs.md) et [exploitation](../../operations/suite-identity-access.md). |

Constats déterminants :

- `Item` n'a actuellement que les types `file` et `folder`. Il possède déjà
  arbre, droits, invitations, liens, corbeille et favoris réutilisables.
- `StorageResource` indexe les objets montés et certaines références de liens
  conservées. Ce n'est pas un registre documentaire universel à réécrire.
- L'API et le frontend communs exposent deux adaptateurs, `item` et `mount`.
  Les opérations de fichiers présument souvent une localisation physique.
- Docs conserve une arborescence de documents pouvant eux-mêmes contenir des
  sous-documents. Une migration qui n'importe que les racines perdrait du sens.
- Docs possède `reader`, `commenter`, `editor`, `administrator`, `owner`.
  Ne pas supposer une équivalence automatique avec les choix Drive.
- La collaboration Docs réévalue déjà l'autorisation avec des baux plafonnés
  à 15 secondes. Réutiliser ce mécanisme au lieu d'ajouter un surveillant.
- Les pièces jointes Docs peuvent être référencées par plusieurs documents ;
  copie, purge et comptabilité doivent respecter ces références.
- Le S3 privé Docs est distinct du stockage Drive. Son isolement corrige une
  incompatibilité précédemment reproduite ; ne pas le fusionner par commodité.

### 3.3 Prototypes officiels examinés

Relecture par API GitHub le 8 septembre 2026, sans écriture vers l'amont :

| Source | État et révision inspectés | Utilisation proposée |
| --- | --- | --- |
| [suitenumerique/drive #790](https://github.com/suitenumerique/drive/pull/790) | Brouillon ouvert, non fusionné ; tête `81aa0e64186c6c826aceafc104fb62e058bfc575`. | Inspiration pour les références documentaires dans l'arbre et le cycle de vie ; adapter au stockage unifié local. |
| [suitenumerique/docs #2548](https://github.com/suitenumerique/docs/pull/2548) | Brouillon ouvert, non fusionné ; tête `b59778f657a5240b2d8b6db3c6596e91ce89b256`. | Inspiration pour la délégation à Drive ; conserver le partage Web et migrer les ACL avant de changer d'autorité. |

Ne reprendre ni leur authentification de démonstration par subject/email,
ni la suppression immédiate des ACL/invitations Docs, ni leur remappage
Keycloak, ni leur absence de recette. Réexaminer leurs changements au D0,
sans rattrapage global des dépôts. L'[inventaire initial](../../../output/research/2026-09-06-lasuite-inventory-and-homelab-integration.md)
reste une recherche datée, distincte de la livraison.

## 4. Architecture retenue

### 4.1 Une autorité par responsabilité

| Responsabilité | Autorité après bascule |
| --- | --- |
| Authentification | IdP OIDC configuré, sans dépendance métier à Keycloak. |
| Identité durable et groupes | People et les associations du socle livré. |
| Accès aux applications, politiques | ST ; l'accès à Docs ne donne aucun droit automatique à un document. |
| Référence, titre, emplacement, partage et corbeille | Drive pour les documents intégrés. |
| Contenu, coédition, commentaires, versions et médias | Docs. |
| Publication d'un export S3/NAS | Services de stockage Drive et leurs réservations. |

Les anciennes ACL Docs restent présentes pendant la migration, mais ne sont
plus une deuxième autorité une fois un document intégré. Un refus ou une panne
de Drive ne déclenche jamais un repli permissif vers ces ACL historiques.
Le mode autonome Docs n'existe que pour les documents explicitement non migrés
pendant la transition ; il n'est pas sélectionné à partir d'une erreur réseau.

### 4.2 Réutiliser l'arbre et les permissions Drive

Solution de départ : ajouter un type d'`Item` explicite `docs` et une relation
`DocsBinding` un-à-un portant l'UUID Docs et l'état du raccordement. Réutiliser
`ItemAccess`, `Invitation`, favoris, liens et opérations d'arbre. Ne créer ni
registre générique d'applications ni moteur parallèle de permissions.

Contrat minimal, à traduire en migrations additives au D1 :

- `Item.id` est la référence stable Drive. `DocsBinding.document_id` est
  unique et immuable ; les anciens UUID Docs et leurs URLs sont conservés.
  Les deux UUID peuvent être différents ; ne pas les rapprocher implicitement.
- Un `Item.docs` n'a ni `filename`, ni clé S3 Drive, ni état d'upload de fichier.
  Son contenu ne doit jamais passer par `file_key`, WOPI ou un Provider.
- Dans un dossier S3 logique, le document utilise le parent `Item` existant.
  Il hérite de sa politique de classement ; cela ne localise pas ses octets
  dans le bucket du parent.
- Dans un dossier monté, la racine documentaire possède un ancrage explicite
  vers le `StorageResource` du dossier et un contexte d'espace validé. Ses
  sous-documents réutilisent l'arbre `Item`. Aucun miroir complet du NAS en
  dossiers `Item`, aucun faux fichier S3 représentant le montage.
- L'ancrage monté et le parent physique logique S3 sont exclusifs. Poser les
  contraintes d'intégrité nécessaires et refuser cycles et auto-parentage.
  L'accès doit être évalué depuis l'ancrage réel, y compris sur les routes
  historiques `items/` qui ne doivent pas contourner la restriction d'espace.
- Une même ressource visible par plusieurs espaces n'est ni dupliquée ni
  facturée plusieurs fois. Son contexte de navigation n'est pas son identité.
- Les routines d'attribution automatique, d'inventaire, de réparation et de
  purge des fichiers doivent reconnaître ce type avant de rechercher une clé
  physique ; elles ne doivent pas lui attribuer le backend S3 par défaut.
- Prévoir une révision monotone de métadonnées/cycle de vie, un état de
  provisioning et les identifiants d'opérations idempotentes. Les titres,
  chemins ou dates de modification seuls ne sont pas des clés de reprise.
- Les références nécessaires à une purge ou à une restauration sont protégées
  des suppressions en cascade prématurées. Conserver une trace de purge
  permettant de rejeter une ancienne notification de restauration.

Si une contrainte réelle du modèle empêche ce choix, documenter l'obstacle
au D1 et retenir la plus petite extension typée satisfaisant ces invariants.
Ne pas profiter de ce chantier pour remplacer tous les modèles stockage.

### 4.3 Sous-documents et parcours depuis Docs

Drive devient l'autorité du parent de chaque document. Docs garde les relations
nécessaires à son moteur, synchronisées depuis les révisions Drive. Un
sous-document est un vrai document, pas une pièce jointe ni une copie de texte.

- Conserver ordre, arbre et liens internes lors de la migration.
- Dans Drive, afficher la racine à son emplacement ; ses sous-documents sont
  accessibles par développement du nœud ou action « Sous-documents », sans
  polluer les listes de racines avec tous les descendants.
- Ouvrir un document ouvre l'éditeur Docs. Une action distincte parcourt ses
  enfants ; navigation clavier et accès mobile doivent rester explicites.
- Dans Docs, créer, renommer, déplacer, partager, dupliquer et supprimer passent
  par les opérations Drive. La grille Docs et la barre latérale montrent les
  métadonnées autorisées actuelles, sans reconstruire un arbre concurrent.
- Une création depuis l'accueil Docs propose la destination Drive ; réutiliser
  la dernière destination si elle est encore autorisée, sinon le choix normal.
- Refuser les fichiers ordinaires comme enfants d'un document Docs. Les pièces
  jointes internes continuent d'employer le mécanisme natif Docs.

### 4.4 Capacités et opérations de fichiers

Ajouter une représentation explicite `docs` au contrat de ressources et aux
adaptateurs frontend. La couche UI utilise les capacités retournées par l'API,
pas la marque du stockage ni une déduction à partir du nom du fichier.

Pour `docs`, désactiver **sur le serveur également** : upload binaire Drive,
`upload-ended`, accès direct S3/NAS, `/text/`, aperçu binaire, conversion Office,
WOPI et duplication par copie d'objet. Exposer à la place ouverture Docs,
duplication documentaire et export explicite. Garder les comportements
`file`/`folder` existants sans changement de défaut.

Le partage et la suppression d'un dossier, les actions en sélection multiple,
la recherche, les collections, le SDK et les exports de dossiers doivent tous
traiter le nouveau type : le masquer côté UI ne sécurise pas une ancienne API.
Fusionner fichiers et documents avant tri/pagination, avec une clé de tri
stable. Ne pas ajouter les documents après une page de fichiers déjà paginée :
cela fausserait compteurs, recherche, ordre et déduplication entre espaces.

## 5. Droits, échanges interservices et révocation

### 5.1 Calcul des droits

Une lecture authentifiée d'un document intégré exige : identité durable valide,
accès courant à Docs **et** Drive, ressource active et droit documentaire
effectif. Les comptes de secours restent réservés à l'administration de
récupération ; aucun droit de contenu implicite pour un opérateur ST/People.

Le rôle effectif combine les droits individuels, groupes et héritages selon
les règles Drive existantes, puis applique les plafonds de l'espace : lecture,
écriture, partage, maintenance et désactivation. Un partage documentaire ne
doit pas contourner un espace interdisant ce partage. Un administrateur
d'espace n'acquiert pas implicitement la propriété de tous les contenus.

À la migration, vérifier aussi que les bénéficiaires existants ont les deux
accès applicatifs requis. Signaler leur éventuelle absence dans l'aperçu ;
ne pas réécrire silencieusement les politiques ST pour réussir la bascule.

| Rôle documentaire | Comportement attendu |
| --- | --- |
| Lecteur | Lire le document et ses médias autorisés ; exporter si autorisé ; aucune écriture. |
| Commentateur | Droits natifs de commentaire Docs, sans mutation arbitraire du contenu ; ne jamais convertir ce rôle en éditeur. |
| Éditeur | Coéditer et gérer le contenu autorisé ; aucun droit implicite de redistribution ou de transfert de propriété. |
| Administrateur du document | Gérer les accès et les opérations permises par le propriétaire et l'espace ; pas d'auto-promotion propriétaire. |
| Propriétaire | Administrer le document ; préserver au moins un propriétaire et le plafonnement de l'espace. |

Les groupes sont identifiés par leur identifiant People stable et la projection
locale correspondante. L'email sert à l'invitation, jamais à associer deux
comptes interservices. Les droits hérités restent distingués des droits directs
dans le dialogue de partage. Le retrait d'un groupe ne supprime pas un droit
individuel indépendant encore valable.

La conservation du commentateur inclut une vérification des voies réelles
d'écriture de Docs. Si le protocole de coédition actuel ne distingue pas
correctement commentaire et édition, corriger la frontière serveur avant
d'annoncer cette distinction ; un bouton désactivé ne suffit pas.

### 5.2 Liens, invitations et accès public

- Documents nouveaux privés par défaut. Une création ou une sélection ne
  change jamais implicitement leur visibilité en `public`.
- Conserver les liens existants et leurs restrictions pendant la migration.
  Les URLs Docs restent valables mais font appliquer la décision Drive.
- Une ouverture publique délibérément autorisée n'exige pas un compte ; elle
  est limitée au document/sous-arbre et au rôle du lien. Elle ne donne accès
  ni aux frères, ni aux groupes, ni aux historiques privés, ni au NAS parent.
- Distinguer le lien public porté par le document du lien temporaire d'un
  dossier parent. Ce dernier doit transporter son contexte borné jusqu'à Docs,
  aux médias et à la collaboration ; connaître seulement l'UUID du document
  ne suffit pas à recréer cette autorisation.
- Expiration, révocation et retrait des droits du créateur du lien sont
  appliqués selon les règles du type de lien existant. Ne pas transformer
  tous les liens historiques en un lien perpétuel de document.
- Inviter depuis Docs ou Drive crée une seule invitation, avec le même rôle,
  état et circuit de notification ; pas de double email ou de double grant.
- Conserver les demandes d'accès Docs. Leur acceptation doit écrire le droit
  dans Drive, sans réactiver une ACL Docs locale parallèle.

### 5.3 Contrat interservice minimal

Réutiliser les outils HTTP, secrets et identités disponibles. Aucun broker,
Menshen, nouveau service d'authentification ou transfert brut de session IdP.
Deux clients étroits suffisent : Drive vers le contenu/cycle de vie Docs,
Docs vers le classement et l'autorisation Drive.

Exigences pour les routes internes, à nommer sous un préfixe dédié :

- Credential privé distinct par sens et usage lecture/mutation, rotation
  documentée, authentification en temps constant, routes et actions autorisées
  explicitement. Ne pas ouvrir toute l'API sous une clé d'administration.
- Le serveur émetteur construit le contexte à partir de sa session vérifiée :
  UUID principal People, organisation, preuve/epoch de session, opération et
  ressource. Il ignore tout en-tête utilisateur prétendant fournir ces valeurs.
- Le destinataire valide le consommateur, les identifiants, l'organisation,
  l'usage et la fraîcheur ; il retrouve son compte local par le principal et
  relit les droits actuels. Un subject d'un autre client OIDC n'est pas réutilisé
  comme identité universelle.
- Les preuves humaines ne sont jamais prolongées par la délégation. Pour une
  mutation utilisateur, exiger une preuve réellement issue de la requête ;
  ne pas utiliser le secours destiné aux jobs internes pour en fabriquer une.
- Une opération asynchrone a un identifiant durable, un acteur, un but précis,
  une destination et des références observées. Les reprises vérifient droits,
  générations et révisions ; une nouvelle preuve peut être requise avant
  publication. La purge d'une suppression déjà autorisée suit la politique
  de rétention, sans prétendre être une nouvelle session humaine.
- Les requêtes utilisateur ne fournissent jamais d'URL interne arbitraire.
  Les origines Docs/Drive sont configurées, les redirections contrôlées ; pas
  de SSRF ni d'ouverture vers un hôte reçu dans le document.
- Timeout court, réponse limitée, pagination/batch borné ; erreurs 401/403/404,
  conflit 409, quota et indisponibilité 503 distingués sans fuite de données.
- La décision d'accès Drive ne rappelle pas Docs : pas de boucle réseau ni
  d'appel distant pendant un verrou SQL. Les lectures de catalogue Drive
  n'exigent pas un appel Docs par ligne.
- Aucun jeton, cookie ou contexte de délégation dans les URL, logs ou rapports.
  Une éventuelle navigation par code à usage unique doit l'échanger aussitôt,
  nettoyer l'URL et empêcher sa journalisation ; préférer les sessions natives.

### 5.4 Surfaces d'autorisation à raccorder

Inventorier les appelants avant de modifier le calcul partagé. Couvrir :
listes, recherche, arbre, favoris/récents, détail, contenu formaté/brut,
versions, commentaire, upload de pièce jointe, média privé et export, APIs
externes, duplication et jobs de nettoyage. Pas de titres ni de compteurs
de documents refusés dans une liste paginée.

La connexion et les réévaluations Hocuspocus doivent obtenir les capacités
déléguées. Un retrait d'édition force une reconnexion en lecture seule ou une
fermeture ; aucune nouvelle trame d'écriture acceptée après expiration du bail.
Une panne du contrôle d'accès ne renouvelle pas un bail positif.

Conserver la borne du socle : refus lié à People/ST en **120 secondes maximum**
pour les sessions ouvertes, sous réserve des flux déjà acceptés. Pour une ACL
Drive directement retirée, viser le prochain contrôle Docs, bail au plus
15 secondes. Le TTL total prend le minimum des preuves, politiques, liens
et baux restants ; les caches successifs n'ajoutent pas leurs durées.
Mesurer ces délais lors de la recette, sans prétendre rappeler des octets
déjà téléchargés ou effacer une copie locale du navigateur.

## 6. Cycle de vie, dossiers et reprise

### 6.1 Opérations documentaires

| Action | Contrat de réussite |
| --- | --- |
| Créer | Vérifier destination et budget, réserver une référence/opération, créer Docs une seule fois, confirmer la liaison. Un timeout se résout par consultation de l'opération, sans deuxième document. |
| Renommer | Drive porte le titre et sa révision ; Docs le reflète. Une notification plus ancienne ne remplace pas le titre récent. |
| Déplacer | Conserver UUID, contenu, favoris et anciennes URL ; recalculer héritage et imputation. Présenter l'impact sur les accès avant changement sensible. |
| Partager | Écrire les droits dans Drive, invalider les décisions concernées et faire réévaluer la coédition. Préserver le dernier propriétaire sous concurrence. |
| Dupliquer | Nouveau document et nouvelle référence, contenu/médias autonomes, sous-documents copiés avec correspondance des nouveaux UUID ; aucun partage public copié par défaut. |
| Mettre à la corbeille | Refus d'accès immédiat dans Drive, puis état Docs convergent. Inclure les descendants et invalider les sessions ; conserver les octets jusqu'à purge. |
| Restaurer | Réutiliser les UUID et l'état connu ; vérifier le parent, les droits, les limites et les révisions. Parent absent : choix d'une destination autorisée, sans recréation aveugle du NAS. |
| Purger | Après rétention et revalidation, supprimer le contenu et les médias devenus sans référence, confirmer, puis libérer les charges correspondantes. Répétition sans effet supplémentaire. |

Utiliser PostgreSQL et les workers Celery existants. Ajouter seulement le
journal durable nécessaire au cycle documentaire ; réutiliser les journaux
de copie/publication pour les exports. Un `transaction.on_commit()` isolé
n'est pas une garantie de livraison après crash.

États minimaux : préparation, attente distante, actif, corbeille, purge en
cours, purgé, erreur récupérable. Les données et la transition à transmettre
sont enregistrées dans la même transaction locale. Les workers traitent par
lots bornés, avec reprises espacées, sans monopoliser les workers de fichiers.
Une opération rejouée avec un autre contenu sous la même clé est un conflit.

Une panne Docs ne fait pas disparaître les fichiers de Drive. Un document
déjà référencé reste classé avec un état d'indisponibilité ; aucune réponse
« sauvegardé » ou « supprimé définitivement » sans confirmation correspondante.
Un document créé mais non confirmé reste privé et récupérable, pas abandonné
dans une corbeille invisible. Une purge ne peut être annulée par une ancienne
notification de restauration.

### 6.2 Déplacements et copies de dossiers mixtes

Le manifeste d'un dossier distingue fichiers, dossiers et documents Docs.
Les documents ne passent jamais par la boucle de copie d'octets S3/Provider.

- Déplacement S3 ↔ S3, S3 ↔ NAS et NAS ↔ NAS : les octets des fichiers suivent
  le flux existant ; les références Docs changent d'ancrage au point de
  confirmation de ce flux. UUID Docs et Drive conservés.
- Avant confirmation, vérifier que l'arbre, les droits et le budget observés
  n'ont pas changé. Tant que la destination n'est pas validée, la source
  reste l'emplacement faisant autorité.
- Copier un dossier duplique les documents qu'il contient ; pas de liens
  involontaires vers des contenus encore appartenant à la source.
- Une sélection comprenant parent et descendant ne lance pas deux opérations
  sur le même document. Une opération partielle affiche ses succès/échecs et
  reprend sans dupliquer les parties confirmées.
- La suppression d'un dossier monté et la suppression logique de ses documents
  sont coordonnées dans le journal. Une suppression externe au NAS ne donne
  jamais instruction de purger les contenus Docs.
- Un export ZIP de dossier contenant Docs propose un export PDF des documents,
  avec noms déterministes et chemins sûrs. Si un export échoue, le résultat
  n'est pas présenté comme complet ; aucune omission silencieuse. La copie
  documentaire conserve un document vivant, tandis que le ZIP contient un export.

### 6.3 Modifications directes sur le NAS

L'utilisateur conserve ses accès SMB directs. L'ancrage documentaire suit
l'identité native du dossier lorsqu'elle est démontrable, jamais son seul nom.

- Renommage/déplacement reconnu par l'inventaire : mettre à jour l'ancrage
  et réévaluer les restrictions du nouvel emplacement avant de l'exposer.
- Dossier supprimé, remplacé au même chemin, identité incertaine ou sortie du
  périmètre autorisé : suspendre l'héritage depuis cet ancrage, conserver
  le document et proposer une récupération à son propriétaire habilité.
- Distinguer indisponibilité du NAS et disparition démontrée. Ne pas classer
  tout un espace comme supprimé après une réponse réseau incomplète.
- Les anciennes métadonnées d'inventaire ne prouvent pas l'identité courante
  d'un parent. Valider l'observation nécessaire à l'accès/déplacement, de façon
  bornée ; une preuve absente ou périmée ne doit pas accorder l'accès à un
  dossier recréé au même chemin.
- Une copie faite depuis un client SMB copie les fichiers du NAS, pas les
  documents virtuels classés dans Drive ; aucune duplication automatique
  par comparaison de noms.

## 7. Quotas et export sans déplacement du stockage Docs

### 7.1 Imputation des documents intégrés

Le type `docs` n'est pas une échappatoire aux quotas des espaces/utilisateurs.
Réutiliser `StorageQuota`, les réservations atomiques et l'attribution stable
existantes, avec une source documentaire explicite. Étendre leur référencement
si nécessaire ; ne pas déclarer le S3 Docs comme un MountProvider ni attribuer
fictivement ses écritures à une connexion SMB.

- Une charge documentaire désigne un document et ses octets logiques courants
  sérialisés, plus les pièces jointes qu'il référence. Elle s'applique aux
  budgets utilisateur, espace et organisation concernés.
- Les limites physiques d'une connexion NAS/S3 Drive ne sont pas consommées
  par le contenu stocké dans Docs. Le stockage physique Docs possède ses
  propres limites d'exploitation et de rétention.
- Séparer également les anciens plafonds de compatibilité `backend:s3` des
  budgets logiques partagés : Docs ne devient pas un fichier S3 Drive pour
  faciliter les agrégats. Vérifier qu'aucun total ne compte à la fois la
  nouvelle charge documentaire et son reflet de métadonnées dans `Item`.
- L'attribution ne change pas avec le dernier éditeur. Un déplacement entre
  espaces réserve la croissance dans la destination avant de libérer la source.
  Les budgets des espaces ancêtres s'appliquent, comme pour les fichiers.
- Une même pièce jointe n'est comptée qu'une fois dans un document ; référencée
  par deux documents autonomes, elle appartient aux deux charges logiques,
  même si le stockage physique optimise ses octets. Documenter cette mesure.
- La corbeille reste comptée jusqu'à purge confirmée. Les anciennes versions
  ne sont pas additionnées au quota logique courant ; leur consommation
  physique et leur rétention sont mesurées séparément et explicitement.
- Un export est une nouvelle ressource de fichiers, facturée une seule fois
  dans sa destination. Il ne supprime pas la charge du document vivant.
- Ne pas sommer périodiquement des métriques en prétendant prévenir les
  dépassements : réservations, compteurs et règles doivent bloquer l'écriture.
- Si les données initiales dépassent un quota existant, les importer sans
  suppression ni augmentation automatique ; interdire la croissance et
  permettre les opérations de réduction/récupération prévues.

### 7.2 Chemins d'écriture à couvrir

Création/import Docs, mises à jour de contenu HTTP, sauvegarde issue de la
coédition, upload et rattachement de pièce jointe, duplication, restauration
de version et déplacement d'imputation doivent utiliser le même garde de quota.

Réserver avant d'accepter une croissance durable. Utiliser tailles maximales
et corps bornés pour le contenu Yjs ; pour les fichiers, réservation préalable
et politique d'upload bornée, puis vérification de la taille publiée. Une
pièce jointe provisoire n'est exposée qu'après validation et scan existant.

Le serveur de coédition et l'UI ne doivent pas annoncer une sauvegarde réussie
sur un contenu refusé par le stockage/quota. À saturation : afficher l'erreur,
stopper les nouvelles écritures concernées, préserver le dernier état durable
et permettre de récupérer les changements locaux non enregistrés. Ne pas
supprimer un contenu accepté avant révocation sous prétexte de purger un buffer.

Pour les crashes entre écriture Docs et confirmation Drive, garder l'identifiant
d'opération et la version publiée ; interroger ce résultat avant toute reprise.
Ne libérer une réservation périmée qu'après résolution de son écriture distante.
Une panne Drive empêche les nouvelles croissances non réservées, pas la
libération aveugle des réservations actives.

### 7.3 Export vers Drive

Réutiliser l'export natif Docs et le sélecteur de destination autorisée ; ne
pas employer le SDK historique qui rend une source publique pour la sélectionner.
Capturer une révision exportée, autoriser la lecture, réserver la destination,
produire/transférer le fichier avec mémoire bornée, puis confirmer la
publication par taille et contrôle d'intégrité adapté. Préserver la source.

Le flux peut utiliser un temporaire privé borné si l'exporteur exige un fichier
seekable. Nettoyer succès, erreur et interruption ; ne pas exposer le bucket
Docs au navigateur Drive ou au compte NAS. Une révocation, une modification
de destination ou un refus de quota avant publication doit empêcher le succès.

## 8. Migration des documents existants

La migration est une commande native documentée, avec `plan`, `apply`,
`status` et `resume` ou options équivalentes. Pas de script SQL manuel comme
seule procédure. La lecture préalable est sans mutation et les reprises
utilisent les mêmes identifiants de lots.

### 8.1 Aperçu

Premier outil disponible dans le dépôt Docs, après migrations additives sur
la base de qualification :

```sh
python manage.py docs_drive_migration plan --output /chemin/prive/inventory.jsonl
python manage.py docs_drive_migration status --output /chemin/prive/inventory.jsonl
```

Le dossier doit être privé (0700), le fichier est créé en 0600 sans écrasement.
L'inventaire parcourt les métadonnées SQL et toutes les métadonnées de versions
du bucket privé Docs ; aucun contenu, commentaire ou objet S3 n'est lu.
Les références aux commentaires/fils sont conservées sans leur corps.
Les références aux pièces jointes sont parcourues par curseur SQL, pas par
chargement d'un tableau complet en mémoire.
Le reçu final contient les compteurs et le SHA-256 des lignes précédentes.
Un export interrompu sans reçu n'est pas utilisable. `status` vérifie le reçu.
Les associations principales/groupes manquantes, racines sans propriétaire et
parents manquants sont signalés pour les documents encore natifs ; le créateur
n'est jamais promu automatiquement en propriétaire.
**Ce premier aperçu n'est ni un point cohérent gelé, ni une autorisation
d'activation. Les commandes apply/resume et la comparaison des droits restent
à implémenter.** Ne pas utiliser cet inventaire comme sauvegarde de contenu.

Inventorier sans journaliser les contenus : nombre de documents actifs/en
corbeille, arbre, créateurs et propriétaires, ACL directes/héritées, groupes,
liens, invitations et demandes d'accès, favoris/récents, versions, médias et
consommation. Relever les références sans correspondance et les cycles/anomalies.

| Situation | Traitement |
| --- | --- |
| Propriétaire avec principal People et compte Drive associés | Proposer un dossier privé « Documents Docs » dans son espace personnel existant ; UUID du dossier mémorisé pour les reprises. |
| Document d'équipe / plusieurs propriétaires | Préserver les propriétaires et l'arbre ; destination commune explicite dans le manifeste, sans choisir le premier email trouvé. |
| Sous-document avec droits hérités | Importer son arbre et conserver la distinction direct/hérité ; ne pas accorder chaque droit d'ancêtre comme droit direct perpétuel. |
| Principal/groupe non rapprochable | Signaler précisément dans l'aperçu et garder le document sous son ancien régime jusqu'à résolution ; aucune association par nom. |
| Invitation non acceptée | Conserver adresse destinataire, rôle, échéance et état ; achever son acceptation via le rattachement vérifié du socle. |
| Document public ou « authentifié » | Préserver le comportement explicitement existant ; ne pas le placer sous une destination qui élargit davantage ses droits. |
| Document en corbeille | Conserver UUID, date et état ; ne pas le faire réapparaître comme actif pendant l'import. |
| Document sans propriétaire valide ou parent incohérent | Mettre en attente de récupération ; aucun propriétaire administrateur automatique. |

L'aperçu compare les droits effectifs avant/après pour les populations
concernées, y compris commentateurs, groupes et invités. Il distingue les
changements hérités d'un déplacement intentionnel des écarts de migration.
Une différence non expliquée bloque l'activation du lot concerné.

### 8.2 Application

1. Sauvegarder bases, stockage Docs et configurations ; tester la lisibilité
   du manifeste. Prendre le point cohérent sous suspension contrôlée des
   mutations Docs concernées, en laissant les autres applications disponibles.
2. Créer les liens et métadonnées Drive en état préparé, sans activer une
   seconde autorité. Les contraintes d'unicité permettent de répéter ce passage.
3. Importer arbre, grants, invitations, états, favoris et attribution de quota.
   Réconcilier les versions observées ; une modification depuis l'aperçu impose
   sa mise à jour, pas un écrasement.
4. Vérifier accès et références par petits lots. Garder les anciennes ACL Docs
   tant que la comparaison n'est pas terminée ; elles restent un historique
   de migration, pas un mode de secours lorsque Drive refuse.
5. Activer le lot par une transition explicite versionnée. Réinitialiser les
   sessions de coédition et caches concernés ; reprendre les écritures après
   validation. Les mutations concurrentes sont bloquées/rejetées proprement,
   jamais écrites dans les deux autorités.
6. En fin de bascule, rapprocher les totaux, garantir zéro document oublié et
   conserver la table de correspondance. Aucun document courant ne doit rester
   en régime autonome sans être annoncé comme blocage de livraison.

Ne pas supprimer les tables d'ACL Docs dans ce chantier. Leur retrait pourra
être un nettoyage ultérieur lorsque le retour arrière n'en dépendra plus.

## 9. Interface et administration

| Surface | Travail attendu |
| --- | --- |
| Création Drive | « Document Docs » dans le menu existant ; destination visible, double clic/retry sans duplication. |
| Explorateur | Icône et type explicites, même sélection et navigation ; pas de taille de faux fichier, ni spinner d'upload. |
| Ouverture | Éditeur Docs et retour au dossier Drive ; ouverture par ancienne URL avec mêmes droits. |
| Docs | Menus de classement/partage conservés et raccordés à Drive ; pas de suppression du dialogue de partage comme dans le prototype. |
| Partage | Personnes/groupes, rôle commentateur, héritage expliqué, invitations et liens ; refus de l'espace visible sans jargon de stockage. |
| Déplacement/copie | Sélecteur existant ; aperçu des accès et de l'imputation, progression et reprise des opérations longues. |
| Corbeille | Documents et sous-documents restaurables ; distinction entre suppression logique et purge confirmée. |
| Favoris/récents/recherche | Référence unique, droits filtrés avant pagination ; titres actualisés depuis Docs comme Drive. |
| Export | « Exporter vers Drive », dossier et nom proposés, retour sur le fichier créé ; aucun changement de visibilité. |
| Administration Drive | État du raccordement, erreurs de migration et opérations à reprendre ; action de récupération réservée aux personnes habilitées. |
| ST/People | Réutiliser politiques, quotas et groupes existants ; aucune nouvelle console parallèle. |

Les actions quotidiennes ne nécessitent pas Django shell. Les informations
d'installation, secrets, URL internes et chemins de stockage restent hors des
parcours utilisateur. Réutiliser le style, les composants, traductions et
modèles d'erreurs existants. Vérifier clavier, focus des dialogues et un
affichage mobile ; aucun redesign.

## 10. Exécution de A à Z

Les étapes sont séquentielles. Valider au fil des lots les quelques frontières
à risque, puis une recette transversale à la fin. Ne pas relancer toute la
suite de tests après chaque fichier.

### D0 — Préserver l'état réel et préparer les sources

- [x] Lire les `AGENTS.md` applicables et les documents routés stockage/identité.
- [x] Relever les services/images/configurations Compose réellement utilisés,
      l'état des bases, les origines LAN et la santé de Drive/Docs/People/ST/Meet.
- [x] Capturer les diffs et fichiers nouveaux préexistants dans les deux
      checkouts ; ils font partie du point de départ fonctionnel.
- [x] Préparer les branches locales de travail sans perdre ces changements.
      Toute fork distante ou publication suit l'autorisation Git applicable.
- [x] Réexaminer seulement les deux prototypes pertinents et figer les
      versions choisies ; conserver les adaptations Apoze déjà livrées.
- [x] Établir la sauvegarde privée initiale et un petit manifeste de données
      de référence ; ne pas utiliser un ancien rapport comme recette actuelle.

**Sortie :** état initial récupérable, chemins/configurations constatés, aucun
service remplacé ni travail précédent perdu. Aucun test complet à ce stade.

### D1 — Poser le modèle et les contrats

- [x] Tracer les appels d'arbre, permissions, partages, purge et transferts
      afin de repérer toutes les hypothèses `file`/`folder`.
- [x] Implémenter le type documentaire, la liaison unique, l'ancrage monté,
      les contraintes et les révisions ; migrations additives uniquement.
- [x] Définir les capacités et le rôle commentateur sans augmenter les droits
      des fichiers ordinaires. Réutiliser les modèles d'accès existants.
- [x] Fixer les opérations internes et leurs états idempotents ; documenter
      le choix court dans un ADR suivant le numéro disponible.
- [x] Étendre `CONTEXT.md` et le contrat stockage aux documents vivants et aux
      exports ; conserver la distinction physique/virtuelle.

**Sortie :** modèle migrable, invariants validés sur PostgreSQL, aucun nouveau
document exposé sur le LAN avant raccordement de l'autorisation.

### D2 — Déléguer l'autorisation de bout en bout

- [x] Ajouter les deux clients internes et leurs routes limitées, secrets
      distincts, identité durable, preuves et erreurs contrôlées.
- [x] Faire converger le calcul des droits Docs vers Drive pour les documents
      intégrés, y compris routes directes, anciennes APIs et médias privés.
- [x] Adapter les listes par batch/pagination ; ne pas filtrer seulement les
      éléments de la page après avoir divulgué le nombre total.
- [x] Raccorder la réévaluation de coédition existante et la révocation des
      liens ; interdire le secours vers les anciennes ACL en cas de panne.
- [x] Vérifier les cas acteur usurpé, autre organisation, ancien epoch,
      absence de preuve, expiration et rôle commentateur.

**Sortie :** refus critiques vérifiés avec un petit scénario API/collaboration.

### D3 — Préparer la migration

- [x] Implémenter l'aperçu, les correspondances, la reprise et la comparaison
      des droits et états décrits au §8.
- [x] Exercer la migration deux fois sur le même petit jeu isolé : mêmes UUID,
      même nombre de documents/droits et aucun doublon de facture/invitation.
- [x] Préparer le manifeste de l'existant local ; identifier sans les masquer
      les propriétaires, groupes ou destinations à résoudre.
- [x] Documenter comment annuler la préparation sans retirer de données Docs.

**Sortie :** migration répétable et rapport d'impact lisible ; bascule réelle
différée au D8, après les fonctionnalités nécessaires.

### D4 — Livrer les opérations communes

- [x] Création depuis les deux applications, renommage et sous-documents.
- [x] Partage individuel/groupe, invitations/demandes d'accès et liens.
- [x] Déplacement de document, duplication avec médias et descendants.
- [x] Corbeille, restauration et purge, y compris tâches planifiées existantes.
- [x] Journal transactionnel, reprises et rejets des révisions obsolètes ;
      vérifier un timeout après succès distant et une reprise après arrêt.

**Sortie :** cycle complet cohérent et récupérable, sans double écriture d'ACL.

### D5 — Brancher quotas et export

- [x] Intégrer la source documentaire aux budgets et réservations existants,
      avec séparation des plafonds physiques et logiques.
- [x] Couvrir tous les chemins de croissance Docs, y compris coédition,
      pièces jointes, duplication et restauration de version.
- [x] Préserver les changements non sauvegardés en cas de refus ; état UI
      exact et reprise après libération/augmentation de quota.
- [x] Export PDF vers S3 et NAS via les publications gouvernées existantes.
- [x] Vérifier une concurrence de deux croissances au plafond et un crash
      avant confirmation : aucune surallocation ni libération erronée.

**Sortie :** budget réellement imposé et export lisible, sans copie publique
temporaire ni octets attribués au mauvais backend.

### D6 — Raccorder les interfaces existantes

**Complément demandé par le propriétaire le 9 septembre 2026 :** vérifier
que l'explorateur unifié conserve l'interface travaillée de l'ancien
« Mes fichiers » S3. Le propriétaire soupçonne la reprise de l'ancien
« Montages » ; ce diagnostic reste à confirmer par inspection et comparaison.

- [x] Retrouver dans l'historique Git les deux explorateurs avant les espaces
  virtuels, puis comparer leurs composants et parcours avec l'explorateur actuel.
- [x] Relever les finitions perdues : navigation, présentation des fichiers,
  sélection, menus, raccourcis, tri, recherche, états de chargement et mobile.
- [x] Si la régression est confirmée, rétablir le socle et les finitions de
  l'ancien « Mes fichiers » dans l'explorateur canonique unique ; conserver
  S3 et MountProvider derrière leurs adaptateurs et capacités.
- [x] Y préserver toutes les nouveautés déjà livrées : espaces virtuels,
  droits/quota, transferts, aperçus, viewers et documents Docs natifs.
- [x] Vérifier dans le navigateur un dossier S3 et un dossier NAS mixtes,
  avec un contrôle ciblé bureau/clavier/mobile ; aucune nouvelle campagne
  complète de tests uniquement pour cette remise en cohérence.

Ce complément fait partie du chantier à terminer. Le traiter après les
vérifications d'intégrité en cours et avant la clôture D9 ; ne pas ouvrir un
second explorateur ni reprendre un autre chantier par déduction.

- [x] Ajouter l'adaptateur documentaire au shell commun et aux routes de
      ressources ; menu de création, icône, ouverture, retour et enfants.
- [x] Raccorder les dialogues Docs à Drive ; conserver l'ergonomie native.
- [x] Uniformiser favoris, récents, recherche, partage et corbeille.
- [x] Réutiliser les sélecteurs et modales de transfert/export ; rendre les
      erreurs, limites et opérations longues compréhensibles.
- [x] Vérifier les capacités des actions en masse et des parcours SDK pour
      qu'une ressource Docs n'atteigne jamais une API binaire par erreur.
- [x] Ajouter les traductions, vérifier clavier et largeur mobile.

**Sortie :** parcours principal utilisable depuis le Web, sans shell manuel.

### D7 — Couvrir le NAS et les dossiers mixtes

- [x] Intégrer les références Docs aux manifestes de transfert, copie,
      suppression et export de dossiers, sans recopier leur contenu comme fichier.
- [x] Faire suivre les ancrages au point de confirmation des transferts ;
      protéger les références lors des suppressions de lignes temporaires.
- [x] Traiter les modifications externes NAS : déplacement reconnu, disparition,
      remplacement au même chemin et indisponibilité.
- [x] Rendre les documents sans parent récupérables sans restaurer de droits
      périmés ni attribuer un propriétaire automatiquement.
- [x] Vérifier dossiers volumineux par un relevé borné de requêtes/page et de
      mémoire ; supprimer les appels Docs par ligne et les chargements d'arbre
      entier qui seraient introduits par ce lot.

**Sortie :** comportement S3/MountProvider cohérent sur les scénarios réellement
utiles ; aucun fichier NAS existant transformé ou supprimé pour ce contrôle.

### D8 — Basculer et documenter l'exploitation

- [x] Mettre à jour seulement les images/services modifiés et leurs paramètres,
      sans démarrer de doublons ni remplacer les scripts Drive/ST existants.
- [x] Réaliser le point de sauvegarde cohérent, l'aperçu final et la migration
      locale ; conserver les identifiants et relever le résultat par lot.
- [x] Reprendre les écritures, contrôler les opérations en attente et la
      fraîcheur des politiques ; conserver les autres services disponibles.
- [x] Exercer une restauration du petit jeu intégré dans des bases/volumes
      isolés, y compris liaison Drive/Docs, pièces jointes et imputation.
- [x] Livrer les commandes de statut, reprise, réparation, mise à jour et
      retour arrière dans un guide `docs/operations/docs-drive-native-documents.md`.
- [x] Actualiser les guides d'installation concernés et les changelogs des
      dépôts réellement modifiés.

**Sortie :** intégration active sur l'environnement local complet et reprise
prouvée. Un simple statut Docker `Up` ne valide pas ce lot.

### D9 — Qualifier, nettoyer et clôturer

- [x] Exécuter la recette ciblée du §11 une fois sur le code final.
- [x] Corriger les échecs du périmètre et rejouer uniquement les cas concernés.
- [x] Nettoyer documents, fichiers exportés, liens, invitations, réservations,
      sessions, téléchargements et conteneurs temporaires du test, par manifeste.
- [x] Vérifier les données conservées, la pile complète et l'absence de jobs
      de migration/purge non résolus ; conserver les sauvegardes privées utiles.
- [x] Compléter les critères C1–C10, le journal et le rapport final expurgé.
- [x] Préparer une livraison Git limitée aux forks Apoze et aux changements
      identifiés ; publier seulement si l'autorisation le couvre. Sans cette
      autorisation, indiquer explicitement « livré localement, non publié ».
- [x] Mettre à jour l'index des plans et les liens du chantier précédent pour
      que le classement Docs ne soit plus annoncé « restant » après livraison.

**Sortie :** résultat utilisable, preuves retrouvables et état Git exact ; aucune
annonce « tout terminé » avec une bascule, migration ou recette encore à faire.

## 11. Validation minimale

Priorité explicite du propriétaire : **tests ciblés, aucun dispositif de tests
supplémentaire disproportionné**. Réutiliser pytest/Django, tests frontend et
Playwright déjà présents. Pas de nouveau framework, grosse batterie de fixtures,
scan de chaînes dans le code ou script qui déclare une fonction correcte parce
que son nom existe dans un fichier.

### 11.1 Petit socle automatisé

Regrouper les cas voisins dans quelques tests des services/contrats touchés,
paramétrés sur S3 et montage lorsqu'ils partagent réellement la même logique.

| Groupe de contrôle | Risque qui justifie le test |
| --- | --- |
| Droits et délégation | Direct/indirect, commentaire, refus d'un tiers, limites d'espace, usurpation/expiration, ancien lien et absence de fallback. |
| Cycle et concurrence | Création rejouée, résultat distant perdu, révision obsolète après purge, dernier propriétaire, déplacement avec droits modifiés. |
| Budget et publication | Deux écritures au plafond, reprise après crash, compteur unique, refus de publication et fichier exporté valide. |
| Migration | Rejouer sans doublons ; ancien UUID, sous-documents, ACL, invitation et corbeille conservés. |

Préférer compléter les tests existants, quelques scénarios d'intégration et
une vérification de routage frontend si nécessaire. Les cases de cette table
sont des risques à couvrir, pas un objectif de créer une classe par ligne.
Exécuter sur des bases isolées, jamais la commande de test destructive contre
les bases de l'environnement local.

### 11.2 Une recette navigateur transversale

Chromium, deux sessions autorisées et une session refusée ; pas de campagne
complète sur trois navigateurs. Réutiliser la même petite arborescence et
quelques documents synthétiques.

1. Connexion habituelle via l'IdP actuel. Dans un dossier S3, créer Docs,
   coéditer à deux, commenter avec le rôle dédié, insérer une petite pièce
   jointe et rouvrir via l'ancienne URL après un redémarrage ciblé.
2. Partager au groupe People, distinguer un droit individuel, retirer l'accès
   puis mesurer le refus HTTP et la fermeture/réduction de droit WebSocket.
   Vérifier aussi une lecture privée de média refusée et une panne Drive
   courte qui ne renouvelle pas le bail Docs.
3. Déplacer le document et un petit dossier mixte vers un dossier NAS de test,
   puis retour ; conserver références, contenu et droits attendus. Renommer
   un parent NAS de test directement puis simuler sa disparition/remplacement.
   Vérifier l'ancrage ou le refus/récupération prévu.
4. Dupliquer avec un sous-document et une pièce jointe, exporter en PDF vers
   S3 et NAS, relire l'export, essayer une croissance au quota, mettre à la
   corbeille, restaurer puis purger les seules copies de test.
5. Exercer un lien public explicitement créé pour le test puis révoqué, sans
   rendre la source privée publique par sélection. Vérifier le périmètre
   d'un lien de dossier et son expiration sur Docs/médias.
6. Contrôle court de conservation : fichier S3 et fichier NAS existants en
   lecture, ouverture Office existante, catalogue ST/People/Docs/Meet ; pas
   de nouvelle recette exhaustive de Meet ou du stockage.

Un affichage mobile et la navigation clavier sont vérifiés dans ce même
parcours. La perte de droits est vérifiée sur la vraie API et le canal de
collaboration, pas seulement par disparition d'un bouton.

### 11.3 IdP, restauration et performance

- La nouvelle délégation ajoute une frontière : réaliser une bascule ciblée
  Keycloak → Authentik → Keycloak en environnement isolé, sur un document
  intégré et ses droits. Réutiliser le dispositif du socle, conserver principal,
  UUID et classement ; refuser l'ancienne preuve. Aucune campagne des quatre
  applications ni Authentik permanent.
- La restauration utilise le même petit jeu déjà créé : bases Drive/Docs,
  stockage Docs, correspondances et quota. Vérifier l'ancien lien et l'absence
  de double traitement des jobs restaurés ; invalider sessions et délégations.
- Un seul relevé comparatif avec deux tailles de dossier synthétique suffit
  pour détecter requêtes réseau par ligne, chargement d'arbre entier ou tri
  incorrect entre fichiers et documents. Pas de banc de charge permanent ni
  de promesse de performance non mesurée.

### 11.4 Commandes et preuves

Au D0, relever les commandes natives exactes de pytest, lint et build des deux
versions locales. Pendant les lots : lint sur les fichiers modifiés et tests
affectés. Avant D9 : migrations `check`/absence de migration oubliée, build/type
check des frontends touchés et tests ciblés concernés par les derniers diffs.
Un full n'est lancé que si une modification transversale non couverte ou un
échec le justifie ; en noter la raison. La demande de tests minimaux prévaut
sur un lancement mécanique de toutes les suites historiques.

Conserver quelques captures, résultats HTTP expurgés, temps de révocation,
résultat de reprise et inventaire de nettoyage. Aucun contenu utilisateur,
cookie ou secret dans `output/`. Aucun test recherchant des chaînes dans les
fichiers de code. Les vérifications de documentation/liens et de secrets
avant publication ne sont pas des tests de fonctionnement du produit.

## 12. Sauvegarde, retour arrière et livraison Git

### Données et exploitation

Sauvegarder ensemble, au même point logique, bases Drive et Docs, stockage
privé Docs avec les versions nécessaires, table de liaison, réservations/jobs
et paramètres privés. Conserver les configurations/identités People/ST/IdP
de référence ; les autres applications ne sont pas des cibles de restauration
par défaut de ce chantier.

Le retour arrière doit distinguer :

- **Avant activation :** retirer la préparation identifiée, conserver les
  données et ACL natives Docs, arrêter les seuls jobs de ce chantier.
- **Après activation sans nouvelle écriture :** restaurer le point cohérent
  et les versions applicatives compatibles, puis invalider les baux/sessions.
- **Après activité utilisateur :** suspendre les mutations concernées,
  sauvegarder l'état actuel et réconcilier les changements ; ne jamais remettre
  un vieux dump en écrasant les nouveaux documents ou les droits retirés.

Une ancienne image Docs ne doit pas être redémarrée seule avec les ACL locales
historiques encore présentes : elle pourrait réaccorder des droits révoqués.
Un rollback applicatif doit préserver le garde de délégation ou être exécuté
en maintenance avec restauration coordonnée. Les révisions/epochs restaurés
ne peuvent rendre de vieux credentials valables de nouveau.

Le guide d'exploitation doit couvrir : diagnostic sans secret, état du
raccordement, contrôle des opérations en attente, reprise d'un document
orphelin, réservation bloquée, rotation des credentials, mise à jour,
sauvegarde et restauration. Aucun `docker prune` ni suppression globale de
volumes pour clôturer ce travail.

### Git

Respecter les modifications préexistantes et les règles de publication des
dépôts. Ne pas faire de consolidation globale des branches par simple effet
de ce plan. Pas de commit, push ou PR pendant la rédaction.

Pour une future publication autorisée :

1. Vérifier les forks `https://github.com/Apoze/drive` et
   `https://github.com/Apoze/docs`, leurs branches de base et remotes exacts.
2. Garder `https://github.com/suitenumerique/drive` et
   `https://github.com/suitenumerique/docs` en lecture seule, push désactivé.
   Aucune PR, publication ou autre écriture vers ces dépôts officiels.
3. Inclure les adaptations antérieures nécessaires au fonctionnement réel
   sans les attribuer à tort à ce seul lot ; examiner les actions CI héritées
   avant de publier une fork Docs.
4. Appliquer les gates Git locaux : pas de `fixup!`, changelog, gitlint,
   secrets, lint/tests ciblés appropriés et conformité du diff.
5. Rapporter dépôt/branche poussés et, s'il existe une PR autorisée, base,
   tête et URL complète. L'état « propre » se rapporte au périmètre identifié,
   jamais à un worktree contenant encore des changements non expliqués.

## 13. Définition de terminé

| Critère | Preuve requise | État |
| --- | --- | --- |
| C1 — Conservation | Comptes, NAS, S3, Office et services de suite conservés ; documents existants rapprochés. | Vérifié |
| C2 — Explorateur | Création, ouverture, classement, sous-documents, favoris/récents/recherche sur S3 et NAS depuis le même Web UI. | Vérifié |
| C3 — Une autorité | ACL et cycle de vie Drive appliqués par Docs ; pas d'écriture concurrente des droits ni repli permissif. | Vérifié |
| C4 — Refus et révocation | Individus/groupes, commentaire, espace, liens, médias et coédition contrôlés ; délais observés consignés. | Vérifié |
| C5 — Cycle complet | Déplacement/copie de dossiers mixtes, corbeille/restauration/purge et reprise sans doublon ni perte. | Vérifié |
| C6 — Quotas et export | Croissance documentaire bornée, compteurs cohérents, PDF S3/NAS relus et aucune attribution physique fictive. | Vérifié |
| C7 — Migration | Aperçu, application rejouable, anciens liens/UUID/arbre/invitations conservés ; zéro cas oublié silencieusement. | Vérifié |
| C8 — Indépendance IdP | Un document intégré et ses droits conservés lors de la bascule isolée ; ancien credential refusé. | Vérifié |
| C9 — Exploitation | Restauration cohérente exercée, reprise documentée, secrets privés et versions connues. | Vérifié |
| C10 — Clôture | Tests ciblés réussis, objets de test nettoyés, stack local conservé, plan/index/rapport/Git exacts. | Vérifié |

Livrables finaux attendus : ce plan rempli, ADR court, guide d'exploitation,
documentation des contrats/API ajoutés au plus près des deux applications,
manifeste de déploiement et rapport final dans
`output/implementation/docs-drive-native-documents/`.

Le rapport final nomme les éventuelles limites observées. Aucun critère
nécessaire ne peut être reclassé discrètement en « amélioration future » pour
déclarer le chantier fini.
