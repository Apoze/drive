# Validation finale — Transfers et Chat Apoze

12 septembre 2026. **Serveur/Web livrés sur le LAN ; Android qualifié sur
émulateur ; code iOS livré avec compilation et recette différées.**
Le [plan canonique](../../../docs/plans/suite/transfers-element-chat-integration-plan.md)
fixe ce périmètre et sa checklist mobile §14. Ce rapport remplace les états
partiels précédents ; le [journal](execution-journal.md) conserve leur chronologie.

## Recettes réellement exécutées

| Domaine | Résultat observé |
| --- | --- |
| Identité et catalogue | Connexion Keycloak/MAS, association `(issuer, subject)` People, autorisation ST ; même People/MXID et historique après migration isolée vers Authentik, sans rapprochement email |
| Accès Chat | Refus avec ancien jeton, lecture/événements/classic et sliding sync filtrés ; panne d'autorité fermée à 80 s, réadmission après rétablissement ; rôles, dernier responsable et reprise administrative qualifiés |
| Transfers standard/confidentiel | Vide, 32 Mio multi-chunks, AES-GCM, téléchargement/déchiffrement et empreinte ; clé confidentielle absente du serveur ; clé standard utilisée pour le scan |
| Scan et quotas | EICAR refusé, panne clamd puis rescan ; admissions concurrentes 201/403 près du plafond ; quotas et calendriers périodiques natifs ; réglages temporaires restitués |
| Cycle Transfers | Métadonnées GET non consommatrices, deux acquisitions one-shot 204/410, finalisation rejouée sans doublon, panne S3 avec réservation conservée puis purge |
| Gros transferts | Copie réelle de 20 Gio, empreinte identique, reprise après perte du worker et nettoyage ; aucune extrapolation du test mobile au plafond de 20 Gio |
| Drive/Docs | Copies S3/NAS, blocs rejoués, fichier vide, collisions, publication native et spool purgé ; export PDF privé ; sélection mixte, SSO, annulation et retour |
| Chat Web natif | Messages, réponse, fil, édition, réaction puis cinq redactions réelles ; médias chiffrés ; récupération/vérification des clés et reconnexion réseau avec renouvellement natif OAuth |
| UI Web | Catalogue, droits et médias, sélecteurs et cartes examinés sur desktop/520 px et sélecteur mobile 393 px ; actions/clavier, fermeture et correction des débordements observés |
| Meet | Création/rejoindre/terminer depuis le salon et appel à deux ; retrait ST à 27,2 s, groupe à 11,9 s ; pas de seconde pile d'appel, enregistrement ou transcription |
| Calendars/Messages | Invitation, mise à jour et annulation réelles ; événement natif et mails LAN ; rejeu sans doublon et accès contrôlé |
| Projects et bot | Création concurrente/rejeu, suppression sans recréation ; cartes privées ; refus ST à 22,2 s ; bot E2EE choisi, notification déchiffrée, perte d'accusé sans doublon, retrait, rotation et clés conservées au redémarrage |
| Android 36 | Login MAS/Keycloak, messages E2EE, ouverture/partage Meet, message sélectionné vers Projects, partage système de fichier Drive 32 Mio et lien Transfers |
| Pièce jointe Android vers Drive | 32 Mio copiés vers S3 après accord dans Drive, SHA-256 identique à la source NAS ; spool nettoyé ; mauvais vérificateur GET/PUT/PATCH/DELETE refusé |
| Pièce jointe Android vers Transfers | Deux envois natifs de 32 Mio en deux parties AES-GCM, finalisation standard et confidentielle, téléchargement/déchiffrement avec empreinte identique ; grants effacés ; mauvais vérificateur et autre fichier refusés |
| Échec multipart | ETag invalide rejeté ; seul le fichier fautif est retiré, le second fichier du brouillon reste présent ; nettoyage final par API |
| Mémoire native | Préflight Synapse sur la taille réelle du média avant SDK : local 32 Mio/200, distant/400, absent/404, anonyme/401 ; plafond 100 Mio, puis copie sortante en blocs de 25 Mio |
| Push côté serveur | Destinations arbitraires et payload privé refusés ; payload iOS natif admis, autre compte refusé ; retrait natif du pusher à 11,1 s après révocation. Aucune remise APNs/FCM revendiquée |
| Restauration Transfers | 6 objets, 211 812 855 octets identiques ; 2 comptes revalidés, lecture API identique, anciennes sessions refusées, one-shot déjà réclamé non rouvert ; aucun mail/usage ancien publié vers la pile vivante |
| Restauration Chat | Données, médias et clés restaurés isolément ; 4 comptes revalidés, anciennes sessions refusées, 5 messages déchiffrés via SDK et média 32 Mio identique ; aucun nouveau login IdP humain revendiqué dans la copie isolée |
| Grants restaurés | Helper courant testé sur PostgreSQL avec fichiers en attente et chargé : autorisations mobiles supprimées, transaction intégralement annulée, zéro écriture S3 ; vérificateur permanent et images historiques compatibles |

