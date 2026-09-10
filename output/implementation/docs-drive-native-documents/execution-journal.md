# Journal historique — Docs dans Drive

Les états ci-dessous sont datés. Le statut courant est dans
[current-status.md](current-status.md) ; ce journal ne pilote pas une reprise.

# Docs dans Drive — état de reprise

**En cours, non livré. Intégration désactivée sur le LAN.**
Plan canonique : `docs/plans/suite/docs-drive-native-documents-integration-plan.md`.
Branches locales Drive/Docs : `codex/docs-drive-native-documents`.
Aucun commit, push, publication ou changement upstream effectué.

## Environnement préservé

- Pile Drive, Keycloak, NAS, People, Docs, ST et Meet conservée.
- `DOCS_DRIVE_ENABLED=False` sur le LAN ; paquet runtime identité 0.1.0.
- Paquet 0.1.1 préparé, non installé sur les services actifs.
- Migrations Drive 0050–0058 et Docs 0034–0048 appliquées seulement aux bases
  de test isolées. Aucun redémarrage Docs backend/worker pour cette intégration.
- Avant activation : installer le paquet, appliquer les migrations, reconstruire
  le convertisseur/collaboration Docs, configurer les quatre credentials privés
  et `DOCS_PUBLIC_URL`, puis qualifier les services et les accès réels.
- Sauvegardes privées initiales : `data/docs-drive-native-documents/baseline/`.
  Inventaire initial Docs : zéro document ; réauditer avant bascule.

## Implémenté, qualification LAN encore nécessaire

- Pointeur documentaire Drive, placement S3/monté, rôle commentateur,
  délégation d’identité actuelle, listes filtrées en SQL et projection révisionnée.
- Partages directs/groupes, héritage affiché, titre, favoris/liens, corbeille,
  restauration et purge native versionnée avant libération des quotas.
  Les mutations ACL génériques Drive invalident aussi les révisions Docs et
  celles des descendants, sans double incrément dans le bridge.
  Les suppressions ACL en lot/cascade conservent au moins un propriétaire ;
  une demande déjà satisfaite n'abaisse pas le droit et ne crée pas de doublon.
- Réservations logiques (propriétaire/espaces/organisation/instance), contenu et
  pièces jointes, antivirus, reprises bornées, réduction comptable, médias partagés.
- Création privée jusqu’à confirmation du contenu ; journal et objet temporaire
  reprenables, nettoyage des versions temporaires après confirmation.
- Abandon explicite : pas de libération avant suppression native confirmée.
  Une absence de réservation doit recevoir un reçu exact, jamais un simple 404.
  Une annulation avant réception pose un tombstone sous le verrou de création :
  une requête retardée ne peut pas recréer le document.
- Ouverture Docs distincte des viewers de fichiers dans Drive, métadonnées et
  taille/date documentaires. Sélecteur Docs paginé des destinations S3/montées.
- Création racine, imports et sous-documents utilisent des UUID/clés conservés
  lors des répétitions. Les réponses 202 ne sont pas interprétées comme un Doc.
- Conversion initiale Yjs déterministe par UUID de création ; les éditions
  courantes gardent leurs identifiants Yjs natifs. Markdown/tableau/imbriqués et
  BlockNote testés en répétition. Pas de réponse de conversion dans les logs.
- Liste serveur paginée des créations privées du créateur, affichée dans Docs :
  reprise du contenu préparé, renvoi du fichier original ou annulation depuis
  une nouvelle session. Aucun principal déduit d’une adresse email.
- Invitations explicites : autorité Drive, nonce/expiration, émetteur revalidé,
  acceptation liée au principal, répétition sans rétablir un droit révoqué.
  État d'envoi queued/sending/sent/uncertain ; pas de renvoi automatique incertain.
  Le jeton quitte le fragment avant Next/router ; acceptation explicite dans Docs.
- Demandes d'accès Docs conservées ; acceptation par commande Drive stable,
  sans ACL locale. Notifications aux responsables actuels (directs/hérités/groupes)
  via une lecture privée paginée réservée au worker. Journal de notification
  atomique avec la demande, repris par le worker existant ; envoi incertain sans
  répétition automatique (SMTP et état métier LAN encore à qualifier).
