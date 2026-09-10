# Exploitation de l'intégration native Docs / Drive

État de livraison et preuves :
[suivi courant](../../output/implementation/docs-drive-native-documents/current-status.md).
Plan : [intégration native](../plans/suite/docs-drive-native-documents-integration-plan.md).

Raccordement activé sur le LAN le 9 septembre 2026. Consulter le suivi pour
les preuves, les versions et les sauvegardes effectivement utilisées.

## Autorités et prérequis

Drive conserve les placements, droits, invitations et budgets logiques. Docs
conserve ses UUID, ses contenus Yjs, médias, versions et commentaires. S3 et le
NAS ne deviennent pas des emplacements physiques pour le contenu vivant Docs.
Un export PDF est un fichier distinct, publié par le journal de copie existant.

Les associations reposent sur les principaux/groupes People. Une association
manquante ou des groupes désynchronisés doivent être résolus dans l'annuaire,
puis projetés avec `suite_sync_directory`. Aucun rapprochement par courriel,
aucune promotion automatique du créateur et aucun relèvement de quota ne sont
réalisés par la migration. Le premier appel documentaire peut rafraîchir la
projection People d'une application avant de valider la preuve de session.

Les commandes de migration s'exécutent dans les conteneurs applicatifs, avec
leurs paramètres habituels. Dans les exemples, `manage.py` désigne celui de
l'application explicitement indiquée. Tous les chemins sont privés et montés
uniquement dans les conteneurs concernés : dossier `0700`, fichiers `0600`.
Ne jamais publier les inventaires, reçus ou choix de destination : ils contiennent
des métadonnées d'utilisateurs et de documents.

## Préparer la connexion locale

Après construction du paquet commun et des images natives, préparer les seules
clés du raccordement, sans changer IdP, stockage ni politiques :

```sh
python3 docker/suite/prepare_documents.py --state data/suite-local
```

Les quatre clés distinguent direction et lecture/mutation. Le générateur
conserve les clés existantes, refuse les divergences, écrit les fichiers privés
et remplace atomiquement chaque environnement. Il ne redémarre aucun service.
Après les reçus d'activation, relancer avec `--mode enable`, puis recréer les
seuls processus Drive/Docs. `--mode disable` prépare leur arrêt fonctionnel.
Après une régénération générale des environnements, réexécuter ce générateur.
Le renderer `docs-pdf-renderer` est interne, sans credentials ni volume de données.

Chaque application conserve son `SUITE_OIDC_ISSUER` et déclare exactement
l'émetteur de l'autre dans `DOCUMENT_PEER_OIDC_ISSUER`. Le générateur les lit
dans les deux environnements existants. Cela couvre les IdP qui attribuent
un émetteur différent à chaque application, sans liste globale permissive.
Lors d'une bascule IdP, mettre à jour les deux émetteurs et leurs références
croisées, puis recréer API/workers/coédition. Les preuves de l'ancien émetteur
doivent être refusées ; aucun changement de UUID People ou documentaire.

## Inventaire et choix, sans activation

Dans Docs :

```sh
python manage.py docs_drive_migration plan --output /private/preview.jsonl
python manage.py docs_drive_migration status --output /private/preview.jsonl
```

L'aperçu lit les métadonnées SQL et les versions S3, sans ouvrir les contenus.
Dans Drive :

```sh
python manage.py docs_drive_migration plan --inventory /private/preview.jsonl --output /private/destinations-preview.jsonl
```

La destination par défaut est un dossier privé « Documents Docs » dans l'unique
espace personnel S3 d'un propriétaire individuel non ambigu. Les autres cas
exigent un fichier `--placements /private/placements.json` : objet indexé par
UUID du document natif racine ; chaque valeur contient `destination` (UUID du
dossier Drive ou de la ressource montée) et `space_id`. Aucun chemin SMB ou
identifiant NAS n'est accepté comme destination. La préparation ne crée rien.

## Point cohérent et préparation

Suspendre d'abord les services qui modifient Docs : API, coédition et workers.
Conserver Keycloak, People, ST et les stockages disponibles. Interrompre aussi
les mutations Drive pendant la confirmation des placements. Sauvegarder de
façon cohérente les deux bases, le bucket Docs avec ses versions, les réglages
privés et les versions de code/images. Une simple copie d'un bucket courant ne
remplace pas ses versions historiques.

Le drapeau `--confirm-frozen` atteste cette suspension ; la commande ne l'effectue
pas. Dans Docs, créer un nouvel inventaire, avec mesure bornée du contenu courant
et de ses médias référencés pour l'imputation logique :

```sh
python manage.py docs_drive_migration plan --confirm-frozen --output /private/frozen.jsonl
python manage.py docs_drive_migration verify --output /private/frozen.jsonl
```

