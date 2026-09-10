---
status: accepted
---

# Séparer la référence commune et la localisation native

L'explorateur présente des ressources et des espaces, tandis que les éléments
Drive restent servis par Django Storage/S3 et les entrées montées par leur
Provider API. Une référence persistante suit une ressource lors d'un déplacement
confirmé, sans transporter des droits incompatibles avec la destination ; une
copie reçoit une nouvelle référence et une charge supplémentaire. Cette frontière
conserve les accès NAS directs et les contrats natifs S3 sans multiplier les
explorateurs ni convertir artificiellement le NAS en objets S3.

La bascule de localisation et l'attribution des quotas doivent être confirmées
ensemble après vérification de la publication. Le retrait de la source utilise
une identité native immuable ou une mise à l'écart contrôlée ; à défaut, la source
reste retenue et l'opération affiche un nettoyage en attente. Les chemins, les
identifiants de connexion et les versions d'édition ne remplacent pas la référence
logique ; les anciens liens restent soumis aux permissions actuelles.

Cette décision est celle du [plan accepté](../plans/storage/unified-storage-spaces-plan.md).
Son [état d'implémentation](../../output/implementation/unified-storage-spaces/current-status.md)
reste distinct : la bascule entre familles a été livrée et
[qualifiée sur le stack local](../../output/implementation/unified-storage-spaces/local-environment-validation.md).
Le périmètre du journal d'activité défini par [ADR 0001](0001-product-activity-journal-not-audit.md)
reste celui des éléments Drive ; la référence commune n'introduit pas un audit
immuable des stockages externes.

Lorsqu'un lien public a été créé sur un dossier S3 provisoire pendant un
transfert, une identité de lien conservée dans `StorageResource` redirige vers
l'Item définitif. Cette ligne est marquée absente de l'inventaire monté : elle
ne sert aucun octet S3 via MountProvider et ne crée aucune charge de stockage.
