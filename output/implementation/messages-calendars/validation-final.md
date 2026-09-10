# Messages et Calendars — validation de l’intégration LAN

10 septembre 2026. **LIVRÉ SUR LE LAN — MC0–MC10 terminés.**
Recette, nettoyage, sauvegarde cohérente et restauration isolée effectués.

## Résultat et périmètre

Messages `http://192.168.10.123:8900` ; Calendars
`http://192.168.10.123:8930`. Projet Docker `suite-mail`, 14 services.
Catalogue visible, connexion OIDC commune, personnes/groupes People et accès
ST. L’environnement Drive/NAS/Keycloak/People/ST/Docs/Meet est conservé.
ST UI : port 8960 ; API : 8961. Les scripts de démarrage Drive sont inchangés.

Les boîtes et agendas de recette sont supprimés. Le domaine LAN
`mail.apoze.test`, les consommateurs, canaux machine, rôles et plafonds
opérationnels sont conservés. L’administrateur crée les nouvelles boîtes depuis
Messages ; aucun destinataire Internet n’est acheminé par ce déploiement LAN.

## Preuves réutilisées

| Parcours réel | Résultat observé |
| --- | --- |
| Connexion et catalogue | Messages/Calendars autorisés depuis Messages, Calendars et Drive ; 11 contrôles de routes/fichier existant réussis |
| Boîtes et groupes | Propriétaire People choisi dans l’UI ; grants directs/groupes composés ; retrait effectif sans effacer le grant direct |
| Rôles | Viewer ne répond pas au nom de la boîte (403) ; administrateur de domaine ne peut supprimer une boîte possédant un agenda (409) |
| Messagerie | Brouillon, envoi, réponse, transfert UI, Bcc non exposé, recherche indexée, export EML ; destinataire valide livré et inexistant échoué séparément |
| Quotas Messages | Deux admissions concurrentes de 8 octets sous un plafond de 10 : 201/507 ; budgets et réservations atomiques, libération après purge |
| Imports | MBOX réduit importé, reprise idempotente, export et oubli natifs ; aucun objet/import réservé restant après nettoyage |
| Antivirus | Upload 503 si ClamAV indisponible ; EICAR SMTP en quarantaine, absent des Messages ; scanner rétabli |
| DAV et ICS | PROPFIND/REPORT 207, PUT/DELETE, abonnement ICS 200 ; anciens canaux DAV 401 et ICS 404 après révocation |
| Récurrences | Fuseau/changement d’heure, exception, édition UI d’une occurrence et des suivantes ; COUNT restant, VALARM et propriété opaque préservés |
| Écriture atomique | Modification invalide rejetée 400 sans tronquer la série ; ancienne ETag rejetée 412 |
| Confidentialité | Calendrier partagé lisible, événement privé retiré du VCALENDAR reçu par un lecteur ; UUID résolu vers l’adresse métier pour les participants |
| Invitations | REQUEST → REPLY → mise à jour EXDATE → CANCEL ; METHOD MIME/ICS identiques, séquences conservées, une copie envoyée et une reçue par émission |
| Boîte partagée | Réponses concurrentes ACCEPTED/TENTATIVE terminées, réponse après modification, annulation des copies ; ancienne invitation refusée même après suppression de la copie |
| Panne ciblée | Intention d’invitation durable pendant une panne Messages, reprise sans doublon de mail |
| Agendas de boîtes | Suppression réelle depuis le bouton natif par admin de boîte (204), absence après rechargement ; utilisateur non autorisé refusé 403 |
| Calendars indépendant | Sans boîte ni adresse principale : création d’agenda personnel depuis l’UI 201, persistance après rechargement, suppression 204 |
| Ressources | Réservation concurrente ACCEPTED/DECLINED ; suppression refusée avec réservation active, acceptée après annulation |
| Drive S3/NAS | Aller-retour pièce jointe/fichier avec même empreinte ; reprise idempotente ; collision refusée sans écrasement ; refus de quota contrôlé par ST, politique restaurée |
| Docs | Export PDF natif et lien authentifié envoyé depuis le sélecteur ; destinataire sans droit refusé 404 ; aucun partage implicite |
| Meet | Création native d’une salle propriétaire ; destinataire en attente d’admission, aucune admission automatique |
| IdP | Keycloak → Authentik → Keycloak isolé : mêmes comptes, mail, événement et UUID ; anciens accès refusés |
| Révocation | Retrait du groupe observé en 16,9 s, mail/calendrier/DAV/ICS refusés 404 ; borne de fraîcheur configurée 90 s |
| Restauration | Mail, pièce jointe, blob S3 et événement réellement relus ; ancien grant retiré après réconciliation People/ST actuelle ; anciennes sessions/canaux désactivés, aucun SMTP/egress |

Preuves structurées : [IdP](identity-roundtrip.json),
[restauration](restoration-readback.json), [iTIP](itip-readback.json),
[smoke final](final-smoke.json), [nettoyage](cleanup-readback.json),
[état runtime](runtime-status.txt). Le
[journal](execution-journal.md) conserve les corrections et résultats
intermédiaires ; ses anciens « non livré » sont des points de reprise datés.

Les outils temporaires Playwright ont piloté le navigateur et les APIs réelles.
Les lectures Django/SabreDAV ont confirmé les effets métier et les empreintes.
Aucune vérification de présence de texte dans le code et aucune matrice E2E
exhaustive n’ont été utilisées. Les scénarios ont été repris uniquement après
correction ou échec de leur préparation (sessions expirées, mauvais chemin DAV,
attente réseau d’une page de diagnostic, comptage GET export non supporté).
Un échec de préparation n’est pas présenté comme un test réussi.

