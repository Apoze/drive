# Activation de l'environnement local existant — 6 septembre 2026

## Périmètre

Environnement habituel Drive, avec sa base, son Keycloak PostgreSQL, son S3
SeaweedFS et les identifiants SMB déjà configurés. ST reste démarré séparément.
Le script `run_env_local.sh` n'a pas été modifié. Aucun commit ni publication.

## Réalisé

- Sauvegarde privée PostgreSQL Drive et ST avant intervention ; copie à froid
  de la base Keycloak historique, sans supprimer son ancien volume.
- Persistance explicite de Keycloak local et séparation du répertoire E2E.
- Relance complète avec le script existant, puis seconde relance pour vérifier
  la conservation exacte des identifiants Keycloak.
- Migrations SQL, simulation, migration des espaces deux fois et inventaire NAS.
  Les 158 Items historiques sont rattachés, sans copie des contenus.
- Activation de la gouvernance et des espaces unifiés sur API, worker et beat.
  Coffre privé commun ; accès réseau limité au NAS configuré et au réseau S3 local.
- Rétablissement du statut incomplet de deux imports de mars 2026 : aucune
  taille, aucun objet, aucune version ni marqueur de suppression S3. Métadonnées
  conservées ; leur ancien timestamp rend ces imports expirés dans l'interface.
- ST : migrations, URLs LAN, callback OIDC autorisé, issuer Keycloak stable,
  origines CSRF configurables. Profil initial du compte bootstrap Keycloak ST
  complété par le parcours normal, sans changer son mot de passe.
- Arrêt des API/frontends/workers de qualification unifiée qui étaient utilisés
  précédemment ; leurs données restent conservées.

## Vérifications

- Drive : 16 services de longue durée démarrés ; PostgreSQL, S3 et les deux
  éditeurs sont sains. ST : ses 6 services de développement démarrés.
- Conservation des identifiants Keycloak après relance : empreinte avant/après
  identique, vérifiée sans afficher les identités.
- Connexion navigateur réelle via Keycloak vers Drive : `/users/me/` HTTP 200.
- Connexion navigateur réelle via Keycloak vers ST : `/users/me/` HTTP 200.
- Interface ST rendue, navigation opérateur présente, aucune erreur navigateur.
- Écran ST des quotas ouvert ; requête PATCH provenant du LAN acceptée par
  CSRF puis refusée par validation métier pour un quota négatif (HTTP 400).
  Aucun changement du plafond réel lors de ce contrôle. Lien du service Drive
  corrigé vers son URL LAN, à la place de l'ancienne URL d'exemple.
- Catalogue commun Drive rendu, espaces S3 et NAS visibles selon les grants.
- Authentification SMB et listing natif de la racine : réussite.
- Création d'un dossier dans l'explorateur sur S3 et NAS : réussite. Navigation
  NAS sans erreur navigateur ; suppression des dossiers vides de vérification
  par les API authentifiées, après contrôle de leur absence de contenu.
- Politique ST reçue et appliquée dans Drive avec accusé de révision.
- Préflight LAN OIDC et `config_preflight` : réussite.
- Audit de compteurs et vérification des tailles S3 : zéro écart après correction.
- Ruff ST sur le fichier de configuration modifié : réussite.
- Configurations Compose local/E2E : répertoires Keycloak distincts vérifiés.

## Recette réelle terminée après autorisation des quotas

L'opérateur a autorisé 20 Go pour les essais. ST conserve désormais
**20 000 000 000 octets pour ce compte de test** et pour l'organisation,
dont le plafond de 10 Go bloquait les 15,59 Go historiques. Le défaut des autres
utilisateurs reste à 5 Go. Aucun rôle administrateur supplémentaire n'a été accordé.
La révision est reçue par l'API et le worker, puis accusée dans ST.

| Parcours sur la pile LAN existante | Résultat |
| --- | --- |
| Connexions Keycloak Drive et ST | Réussite |
| Import et aperçu PDF deux pages sur S3 et NAS | Réussite |
| Téléchargements navigateur S3 et NAS | Réussite, octets identiques |
| Création ODT et DOCX sur S3 et NAS | Réussite |
| Collabora : modification et sauvegarde ODT S3/NAS | Réussite |
| ONLYOFFICE : modification et sauvegarde DOCX S3/NAS | Réussite |
| Copie S3 vers NAS et NAS vers S3 | Réussite |
| Déplacement S3 vers NAS et NAS vers S3 | Réussite |
| Intégrité des cinq PDF après les transferts | Identiques |
| Journal des transferts dans l'interface | Résultats affichés |
| Session Drive anonyme | Refus HTTP 401 |
| Politique ST appliquée et accusée | Réussite |

Les sauvegardes des quatre documents ont été vérifiées en relisant leurs octets
sur le stockage final, avec les droits du compte de test. Ouvrir l'éditeur seul
n'a pas été considéré comme une réussite. La fenêtre de bienvenue Collabora
sur le parcours NAS a été fermée par son gestionnaire DOM pendant l'automatisation ;
les clics Playwright ciblaient son document préchargé invisible. Les modifications
et sauvegardes ont ensuite été effectuées au clavier dans l'éditeur réel.

### Correction révélée par la recette

L'API résolvait `host.docker.internal`, contrairement au worker et au scheduler.
Les transferts ne pouvaient donc pas rafraîchir la politique ST. Le même
`extra_hosts` que celui de l'API a été ajouté à ces deux services dans
`compose.yaml`, puis ils ont été recréés en mode local. La réception de la
politique depuis le worker, la reprise par l'API normale et les transferts réels
valident cette correction. Le script de démarrage reste inchangé.

### Nettoyage et état final

- Suppression par les API authentifiées des fichiers et dossiers dédiés, y
  compris le dossier vide d'un essai précédent et la corbeille S3 correspondante.
- Nettoyage des copies de secours et fichiers intermédiaires de ces seuls essais
  via les services existants. Le délai de rétention a été ramené à zéro seulement
  dans le processus de nettoyage ciblé, sans changer la configuration de la pile.
- Suppression physique des versions et marqueurs S3 des clés de test exactes ;
  vérification de leur absence, et de 14 chemins NAS de test/intermédiaires.
- Retour aux **158 Items historiques** et à **15 586 247 860 octets** comptabilisés.
  Aucun dossier `verification-locale-*` ne reste dans les Items.
- Audit final avec vérification des tailles S3 : aucun écart, conflit
  d'attribution, opération active, transfert actif ou connexion non initialisée.
- Les 16 services Drive et les 6 services ST restent démarrés ; les services
  disposant d'un contrôle de santé sont sains. Vérification système Django réussie.
- Fichiers téléchargés et captures temporaires de ces essais supprimés localement.

Les contrôles portaient sur les parcours navigateur, les réponses des services,
les fichiers synthétiques sauvegardés et les compteurs. Aucun test de présence
ou de contenu textuel dans les fichiers de code n'a été ajouté ou exécuté.
Il s'agit d'une recette fonctionnelle ciblée de la pile LAN, pas d'une nouvelle
campagne exhaustive, d'un test de charge ou d'une validation de toutes les
combinaisons de fournisseurs. Les preuves antérieures restent documentées dans
la recette générale. Aucun commit ni publication.

Les sauvegardes privées de configuration et de bases sont conservées dans
`tmp/local-stack-restart/`, exclues de Git. Les journaux de diagnostic et scripts
locaux de recette y restent ; les fichiers téléchargés et captures ne sont pas
conservés. L'attribution d'un administrateur Drive reste un choix de l'opérateur,
indépendant des essais utilisateur terminés ici.
