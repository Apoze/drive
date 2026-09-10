# Exploiter Visio dans la suite Apoze

Le [guide canonique Apoze/meet](https://github.com/Apoze/meet/blob/main/docs/apoze/meet-core-operations.md)
regroupe démarrage, arrêt, sauvegarde, restauration, diagnostic, changements
IdP et retour arrière. Le [plan exécuté](../plans/suite/meet-visio-core-integration-plan.md)
conserve le périmètre et les critères.

Depuis `/root/Apoze/meet` :

```sh
python3 docker/suite/manage.py status --state /root/Apoze/drive/data/meet-local
python3 docker/suite/manage.py backup --state /root/Apoze/drive/data/meet-local
```

`start`, `stop`, `update` et `restore --backup <dossier>` ciblent uniquement
Meet. Sauvegarder avant mise à jour/restauration. La restauration remplace la
base Meet et invalide sessions/admissions ; elle ne restaure pas les anciennes
autorisations de transport à partir du cache.

ST gère l'accès à Visio et sa vignette ; People gère identités/groupes/bindings ;
Meet gère les salles, rôles, admission et fermeture. Le paramètre invités est
dans `/admin/`, via le compte local de récupération `recovery@meet.local`.
Son secret reste dans `data/meet-local/keys/recovery_password` ; aucune copie
publique. Ce compte n'a pas de droit implicite sur les appels.

Les dossiers de recette Authentik/Meet isolés ont été retirés après validation.
Grist reste en pause et ne doit pas être repris sans demande explicite.