- Menu de création Docs depuis les dossiers S3 et montés préparé ; destination
  courante transportée puis contrôlée par le sélecteur Docs. Contrôle ciblé
  Chromium simulé et menus Jest réussis. Créations binaires masquées dans un
  parent Docs ; icône documentaire dans les listes.

- D7 débuté : pagination SQL commune fichiers NAS/Docs, sérialisation de page
  partagée avec recherche/favoris/récents. Les documents ne sont plus perdus par
  l'adaptateur de navigation monté ; pagination et ouverture dédiées.
  Sélection/bulk Docs et menus de transfert raccordés. Qualification
  navigateur du dossier mixte réel encore nécessaire.
- D7 : observation technique des ancres NAS avec identité Provider, cache positif
  de dix secondes, refus des identités absentes/remplacées et 503 en cas de panne.
  Aucun appel Provider sur cache absent sous transaction ; prélecture des
  commandes et invitations. La disparition externe ne supprime aucune donnée
  Docs. Contrôle réel localfs réussi ; récupération Web et garantie contre la
  réutilisation d'un identifiant Provider restent ouverts.
  Recherche filtrée par espace corrigée pour les documents montés et S3.
- Une ouverture explicite dans Docs écrit le récent Drive via une mutation privée
  avec preuve actuelle ; les sondages d'autorisation et listes ne le font pas.
  Répétition et refus après révocation vérifiés. La découverte dans l'accueil Docs
  des documents visités uniquement par lien utilise le filtre SQL courant,
  y compris les contextes de dossier encore valides.
  Les requêtes collaboration utilisent `record_visit=false` : ni le récent
  Drive ni la trace native Docs ne sont créés par ces sondages.
- « Afficher dans Drive » ajouté au menu Docs : adresse du catalogue ST, service
  autorisé/disponible, nouvel onglet sans accès à l'opener. Contrôle Chromium
  simulé bureau/mobile réussi, entrée absente sans service disponible ; aucune
  ouverture réelle de document LAN. Typage et lint ciblé réussis.
- Convertisseur : aucune exception brute de lecture/écriture envoyée au logger
  ou à Sentry dans le handler de conversion. Message fixe testé sur entrée Yjs
  invalide. Reconstruction du convertisseur encore requise avant activation.

## Reprise du 9 septembre — transferts et interface

- Déplacement de sous-arbre Docs avec réattribution atomique des quotas,
  positions relatives et ordre de projection ; migrations additives 0058/0048.
- Copies natives avec descendants et médias partagés protégés, identifiants
  stables par manifeste et reprise après perte de confirmation. Un reçu
  d'identité inattendue est refusé. Les transferts exigent la preuve réelle
  du demandeur, renouvelée lors d'une reprise ; aucun compte propriétaire simulé.
- Dossiers mixtes : inclusion Docs dans les copies S3/NAS, libération des
  verrous de namespace pendant les callbacks interservices, suivi d'ancre
  lors de confirmation et conservation des champs physiques nuls des Docs.
- Renommage/déplacement natif de dossier : quotas des Docs descendants inclus
  dans le journal existant ; ancre stable et espace réattribués après confirmation.
  Test localfs réel : refus au plafond avant renommage, puis transfert des
  sept octets logiques au destinataire, sans charge physique NAS.
- Export PDF individuel : transport borné vers le journal de publication
  S3/NAS, version/digest vérifiés et reprise de publication. UI préparée.
  Le renderer isolé produit un PDF réel vérifié ; les ZIP mixtes sont testés
  avec le pair PDF simulé. Publication individuelle S3/NAS LAN à qualifier.
- Sélecteur de classement dans Docs avec impact des quotas/partages ; actions
  Docs dans les dossiers NAS, sélection mixte et suppressions via l'adaptateur
  correspondant. Identifiant de copie conservé après erreur réseau ; UUID
  cryptographique compatible HTTP LAN sans dépendance supplémentaire.
- Commentateur : interface documentaire conservée avec édition désactivée,
  sauvegarde de texte inactive ; ancres relatives stockées avec le fil REST
  et réappliquées localement, sans autoriser l'écriture WebSocket du texte.
  Contrôle API ciblé passé : commentaire, refus de modification, refus après
  révocation, ancre invalide rejetée. Recette navigateur encore requise.
