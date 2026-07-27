# Drive Feature Roadmap

Derniere passe: 2026-07-25.

## Etat upstream La Suite Numerique

- Aucun depot public `suitenumerique/beepole` ou `beepole` clair n'a ete
  trouve; le candidat realiste semble etre `suitenumerique/people`.
- `suitenumerique/people` est le projet le plus proche du "repertoire": gestion
  des utilisateurs, contacts, equipes, roles, invitations et domaines mail.
- Son frontend `desk` est avance sur equipes/domaines mail, mais la doc indique
  encore qu'une UI d'organisation reste a creer.
- `suitenumerique/st-deploycenter` sert plutot aux operateurs: organisations,
  services, abonnements, entitlements et metriques.
- `suitenumerique/drive` a deja une brique metriques/entitlements vers
  Deploy Center, mais les tickets quota UI et file request sont encore ouverts.
- Conclusion: il existe un socle admin transverse, mais pas encore une console
  admin Drive complete et directement reutilisable.

## Mis De Cote

- Historique de versions: voir, restaurer, telecharger ou supprimer les
  anciennes versions d'un fichier. A garder dans la roadmap, mais pas a traiter
  maintenant: le versioning S3/SeaweedFS aide surtout les fichiers Drive
  standards et WOPI. Pour une compatibilite propre entre SeaweedFS, stockage
  local, NFS et futurs providers, il faudra une couche produit `FileVersion` en
  base et une capacite MountProvider dediee pour lister, lire et restaurer les
  versions quand le provider sait le faire.

## Priorite Haute

- Journal d'activite: afficher qui a cree, modifie, partage, telecharge,
  deplace ou supprime un element.
- Liens avances: expiration, mot de passe, desactivation du telechargement et
  revocation simple.
- Quotas visibles et appliques: afficher l'espace consomme et bloquer clairement
  les uploads quand la limite est atteinte.
- Demandes de fichiers: lien upload-only pour collecter des documents sans
  exposer le contenu du dossier.
- Restauration massive anti-ransomware: revenir a un etat anterieur apres
  suppression, corruption ou attaque.
- Console admin Drive: partir de `st-deploycenter` pour organisations,
  abonnements, quotas et roles; garder les actions fichier Drive dans Drive.

## Priorite Moyenne

- "Partage par moi": retrouver tous les fichiers et dossiers que l'utilisateur
  a partages.
- Inventaire des liens publics: lister, filtrer et couper les liens publics
  actifs.
- Transfert de propriete: changer le proprietaire d'un fichier, dossier ou
  espace de travail.
- Upload resumable/chunked: reprendre un upload interrompu, surtout pour les
  gros fichiers.
- Duplication de dossiers: copier un dossier complet avec son arborescence.
- Commentaires et mentions: discuter autour d'un fichier sans sortir du Drive.
- Notifications: prevenir sur invitations, commentaires, demandes d'acces,
  echecs d'upload ou changements importants.
- Recherche contenu/OCR: chercher dans les PDF, documents, images scannees et
  metadonnees.

## Bien A Avoir

- Tags, labels et classification: organiser les fichiers et preparer des regles
  de gouvernance.
- Workflow d'approbation: demander une validation avant diffusion ou verrouiller
  un document pendant revue.
- File requests avec deadline: ajouter une date limite et fermer automatiquement
  la collecte.
- Panneau activite dans le panneau droit: exposer l'historique directement dans
  les details d'un fichier.
- Miniatures plus completes: apercus rapides pour images, videos, PDF et
  documents bureautiques.
- Liens de transfert temporaires: liens limites dans le temps pour envois
  ponctuels.
- Watermark: marquer les apercus/exports de documents sensibles.
- Webhooks API: notifier des systemes externes lors des creations,
  modifications, suppressions ou partages.
- PWA/mobile: usage mobile plus propre, scan de documents et navigation adaptee.
- Chiffrement cote client: option avancee pour espaces tres sensibles.

## Choix Console Admin

- `st-deploycenter`: meilleur point de depart pour une console admin
  operateur/instance, surtout quotas, abonnements, services, entitlements et
  roles admin par organisation.
- `people`: a traiter comme brique annuaire/RBAC transverse de la suite:
  utilisateurs, organisations, contacts, equipes, invitations, domaines et
  groupes reutilisables par Drive, Doc et les futures apps collaboratives.
- Drive lui-meme: doit rester la source des fonctions produit specifiques:
  liens publics, fichiers, trash, logs d'activite, support, restaurations.
- Strategie conseillee: integrer et ameliorer `st-deploycenter` et `people`,
  contribuer upstream les briques generiques, et garder dans ton Drive fork les
  endpoints trop specifiques aux fichiers.

## Sources

- La Suite People: https://github.com/suitenumerique/people
- Modele People: https://github.com/suitenumerique/people/blob/main/docs/models.md
- Service providers People: https://github.com/suitenumerique/people/blob/main/docs/serviceProviders.md
- Interoperabilite People/Messagerie: https://github.com/suitenumerique/people/blob/main/docs/interoperability/dimail.md
- Organisation dans People: https://github.com/suitenumerique/people/blob/main/docs/organizations.md
- La Suite Deploy Center: https://github.com/suitenumerique/st-deploycenter
- Deploy Center account roles: https://github.com/suitenumerique/st-deploycenter/blob/main/docs/account_roles.md
- Deploy Center accounts: https://github.com/suitenumerique/st-deploycenter/blob/main/docs/accounts.md
- Deploy Center Drive handler: https://github.com/suitenumerique/st-deploycenter/blob/main/src/backend/core/services/drive_service_handler.py
- Deploy Center Drive storage: https://github.com/suitenumerique/st-deploycenter/blob/main/src/backend/core/entitlements/resolvers/drive_storage_entitlement_resolver.py
- Drive metriques/entitlements: https://github.com/suitenumerique/drive/pull/395
- Drive quota: https://github.com/suitenumerique/drive/issues/286
- Drive UI quota: https://github.com/suitenumerique/drive/issues/407
- Drive file request: https://github.com/suitenumerique/drive/issues/770
- People vue admins: https://github.com/suitenumerique/people/issues/885
- SeaweedFS: https://github.com/seaweedfs/seaweedfs
- SeaweedFS releases: https://github.com/seaweedfs/seaweedfs/releases
- AWS S3 versioning: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html
- Google Drive: https://workspace.google.com/products/drive/
- Google Drive activite et versions: https://support.google.com/drive/answer/2409045
- Google Drive labels: https://developers.google.com/workspace/drive/api/guides/about-labels
- Google Drive approvals: https://support.google.com/drive/answer/9387535
- OneDrive file requests: https://support.microsoft.com/en-us/onedrive/create-a-file-request
- OneDrive version history: https://support.microsoft.com/en-us/onedrive/restore-a-previous-version-of-a-file-stored-in-onedrive
- OneDrive restore: https://support.microsoft.com/en-us/onedrive/restore-your-onedrive
- OneDrive sharing permissions: https://support.microsoft.com/en-us/onedrive/sharepoint/manage-sharing-and-permissions-in-onedrive-and-sharepoint
- Dropbox file requests: https://help.dropbox.com/share/create-file-request
- Dropbox link permissions: https://help.dropbox.com/share/set-link-permissions
- Dropbox Rewind: https://help.dropbox.com/delete-restore/rewind
