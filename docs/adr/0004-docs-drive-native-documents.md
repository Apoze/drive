# ADR 0004 — Documents Docs natifs dans Drive

Date : 8 septembre 2026. Implémentée et activée le 9 septembre 2026.

## Autorités et identifiants

Drive porte un `Item` de type `docs`, son arbre, ses droits et son état de
corbeille. `DocsBinding` associe cet Item à l'UUID du document Docs ; la
liaison réciproque est `DriveDocument`. Ces identités ne changent pas lors
d'un déplacement, renommage ou changement d'IdP. Une liaison purgée reste
un témoin de suppression : une ancienne requête ne peut pas la recréer.

Docs conserve son contenu Yjs, ses médias et ses versions dans son stockage
privé. L'Item documentaire n'a ni clé S3, ni fichier physique, ni état
d'upload. L'ancrage monté désigne un `StorageResource` dossier stable et son
espace ; les sous-documents héritent de l'ancrage de la racine documentaire.
Un export produit un fichier distinct dans un espace Drive autorisé.

Le rôle `commenter` existe dans les accès et invitations documentaires.
Les fichiers ordinaires conservent les rôles qu'ils supportaient déjà.
L'autorisation effective reste bornée par les droits de l'espace.

## Échanges et reprise

Les appels privés réutilisent le transport HTTP borné du paquet d'identité,
sans redirection, avec quatre secrets : lecture et mutation dans chaque
direction. L'acteur est un principal People, une organisation et la preuve
de sa session vérifiée ; jamais une adresse email ou un subject arbitraire.
Une clé de lecture ne permet aucune mutation. Les messages sont limités à
1 Mio et les contrôles groupés à 100 identifiants par appel.

La création emploie une clé d'idempotence et l'empreinte des paramètres.
Les opérations de métadonnées portent une révision croissante. La liaison
Drive conserve révision désirée/appliquée, état et prochaine reprise ; les
appels réseau ont lieu hors des transactions SQL. Les opérations de contenu
réutilisent les réservations et journaux de publication des quotas existants.
Un délai dépassé ne prouve ni un échec d'écriture ni une purge distante.

L'existence de la liaison sélectionne l'autorité Drive côté Docs. Une panne
ou la désactivation du raccordement ne réactive pas les anciennes ACL Docs.
La coédition réutilise son contrôle périodique existant ; une ancienne
décision ne devient pas un droit permanent.

La lecture privée `notification-recipients` est réservée au worker Docs muni
de la clé de lecture. Elle n'imite aucune session humaine, ne modifie aucun
droit et retourne au plus 100 responsables actuels après contrôle People et
placement. Les coordonnées ne sont jamais renvoyées par l'API publique Docs.
L'acceptation d'une demande exige, elle, la preuve réelle du responsable et
écrit une commande idempotente dans Drive.

## Activation

Les migrations sont additives. Le raccordement est activé sur le LAN.
Le suivi de livraison est exclusivement dans le
[plan du chantier](../plans/suite/docs-drive-native-documents-integration-plan.md).
Cet ADR ne constitue pas une preuve de livraison des opérations décrites.

L’adresse vérifiée portée par la preuve de connexion sert uniquement à
reconnaître le destinataire d’une invitation explicite. Elle ne rapproche
jamais les comptes et ne dépend pas d’une connexion préalable à Drive.
