# Qualification ciblée — administration et explorateur unifié

5–6 septembre 2026. Verdict : parcours ci-dessous qualifiés après corrections.
La [recette finale](../validation-final.md) clôture les lots L0–L12 localement.
Les sections suivent la chronologie : les mentions de travaux restants et les
versions de schéma décrivent leur séance, pas l'état final de l'installation QA.

## Environnement isolé

- Drive : interface `http://127.0.0.1:8980`, API `http://127.0.0.1:8981`.
- ST : interface `http://127.0.0.1:8987`, API `http://127.0.0.1:8986`.
- Bases dédiées `driveqa` et `stqa`, Redis et worker dédiés ; aucun changement
  de schéma dans la base partagée ou dans l'ancienne fixture de production.
- Schémas Drive jusqu'à 0043 et ST jusqu'à 0023.
- Deux buckets S3 synthétiques et un dossier local dédié au provider natif.
  Cette séance ne constitue pas une nouvelle qualification SMB.
- Chromium via Playwright installé : aucun connecteur navigateur automatisable
  n'était disponible. Contextes neufs, sessions synthétiques conservées en
  fichiers privés ignorés, sans secrets dans ce rapport ou les captures.
- Écrans 1440 × 1000 et 390 × 844 ; serveurs de développement, pas les images
  finales. Ports séparés pour préserver les environnements existants.

## Parcours contrôlés

1. Administration Drive : connexions présentes, état accessible, propriétaire
   nommé dans le formulaire ; création de racine et inventaire depuis le web,
   exécution par worker et historique visible.
2. Depuis Documents NAS, ouverture de l'organisation et du service ST exacts,
   portée « Espace virtuel » et ressource présélectionnées. Enregistrement
   d'une limite de 1 000 octets dans ST puis application réelle dans Drive.
3. Restauration d'une version conservée vers un nouveau nom depuis le web ;
   tâche durable et copie visible dans l'explorateur. Comparaison des octets
   synthétiques restaurés et audit des compteurs sans divergence.
4. Catalogue commun « Mes fichiers » : ouverture des espaces NAS et S3.
   Import et aperçu texte réussis sur les deux familles.
5. Import NAS dépassant la limite ST : réponse 413, aucun fichier physique
   à destination ; régression ciblée empêchant une entrée d'index fantôme.
6. Administration mobile : contenu visible dans un contexte initialement
   mobile, sans débordement horizontal du document ; tables défilables.

Après correction, aucun échec réseau inattendu ou exception JavaScript sur
les parcours import/aperçu. Le 413 fait partie du scénario attendu.

## Corrections issues du navigateur

- Les attributs d'accessibilité du glisser-déposer désactivé empêchaient les
  outils d'assistance de considérer les dossiers comme accessibles.
  Le composant partagé n'expose plus ces attributs quand le drag est désactivé.
- Le catalogue affichait « Mount » comme auteur, même pour S3, et utilisait
  l'heure de rendu comme date. Il utilise maintenant les dates persistées et
  laisse l'auteur inconnu vide ; les actions sans objet sont retirées.
- Le fil d'Ariane NAS revient vers « Espaces » sur les routes unifiées,
  avec un vrai lien utilisable au clavier.
- L'URL d'import gouverné utilisait l'origine web. Elle suit maintenant
  l'origine API de la requête, également lors d'une reprise d'import.
- Une admission NAS créait une référence avant l'existence du fichier.
  Les demandes refusées restent comptabilisées sans être publiées au catalogue.
- Le message de quota applicatif est traduit dans le chemin d'erreur partagé
  et reste lisible sans survol. Un refus après la transmission des octets
  ne présente plus une icône de succès.

## Preuves et contrôles minimaux

- [Administration ordinateur](administration-desktop.png).
- [Administration mobile](administration-mobile-fresh.png).
- [Propriétaire configuré](space-editor-desktop.png).
- [Restauration](restoration-dialog.png).
- [Organisation ST](st-quota-desktop.png).
- [Aperçu S3](s3-preview.png), [aperçu NAS](nas-preview.png).
- 17 contrôles backend import/S3/outil de connectivité réussis.
- Quatre contrôles backend d'espaces et trois de publication NAS/restauration
  réussis, dont refus sans référence fantôme.