- Régressions ciblées réussies : déplacement Docs/rollback quota, copie native
  avec média et confirmation perdue, manifeste de sous-documents avec reçu
  erroné puis reprise, déplacement de dossier localfs et budget logique.
- Typages Drive et Docs réussis après les dernières corrections ; linters
  ciblés passés. Les derniers ajouts demandent encore leurs contrôles groupés.
- Aucun arrêt, activation ou migration LAN. Ce point de reprise n'est pas
  une livraison et n'enlève aucun critère D1–D9.

## Contrôles exécutés

### Suite du 9 septembre — ancres, récupération et PDF

- Classement Docs contrôlé dans Chromium avec APIs simulées : impact visible,
  erreur 503 puis confirmation avec la même clé. Libellés français complétés.
- Suppression d'un dossier NAS : vérification des droits documentaires avant
  rétention, blocage durable des créations/déplacements concurrents, corbeille
  documentaire après confirmation native, sans libération des octets Docs.
  Test PostgreSQL/localfs avec interruption, reprise deux fois et refus d'un
  opérateur NAS sans propriété documentaire réussi.
- Récupération des ancres manquantes/hors périmètre : liste privée paginée,
  propriétaire documentaire courant uniquement ; aucun droit de contenu donné
  à un administrateur NAS. Reclassement rejouable, quotas réattribués, corbeille
  conservée. API et interface Docs préparées ; test serveur passé, navigateur
  du nouveau panneau encore nécessaire.
- Les preuves des transferts sont obtenues avant les transactions SQL.
  Le sérialiseur de copie native conserve désormais la révision exigée par
  le service, au lieu de supprimer ce champ de la requête privée.
- PDF serveur : même exporteur que l'interface, lecture explicite du snapshot
  Yjs (une première version produisait une page vide, corrigée), images et liens
  publics conservés. Surface de rendu sans session applicative, service Docker
  séparé sans clés de stockage/IdP, conteneur non privilégié en lecture seule,
  limites mémoire/processus/temps/taille et fichiers temporaires privés.
  Bail de 150 s limité au document, droits/version revérifiés ; images natives
  seulement, sans requête vers un hôte fourni par le document. Les images
  externes doivent actuellement être importées pour un export d'archive.
- Image `apoze/docs:identity-pdf-renderer` construite. Contrôle réel du moteur
  isolé réussi : titre, texte, image, légende et lien Docs vers l'adresse
  publique. Reçu : `pdf-renderer-check.json` dans ce dossier. Aucun document
  utilisateur ou stockage NAS réel utilisé. Service ajouté au compose Docs,
  pas encore activé dans la pile courante.
- ZIP du journal de transfert : fichier NAS, document et sous-document PDF
  présents sans duplication des documents vivants ; contrôle PostgreSQL/localfs
  réussi avec le pair PDF simulé. Le transport HTTP réel refuse dépassement
  et digest erroné. Le backend Docs refuse aussi une révocation pendant le rendu.
  Les anciennes routes de téléchargement ZIP direct restent à raccorder.
- Incident du mode dev : l'ajout initial du point d'entrée PDF sous `src/`
  a fait échouer la compilation automatique de la collaboration, car sa nouvelle
  dépendance n'était pas installée dans ce conteneur. Coédition rétablie
  (`/ping` 200). Le moteur est maintenant dans `renderer/`, hors surveillance,
  avec sa compilation séparée ; aucune base/configuration LAN réinitialisée.
- Restent notamment migration complète, liens contextuels, ZIP directs,
  fin des transferts mixtes, qualification UI réelle puis bascule D8/D9.
  Ces résultats ne constituent toujours pas la livraison du chantier.

- PostgreSQL isolé : scénarios ciblés d’autorisation, partage, projection,
  quota/purge, création, annulation avant/après réception et isolation des
  préparations entre créateurs. Pas de suite complète relancée.
- Conversion : un scénario Y-provider sur répétition/validité sémantique et
  clé invalide ; quatre régressions existantes d’orchestration Docs.
- Typages frontend Drive/Docs/Y-provider et lints ciblés réussis au fil des lots.
- `makemigrations --check --dry-run` : aucun changement détecté dans les deux apps.
- Chromium simulé uniquement : création/import, destination lecture seule,
  répétition après 503, annulation interrompue puis confirmée, reprise depuis
  une session sans historique navigateur. Rapport et captures :
  `output/playwright/docs-native-create/report.md`.
