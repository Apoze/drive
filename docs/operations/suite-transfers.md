# Transfers — exploitation LAN

État : parcours Transfers qualifiés le 11 septembre 2026 ; chantier Chat en
cours. Références : [plan](../plans/suite/transfers-element-chat-integration-plan.md)
et [preuves](../../output/implementation/transfers-element-chat/validation-final.md).

## Démarrage et mise à jour

Depuis `Apoze/drive`, avec les services communs et ST déjà démarrés :

```sh
python3 docker/suite/provision_transfers_local.py --register-current-keycloak
python3 docker/suite/prepare_transfers.py
docker compose -f data/transfers-local/compose.json build transfers frontend
docker compose -f data/transfers-local/compose.json up -d
```

Le premier argument adapte uniquement l'inscription du client à l'IdP local
actuel. L'application utilise OIDC et les associations People ; un autre IdP
se configure avec les mêmes redirections et associations explicites. Ne pas
remplacer l'issuer d'un état existant sans procédure de migration des identités.
Le script de démarrage Drive est conservé ; ces services se gèrent séparément.

Interface : `https://192.168.10.123:8950`. Stockage signé : port 8952.
Importer **uniquement** `data/transfers-local/tls/ca.crt` dans les magasins de
confiance des appareils LAN. Ne jamais diffuser `ca.key` ou `server.key`, ni
neutraliser les vérifications TLS. La CA n'est pas montée dans le proxy.
La préparation conserve les secrets existants ; récupérer une génération TLS
incomplète avant de la relancer. Prévoir le renouvellement avant expiration.

Dans ST, autoriser Transfers pour les utilisateurs/groupes voulus et rendre
sa fiche visible après qualification. Les inscriptions neuves restent fermées.
Les quotas utilisateur/organisation se règlent dans l'administration native ST.
20 Go décimaux par défaut ; `0` signifie sans limite à ce niveau, jamais une
capacité physique infinie. Les octets chiffrés, brouillons et purges en attente
comptent dans les réservations. Le plafond par fichier clair est 20 Gio : son
admission exige aussi la place pour l'enveloppe chiffrée.

Le compte d'administration technique Transfers se délègue explicitement :

```sh
docker compose -f data/transfers-local/compose.json exec transfers   python manage.py suite_admin UUID_PEOPLE
```

Ajouter `--revoke` pour retirer ce rôle. L'interface native `/admin/` emploie le
SSO de la suite ; les actions de gouvernance demandent un aperçu confirmé.
Ne pas utiliser un compte local ou une mutation brute des modèles pour contourner
People/ST.

## Garanties et limites visibles

- Standard : clé reçue par Transfers, analyse antivirus avant publication.
  Le scanner partagé accepte 60 Mio. L'exemption ST des fichiers plus grands
  est désactivée par défaut ; une infection ou erreur n'est jamais exemptée.
- Confidentiel : clé conservée dans le navigateur et fragment du lien. Aucun
  scan serveur promis ; les mails ne contiennent pas cette clé.
- Source Drive/NAS privée, export Docs PDF explicite plafonné à 25 Mio. Une
  copie reçue a ses propres droits et ne suit pas les révocations de la source.
- Retour Drive : blocs de 25 Mio, journal et quotas natifs, nom sans écrasement.
  Spool privé `data/transfer-intakes`, monté dans Drive app et worker, UID 1000,
  mode 0700 ; fichiers 0600, suppression après publication ou abandon.
  Budget spool 100 Gio, réserve disque libre 5 Gio, abandon inactif après 1 h.
  Ne jamais effacer le spool d'un job actif. Pendant la confirmation finale de
  publication, une annulation peut être refusée : consulter le résultat.
- L'accès unique est réclamé par POST ; ouvrir un aperçu GET ne le consomme pas.
  Le navigateur gagnant peut reprendre le téléchargement jusqu'à l'expiration
  de sa session. Une copie déjà téléchargée ne peut pas être rappelée.
- Reconnexion : conserver l'onglet Transfers pour garder la clé/le brouillon en
  mémoire. Une fermeture de cet onglet n'est pas une sauvegarde des clés.

## Supervision et reprise

```sh
docker compose -f data/transfers-local/compose.json ps
```

Vérifier API, frontend, worker et beat. Les synchronisations People/ST et quotas
s'exécutent périodiquement ; une autorisation trop ancienne ferme les accès.
Ne pas allonger la fraîcheur pour masquer un ordonnanceur arrêté. Les journaux
restent privés : ils peuvent inclure des références techniques sensibles.
La purge conserve les objets/réservations incertains jusqu'à la reprise S3.
L'administration expose la reprise de nettoyage ; ne pas libérer un quota à la
main avant d'avoir confirmé la suppression effective. Les imports interrompus
reprennent les parties déjà confirmées dans le journal.

## Sauvegarde et restauration

Sauvegarder ensemble, en stockage protégé : base PostgreSQL `transfers`, bucket
privé `transfers` du S3 partagé, état `data/transfers-local`, configuration des
clients IdP et associations People/ST. Les identités et droits restent dans les
bases People/ST : leurs sauvegardes doivent être cohérentes avec ce point.
Pour des copies retour actives, sauvegarder également la base Drive et son
spool cohérent. Ne pas copier à chaud des fichiers PostgreSQL comme un dump.

Pour un point cohérent, suspendre les nouvelles écritures Transfers, attendre
les opérations actives puis arrêter ses API/worker/beat ; conserver les services
communs. Utiliser `pg_dump` et l'outil S3 de sauvegarde déjà administré, vérifier
les codes retour, puis redémarrer Transfers. Ne jamais employer `down -v`.

Restaurer d'abord dans un environnement isolé, avec SMTP désactivé et sans
accès en écriture aux autorités/stockages vivants. Restaurer base, bucket et
secrets du même point ; lancer migrations et réconciliation sur cette copie.
Vérifier un téléchargement/digest, une expiration et une reprise de purge avant
toute bascule. **La recette de restauration de ce nouveau service reste à
exécuter dans TC11 ; elle n'est pas déclarée réussie par ce document.**
