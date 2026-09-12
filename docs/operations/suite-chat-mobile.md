# Apoze Chat mobile — builds et recette LAN

État du 12 septembre 2026 : Android compilé et installé sur l’émulateur,
connexion Keycloak/MAS et premier message chiffré validés ; intégrations en
cours. iOS : code préparé, aucun build exécuté sans macOS/Xcode.
Le suivi et les validations restant à faire sont dans le
[plan canonique](../plans/suite/transfers-element-chat-integration-plan.md).

## Périmètre

Element X reste le client Chat. Les actions Drive/Transfers, Meet, Calendars et
Projects ouvrent les écrans des applications dans le navigateur système ;
le partage est relu et confirmé dans le salon. Les droits de chaque application
restent indépendants. Aucun jeton Matrix n’est transmis au navigateur ou à une
autre application. Le chiffrement appartient au SDK natif.

## Réseau LAN

- Identité Matrix durable : `chat.zohenhl.ovh` ; HTTPS 443, MAS HTTPS 8955.
- Résoudre ce nom vers `192.168.10.123` dans le DNS LAN ou sur chaque appareil.
  La configuration actuelle couvre la VM et l’émulateur de recette seulement.
- Installer les CA publiques LAN du Chat, de Meet et de Transfers dans le
  magasin de confiance du système/navigateur ; ne jamais partager leurs clés.
  Fichiers publics locaux : `data/chat-local/tls/ca.crt`,
  `data/meet-local/tls/ca.crt`, `data/transfers-local/tls/ca.crt`.
- Aucun contournement de validation TLS. Le serveur Chat est privé ; WAN/VPN
  et certificats publics seront traités séparément.
- Keycloak existant authentifie toujours via les origines LAN actuelles.
  Le code des applications utilise OIDC/MAS et les identifiants durables People.

## Android

Fork : https://github.com/Apoze/element-x-android ; branche `codex/suite-chat`.
JDK 21, SDK Android dans `/opt/apoze-android-sdk`, versions du projet verrouillées.
Depuis le dépôt Android :

```sh
ANDROID_HOME=/opt/apoze-android-sdk ./gradlew --no-daemon --max-workers=2 \
  -Dorg.gradle.jvmargs='-Xmx4g -Dfile.encoding=UTF-8' :app:assembleFdroidDebug
```

APK émulateur : `app/build/outputs/apk/fdroid/debug/app-fdroid-x86_64-debug.apk`.
Identifiant debug : `ovh.zohenhl.chat.android.debug`. Ce build utilise une clé
locale de développement ; il ne constitue pas un APK signé pour distribution.
Aucune configuration Firebase Element ni clé de signature Element embarquée.
Sans paramètres Firebase Apoze, aucun fournisseur push n’est compilé.

Le retour `apozechat://return` remet la conversation au premier plan ; il ne
porte ni autorisation ni résultat. La sélection est relue au serveur sous la
session native avant son envoi chiffré.

## iOS

Fork : https://github.com/Apoze/element-x-ios ; branche `codex/suite-chat`.
Bundle `ovh.zohenhl.chat.ios`, groupe `group.ovh.zohenhl.chat.ios` ; signature
et équipe Apple propres au propriétaire. Aucun certificat ni compte tiers.
Sur Mac, suivre `docs/FORKING.md`, lancer `swift run tools setup-project`,
puis construire la cible ElementX pour un simulateur avec les versions Xcode
requises par la release. Le SDK Swift/Rust verrouillé reste la référence.
Les extensions de partage et de notifications utilisent le même groupe Apoze.

## Push

`docker/suite/prepare_chat_push.py` prépare le Sygnal officiel figé et les
credentials privés Apoze. La livraison APNs/FCM n’est pas validée tant que
les credentials de propriétaire et les moyens de réception ne sont pas fournis.
Un démarrage Sygnal ou une notification injectée ne prouve pas cette livraison.
Les push ne contiennent pas de texte privé : identifiants opaques seulement,
aperçu éventuellement déchiffré sur l’appareil selon les réglages natifs.

Installer les CA via les réglages natifs du système. Lors d'une préparation
manuelle d'un émulateur jetable, deux CA de même sujet doivent conserver des
suffixes distincts (`hash.0`, `hash.1`) ; ne jamais remplacer la première.
La recette a reproduit puis corrigé cette collision, sans réinitialiser la
session ni accepter un certificat non vérifié.

## Sélecteur Drive et partage système

Le menu mobile ouvre les parcours Drive/Transfers existants. Le navigateur
prépare la copie privée ou le lien, puis l'utilisateur choisit Apoze Chat et
la conversation dans le partage système. Le SDK natif chiffre le message.
La fermeture de cette feuille ne constitue pas une preuve d'envoi. Les copies
Drive restent plafonnées à 100 Mio (export PDF Docs : 25 Mio) ; les téléchargements
locaux et le presse-papiers sont des alternatives explicites si le partage
n'est pas disponible. Les liens Transfers sont des capacités de téléchargement.

Web Share exige une origine sûre. La façade locale du sélecteur Drive utilise
le certificat LAN Transfers déjà approuvé, sans modifier le script Drive :

```sh
python3 docker/suite/prepare_drive_tls.py --host 192.168.10.123 \
  --state data/drive-tls-local --tls data/transfers-local/tls
docker compose -f data/drive-tls-local/compose.json up -d
ENV_OVERRIDE=local docker compose up -d --no-build --no-deps \
  app-dev celery-dev celery-beat-dev frontend-dev
```

Ajouter dans le client OIDC **Drive existant** le callback
`https://192.168.10.123:8445/api/v1.0/callback/`, en conservant ses autres
callbacks. Cette configuration s'applique à l'IdP utilisé ; elle ne change pas
le modèle d'identité. Le Keycloak local a reçu ce callback lors de la recette.
Le générateur conserve les origines CSRF et les retours existants. Il active
explicitement `SECURE_PROXY_SSL_HEADER` dans le profil de développement ;
la façade écrase cet en-tête. L'API de développement reste limitée au LAN de
confiance, sans accès WAN. Le déploiement WAN utilisera le profil production.

Le sélecteur mobile rejoint `CHAT_PICKER_PUBLIC_URL`. Ses liens privés
conservent l'origine canonique `LOGIN_REDIRECT_URL` ; les anciens accès Drive
restent disponibles. Conserver `data/drive-tls-local` et les certificats avec
les paramètres d'exploitation locaux. Arrêt indépendant :
`docker compose -f data/drive-tls-local/compose.json stop`.

## Message vers Projects

Le menu contextuel d'un message texte permet de préparer une tâche Projects.
Le navigateur capture un brouillon privé borné avant la connexion, puis retire
le fragment de l'URL. L'utilisateur choisit tableau, liste et titre et confirme
la copie du texte dans Projects. Le retour au Chat permet de relire le lien et
de confirmer son envoi chiffré. Les pièces jointes ne sont pas copiées avec le
texte. Le brouillon est conservé dans la session du navigateur pendant le SSO
et supprimé après création. Vérifier le texte affiché avant de confirmer.