- Test S3 Docs réel antérieur : écritures conditionnelles/versionnement réussis,
  toutes versions et marqueurs de test supprimés.

## Restant indispensable

1. D1/D2 : terminer tous les chemins indirects, liens contextuels et commenter
   réellement utilisable avec la collaboration ; optimiser les accès répétés.
2. D3 : `docs_drive_migration plan/status` dans Docs produit/vérifie un inventaire
   privé de métadonnées SQL et versions S3, sans changement d'autorité.
   Signale les principaux/groupes non associés, racines sans propriétaire et
   parents absents des documents natifs, sans rapprochement par email.
   Répétition de l'inventaire et refus d'écrasement/export interrompu testés sur
   PostgreSQL isolé (S3 simulé). Comparaison complète, stage/apply/resume,
   point gelé, retour arrière et répétition d'une vraie migration restent à faire.
3. D4 : qualifier notifications SMTP/UI réelle, déplacements/ordre,
   duplication/médias/descendants et budgets ; chemins natifs onboarding,
   create-for-owner, suppression de compte et mutations anonymes à traiter.
4. D5 : exports PDF gouvernés, transferts de budgets et refus de sauvegarde dans
   l’éditeur réel. Les tests de préparation ne remplacent pas cette recette.
5. D6 : qualification visuelle des menus Drive, actions/bulk/import/export/retour,
   favoris/récents ; création de sous-document non qualifiée en navigateur.
6. D7 : dossiers mixtes, déplacements/copies/archive manifeste, fraîcheur et
   identité réelles des ancres NAS, absence/disparition, gros dossiers.
   Durée restante NAS propagée via `access_ttl` et `X-Docs-Access-TTL` ; le client
   collaboration prend le minimum avec le TTL identité et les 15 s, depuis le
   début de sa requête. Contrôles ciblés réussis ; mesurer encore sur pile LAN.
7. D8/D9 : activation contrôlée, restauration cohérente et recette réelle
   Keycloak/NAS/ST/People/Docs/coédition puis second IdP ; nettoyage et livraison.

Aucun de ces points restants ne peut être considéré comme terminé par le seul
fait que les tests de socle passent. Grist reste en pause.


## Suite du 9 septembre — finalisation, téléchargements et liens contextuels

- Finalisation des dossiers transférés : après remplacement du dossier temporaire
  par son UUID définitif, les projections Docs du sous-arbre sont révisionnées.
  Contrôle PostgreSQL/localfs réussi. Les dossiers contenant encore des Docs
  en préparation/corbeille sont refusés avant transfert et avant rétention.
- ZIP direct authentifié et ZIP de transfert réutilisent le manifeste et le
  moteur borné. Le parcours S3 historique sait également émettre les PDF des
  Docs et désambiguïser les noms. Dix-huit régressions ZIP existantes passent.
- Capture de la vraie preuve de session avant retour StreamingHttpResponse :
  le middleware réinitialise ses ContextVars avant l'itération des octets.
  Le destinataire revalide toujours cette preuve. Les ZIP de liens montés
  utilisent une délégation anonyme du bearer, pas l'identité de son créateur.
- Reprise de copie native après préparation privée : réutilisation des octets
  préparés même si la source a changé. Coupure de publication et perte de
  confirmation finale testées, sans seconde copie ni double charge.
- Préparation de 201 Docs : 1 823 requêtes avant, moins de 30 après insertion
  par lots et pile d'ancêtres bornée en profondeur ; rejeu sans requête ni doublon.
- Liens de dossiers : contexte borné (8 sous-arbres maximum), transmis avec
  l'acteur réel ou explicitement anonyme, revérifié par Drive pour chaque accès.
  Un UUID Docs seul ne reconstitue plus le lien de dossier parent. Liens Docs
  directs inchangés. Révocation/rotation S3 et retrait du partage NAS testés.
- L'échange Web Docs utilise GET de jeton CSRF puis POST validé et session
  serveur. Les cookies de session suivent les médias et la coédition ; le bail
  WebSocket tient compte de X-Docs-Access-TTL pour un document privé ouvert
  par lien contextuel. Test API réel avec contrôles CSRF réussi.
