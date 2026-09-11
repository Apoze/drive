# Transfers et Chat — état courant

Mise à jour : 11 septembre 2026. **Chantier en cours, non livré dans son ensemble.**

## Lot actif et prochaine action

TC6 : Drive/Docs, catalogue et Chat ↔ Transfers qualifiés dans le navigateur.
Le lot Chat ↔ Transfers est publié et vérifié. TC7 Meet serveur/Synapse
et Element sont publiés ; le suivi et les générateurs Drive sont publiés.
Calendars : création, édition, annulation, refus et carte chiffrée qualifiés.
Projects : création native et partage chiffré qualifiés ; bot à faire. Aucun code mobile livré.
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
- Image Web TC7 déployée, adaptation compacte incluse :
  `090c465fa1d8e66270e0f33feb2dd308fefabc4791e7b89afa5302c802439bb2`.
- Les incidents mémoire sont consignés dans I52/I72/I75. Configuration
  actuelle qualifiée par compilation complète : worker BuildKit `apoze-suite`
  2,5 Gio/deux CPU/sans swap, tas Node 1024 Mio, préflight 3 Gio disponibles.
  Les navigateurs de recette sont fermés avant compilation. Le worker est
  arrêté après le build ; aucun service métier arrêté pour libérer sa mémoire.
- Les limites sont persistées dans le nœud Buildx et vérifiées sur le vrai
  conteneur. Dernière compilation réussie, sans nouvel OOM global.

## Données de recette à conserver puis nettoyer

- Les fichiers médias des derniers tests UI/quota/purge sont supprimés.
  Passerelle `apoze.qa`, pusher synthétique et rôle administrateur temporaire
  `chat-admin-ui-grant.json` retirés ; grant ST initial restauré.
- Les deux personnes de recette, leur groupe People avec le second membre (état initial vide), les salons
  `TC encrypted qualification` et `TC managed UI`, associations IdP et les
  fixtures Transfers/Drive/Docs antérieures restent nécessaires aux lots suivants.
- État privé de suivi : `tmp/transfers-chat-qa/`, jamais à publier. Les identifiants
  des fixtures et restaurations sont documentés dans le journal d’exécution.
  Ne pas supprimer l’espace NAS préexistant ni les données métier.

## Travail restant

- Compléter TC1/TC5 : voies encore non qualifiées ; la panne d’autorité réelle
  a fermé l’accès à 80 secondes, puis la restauration a réadmis la même session ;
  terminer la preuve et configuration du transport push avec la passerelle.
- TC6 : terminer la revue ciblée des fonctions natives conservées.
- TC7 : bot E2EE et notifications choisies ; Meet/Calendars/Projects qualifiés.
- TC8/TC9 : code/configuration Element X Android/iOS ; tests appareils reportés
  selon l’autorisation explicite, mais pas le travail de code.
- TC10 : Sygnal, credentials et liens mobiles ; distinguer code prêt et vraie
  remise APNs/FCM, qui ne peut pas être prétendue sans ces moyens.
- TC11/TC12 : sauvegarde/restauration isolée, guides complets, contrôle de la pile,
  nettoyage final et publication de tous les lots sur les seuls forks Apoze.

## Point de reprise immédiat

Les images Web et Transfers de la recette Chat ↔ Transfers sont déployées.
Le sélecteur à 520 px tient dans la fenêtre ; le transfert natif d’un message
conserve son aperçu et sa fermeture clavier. L’annulation depuis Transfers
ferme le sélecteur Chat sans fermer le formulaire. TC7 : invitation chiffrée et appel à deux comptes qualifiés. Retrait ST à
27,2 s, retrait du groupe à 11,9 s ; responsable maintenu. Salle de recette
fermée, droits ST restaurés. Groupe avec le second membre pour Calendars. Serveurs publiés, en-tête Element qualifié à 520 px et publié ; générateurs Drive publiés.
Calendars et invitations Messages : recette réussie ; Projects qualifié ; prochain lot bot E2EE.
Aucun client arrêté artificiellement, aucune panne injectée ni mode hors ligne
actif. Les fixtures restent pour les lots suivants, nettoyage final TC12.