- Dix contrôles frontend adaptateurs/fil d'Ariane, trois notifications et
  17 contrôles
  erreur API/import XHR réussis.
- TypeScript, ESLint ciblé, Ruff et Pylint des corrections passent ; dernière
  vérification globale des fichiers du lot à renouveler après ses dernières
  modifications.

Restent notamment les transferts complets L9, éditeurs réels, partage et
révocation entre familles, qualification SMB renouvelée, performances, images
finales et restauration complète de l'installation. Les fichiers privés de
reproduction restent sous `tmp/unified-storage-browser/`.

## Copies entre familles

- S3 → NAS et NAS → S3 lancées depuis « Copier vers… », destination choisie
  parmi les espaces et terminaison visible dans l’historique. Aucun échec
  réseau dans les deux parcours.
- La comparaison d’une racine NAS avec son grant `/` normalise maintenant
  le slash final ; les lecteurs restent exclus des destinations inscriptibles.
- [Sélecteur S3 vers NAS](copy-destination.png),
  [résultat S3 vers NAS](copy-completed.png),
  [sélecteur NAS vers S3](copy-nas-destination.png),
  [résultat NAS vers S3](copy-nas-completed.png).
- L’inventaire synthétique a été renouvelé avant le parcours réussi :
  cette pile isolée n’exécute pas encore le planificateur périodique. Le refus
  préalable sur inventaire périmé a été affiché dans l’historique.
- La migration 0044 est appliquée à `driveqa` ; aucun changement de schéma
  dans la base partagée.

- Copie d’un dossier NAS vers S3 avec workers réels :
  [destination](copy-folder-destination.png), [résultat](copy-folder-completed.png).
  Le manifeste est traité par lots et l’historique affiche son avancement.

## Détail et reprise des transferts

- Chromium 1440×1000 et mobile 390×844 : ouverture du manifeste d'un dossier,
  fichier et dossier vide visibles, pagination et actions présentes. L'historique
  s'affiche verticalement sur mobile pour éviter de couper les détails.
- Mobile : ouverture du sélecteur, choix d'une racine S3, bouton de copie actif,
  fermeture sans soumission. Aucun débordement horizontal du dialogue.
- Worker réel : copie NAS→S3 du dossier sous le nom `dossier-browser-reprise`,
  état terminé. Aucune réponse HTTP en erreur ni exception JavaScript observée.
- Preuves : `transfer-details-desktop.png`, `transfer-details-mobile.png`,
  `copy-picker-mobile.png`, `copy-folder-destination.png`,
  `copy-folder-completed.png`.
## Déplacements et fenêtres NAS — qualification isolée

Déplacement SMB réel terminé depuis le sélecteur commun sur ordinateur, sans
erreur HTTP ou JavaScript : `move-common-picker.png`,
`move-common-completed.png`. Sur mobile 390×844, Renommer, Supprimer et Déplacer
s'ouvrent et s'annulent ; le sélecteur choisit une autre vue autorisée :
`move-picker-mobile.png` (inspection visuelle effectuée).

Le texte commun de destination a ensuite été corrigé pour couvrir copie et
déplacement. Ces scénarios ne qualifient pas les déplacements S3↔NAS.

Téléchargement public NAS : contexte mobile sans session, ouverture du lien
de fichier SMB, téléchargement natif et égalité des octets synthétiques.
Aucune erreur HTTP ou JavaScript ; `public-download-mobile.png` inspectée.
Le jeton de partage demeure dans le fichier de qualification privé.


## Fichier SMB déplacé vers S3

- Parcours réel : SMB destination → menu Déplacer → Documents objets 1 →
  historique affichant la rétention de la source. Aucun échec HTTP/JavaScript
  sur le second parcours après correction de fermeture du flux SMB.
- La première publication avait copié ses octets, mais SMB refusait le
  renommage pendant la lecture. Sa reprise a conservé UUID, favori et charge,
  sans refaire la copie. La fermeture préalable est couverte par le test backend.
- L'ancien lien public télécharge toujours les octets attendus sur mobile,
  sans session ; l'ancien UUID de ressource ouvre le lecteur texte natif S3.
- Captures inspectables : `move-smb-s3-picker.png`,
  `move-smb-s3-completed.png`, `moved-resource-bookmark.png` (inspectée),
  `public-download-mobile.png` (mise à jour après déplacement).
