# Apoze Drive

Apoze Drive provides collaborative storage and access to files and folders.
This glossary names the product concepts whose boundaries matter across the
backend and frontend.

## Language

**Élément Drive**:
Fichier ou dossier géré durablement par Drive avec une identité stable.
_Avoid_: Entrée montée

**Entrée montée**:
Fichier ou dossier exposé par un système de fichiers externe à travers un
montage, sans devenir un élément Drive.
_Avoid_: Élément Drive

**Ressource**:
Fichier ou dossier présenté dans l'explorateur commun, qu'il soit un élément
Drive ou une entrée montée. Sa référence désigne le même contenu logique lors
d'un déplacement confirmé.
_Avoid_: Connexion, copie, emplacement

**Connexion de stockage**:
Accès administré à un stockage externe avec sa propre configuration et son
compte d'authentification, distincts des comptes des utilisateurs de Drive.
_Avoid_: Compte utilisateur, espace

**Espace**:
Vue autorisée d'une partie du stockage, avec ses bénéficiaires et sa politique
d'utilisation. Plusieurs espaces peuvent présenter une même ressource.
_Avoid_: Partition physique, connexion

**Attribution de stockage**:
Rattachement d'une ressource aux personnes et espaces dont elle consomme les
quotas, indépendamment de ceux qui peuvent la lire ou de son dernier auteur.
_Avoid_: Droit d'accès, propriété du NAS

**Quota applicatif**:
Limite d'utilisation définie par l'application pour une instance, organisation,
connexion, espace ou utilisateur, indépendamment des limites du stockage externe.
_Avoid_: Espace disque libre, quota du NAS

**Copie**:
Nouvelle ressource indépendante créée à partir d'une source conservée, avec une
nouvelle attribution et une consommation supplémentaire de quota.
_Avoid_: Déplacement, duplication de référence

**Déplacement**:
Changement d'emplacement d'une ressource conservant sa référence. Le retrait de
la source fait partie de l'opération et peut rester en attente après publication.
_Avoid_: Copie terminée, suppression immédiate

**Source retenue**:
Version d'origine conservée après une publication confirmée tant que son retrait
ne peut pas être prouvé sûr ou que le délai de rétention n'est pas écoulé.
_Avoid_: Transfert entièrement terminé, sauvegarde générale

**Journal d’activité**:
Historique chronologique des actions concernant directement un fichier ou
dossier Drive, visible par ses propriétaires et administrateurs. Il n’agrège
pas l’activité des descendants d’un dossier.
_Avoid_: Journal d’audit, audit global, télémétrie PostHog

**Journal d’audit**:
Historique global destiné aux administrateurs pour la sécurité, la conformité
et le contrôle d’une organisation.
_Avoid_: Journal d’activité

**Téléchargement lancé**:
Événement d’activité indiquant qu’un utilisateur a commencé un téléchargement
autorisé. Il n’atteste pas de la réception complète du fichier par le client.
_Avoid_: Fichier téléchargé, téléchargement terminé

**Modification d’un élément**:
Famille de trois événements d’activité distincts : élément renommé, description
modifiée et contenu modifié.
_Avoid_: Élément modifié

**Suppression d’un élément**:
Dans le journal d’activité, désigne la mise à la corbeille; la restauration est
un événement distinct. La suppression définitive efface aussi le journal.
_Avoid_: Suppression définitive journalisée

**Partage d’un élément**:
Famille d’événements distincts pour les accès utilisateur ou équipe, les
invitations et les liens de partage, chacun couvrant sa création, modification
ou révocation.
_Avoid_: Élément partagé


## Identité de la suite

**Principal** : personne People identifiée durablement par son UUID, distincte
de ses comptes applicatifs et de ses connexions IdP.

**Identité externe** : liaison vérifiée issuer/subject/client vers un principal.
L'email n'est pas une clé de rapprochement.

**Groupe de suite** : équipe People identifiée par `Team.external_id`, projetée
vers les clés de groupes natives sans réécrire les grants existants.

**Accès applicatif** : décision ST autorisant l'ouverture d'une application ;
elle ne donne pas à elle seule de droits sur un document ou un espace.

**Autorité de groupe** : People par défaut, ou une source externe explicitement
reliée par SCIM ; une seule source peut modifier le membership d'un groupe.

**Projection** : copie locale versionnée de l'annuaire et des politiques,
utilisable seulement pendant la durée de fraîcheur publiée.

Décision : [ADR 0003](docs/adr/0003-suite-durable-identity-and-access.md).


## Native Docs documents in Drive

Integration is enabled on the LAN since 9 September 2026. Drive owns
logical placement, grants, lifecycle and quotas; Docs retains content, media
and versions in private storage. S3 and mounted spaces share the historical
My Files explorer. Follow
[the canonical plan](docs/plans/suite/docs-drive-native-documents-integration-plan.md)
and [ADR 0004](docs/adr/0004-docs-drive-native-documents.md). Do not interpret
the already operational Docs catalogue/SSO entry as native document integration.


## Messages et Calendars

Messagerie et agendas LAN intégrés au projet `suite-mail`. People identifie les
personnes/groupes, ST autorise les applications et budgets ; Messages possède
les boîtes et leurs droits, Calendars les agendas/événements. L’adresse d’une
boîte est un attribut de routage, pas une identité utilisateur. Les agendas
restent utilisables sans boîte mail ; les invitations exigent une boîte
émettrice autorisée. Le [plan canonique](docs/plans/suite/messages-calendars-integration-plan.md)
et le [guide](docs/operations/suite-messages-calendars.md) décrivent les limites
et la reprise. Grist reste en pause et le WAN n’est pas activé.

## Projects — intégration LAN

Projects utilise OIDC, People et ST ; Drive/Docs restent les autorités des
fichiers liés et Messages assure les notifications LAN.
Plan : `docs/plans/suite/projects-integration-plan.md`.
Exploitation : `docs/operations/suite-projects.md`.
Suivi : `output/implementation/projects-integration/current-status.md`.
Grist reste en pause ; ne pas reprendre ce chantier implicitement.
