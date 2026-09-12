# Transfers et Chat — état courant

12 septembre 2026 : **périmètre LAN livré**. Serveur/Web fonctionnels, code des
deux clients mobiles livré ; Android qualifié sur émulateur. Compilation iOS,
signature/distribution, téléphones et remise APNs/FCM différés explicitement.

## Livré

- Transfers : SSO People/ST, quotas, modes standard/confidentiel, antivirus,
  invitations Messages, cycle expiration/one-shot/purge et copies S3/NAS/Docs.
- Chat : domaine durable `chat.zohenhl.ovh`, Synapse/MAS/Element Web, identité
  indépendante de l'IdP, groupes/rôles, révocation, quotas et chiffrement natif.
- Intégrations Drive/Transfers, Meet, Calendars et Projects ; bot Projects E2EE
  activé explicitement, sans second moteur d'appel ni fonctions expérimentales.
- Element X Android/iOS : actions contextuelles, partage système, message vers
  Projects et pièces jointes vers Drive/Transfers. Android 32 Mio réel dans les
  deux sens ; source iOS relue, compilation non exécutée faute de Mac/Xcode.
- Exploitation : commandes séparées, sauvegardes/restaurations isolées réelles,
  revalidation des autorités et invalidation des anciennes sessions/autorisations.
- Données/droits de recette nettoyés, profil Chat jetable et restaurations retirés ;
  pile métier, NAS et Keycloak conservés. Fiches Chat/Transfers visibles dans ST.
- Tous les changements de ce chantier publiés sur les forks Apoze correspondants ;
  aucune PR, fusion ou écriture upstream. État et révisions : [publication.md](publication.md).

## Accès et limites

Chat : `https://chat.zohenhl.ovh`, MAS port 8955 ; Transfers :
`https://192.168.10.123:8950`. Drive conserve ses accès LAN et dispose du
sélecteur HTTPS 8445. Sur un nouvel appareil, configurer DNS LAN et confiance
aux CA publiques selon le [guide mobile](../../../docs/operations/suite-chat-mobile.md).

Les pièces jointes Chat sont limitées à 100 Mio avant chargement SDK ; envoi
par blocs de 25 Mio, application maintenue ouverte. Les gros transferts 20 Gio
ont leur parcours Transfers distinct, réellement qualifié. Pas de WAN, invités,
fédération, enregistrement/transcription ou reprise de Grist par ce chantier.

## Prochaine action

Aucune implémentation obligatoire identifiée restante pour ce périmètre.
Reprendre seulement la [checklist mobile §14](../../../docs/plans/suite/transfers-element-chat-integration-plan.md#14-recette-mobile-différée--à-reprendre-ultérieurement)
lorsque le propriétaire fournira les moyens correspondants et demandera cette
recette. Ne pas qualifier un test iOS, physique ou APNs/FCM non exécuté.

[Validation finale](validation-final.md) · [Journal historique](execution-journal.md)
· [Plan](../../../docs/plans/suite/transfers-element-chat-integration-plan.md)
· [Roadmap](../../../docs/plans/suite/roadmap.md).

Les références privées de l'ancien point de reprise et du journal sont
historiques : leurs fichiers de session/recette ont été nettoyés. Seules les
archives opérationnelles privées restent conservées selon leur rétention.
