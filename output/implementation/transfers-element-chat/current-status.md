# Transfers et Chat — état courant

Mise à jour : 11 septembre 2026. **Chantier en cours, non livré dans son ensemble.**

## Lot actif et prochaine action

TC6 : échanges Drive/Docs, retour des pièces jointes et reprise après coupure
réseau qualifiés. Catalogue serveur ST qualifié ; dernier menu Web à construire
et contrôler, puis publication. Aucun code mobile livré.
Ne pas annoncer TC0–TC12 terminés.

## Réalisé et qualifié

- Transfers TC3/TC4 : identité People/ST, quotas, AV et modes standard/confidentiel,
  notifications Messages, fichiers S3/NAS, exports Docs et retour Drive privé.
  Copie réelle 20 Gio avec empreinte, reprise après perte du worker, quota et
  purge. Jalon publié sur les forks Apoze ; voir [publication.md](publication.md).
- Synapse/MAS : deux logins natifs, sujets OIDC vérifiés et approuvés dans People,
  MXID durable `p<UUID>`, refus ST, sync bornée et médias privés comptabilisés.
- Passage Keycloak → Authentik : même compte Matrix, même salon et récupération
  native des clés/historique chiffré. Aucune correspondance par email.
- Groupes et droits directs : projection native, provenance, rôles, protection
  du dernier responsable, reprise administrative d’orphelin et audit.
  Retrait final : lecture/événement et classic/sliding sync refusés ou filtrés.
- Administration Element : activation de groupes depuis le salon ; paramètres
  du compte pour usage, médias, aperçu, réattribution et suppression ; recherche
  administrative des salons. Parcours réels et capture desktop/520 px vérifiés.
- Panne de purge réelle : dossier miniature rendu temporairement non supprimable,
  refus 503, réservation conservée, permissions restaurées puis purge confirmée.
- Pushers : refus des destinations arbitraires/payload complet, inscription native,
  révocation ST et retrait natif du pusher mesuré à 11,1 s. APNs/FCM non testés.
- TypeScript complet, lints ciblés, image communautaire complète depuis le fork.
  SDK verrouillé corrigé pour son export cryptographique typé `unknown`.

## État d’exploitation

- La pile métier existante est démarrée. Drive/Keycloak/NAS n’ont pas été
  remplacés par une stack de démonstration. Grist reste en pause.
- Chat est **jetable** : `chat-qa.invalid`, état `data/chat-qa`, HTTPS 8954/8955.
  Le nom durable contrôlé par le propriétaire reste attendu ; ne pas inventer
  un domaine ni migrer des comptes réels sur cette identité de recette.
- Dernière image Web déployée (recette TC6 en cours) :
  `75edd1dabef58674abf7cd89d54c69ee4a9fed663b10dc9da1b70866d2ef3bd1`.
- Deux OOM du builder par défaut ont fermé Chrome de recette. Correction I52 :
  worker BuildKit `apoze-suite` limité à 3 Gio/2 CPU, minification un seul worker,
  préflight 3,5 Gio disponibles. Deux constructions complètes bornées ont réussi
  sans nouvel OOM après limitation des workers de minification.
- Transfers, Chat et Authentik QA restaurés et sains après la compilation.
  Le builder borné est arrêté ; navigateur `chatak` utilisé pour la recette TC6.

## Données de recette à conserver puis nettoyer

- Les fichiers médias des derniers tests UI/quota/purge sont supprimés.
  Passerelle `apoze.qa`, pusher synthétique et rôle administrateur temporaire
  `chat-admin-ui-grant.json` retirés ; grant ST initial restauré.
- Les deux personnes de recette, leur groupe People vide, les salons
  `TC encrypted qualification` et `TC managed UI`, associations IdP et les
  fixtures Transfers/Drive/Docs antérieures restent nécessaires aux lots suivants.
- État privé de suivi : `tmp/transfers-chat-qa/`, jamais à publier. Les identifiants
  des fixtures et restaurations sont documentés dans le journal d’exécution.
  Ne pas supprimer l’espace NAS préexistant ni les données métier.

## Travail restant

- Compléter TC1/TC5 : panne d’autorité réelle et voies encore non qualifiées ;
  terminer la preuve et configuration du transport push avec la passerelle.
- TC6/TC7 : catalogue/retour suite, Drive/Docs/Transfers dans le compositeur,
  retour des pièces jointes, Meet/Calendars/Projects, bot E2EE choisi.
- TC8/TC9 : code/configuration Element X Android/iOS ; tests appareils reportés
  selon l’autorisation explicite, mais pas le travail de code.
- TC10 : Sygnal, credentials et liens mobiles ; distinguer code prêt et vraie
  remise APNs/FCM, qui ne peut pas être prétendue sans ces moyens.
- TC11/TC12 : sauvegarde/restauration isolée, guides complets, contrôle de la pile,
  nettoyage final et publication de tous les lots sur les seuls forks Apoze.

## Point de reprise immédiat

Image des échanges Drive qualifiée ; menu catalogue ajouté ensuite, TypeScript
réussi, construction et vérification visuelle restantes. Le build précédent
a utilisé `tmp/transfers-chat-qa/build_chat_with_restore.py`.
Ce wrapper restaure en `finally` Transfers (API/worker/beat), Chat (Synapse/MAS)
et Authentik QA (serveur/worker), puis arrête le builder. Vérifier leur état réel
avant les prochaines recettes. Docs frontend est revenu HTTP 200 après redémarrage.
Les nouveaux médias et le retour Drive 32 Mio restent à nettoyer ; journal et
`chat-drive-roundtrip.json` donnent leurs identifiants sans clés.