## Validation statique et construction

Ruff ciblé sur les fichiers Python modifiés des deux forks, checks Django et
absence de migrations manquantes ; syntaxe des 18 fichiers PHP touchés.
Builds natifs frontend avec TypeScript ; oxlint ciblé Calendars, contrôles
frontend précédents conservés. Whitespace des diffs vérifié. Pas de full pytest
ou de full E2E déclenché pour ce chantier.

Les versions Django/Pillow ont été corrigées à partir des avis officiels :
[Django 5.2.17](https://www.djangoproject.com/weblog/2026/aug/04/security-releases/),
[Pillow EPS](https://github.com/python-pillow/Pillow/security/advisories/GHSA-pg7v-jwj7-p798),
[Pillow FITS](https://github.com/python-pillow/Pillow/security/advisories/GHSA-whj4-6x5x-4v2j).
Cela n’est pas un audit exhaustif de sécurité de l’ensemble du serveur.

## Refaire une régression utile

1. Depuis l’UI admin Messages, créer deux boîtes temporaires ; attribuer un
   propriétaire People à chacune et un accès Viewer à la boîte partagée.
2. Créer un agenda de boîte et une série de trois occurrences. Ajouter une
   exception, inviter la seconde boîte, répondre dans Messages puis modifier
   et annuler. Vérifier le statut organisateur et le refus de l’ancien RSVP.
3. Pour un changement au découpage : modifier « cette occurrence et suivantes »
   au milieu de la série ; relire l’ICS et son COUNT restant. Soumettre une fin
   avant début avec l’ETag courante : 400 et original inchangé. Ne pas relancer
   toute la suite pour cette seule correction.
4. Pour un changement de droits : retirer le grant People, attendre au plus
   90 secondes ; l’ancienne session et le canal personnel doivent perdre
   l’accès. Un rôle Sender ne doit pas supprimer l’agenda de boîte.
5. Pour les ressources : créer une réservation, tenter la suppression (refus),
   annuler, puis confirmer la suppression (204). Pour compter les réservations,
   utiliser REPORT calendar-query ; GET `?export` n’est pas cette vérification.
6. Pour un changement de stockage : une pièce jointe minuscule vers S3 puis NAS,
   une relecture d’empreinte ; baisser le budget **dans ST**, vérifier le refus,
   restaurer le budget dans un finally. Supprimer ensuite tous les fichiers.
7. Effacer uniquement les fixtures créées. Contrôler `mail_operations.py status`
   et la collecte native avant sauvegarde. Restaurer en isolat seulement si les
   mécanismes de sauvegarde, schéma, stockage ou identité ont changé.

## Exploitation, limites et état Git

Le [guide d’exploitation](../../../docs/operations/suite-messages-calendars.md)
contient les commandes, comptes de récupération, règles d’adresse/boîte,
limites mémoire/tailles/récurrence et restauration. Les mesures runtime
rapportent de petits volumes LAN ; aucun engagement de débit sous forte charge
n’en est déduit. WAN, DNS/certificats publics, délivrabilité Internet, IMAP/POP,
IA, enregistrement/transcription et Grist restent hors de ce chantier.

Révisions locales : [manifest des checkouts](local-revisions.json).
Sources amont de base : Messages v0.9.0
`1cb101c0659256212ec8f803d96aa2a24334c4f8` ; Calendars v0.1.0
`00487b531328dfb9989181b6d446504d4f6aca3a`. Les nouveaux développements sont dans
les diffs locaux et les archives de sauvegarde, pas dans ces commits amont.

- Fork `https://github.com/Apoze/messages.git`, branche locale
  `codex/suite-messages-calendars` ; source `https://github.com/suitenumerique/messages.git`, fetch-only.
- Fork `https://github.com/Apoze/calendars.git`, branche locale
  `codex/suite-messages-calendars` ; source `https://github.com/suitenumerique/calendars.git`, fetch-only.
- Drive `https://github.com/Apoze/drive.git`, branche locale
  `codex/messages-calendars-integration`. Le travail antérieur était déjà très
  important : aucune réinitialisation ni publication globale de ce diff.
- ST reste local ; Docs/Meet conservent leurs checkouts et modifications
  ciblées du SDK. Les deux forks Messages/Calendars ont ensuite été publiés
  sur demande explicite ; voir [publication](publication.md).

Les contrôles de publication des deux forks sont passés ; les modifications
historiques des autres checkouts restent locales.
Le travail fonctionnel LAN n’est pas conditionné à une publication GitHub.


## Sauvegarde finale

`data/messages-calendars-backups/20260910T130928Z/` : sauvegarde complète après
nettoyage, trois dumps, configuration/clés, archives sources, images exactes,
blobs natifs. [Manifeste public sans secrets](backup-manifest.json).
La correction de résolution des index OCI a été exercée sur les conteneurs
réels : manifeste de plateforme identique, archive finale complète. Les essais
refusés avant arrêt sont écartés et les archives contenant des fixtures sont
retirées après qualification de cette dernière sauvegarde.


La dernière archive a aussi été restaurée en isolat :
[preuve de restauration après nettoyage](final-restore-readback.json).
Zéro mail/événement est le résultat attendu de ce second contrôle, puisque les
fixtures ont été effacées ; la lecture réelle de contenu reste démontrée par
la précédente [recette de restauration](restoration-readback.json).
L’isolat final et ses volumes ont été supprimés. Une seule sauvegarde mail
nettoyée est conservée ; [archives de recette retirées](backup-cleanup.json).
Les autres données/historiques du serveur n’ont pas été purgés.