- Les pages de partage S3/montées proposent l'ouverture Docs ; les documents
  montés suivent les lignes natives dans la pagination publique, sans liste
  complète en mémoire. Renommage du helper invitationToken.ts en
  linkCredentials.ts pour effacer les fragments avant Next/telemetry.
- Navigateur du parcours contextuel vérifié (API simulée) : fragment retiré
  avant routeur, POST 503 puis reprise 200, bonne destination et secret local
  effacé après succès. Preuve : public-context-check.json.
  Une mauvaise importation de bouton sur la nouvelle page a été corrigée ;
  typage complet Docs réussi, endpoint frontend de nouveau HTTP 200.
- Validation ciblée récente : 9 scénarios Drive droits/ZIP, 2 reprises de copie
  Docs, 1 échange de contexte CSRF, 2 contrats identité. Pas de bascule LAN.

Restent notamment : terminer et qualifier les liens/publication PDF réels,
cohérence du schéma convertisseur, migration complète apply/resume/comparaison,
recette réelle commentateur/coédition/médias/exports, activation contrôlée,
sauvegarde/restauration et nettoyage D8–D9. Le chantier reste en cours.

- Migration native : `plan --confirm-frozen` vérifie deux inventaires SQL/S3
  identiques, puis `verify` refuse une modification depuis ce point. Contrôle
  ciblé réussi. L'option exige la suspension préalable des services mutateurs
  Docs par l'opérateur ; aucune suspension LAN effectuée pour ce contrôle.
- Index privé SQLite des métadonnées JSONL en préparation pour l'application
  bornée de la migration : réception complète et reçu vérifié avant mutation,
  fichier/dossier privés et suppression du temporaire en sortie.

## Suite du 9 septembre — migration et reprises

- Index SQLite privé terminé, reçu complet vérifié avant mutation et unicité
  des documents/chemins contrôlée. Le point gelé inclut les charges logiques et
  le pas de l'arbre natif. Les groupes People doivent correspondre entre pairs.
- Drive : commandes plan/stage/compare/activate/rollback/status implémentées.
  La comparaison bloque les nouveaux droits hérités du dossier de destination.
  Préparation cachée, reprise avec mêmes UUID et absence de double imputation.
  Activation et annulation rejouées sur PostgreSQL isolé ; trace d'annulation
  conservée, contenus natifs non concernés. Le worker ignore les migrations
  encore préparées.
- Docs : attach/detach à partir du reçu Drive, vérification du contenu/métadonnées
  gelés avant/après ; ajout/retrait des seules liaisons et références comptables
  de médias. Deux scénarios ciblés réussis, dont refus après modification native.
- Invitations historiques : proposition limitée au destinataire connecté,
  acceptation explicite par le mécanisme existant depuis l'ancien UUID Docs.
  Contrôle Source de destinataire/rejeu réussi ; typage frontend Docs réussi.
  Qualification Web réelle de ce bouton toujours nécessaire.
- Premier appel entre pairs : si la projection locale n'a pas encore associé
  le principal, rafraîchissement via People puis validation normale de la preuve.
  Aucun compte créé depuis l'identité affirmée par le pair. Contrat ciblé réussi.
- PDF gouverné : publication localfs interrompue avant confirmation, modification
  ultérieure du Docs puis reprise confirmée sans réécriture ni seconde charge.
  Test PostgreSQL/localfs réussi ; publication réelle LAN encore à qualifier.
- Guide opérateur ajouté : `docs/operations/docs-drive-native-documents.md`.
  Aucun reçu d'activation LAN émis ; intégration toujours inactive.
- Convertisseur : dépendances natives math/diagram/colonnes ajoutées et installées
  dans le conteneur collaboration. Un essai d'import React direct a interrompu
  brièvement le processus (CSS Node) ; retour immédiat au schéma précédent,
  `/ping` 200. Essai isolé ensuite : schémas/parsers natifs réutilisés avec rendu
  DOM serveur, hooks Node limités aux CSS de dépendances. MathML, Mermaid et
  colonnes conservés en Yjs/HTML dans un scénario ciblé ; typage réussi.
  Raccordement au schéma final en cours, images finales à reconstruire.

La migration reste à compléter sur un jeu isolé comprenant descendants,
corbeille, groupes et invitations, puis à exécuter au point cohérent LAN.
D8/D9 (configuration des clés, installation des paquets, migrations, activation,
restauration intégrée, recette réelle et nettoyage) ne sont pas encore livrés.

