# Utiliser et administrer les espaces de stockage

Les espaces apparaissent dans la page normale de Drive. Leur nom décrit leur
usage ; leur destination technique est un réglage administratif. Un espace
utilise une connexion S3 ou MountProvider. Plusieurs espaces peuvent partager
une connexion, avec des droits et quotas différents.

## Utilisation quotidienne

Choisir un espace dans **Mes fichiers**, puis utiliser l'arbre, la recherche,
les favoris et les commandes habituelles. Les anciennes adresses de montages
restent compatibles et rejoignent la ressource autorisée. La recherche porte
sur les métadonnées accessibles ; elle ne parcourt pas le NAS à chaque frappe.

La création de documents, l'import, l'aperçu et l'édition utilisent le dossier
courant. Les éditeurs Collabora et ONLYOFFICE demandent leur configuration
WOPI habituelle. La conversion NAS des anciens formats Office demande le
service de conversion ONLYOFFICE ; l'original est conservé et le résultat
est publié comme un nouveau document. Une modification externe concurrente
provoque un conflit, sans écraser silencieusement les nouvelles données.

**Copier vers…** et **Déplacer** utilisent le même sélecteur d'espaces.
L'estimation montre les octets connus, les budgets concernés et l'impact sur
les partages. Un déplacement conserve les identifiants lorsque les contrôles
réussissent ; les liens incompatibles avec les droits de destination sont
révoqués durablement. Réactiver le partage ne réactive pas ces anciennes URLs.
Les octets sources peuvent rester temporairement en rétention pour la reprise.