- Données exclusivement synthétiques ; les deux sources privées sont encore
  retenues selon la politique du laboratoire. Aucun stockage utilisateur réel
  n'a été déplacé.


## Retours S3/NAS, NAS indépendant et gestion des liens (5 septembre)

- S3→SMB : `external.txt` déplacé depuis le sélecteur normal ; le lien public
  créé avant son passage en S3 continue à télécharger ses octets sur mobile.
  L'ancienne route `/explorer/items/files/<uuid>` ouvre son lecteur natif.
- SMB→autre partage SMB : deux comptes séparés, deux namespaces déclarés ;
  déplacement du même fichier depuis le sélecteur vers `SMB indépendant`.
  Publication terminée avec rétention de source, aucun HTTP/JS en erreur.
- Gestion des liens : fenêtre mobile, création et révocation ; l'adresse
  révoquée est refusée. Le panneau liste aussi un lien conservé après S3.
  Les captures `public-links-mobile.png` et `public-links-moved-s3.png`
  masquent les URL publiques porteuses de tokens.
- Ces parcours utilisent uniquement les services et fichiers synthétiques de
  qualification. Les éditeurs réels, les dossiers inter-stockages et la
  qualification globale restent à poursuivre.

- La fenêtre de partage S3 habituelle, ouverte depuis le menu contextuel de
  `move-new.txt`, affiche et révoque le lien NAS conservé. Aucun HTTP/JS en
  erreur. Capture masquée : `public-links-regular-share-modal.png`.


## Déplacements de dossiers — S3 et SMB

Deux dossiers synthétiques contenant un fichier, un sous-dossier et un dossier
vide ont été déplacés depuis l'explorateur commun : vers un autre bucket S3
puis vers le partage SMB indépendant (autre compte et namespace). Le navigateur
retrouve les dossiers par leur UUID initial. Les historiques affichent les
quatre entrées traitées et la conservation des sources.

Le parcours SMB a d'abord été arrêté par le contrôle de fraîcheur de
l'inventaire (le Beat de qualification est volontairement arrêté). Après
actualisation de l'inventaire dédié, « Vérifier la reprise » termine le
transfert. Le contrôle navigateur final ne relève aucune erreur HTTP/JS.
Le script `recover-folder.cjs` et son journal privé
`/tmp/drive-folder-browser-recover2.log` contiennent la preuve de reprise.

L'ancienne adresse publique du dossier S3 redirige vers le partage natif
sur un écran de 390 × 844. La capture masque les liens porteurs de jetons.
Captures examinées :

- `browser_s3_folder-picker.png`, `browser_s3_folder-completed.png` ;
- `browser_native_folder-picker.png`, `browser_native_folder-completed.png` ;
- `folder-legacy-public-mobile.png`.

Migration 0048 appliquée uniquement à la base `driveqa` dédiée et aux bases
éphémères de tests. API et worker dédiés redémarrés après contrôle d'absence
de transfert actif. Aucun service ni schéma partagé/de production modifié.

## 6 septembre — dossiers NAS et sous-espaces S3

- Dossiers SMB vers S3 et entre deux partages SMB indépendants, reprise du
  manifeste, dossiers vides, UUID, favoris et anciens liens publics préservés.
  Aller-retour S3→NAS→S3 parcouru sur mobile jusque dans un sous-dossier.
  Preuve : `/tmp/drive-native-trees-browser-recover.log`, aucune erreur HTTP/JS.
- Choix d'une racine S3 existante dans Drive, avertissement de superposition,
  création du sous-espace, réattribution asynchrone et navigation via le parent.
  Preuve : `/tmp/drive-nested-browser7.log`, aucune erreur HTTP/JS.
  La tâche était terminée mais les connexions n'étaient pas rafraîchies ;
  l'administration invalide désormais les données concernées à chaque fin
  de tâche. Le formulaire défile dans la hauteur de l'écran et son bouton
  de sauvegarde a un libellé traduit.
- Captures examinées : `folder-roundtrip-public-mobile.png`,
  `s3-nested-root-picker.png`, `s3-nested-root-completed.png`.

- Impact de copie présenté avant admission : volume connu, budgets, attribution
  et règles de partage. La copie S3→S3 avec un nom choisi est terminée ;
  `/tmp/drive-impact-browser-completed.log` ne signale aucune erreur HTTP/JS.
  Capture `transfer-impact-picker.png` examinée visuellement.