## Bascule LAN du 9 septembre — en qualification

- Sauvegarde cohérente supplémentaire :
  `data/docs-drive-native-documents/pre-activation-20260909/` (privé).
  Deux dumps PostgreSQL, volume Docs arrêté avec toutes ses versions, anciens
  réglages privés et manifeste SHA-256 ; 57 778 165 octets au total.
- Inventaire réel gelé : zéro document natif, zéro association non résolue.
  Reçus plan/stage/compare/attach/activate émis et conservés dans ce dossier.
- Migrations Drive 0050–0058 et Docs 0034–0048 appliquées. `check` et
  `makemigrations --check --dry-run` passent dans les deux applications.
- Configuration locale des quatre clés distinctes, remplacement atomique des
  environnements. Générateur `prepare_documents.py`, test ciblé de rejeu passé.
- **DOCS_DRIVE_ENABLED=true dans les deux applications.** Paquet 0.1.1 installé
  via images reconstruites (wheel SHA-256
  `0769a36afbc912e7bd38afc765da208daedfd1e145d31d8c32366834dedb2e9d`).
  Drive/Docs API-workers-beat et collaboration recréés ; renderer privé healthy.
  Keycloak, People, ST, Meet et NAS conservés. Aucun doublon de processus ajouté.
- Connexions Keycloak réelles Drive/Docs réussies. Compte de test conservé avec
  quota 20 Go. Création Docs placée dans l'espace S3 Test1 : liaison active,
  révisions synchronisées. Édition, sauvegarde par navigation HTTP 204 et
  réouverture avec contenu identique ; 348 octets imputés une seule fois.
- Partage depuis Docs au groupe People « Administration de la suite » en
  commentateur : HTTP 201. Autre session IdP réelle : lecture 200, commentaire
  autorisé, modification refusée et éditeur non modifiable.
- Qualification Web toujours en cours : objets de test présents, à nettoyer
  selon le manifeste privé `data/docs-drive-native-documents/lan-fixture.json`.
  Exports, coédition/révocation, NAS, restauration isolée et bascule IdP ciblée
  restent à finir ; aucune clôture D9 annoncée.

### Compléments de qualification après activation

- API d'autorisation documentaire : favoris et parent immédiat calculés dans
  la requête de lot. Le contrôle PostgreSQL sur 50 Docs couvre maintenant le
  véritable handler API : moins de 30 requêtes, bonnes destinations/favoris,
  capacités identiques et cache éliminé à la fin de la réponse.
- Commentaire réellement créé HTTP 201 par le rôle commentateur ; son éditeur
  principal reste non modifiable. Le contrôle utilise le sélecteur natif
  `data-test=save` de la fenêtre de commentaire.
- PDF S3 relu via l'URL privée autorisée : 4 683 octets, entête PDF valide,
  titre dans les métadonnées et texte attendu extrait avec pdfjs existant.
- Média : première image synthétique de test invalide remplacée par une vraie
  image PNG 64 × 32 ; son affichage et sa sauvegarde HTTP 204 sont confirmés.
- Défaut opérationnel corrigé dans le Nginx média : résolution Docker dynamique
  des upstreams API et S3. Il retenait l'ancienne adresse du backend après
  recréation et produisait une erreur 500. `nginx -t` passé, service relancé.
- Export natif : l'origine média configurée est chargée directement avec les
  cookies, les autres origines passent toujours par le proxy public protégé.
  Douze tests du résolveur passent. L'export NAS avec image est encore en cours
  de diagnostic/qualification ; ne pas le considérer validé.
- Le proxy média masque désormais les en-têtes CORS du S3 avant d'émettre
  l'unique origine frontend autorisée. Un GET navigateur avec credentials
  produisait deux valeurs, contrairement au GET sans Origin de la sonde HTTP.
  L'export NAS avec image est maintenant HTTP 201, relu HTTP 200 (5 184 octets).
  `lan-pdf-check.json` confirme texte, titre PDF et image embarquée.
- Coédition réelle à deux comptes : modifications propagées dans les deux sens,
  sauvegarde HTTP 204. Retrait du groupe : accès HTTP 403 immédiat et fermeture
  WebSocket mesurée à 10 522 ms. Preuve : `lan-revocation.json`.
  Le droit temporaire au groupe Administration a été supprimé par ce contrôle.