Deux lectures identiques sont exigées avant émission du reçu. Une modification
ultérieure des contenus, groupes, métadonnées, versions ou invitations bloque
la vérification. Refaire ensuite le plan Drive à partir de cet inventaire gelé :

```sh
python manage.py docs_drive_migration plan --inventory /private/frozen.jsonl --output /private/placements-reviewed.jsonl
python manage.py docs_drive_migration stage --confirm-frozen --inventory /private/frozen.jsonl --plan /private/placements-reviewed.jsonl
python manage.py docs_drive_migration compare --inventory /private/frozen.jsonl --plan /private/placements-reviewed.jsonl --output /private/attachment.jsonl
```

`stage` crée les références cachées et leur imputation, par document atomique.
Le rejeu garde les mêmes UUID, droits et budgets. `compare` vérifie les rôles
hérités (utilisateurs et groupes), les capacités effectives, métadonnées et
imputations. Tout ajout de droits par le dossier de destination bloque le reçu.
Une modification de connexion ou un déplacement de destination exige un nouveau
plan. Aucun reçu complet n'est émis en cas d'échec.

## Liaison puis activation

Garder `DOCS_DRIVE_ENABLED=false` dans les deux applications et les mutations
suspendues pendant ces commandes. Dans Docs :

```sh
python manage.py docs_drive_migration attach --confirm-frozen --inventory /private/frozen.jsonl --attachment /private/attachment.jsonl --output /private/native-attached.jsonl
```

Cette commande conserve les documents, ACL historiques, demandes d'accès,
commentaires et invitations natifs. Elle ajoute seulement les liaisons et la
comptabilité des médias référencés. Elle est rejouable après une interruption.

Dans Drive :

```sh
python manage.py docs_drive_migration activate --confirm-frozen --inventory /private/frozen.jsonl --plan /private/placements-reviewed.jsonl --attachment /private/attachment.jsonl --native-receipt /private/native-attached.jsonl --output /private/drive-active.jsonl
```

L'activation relit la comparaison et le reçu natif avant de confirmer les
références. Elle n'active pas les paramètres des services. Après confirmation,
activer les deux applications ensemble et reprendre leurs services modifiés.
Vérifier connexion, ouverture, édition, révocation et sauvegarde avant de lever
la suspension des utilisateurs. Les autres services de la suite restent en place.

Les anciens courriels d'invitation continuent à ouvrir le même UUID. Le
bénéficiaire connecté peut accepter explicitement l'invitation depuis cette
page. Le serveur vérifie toujours destinataire, expiration, révocation et droits
actuels de l'émetteur ; un ancien courriel ne recrée pas un droit retiré.

## Reprise et annulation avant nouvelles écritures

Rejouer la même opération avec les mêmes entrées et un nouveau nom de reçu si
le précédent est incomplet. Ne jamais modifier un inventaire ou un reçu à la
main. `status --output …` vérifie son intégrité sans afficher les métadonnées.
Les reprises `stage`, `attach`, `activate` et `detach` conservent les identifiants.

Si la préparation a échoué avant toute liaison native, même sans comparaison
réussie, obtenir un reçu de non-liaison dans Docs puis annuler Drive :

```sh
python manage.py docs_drive_migration verify-unbound --confirm-frozen --inventory /private/frozen.jsonl --output /private/native-unbound.jsonl
```

```sh
python manage.py docs_drive_migration discard --confirm-frozen --inventory /private/frozen.jsonl --plan /private/placements-reviewed.jsonl --native-receipt /private/native-unbound.jsonl --output /private/discarded.jsonl
```

Les données natives doivent toujours correspondre au point gelé. Une préparation
déjà activée ou une réservation en cours bloque cette annulation partielle.

Avant toute nouvelle écriture intégrée, l'annulation conserve les données Docs.
Services mutateurs suspendus et intégration désactivée, dans Docs :

```sh
python manage.py docs_drive_migration detach --confirm-frozen --inventory /private/frozen.jsonl --attachment /private/attachment.jsonl --output /private/native-detached.jsonl
```

Puis dans Drive :

```sh
python manage.py docs_drive_migration rollback --confirm-frozen --inventory /private/frozen.jsonl --plan /private/placements-reviewed.jsonl --attachment /private/attachment.jsonl --native-receipt /private/native-detached.jsonl --output /private/drive-rollback.jsonl
```

