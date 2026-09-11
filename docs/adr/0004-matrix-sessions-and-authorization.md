# ADR 0004 — Sessions Matrix et autorisation de la suite

Date : 11 septembre 2026. Statut : implémentation et recette en cours.
Complète ADR 0003 sans modifier les sessions Drive/Docs/People/ST.

## Décision

- MAS conserve OAuth/OIDC, PKCE, appareils et rotation des refresh tokens.
  Une session Matrix possède une borne absolue de 30 jours, contrôlée à partir
  de sa session navigateur MAS d'origine ; un refresh ne remet pas ce délai à zéro.
- Le premier login exige une authentification IdP récente (900 secondes), un
  ID token signé avec issuer/audience/nonce vérifiés et un UserInfo concordant.
  Ensuite l'âge du login interactif n'interrompt pas les sync mobiles toutes les
  quinze minutes. L'epoch People reste contrôlé et invalide une ancienne preuve.
- Le localpart Matrix vaut `p` suivi des 32 chiffres hexadécimaux de l'UUID
  People. Ni email ni nom ne rattache un compte. Les liens externes autorisés
  proviennent exclusivement de People, par consommateur `chat`.
- Une extension Python native de la fork Synapse lit les contrats HTTP People/ST.
  Elle ne charge pas Django. Snapshot paginé borné sur disque, révisions et
  epochs monotones, collisions d'identité refusées et checkpoint atomique SQLite.
  Le déploiement initial est un seul processus Synapse ; l'extension refuse le
  démarrage comme worker distribué. Les migrations du journal sont explicites.
- MAS appelle cette extension avant connexion/émission/refresh/introspection,
  avec une clé machine distincte et endpoint privé fixe. Les comptes sont créés
  et gérés via l'API Admin native MAS, sans écritures directes dans ses tables.
- Les autorisations positives expirent au plus à 90 secondes ; lecture
  People/ST toutes les 30 secondes. Une panne ne prolonge aucune permission.
  Introspection en cache au plus 30 secondes, sync bornée à 30 secondes et
  nouvelle vérification avant de retourner son résultat. Objectif de révocation
  de bout en bout : 120 secondes, à mesurer avec un token antérieur.
- Les accès natifs Matrix restent soumis au même contrôle que les clients Apoze.
  Les anciens downloads médias anonymes et la fédération sont fermés au proxy.
  Les endpoints Admin Synapse/MAS ne sont pas publiés. Les opérations suite
  exposées exigent un token natif et le groupe People `suite-administrators`. Les clés E2EE restent dans les SDK.
- Médias : stockage natif local dédié ; réservations atomiques avant écriture,
  budgets ST compte/organisation/instance et miniatures natives comptabilisées.
  Journal conservé jusqu'à purge confirmée ; reprise des écritures interrompues.
  Le tampon HTTP privé est plafonné à 384 Mio, réservé à l'instance, avec
  deux uploads simultanés. Aucune promesse de quota par salon
  sur des pièces jointes chiffrées dont le serveur ignore le contenu.

- Salons gérés : droits directs et groupes People réunis par UUID, rôle maximal
  effectif, projection par les handlers Matrix natifs et journal de provenance.
  L’accès est contrôlé aussi sur la visibilité des événements et les réponses
  sync ; le cache initial est segmenté par la révision des droits.
- Salon orphelin : conserver une autorité native techniquement nécessaire à la
  reprise, tout en lui refusant lecture et sync. La reprise explicite par un
  administrateur People invite/joint le nouveau responsable puis retire l’ancien.
  Aucune clé de chiffrement n’est récupérée par ce mécanisme.
- Le profil livre des salons v11, avec propriétaire transférable. Création,
  événements de création et capacités clients refusent une migration implicite
  vers les créateurs indélogeables v12, dont la gouvernance n’est pas qualifiée.
- Réattribution des médias : l’attribution du quota et du droit de purge peut
  être transférée avec aperçu et revalidation transactionnelle. L’auteur Matrix
  d’origine, les clés et les droits de salon restent inchangés. Réservations
  actives exclues ; plafond du destinataire contrôlé sans déplacer les octets.

## Limites de validation

Le serveur `chat-qa.invalid` est jetable. Aucun compte de production ne doit y
être créé. Le nom contrôlé par le propriétaire reste attendu. Les migrations
IdP Keycloak → Authentik et récupération native de l'historique chiffré ont
été vérifiés avec le même compte Matrix. Retrait ST mesuré à 22,6 secondes,
sessions MAS réellement terminées. Projection des groupes, révocation de salon
et reprise administrative vérifiées. Administration Web en recette ;
intégrations de la suite encore en cours. Pas de Mac, téléphone ou SDK mobile disponible identifié ; les
recettes dépendantes suivent le report explicitement autorisé dans le plan.

## Sources de référence

- [MAS SSO](https://element-hq.github.io/matrix-authentication-service/setup/sso.html)
- [API Admin MAS](https://element-hq.github.io/matrix-authentication-service/topics/admin-api.html)
- Forks locales : Synapse v1.160.0 ; MAS v1.24.0. La matrice des points de
  contrôle et les preuves réelles sont suivies dans le plan et son journal.