- Typage complet du frontend Docs passé après le raccordement des médias.

### Qualification LAN poursuivie — 9 septembre, 10 h 25 UTC

- Classement réel S3 → NAS → S3 : HTTP 200, ancien UUID et contenu conservés.
  Correction : `Item.move` incrémente la révision ; rafraîchir la liaison avant
  de lui associer l'ancre NAS. Le test existant couvre l'aller-retour avec
  descendant et l'imputation unique (1 passé, 1,17 s).
- Création depuis le menu Drive : nouvelle fenêtre Docs avec dossier transmis,
  création 201 et éditeur utilisable ; sous-document natif créé 201.
- Copie réelle avec image et descendant : 202/running puis 201/done ; texte,
  image et descendant relus. Corbeille 204 puis restauration 200 et réouverture.
  Correction : la réservation de copie exclut les médias en attente non
  référencés de la source ; ils restent facturés à celle-ci. Deux tests de
  copie/reprise passent (0,73 s), lint natif passé.
- La première préparation synthétique erronée a été annulée et purgée ; son
  journal de copie sans sortie a été clôturé `failed` après contrôle sous
  verrou. La trace est conservée pour le nettoyage final. Attention : l'UI
  copie garde encore sa clé en mémoire seulement ; une reprise après
  rechargement et l'annulation d'une préparation de copie méritent correction
  avant clôture, pour éviter une contrainte de transfert actif opaque.
- Transport : un refus 400 ne devient plus une panne 503 ; 3 contrats isolés
  passent. Wheel commune reconstruite SHA-256
  `afa0265c67528bc20baf7a2b3607ffa25e2aab8f834becf0f63b0e5fb5a68f49`.
  Images backend Drive et Docs reconstruites et API/worker/beat recréés.
- Lien public documentaire : lecture avec image et éditeur non modifiable ;
  après révocation, document 401 et média 403. Preuve `lan-public.json`.
- Brouillon au quota : refus réel 413 après abaissement temporaire de la seule
  allocation de l'utilisateur de recette dans ST. Route et texte conservés,
  bouton de reprise ; restauration des 20 Go, sauvegarde 204, relecture du
  texte. Preuve `lan-quota.json`. Aucun quota n'est resté abaissé.
  `useSaveDoc` protège désormais la navigation des documents intégrés et
  affiche l'erreur/reprise. Les accusés de réception ne retirent plus le statut
  modifié des frappes ultérieures. Huit contrôles ciblés passent ; typage Docs
  complet passé. Tests lancés avec `NEXT_PUBLIC_API_ORIGIN=http://test.jest`.
- Dossier S3 de recette contenant Docs + PDF : API et explorateur affichent les
  deux types. Lien de dossier réellement exercé : contexte ouvert, fragment
  effacé, image lisible ; autre document refusé ; révocation document 401 et
  média 403. Preuve `lan-folder-link.json`.

Le dossier mixte part maintenant vers le NAS. Restauration isolée, bascule IdP,
ancres externes, ZIP réel, contrôles de conservation et nettoyage restent ouverts.


### 9 septembre, qualification complémentaire

- Dossier mixte S3 → NAS → S3 terminé ; document, enfant et image conservés.
  Correction de portée de preuve dans `storage_move_job.execute_move` pour
  les workers sans middleware HTTP ; contexte remis à zéro après chaque job.
- ZIP réel valide : PDF du parent, PDF de l'enfant et export PDF existant.
- Renommage direct du dossier NAS observé : l'identité du dossier suit le
  renommage et le nouveau dossier au même chemin ne reçoit pas les Docs.
  Suppression directe du dossier original : refus 403 ; récupération par le
  propriétaire vers S3 : 200, contenu/image conservés. Dossiers NAS de ce
  scénario nettoyés (`lan-anchor.json`).
- Copie : clé conservée en sessionStorage par acteur/document/options ;
  annulation d'une préparation clôture le job après purge confirmée, sans
  résurrection par un worker concurrent. Contrôles ciblés copie, annulation
  et frontend réussis ; lint et typage natif réussis.
