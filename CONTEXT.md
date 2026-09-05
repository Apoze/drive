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
