# Validation Transfers et Chat

**Recette partielle ; chantier non livré.**

| Parcours réellement exécuté | Résultat |
| --- | --- |
| Keycloak → sujet pairwise vérifié → liaison People → autorisation ST | Connexion et profil authentifié 200 |
| Standard 32 Mio, deux chunks AES-GCM, S3 et clamd réels | Upload, scan, téléchargement et empreinte identique |
| Confidentiel vide, clé conservée dans le client de recette | 28 octets chiffrés ; téléchargement et déchiffrement vérifiés |
| EICAR chiffré en standard | Déchiffrement et détection réels ; finalisation refusée |
| Dépendances backend Transfers | Audit : aucune vulnérabilité connue après mise à jour des pins |
| Builds backend/frontend ciblés | Réussis ; migrations appliquées sur la seule base Transfers |
| Navigateur Chromium HTTPS avec CA reconnue | Interface authentifiée native visible |
| Session unique | GET non consommateur ; deux POST concurrents : 204/410 ; reprise et téléchargement S3 réussis |
| Quota utilisateur ST | Deux réservations réelles simultanées près du plafond : 201/403 ; plafond temporaire restauré et fichiers retirés |
| Finalisation rejouée | Même transfert rendu ; recette scripts/qa/suite-transfers.py exécutée avec nettoyage |
| Invitation confidentielle | Journal Messages sent et un message reçu via SMTP LAN ; aucune clé dans l’intention |
| Panne S3 limitée à Transfers | Réservation maintenue ; suppression multipart et ligne reprises automatiquement après rétablissement |
| Panne clamd limitée au worker Transfers | Finalisation standard bloquée, rescan explicite réussi et fichiers nettoyés ; scanner partagé préservé |
| Audit frontend de production | Aucune vulnérabilité connue après mise à jour i18next-http-backend et immutable |
| Calendrier Celery | Cause de la péremption des quotas corrigée ; fraîcheur périodique observée sans appel manuel |

R0/R1/R3 partiels uniquement ; R2 et R5–R9 non exécutés. Aucun résultat mobile,
aucune validation 20 Gio ni restauration annoncés. Les comptes/fichiers privés
de recette ne sont pas encore nettoyés.

## Jalon TC3/TC4 — 11 septembre 2026

- Retour Drive S3/NAS : blocs rejoués, fichier vide, publication native,
  digest et purge du spool passés après les derniers correctifs.
- Navigateur : copie confidentielle 32 Mio vers Drive vérifiée ; Docs PDF
  privé 1 285 octets ; sélection S3 + Docs, retour SSO, annulation et
  réouverture du sélecteur réussis.
- Contrôle visuel étroit : pas de débordement horizontal ; actions de gestion
  retirées du sélecteur, libellé de sélection mixte corrigé.
- Projects/Messages : deux requêtes du même événement, un mail reçu, journal
  `sent`. Le parseur Messages normalise les chevrons de Message-ID ; le contrôle
  porte sur l’identifiant opaque, pas son enveloppe SMTP.
- Ruff des backends modifiés, TypeScript et ESLint ciblés des trois frontends
  passent. Aucun test global ni comparaison de contenu source ajouté.
- Chat, mobiles, restauration isolée et nettoyage final : non validés.
