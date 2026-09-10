# Visio Apoze — recette locale du 8 septembre 2026

Périmètre : cœur Meet/LiveKit, People/ST, OIDC, groupes, invités admis.
Aucun enregistrement, transcription, IA, téléphonie, fichier ou S3 Meet.
Déploiement LAN uniquement ; exposition Internet/certificat public différés.

## Résultats

| Contrôle ciblé | Résultat |
| --- | --- |
| Chromium organisateur + Firefox invité | Audio/vidéo reçus des deux côtés, contexte HTTPS sécurisé. |
| Écran et chat | Écran décodé chez le second participant ; message reçu. |
| Salle d'attente et expulsion | Admission explicite ; expulsion constatée en 356 ms. |
| Jetons transport | JWT initial et vrai JWT renouvelé par LiveKit refusés après retrait : 403/403. |
| Retrait ST sous Authentik | Médias interrompus en 35,44 s, accès transport ensuite refusé. |
| Arrêt du contrôleur isolé | LiveKit arrêté par son garde ; navigateur fermé en 56,35 s. |
| Reconnexion | Interruption réelle du proxy Meet 3 s ; nouvelle signalisation et connexion WebRTC rétablie. |
| Renouvellement OIDC Web | Popup Keycloak, nouvelle preuve vérifiée, admission existante prolongée. |
| Gestion Web | Groupe, rôle de groupe, personne, renommage, fermeture/réouverture, suppression. |
| Rôles serveur | Coorganisateur autorisé ; promotion vers propriétaire et mutation d'un membre refusées. |
| Concurrence propriétaire | Deux suppressions concurrentes : une seule réussit, un propriétaire reste. |
| Administration locale | Accès au paramètre invités ; compte de récupération refusé sur l'API utilisateur. |
| Fonctions exclues | Routes fichiers/recordings/subtitles/roomkit/addons/diagnostics refusées. |
| Webhook | Signature/corps/type vérifiés ; événement optionnel répété ignoré sans créer de fichier/job média. |
| IdP | Keycloak → Authentik → Keycloak sur copie isolée : même PK utilisateur, propriétaire et ACL de groupe. |
| Restauration | Dump PostgreSQL réellement restauré ; salle, propriétaire, groupe conservés ; admissions/cache de sessions invalidés. |
| Catalogue | Lien Visio visible et autorisé depuis Drive, ST, People, Docs et Meet. |
| Suite existante | Une seule saisie Keycloak pour Drive/ST/People/Docs ; API et navigation NAS/S3/Documents : 200. |
| Déconnexion Web | Révocation commune confirmée, ancienne session Meet refusée : 401. |
| Nettoyage | Salles/admissions de recette et piles isolées supprimées ; 36 services initiaux + 6 Meet. |

Dernier relevé RTP de contrôle : Chromium 175 images vidéo décodées, Firefox
115 ; aucun paquet perdu observé pour l'audio et la vidéo sur cet intervalle.
Transport candidat retenu UDP, jitter observé au plus 5 ms. Il ne s'agit pas
d'un benchmark de charge ni d'une garantie sur d'autres réseaux.

Les deux tests natifs de `core/tests/test_suite_admissions.py` passent.
Ruff sur les sources concernées, Pylint erreurs sur les modules backend
concernés, ESLint sur les fichiers frontend modifiés, build TypeScript/Vite,
checks Django et absence de migration manquante : vérifiés. Aucun full E2E,
aucune nouvelle infrastructure de tests et aucun test de contenu des sources.
Les contrôles de publication recherchent séparément les secrets et les
instructions Git interdites.

## Défauts corrigés pendant qualification

- Sélecteur de partage adapté aux réponses paginées natives.
- DNS Docker du proxy actualisé lors du remplacement d'un backend.
- Renouvellement du même compte OIDC : persistance explicite de la preuve
  vérifiée, car le callback natif ne réémet pas de signal de login.
- Signalisation refusée pendant une amorce SFU sans contrôle frais.
- Sessions du cache natif invalidées lors d'une restauration.
- Default de salle évalué à l'exécution, sans migration différente selon le
  profil de configuration.
- Webhooks internes conservés sur le réseau privé, sans redirection HTTPS
  vers un port qui ne sert pas TLS.

## Limites explicites

Les médias de qualification sont synthétiques, échangés par deux vrais
navigateurs. Aucun poste physique de l'utilisateur n'a été configuré ni sa
caméra/micro testé à distance. La CA locale est approuvée dans les profils
de qualification du serveur ; ses appareils doivent lui faire confiance
avant d'utiliser micro/caméra. Certificat public, DNS extérieur, NAT/TURN et
exposition Internet restent hors de cette livraison à sa demande.

Le repli TCP direct est configuré ; ce relevé de médias porte sur UDP.
Le partage mobile et le son système restent soumis aux capacités natives.
Les profils individuels du sélecteur sont disponibles après première
connexion ; les droits de groupes People sont attribuables à l'avance.

Les scripts de recette et journaux privés restent dans le workspace Drive
`tmp/meet-execution` et `data/meet-execution`. Les preuves publiques sobres
sont dans `output/playwright/meet-core`. Aucun token/cookie/secret ne figure
dans ce rapport ni dans les sources publiées.

## Livraison

Commit `9a3d588907e94d725ebf24576156c141e90892fd`, publié sur
https://github.com/Apoze/meet.git, branche `main`. Fork local propre, seule
branche locale/distante `main`. `upstream` : https://github.com/suitenumerique/meet.git,
fetch-only, push désactivé. Aucune PR (base/head/URL sans objet), aucune action
vers le dépôt officiel. GitHub Actions du fork reste désactivé ; contrôles
locaux et gitlint réussis. Les travaux préexistants Drive/ST/People/Docs sont
conservés et ne sont pas inclus dans cette publication.