- QA IdP isolée démarrée (`suite-identity-qa` et
  `suite-identity-authentik-qa`). Authentik expose un émetteur par application :
  correction du contrat avec `DOCUMENT_PEER_OIDC_ISSUER` explicite, aucune
  modification de validation du login OIDC. Émetteur non déclaré/ancien refusé
  dans le contrat ciblé ; Keycloak ancien refusé 401 après bascule réelle ;
  même document/placement lisible sous Authentik, groupe People éditeur vérifié.
  Retour Keycloak et révocation finale en cours.
- Wheel actualisée : `8928a1a52f4d5a0dcee0335747af1e8b70193f232530407d68893f029c46f239`.
  Reconstruction des images Drive/Docs en cours ; LAN pas encore recréé avec
  cette version.
- Demande du propriétaire ajoutée à D6 : comparer l'explorateur actuel à
  l'ancien « Mes fichiers » S3 et rétablir ses finitions si perdues, en
  conservant tous les raccordements. À traiter avant clôture D9.


### 9 septembre, 11 h 15 — restauration et interface historique

- Preuve IdP complète : `isolated-idp.json` (Keycloak → Authentik → Keycloak,
  ancien credential 401 dans les deux sens, UUID/placement/contenu identiques,
  groupe éditeur conservé puis révoqué 403, propriétaire conservé).
- Panne Source : HTTP 503 et fermeture coédition 9 818 ms,
  `lan-outage.json`. Service redémarré dans le bloc de récupération.
- Sauvegarde cohérente intégrée sous
  `data/docs-drive-native-documents/integrated-restore-20260909/` (57 855 484
  octets au relevé initial). Deux bases et volume S3 Docs avec versions
  restaurés dans un réseau interne sans ports ni montage NAS. Comparaison
  de cinq documents, métadonnées/droits/quotas et octets hachés de toutes les
  versions/médias : identique ; rejeu des projections et jobs terminés sans
  double charge. `isolated-restore.json`. Trois projets QA arrêtés et volumes
  éphémères supprimés ; sauvegardes privées conservées.
- Images Drive/Docs et frontend Docs reconstruites, quatre clés conservées,
  générateur des émetteurs croisés appliqué, API/workers recréés sur le LAN.
  Depuis, le complément explorateur a modifié le code Source : image Drive
  à reconstruire une dernière fois avant clôture.
- Diagnostic explorateur confirmé : le shell historique `AppExplorer` avait
  été conservé, mais « Mes fichiers » pointait vers `SpacesExplorer`, catalogue
  simplifié avec faux dossiers pour les 54 allocations historiques dont la
  racine est un fichier. Aucun changement de ces allocations/données.
- « Mes fichiers » utilise maintenant les véritables ressources et l'ancienne
  grille/breadcrumb/filtres/menus/aperçus. Entrées S3/NAS autorisées réunies,
  fichiers historiques exclus du sélecteur de dossiers. Tri commun en SQL,
  filtres repris depuis `ItemFilter`, aucun listing complet côté client.
  `ResourceCollection` mode `home`, `item_entrances`, invalidations communes
  après mutation ; date presets repris du convertisseur existant.
- Contrôle PostgreSQL home : types/pagination/filtre PDF et accès limité à un
  sous-dossier réussis. Filtre catégorie texte inclut désormais les Docs natifs ;
  contrôle document-page existant (50 Docs, autorisation < 30 requêtes) réussi.
  Neuf contrôles existants de rafraîchissement de cache réussis.
- Navigateur : filtre PDF réel, navigation NAS depuis Mes fichiers, clavier,
  mobile 390 px sans débordement, ouverture Docs mobile et dossier S3 mixte
  passent, sans erreur de page. `lan-explorer.json`, captures dans
  `output/playwright/docs-native-lan/`. Dernier ajustement : glisser-déposer
  réactivé sur l'accueil via les mécanismes communs existants.

Reste : contrôle comparatif de charge à deux tailles et derniers contrôles
front ciblés, nettoyage des documents/exportations synthétiques et réservations,
qualification de purge réelle, documentation/plan/contrats/CHANGELOG alignés,
reconstruction finale Source et vérification locale de la pile. Aucun D9
terminé déclaré. Les invitations ont des contrôles de migration/backend et
UI simulée ; la validation SMTP/UI réelle annoncée précédemment reste à
qualifier ou à justifier explicitement selon le critère minimal du plan.
