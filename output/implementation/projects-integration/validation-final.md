# Projects — validation LAN du 10 septembre 2026

Périmètre : Projects natif, People/ST/OIDC, Drive/Docs, Messages et exploitation.
Guide : [suite-projects](../../../docs/operations/suite-projects.md).
La publication est suivie séparément dans [publication.md](publication.md).

| Référence | Résultat observé |
| --- | --- |
| R0 | Login Keycloak, demande/approbation People, refus puis attribution ST ; Projects visible dans le catalogue Drive |
| R1 | Checklist, échéance, minuterie, commentaire, affectation, duplication avec pièces et liens, export CSV ; modification visible dans le second navigateur ; lecteur refusé en écriture |
| R2 | Groupe + accès direct cumulés ; retrait du groupe conserve le direct ; UI d’attribution/retrait utilisée ; retrait ST coupe le socket inactif et refuse HTTP en **38,645 s** ; lecture privée refusée après retrait du grant |
| R3 | Upload privé, même ID au retry, SHA identique ; anonyme 401 ; EICAR 422 ; scanner indisponible 422 puis santé rétablie ; concurrence sous quota 200/413 ; quota projet 1 octet refuse le déplacement, rétablissement permet l’aller-retour ; S3/NAS/PDF et popup Messages réussis ; collision sans écrasement |
| R4 | Affectation native remise dans Messages ; panne ciblée, retry puis **un seul Message pour l’UUID** ; rejeu sans nouveau mail ; destinataire retiré avant reprise annulé ; credential machine invalide refusé |
| R5 | Projects redémarré seul ; sauvegarde DB/objets/images/config cohérente ; restauration interne avec sessions et mails historiques invalidés ; même fichier SHA et mêmes IDs relus ; un accès ST retiré après le backup reste refusé après relecture des autorités actuelles |
| R6 | Keycloak → Authentik → Keycloak dans une restauration isolée ; mêmes principal People, user natif, cartes et fichiers ; ancien JWT Authentik refusé ; aucun changement d’IdP du LAN |

Contrôles UI ciblés : carte et actions à 390 px sans débordement, groupes,
stockage/responsable, statut, récupération d’un projet orphelin et catalogue.
Brouillons de création **et modification** conservés après reconnexion ;
effacement après confirmation WebSocket. Déconnexion de suite puis
réauthentification OIDC fraîche et reconnexion réussies.

Contrôles de code : linters natifs ciblés Projects serveur/client, Drive et
Messages Python, ST Python/TypeScript ; typecheck ST, build Docker Projects,
checks Django Drive/Messages. **Deux tests Mocha** pour la frontière d’identité
et la pagination/purge S3 ; **un test ST** de budgets cumulés. Aucun full E2E,
aucune matrice de navigateurs et aucun test de présence de fragments de code.
Les anciennes assertions intégrales de `test_entitlements_messages.py` divergent
sur `storage_policy`, déjà présent avant ce chantier ; elles ne sont pas données
comme passantes. La copie Messages réelle a été rejouée après factorisation.

Nettoyage : projets et contenus de recette retirés, objets privés Projects
vides, zéro écriture/mail en attente, fichiers S3/NAS et document Docs purgés,
boîte et mails temporaires retirés, blobs correspondants collectés. Les isolats
Projects sont supprimés et le stack Authentik QA remis à l’arrêt ; clients,
consumer et compte Authentik de recette retirés. Quotas temporaires restaurés.
Les identités People existantes, le NAS et les autres applications sont conservés.

Configuration opérationnelle conservée : catalogue Projects ouvert au groupe
People **Membres de la suite**, budgets ST 20 Go organisation/utilisateur,
administrateur initial Projects associé au compte LAN `drive`. Création de
projets administrable depuis ses réglages. Cette autorité initiale est un
bootstrap opérationnel, pas un grant temporaire de recette.

Limites explicites : LAN ; fichiers de transfert de 1 octet à 25 MiB ; absence
de plafond ST/zéro signifie illimité, blocage de croissance distinct ; les
uploads d’avatars/fonds/imports désactivés dans la base ne sont pas activés.
Une copie de tableau entière attend son résultat avant relance ; l’admission
par fichier est journalisée. Une notification SMTP incertaine requiert une
vérification et une reprise explicite. La reconnexion des sockets lors d’une
modification des grants concerne l’instance LAN entière. Aucun droit retiré ne
rappelle un téléchargement terminé ou un mail déjà remis.