Les tests ont été regroupés par parcours ; aucun full systématique ni test de
présence de chaînes dans les fichiers source. Les vérifications Git de secrets,
changelog et publication sont des contrôles de livraison distincts.

## Builds et contrôles ciblés

- Images Transfers backend/frontend, Synapse, MAS, Element Web, Projects/bot et
  services modifiés construites et déployées au fil des lots ; migrations natives.
- Android Fdroid debug x86_64 : build 18 réussi. Build 17 installé et qualifié ;
  le dernier build ne change que les prévisualisations UI. APK conservé dans
  `Apoze/element-x-android/app/build/outputs/apk/fdroid/debug/`.
- iOS : sources relues et publiées ; **aucune compilation ni exécution Xcode**.
- TypeScript/builds Web et Ruff ciblés réussis. Dernier lint Drive sans erreur
  ni avertissement ; dernier lint Transfers sans erreur, trois avertissements
  préexistants dans les composants non modifiés sur ces lignes.
- Gitlint et gates de publication appliqués ; révisions dans [publication.md](publication.md).

## Nettoyage et pile conservée

- Vingt transferts et tous les brouillons de recette retirés avec purge réelle.
  Aucun item Drive de recette restant ; dossier/fichiers NAS retirés via provider.
  Le backend NAS, ses authentifications et la boîte mail préexistants sont conservés.
- Documents, projet/tableau/cartes et événement de recette supprimés ; réunion
  fermée et admissions révoquées. Dix-huit mails et treize blobs supprimés.
- Salon/médias de la nouvelle instance Chat de recette purgés : zéro salon,
  événement et média local au contrôle SQL. Dernier propriétaire et garde MAS
  conservés ; purge native hors ligne, puis Synapse/bot redémarrés.
- Deux personnes de recette suspendues, liens et sessions révoqués ; groupe,
  règles ST et utilisateurs/fournisseur IdP temporaires supprimés. Les références
  d'identité/quota/job utiles à l'audit restent inactives, sans fichiers vivants.
- Instances de restauration et ancien profil chat-qa supprimés. Archives privées
  de sauvegarde conservées selon la rétention ; elles contiennent l'état historique
  de recette et ne sont ni publiées ni des instances actives.
- Données des applications Chat/Chrome et téléchargements de l'émulateur retirés ;
  émulateur et worker de compilation arrêtés après les builds. Fichiers privés de
  recette/sessions téléchargés localement supprimés après extraction de ce bilan.
- Pile métier conservée : 72 conteneurs démarrés, aucun unhealthy. NAS : stat réel avec un
  utilisateur déjà autorisé. Chat discovery/versions, MAS discovery, Transfers,
  Drive HTTP/HTTPS et Keycloak : HTTP 200. Grist reste arrêté.

## Limites explicites et reprise autorisée plus tard

- LAN uniquement : `chat.zohenhl.ovh` doit résoudre vers `192.168.10.123` et les
  CA publiques LAN doivent être approuvées sur chaque nouveau client. WAN différé.
- iOS n'est pas encore compilé ; téléphone, signature/distribution Android/iOS,
  micro/caméra et cycle physique d'arrière-plan attendent les moyens correspondants.
- Credentials et réception APNs/FCM non qualifiés. Le build Android sans fournisseur
  push n'annonce pas de notification reçue. Checklist mobile §14 obligatoire avant
  d'annoncer une distribution mobile validée.
- SDK média mobile actuellement tamponné en mémoire : 100 Mio maximum pour les
  exports de pièces jointes Chat ; garder l'application ouverte pendant la copie.
  La reprise concerne le journal courant, pas un processus mobile détruit.
- E2EE : retirer un droit bloque les nouveaux accès ; cela n'efface pas un fichier
  ou des clés déjà reçus sur un appareil. Copies Drive/Transfers autonomes et droits
  propres à chaque application, confirmés explicitement.
- Standard Transfers : limite de scan partagée de 60 Mio, exemption administrative
  des gros fichiers désactivée par défaut et affichée honnêtement. Confidentiel :
  aucun scan serveur ni récupération de clé par l'administrateur.

Aucun défaut connu restant dans le périmètre livré n'est dissimulé derrière ces
reports. Les fonctions physiques et iOS non exécutées ne sont pas certifiées.

Artefact Android conservé : Fdroid debug x86_64, SHA-256
`03f30227f4d9daf5be290ee56db982c7b9da0bac6491728909db13143bca7cb2`. Build de développement, pas de distribution signée.