**Compresser…** crée un ZIP dans l'espace choisi. Une sélection peut réunir
plusieurs ressources S3 et NAS. **Extraire vers…** accepte ZIP et TAR, y compris
les TAR compressés, et crée un nouveau dossier. Le lecteur d’archives permet aussi d’extraire
seulement les entrées sélectionnées vers n’importe quel espace autorisé.
Aucun fichier préexistant
n'est écrasé. Les limites de taille décompressée, de profondeur et de nombre
d'entrées sont vérifiées ; les liens et chemins dangereux sont refusés.
L'extraction vers un NAS exige son durcissement et l'activation de la protection
prévue dans le [contrat stockage](agent-storage-contract.md#mount-archive-extraction-hardening).
Le quota porte sur les octets réellement publiés, après compression ou
extraction. Les dossiers peuvent aussi être téléchargés directement en ZIP.

Les opérations longues figurent dans **Transferts**. Un conflit conserve les
résultats confirmés et indique l'action de reprise. Reprendre l'extraction
parente après avoir résolu ses fichiers en conflit. Une annulation n'est
possible qu'avant le début des écritures ; elle n'efface pas une publication.

La suppression NAS utilise les copies retenues lorsque le stockage le permet.
L'administration peut les restaurer vers une nouvelle destination autorisée.
Drive ne présente pas cette rétention comme des versions natives du NAS.
Une opération irréversible doit être confirmée comme telle dans l'interface.

## Administration courante sur le Web

Depuis l'administration du stockage dans Drive :

1. Ajouter une **connexion** et choisir sa famille. Pour S3, renseigner endpoint,
   bucket, région/adressage et préfixe éventuels ; pour MountProvider, choisir
   le provider et ses paramètres. Saisir les identifiants dans le formulaire
   sécurisé. Leur valeur existante n'est jamais relue dans une réponse API.
2. Tester la connexion, vérifier son état et l'activer. Les destinations doivent
   appartenir aux réseaux ou endpoints autorisés pendant l'amorçage.
3. Créer un **espace** : nom, connexion, racine, organisation et attribution
   comptable. Une racine NAS absente peut être créée depuis ce parcours.
   Une racine S3 existante peut être sélectionnée. Examiner les avertissements
   de recouvrement avant de confirmer une allocation imbriquée.
4. Accorder les droits de lecture, écriture et partage à des utilisateurs ou
   groupes. Une restriction de sous-dossier n'autorise pas ses voisins.
   Le propriétaire comptable n'obtient pas de droit supplémentaire implicite.
5. Utiliser le lien **ST Deploy Center** du périmètre pour régler son quota.
   Revenir dans Drive et vérifier la révision appliquée et la fraîcheur des
   compteurs. Un changement ST n'est pas effectif simplement parce que son
   formulaire a été enregistré : son application doit être confirmée.
6. Suivre inventaires, opérations, maintenance, reclassification et rétention.
   Une connexion encore référencée ne peut pas être supprimée. Un autre bucket
   ou namespace demande une nouvelle connexion ou un transfert explicite.

Les connexions techniques et leurs secrets sont réservés à l'administrateur
d'instance. Un administrateur délégué reste limité à ses espaces autorisés.
Une connexion importée du registre indique sa gestion externe ; sa reprise
sous gestion web est explicite. Un redémarrage ne réimporte pas un ancien
secret par-dessus une connexion reprise dans l'interface.

Les groupes sont les groupes Django, administrables depuis la gestion web des
utilisateurs. Leur identité `group:<id>` reste stable après renommage. Les
claims arbitraires d'un fournisseur OIDC ne créent pas automatiquement des
appartenances ; provisionner celles-ci selon la politique d'identité retenue.

## Quotas et accès directs au NAS

Les plafonds ST peuvent s'appliquer simultanément à l'instance, l'organisation,
l'utilisateur, au namespace, à l'espace et au couple utilisateur/namespace.
Un budget commun peut limiter un quota personnel plus élevé. Les espaces
imbriqués cumulent leurs contraintes sans doubler les octets du budget global.

Un compte technique NAS donne accès au stockage ; les grants et quotas Drive
répartissent cet accès virtuellement entre utilisateurs. Plusieurs comptes
peuvent représenter des connexions distinctes. Les alias physiques qualifiés
partagent une identité de namespace afin de ne pas compter deux fois les
mêmes données dans un budget donné.

Les écritures directes depuis un ordinateur ou une autre application restent
possibles. Drive les observe par inventaire : il ne peut pas intercepter leur
croissance. Après dépassement, il conserve les fichiers et refuse ses nouvelles
croissances. Un inventaire trop ancien bloque les admissions concernées jusqu'au
rapprochement. La capacité physique, lorsqu'elle est connue, reste distincte du
quota applicatif ; une capacité inconnue est affichée comme inconnue.

## Amorçage et exploitation

Docker, TLS, l'IdP, la première identité administrateur, la clé maîtresse du
coffre, les réseaux autorisés et les CA privées se configurent hors interface.
Voir le [guide homelab](homelab-storage-operations.md), puis la
[procédure de migration](installation/unified-storage-migration.md).

Le scheduler doit fonctionner avec les workers. Les archives et conversions
utilisent un espace temporaire sur disque, avec des buffers mémoire bornés.
Dimensionner ce volume pour les traitements simultanés ; le traiter comme
sensible et ne pas le nettoyer pendant une opération active. Les plafonds
`ARCHIVE_EXTRACT_MAX_*` bornent aussi la création d'archives unifiées.
Le répertoire central ZIP est plafonné à 32 Mio avant son chargement et les
archives TAR sont contrôlées avant la lecture des corps annoncés.

Sauvegarder les bases Drive/ST, chaque destination S3, chaque namespace NAS,
les journaux privés de reprise et le coffre avec sa clé séparée. Un simple
miroir de fichiers ne préserve pas nécessairement les identités de versions ou
les identifiants NAS. Suivre le [guide de restauration](installation/backup-restore.md).

La connexion S3 expose les objets gérés par Drive. L'import arbitraire d'un
bucket existant, la découverte native OpenZFS, la réplication et les autres
applications de la Suite restent des chantiers distincts.
