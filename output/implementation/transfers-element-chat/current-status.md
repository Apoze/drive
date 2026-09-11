# Transfers et Chat — état courant

Exécution autorisée le 10 septembre 2026. **Chantier en cours, non livré.**

- Lot actif : préparation Chat TC1/TC5 ; parcours Transfers TC3/TC4 validés.
  Fondations TC0/TC2 partielles.
- Pile existante préservée et démarrée. Ajout des cinq services Transfers
  (backend, worker, beat, frontend, edge HTTPS) ; base et bucket dédiés.
- Identité native raccordée à People/ST. Connexion Keycloak réelle avec
  rattachement explicite du sujet pairwise vérifié ; aucun rapprochement email.
- Upload chiffré standard 32 Mio, téléchargement et empreinte : validés.
  Fichier vide confidentiel : validé. EICAR chiffré analysé par clamd : bloqué.
- Quotas utilisateur concurrents, reprise après panne S3, session unique,
  administration et catalogue : recettes réelles passées. Politique et quotas
  configurés depuis ST Web ; invitation remise réellement par Messages.
- Révocation ST : refus mesuré à 4,2 s ; ancienne URL S3 expirée à 40,3 s.
- Fichier de 20 Gio : upload, téléchargement, digest et nettoyage réussis
  en 165,3 s après correction de la capacité S3 partagée ; budgets restaurés.
- HTTPS LAN avec CA privée ; confiance installée dans le navigateur de recette.
  Distribution de la CA aux appareils du propriétaire encore à documenter.
- Limite du clamd partagé : 60 Mio en standard analysé ; aucun dépassement
  silencieusement accepté. Dérogation aux fichiers trop grands administrable
  dans ST, désactivée par défaut et remise à cet état après recette.
- Forks créées : Apoze/transfers, Apoze/synapse, Apoze/element-web,
  Apoze/element-x-android, Apoze/element-x-ios. Aucun commit/push d'implémentation.
- Messages relié ; imports privés S3/NAS standard et confidentiel validés.
  Reprise après perte du worker et refus de source modifiée validés.
  Retour OIDC après approbation People corrigé (paquet identité 0.1.5).
  Reconnexion Transfers préservant le brouillon validée en navigateur.
  Retour vers Drive : API S3/NAS et fichier vide validés ; parcours navigateur
  confidentiel S3 32 Mio passé, empreinte identique et spool supprimé.
  Export PDF Docs privé réussi. Matrix/MAS/Element : non livrés.
- Nom durable Matrix demandé au propriétaire, réponse attendue ; aucune
  identité Matrix de production créée. Les autres travaux restent possibles.
- Linux, Xcode/Android SDK/adb/émulateur absents du PATH ; KVM présent.
  Aucun Mac accessible identifié. Recette mobile reportable selon le plan.
- Modifications antérieures People et Grist conservées ; Grist reste en pause.

Prochaine action : publier le jalon Transfers, puis poursuivre Synapse/MAS
et Element (TC1/TC5). Guide exploitation Transfers rédigé ; restauration TC11
et nettoyage final restent à exécuter.
Les fixtures et sauvegardes restent privées dans data/ et tmp/ ; nettoyer
exactement le principal de recette et ses octets avant livraison.

Compléments du 11 septembre :
- Reconnexion Transfers par popup : brouillon conservé, ajout repris.
- ST beat était sorti sur erreur DNS temporaire ; DNS vérifié, service repris
  et redémarrage automatique configuré. Fraîcheur People/ST rétablie.
- Retour Drive : rejeux de blocs, collision sans remplacement, annulation et
  libération des réservations passés en conditions réelles.
- Mémoire bornée à 25 Mio par bloc reçu, spool privé partagé app/worker,
  plafond disque séparé et publication par les journaux natifs S3/NAS.
- Les changements restent locaux, sans commit ni push d’implémentation.

- Sélection multiple S3/Docs PDF, annulation du picker, nouvelle ouverture et
  conservation des fichiers après SSO : validées. TypeScript/ESLint ciblés
  Drive/ST/Transfers passent ; Ruff backend ciblé passe.
- Régression Projects → Messages : deux soumissions du même événement, une
  seule remise SMTP reçue ; journal `sent`. Aucune modification Projects.