Seules les références importées, leurs imputations et les dossiers de migration
restés vides sont retirés. Des traces techniques d'annulation sont conservées
pour rendre son rejeu sûr. Une modification ultérieure des données ou des droits
bloque cette procédure. Après de nouvelles écritures intégrées, restaurer un
point cohérent des deux applications et du stockage Docs dans un environnement
isolé, puis vérifier ensemble contenu, liaisons, médias et budgets ; ne jamais
restaurer seulement une base ni effacer des réservations à la main.

## Réconciliation courante

Le worker Drive réconcilie les projections toutes les dix secondes, par lots de
50. Une référence en préparation de migration ne peut pas être activée par ce
worker. Le worker Docs reprend les publications de contenu et notifications
toutes les trente secondes, par lots bornés. Les reçus de publication et les
réservations incertaines sont conservés jusqu'à vérification du stockage.

Les erreurs de connexion, révocation et changement de version restent distinctes.
Un export déjà publié peut être confirmé après modification du document source :
il conserve le PDF capturé par la demande initiale et ne réserve pas une seconde
copie. Un nouvel export de la version récente utilise une nouvelle demande.

## Profil du destinataire des invitations

L’IdP doit fournir `email` et `email_verified: true` dans UserInfo (connexion
Web) ou dans le jeton signé (API). La preuve de session conserve cette adresse
vérifiée jusqu’à son expiration ; une nouvelle connexion actualise le profil.
Une adresse non vérifiée ou absente refuse l’acceptation ; elle ne crée pas
d’association de compte. Les anciennes sessions sans cette preuve doivent se
reconnecter pour accepter une invitation. Aucune connexion préalable à Drive
n’est requise pour un utilisateur Docs.

## Diagnostic et reprise ciblée

Ces commandes n’affichent ni nom de document, ni contenu, ni credential.
Dans le backend Drive :

```sh
python manage.py shell -c 'from django.db.models import Count; from core.models import DocsBinding; print(list(DocsBinding.objects.values("state").annotate(total=Count("pk"))))'
python manage.py shell -c 'from core.tasks.docs_documents import reconcile_documents; reconcile_documents.delay()'
```

Dans le backend Docs :

```sh
python manage.py shell -c 'from django.db.models import Count; from core.models import DriveContentWrite; print(list(DriveContentWrite.objects.values("state").annotate(total=Count("pk"))))'
python manage.py shell -c 'from core.tasks.drive_documents import recover_document_writes; recover_document_writes.delay()'
```

- Création inachevée : rouvrir Docs avec le même compte ; la liste des
  préparations permet reprise ou annulation. Réutiliser la préparation et sa
  clé, ne pas recréer une seconde intention.
- Copie interrompue : reprendre depuis le même compte ; la clé conservée en
  sessionStorage est liée au document et aux options. Si la preuve a expiré,
  se reconnecter puis reprendre ; aucun worker ne simule le propriétaire.
- Dossier NAS disparu : le propriétaire utilise la récupération de classement
  présentée par Docs et choisit un espace autorisé. Ne pas recréer le chemin
  NAS pour tenter de récupérer une identité de dossier disparue.
- Quota refusé : le brouillon reste dans l’éditeur ; libérer de la place ou
  modifier l’allocation dans ST, puis utiliser le bouton de reprise.
- Publication incertaine : garder journal et réservation, rétablir le pair ou
  le stockage puis relancer la récupération bornée. Ne pas remettre les
  compteurs à zéro. Un envoi de courriel incertain exige un renvoi explicite.
- Purge interrompue : après confirmation native, une relance ciblée de
  `core.tasks.item.process_item_purge` sur l’Item déjà marqué pour suppression
  termine le nettoyage ; conserver les témoins et reçus d’idempotence.

## Mise à jour et rotation

Reconstruire la wheel commune avec `docker/suite/package_identity.py`, puis
les seules images modifiées. Vérifier les migrations additives, les quatre
credentials appariés et les deux émetteurs avant de recréer API et workers.
Une modification du frontend ou de la coédition impose aussi leur rebuild.
Le script de démarrage Drive reste séparé du démarrage de ST.

Pour une rotation, suspendre API/coédition/workers des deux applications,
sauvegarder en privé les deux jeux de clés puis retirer leurs copies actives
ensemble : `data/storage-secrets/docs-documents/` côté Drive et
`data/suite-local/docs/keys/documents/` côté Docs. Relancer le générateur sur
ces deux répertoires absents, puis recréer les services avec les quatre
nouvelles paires. Une divergence est une erreur, jamais une rotation implicite.
Après restauration, invalider sessions et délégations avant de rouvrir :
utiliser la révocation du socle d’identité et renouveler les credentials
interservices. Ne pas reprendre les anciens caches/sessions du point restauré.

Les sauvegardes privées utilisées et les résultats de restauration isolée
sont référencés dans le rapport final ; elles ne doivent pas être publiées.