## 6 septembre — Collabora, ONLYOFFICE et groupes

- Collabora 26.04 et ONLYOFFICE 9.2.1 réellement ouverts dans Chromium :
  modification et sauvegarde des mêmes DOCX sur S3 explicite et NAS local.
  Les relectures des fichiers confirment les marqueurs saisis ; audit de
  comptabilité sans écart. Captures `collabora-*-saved.png` et
  `onlyoffice-*-saved.png`. Le libellé `common.back` NAS a été corrigé.
- Premier essai ONLYOFFICE NAS : rejet 409 attendu pour inventaire âgé de
  1 451 s alors que le beat était arrêté. Actualisation, reprise et relecture
  réussies sans désactiver le contrôle de fraîcheur. Beat réactivé à 300 s.
- Des assets facultatifs manquent dans les images tierces : icônes/index
  d'extensions Collabora et traduction française d'un plugin ONLYOFFICE (404).
  Les écritures/relectures fonctionnent ; aucun de ces 404 ne vient de Drive.
- Groupe créé dans l'administration Django, membre ajouté dans le formulaire
  utilisateur, groupe recherché par nom puis autorisé en lecture dans l'espace
  « Edition NAS ». Lien d'administration vérifié vers l'origine API.
  Capture `group-grant-picker.png` inspectée ; suppression des paginations
  inactives lorsqu'il n'y a qu'une seule page pour alléger le formulaire.
- Vérification sur la vraie fixture : membre autorisé à lire, renommage refusé,
  accès révoqué après retrait du groupe, y compris sur la vue native déjà
  résolue puis revalidée. Le groupe utilise une identité stable indépendante
  du nom ; les scénarios backend vérifient aussi les racines S3.

## 6 septembre — création et conversion natives

Chromium : création ODF depuis le formulaire commun, puis conversion de DOC
vers DOCX via le menu contextuel et suivi dans les transferts. Le DOC de fixture
vient d'une conversion Collabora d'un RTF synthétique ; le DOCX final est produit
par ONLYOFFICE. Relecture du marqueur, conservation de la source et audit des
quotas réussis. Aucun échec HTTP Drive/JavaScript sur le parcours final.

Preuves : `native-create-dialog.png`, `native-conversion-menu.png`,
`native-conversion-queued.png`. Les screenshots intermédiaires ne constituent
pas seuls une preuve de publication : la relecture du DOCX et du journal `done`
a été vérifiée dans le runtime dédié.

## 6 septembre — archives et finitions

- Compression depuis le menu NAS vers « Edition NAS » : réponse 202, job terminé,
  ZIP contenant les octets du document source. Extraction vers un nouveau dossier
  NAS depuis le même sélecteur, job terminé et contenu identique à l'original.
- Téléchargement du dossier extrait par le menu habituel : ZIP valide, octets
  identiques. Aucun écart au contrôle comptable après ces trois opérations.
- Lecteur d'archives : sélection de `a.txt`, destination « Documents objets 2 »
  choisie dans le sélecteur commun, publication S3 confirmée ; `b.txt` absent.
- Mobile sans session : téléchargement des dossiers publiquement partagés sur
  NAS et après déplacement NAS→S3. Aucun débordement horizontal ni erreur JS/HTTP.
- Mobile authentifié 390×844 : formulaire d'extraction complet, focus clavier
  conservé dans la modale et Échap fonctionnel. Les premières recherches de
  boutons dans les scripts ont été corrigées pour les intitulés réels et les
  éléments mobiles visibles ; aucun échec produit n'a été masqué.
- Les captures ont révélé un libellé de colonne non traduit et un nom de champ
  imprécis ; corrigés. La taille présentée pour l'extraction est explicitement
  celle de l'archive source, sans estimation trompeuse des octets décompressés.

Preuves : `archive-queued.png`, `extraction-destination.png`,
`archive-folder-download.png`, `archive-selected-destination.png`,
`archive-selected-mobile.png`, `public-folder-native-mobile.png` et
`public-folder-moved-s3-mobile.png`. Les deux dernières masquent le lien porteur.
Les captures de destination, formulaire mobile et dossier public ont été
inspectées visuellement. Les ZIP et bases de vérification restent privés.
