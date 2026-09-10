# La Suite numérique — inventaire complet et intégration homelab

État des lieux du **6 septembre 2026**. Périmètre : organisation publique
`suitenumerique`, produits externes officiellement référencés et travaux
d’interconnexion utiles à `Apoze/drive`. **Recherche et proposition uniquement.**

## 1. Résultat et point de départ

La plupart des briques existent. En revanche, une installation de tous les
conteneurs ne suffit pas à produire une suite cohérente : identité, groupes,
droits, quotas, classement des documents natifs et transferts entre applications
demandent encore des raccordements. Plusieurs de ces raccordements font déjà
l’objet de prototypes officiels non fusionnés.

| Besoin | Cible recommandée | Décision |
| --- | --- | --- |
| Fichiers et bureautique Office | Apoze Drive, S3/NAS, Collabora/ONLYOFFICE | Conserver l’existant ; connecter les autres applications aux espaces autorisés. |
| Notes, wiki, documents collaboratifs | Docs | Intégrer ; distinguer document vivant et export bureautique. |
| Tableaux de données, formulaires, automatisations | Grist | Intégrer ; complément des classeurs Office. |
| Visio | Meet | Intégrer ; enregistrement et transcription en modules séparés. |
| Courriel | Messages, ou DIMAIL pour le groupware traditionnel | Choisir le stockage faisant autorité ; examiner le pont IMAP proposé pour Messages avant de décider de maintenir deux piles. |
| Agenda | Calendars, ou celui d’Open-Xchange si DIMAIL retenu | Un agenda faisant autorité ; clients CalDAV à qualifier. |
| Tâches et Kanban | Projects | Intégrer pour ce besoin ; ancien Planka inutile en parallèle. |
| Chat | Écosystème Tchap/Matrix | Pilote avec clients maintenus ; Hub reste expérimental. |
| Envoi temporaire | Transfers | Pilote après adaptation des accès Drive ; France Transfert est une alternative. |
| Assistant et transcription | Conversations, Dictaphone, pipeline Meet | Modules utiles, à dimensionner selon les modèles et le matériel. |
| Administration et identité | ST + Keycloak + People | Rôles complémentaires ; pas de remplacement de Keycloak par ST. |
| Navigation et recherche | Gaufre/catalogue ST + Find | Réutiliser les composants existants ; les permissions doivent rester vérifiées par les services. |
| Tableau blanc, portail riche, Calc | Prototypes ou besoins déjà partiellement couverts | Développement facultatif, après les applications et leurs liaisons. |

Des recherches antérieures ont bien été retrouvées, mais elles sont partielles :

- [Roadmap Drive et administration](../../docs/drive-feature-roadmap.md).
- [Recherche ST et homelab du 4 septembre](2026-09-04-st-deploycenter-homelab-plan.md).
- [Validation précédente de l’environnement local](../implementation/unified-storage-spaces/local-environment-validation.md).

Le dernier rapport local décrit Drive, ses espaces S3/NAS, son Keycloak,
ST et les éditeurs Office qualifiés ensemble. Il ne valide pas les applications
supplémentaires proposées ici. Drive et ST utilisent actuellement des realms
distincts : leur présence ne constitue pas encore un SSO commun à toute la suite.
Le script de démarrage Drive reste séparé de celui de ST, conformément au choix
du propriétaire du homelab.

## 2. Méthode, couverture et preuves

- **49 dépôts publics**, collectés par pagination API : **30 + 19 + 0** ;
  rapprochement avec le compteur de l’organisation et les identifiants uniques.
- **49 arborescences récursives**, **20 969 entrées**, aucune réponse tronquée.
  Les fichiers imbriqués servent à repérer services, SDK, applications mobiles,
  charts, exemples, documentation et propositions. Aucun sous-module Git trouvé.
- Lecture des présentations et sources structurantes : déploiement, dépendances,
  protocoles, intégrations, avertissements de maturité ; lecture ciblée du code
  lorsqu’il contredit ou précise une présentation.
- Catalogue paginé des **1 119 issues ouvertes et 438 PR ouvertes**. Analyse des
  sujets utiles au périmètre, puis des descriptions et changements pertinents ;
  il ne s’agit pas d’une revue de chacun des tickets.
- **6 tableaux publics**, **1 315 éléments**, dont **21 brouillons** : les idées
  sans issue ont donc aussi été recherchées. Les tableaux fermés sont conservés
  comme historique, pas interprétés comme une feuille de route actuelle.
- **55 dossiers de soumission Hack Days 2025**, tous classés en annexe.
- Suivi des liens produits externes vers Grist, Tchap, France Transfert et DIMAIL,
  ainsi que des dépendances et branches particulières nécessaires à l’analyse.

L’exhaustivité porte sur **les dépôts publics de l’organisation et leurs
arborescences aux commits indiqués**, pas sur chaque ligne de code, toutes les
branches historiques, les dépôts privés ou une vérification opérationnelle de
tous les logiciels. Les dépôts externes ont reçu une inspection ciblée ; la
pagination de grandes arborescences DIMAIL a rencontré une limitation GitLab
HTTP 429, sans empêcher la lecture des présentations des composants principaux.
Les liens vers des démonstrateurs tiers ne constituent pas une exploration
récursive de toutes leurs dépendances ni un engagement de maintenance officiel.

Les qualificatifs de maturité ci-dessous sont une **analyse de cet inventaire**.
Une release ou une image Docker ne vaut pas qualification pour ton serveur.
`pushed_at`, parfois modifié par un robot sur une branche, n’est pas utilisé
comme preuve de progrès fonctionnel sur la branche principale.

Preuves durables : [inventaire CSV](lasuite-inventory-2026-09-06/repositories.csv)
et [manifeste des sources et commits](lasuite-inventory-2026-09-06/sources.json).
Le manifeste conserve aussi les titres/états des travaux sélectionnés et les
brouillons des tableaux ; les données publiques brutes de collecte restent dans
`tmp/lasuite-research-2026-09-06/`, hors documentation canonique.

## 3. Les 49 dépôts officiels

Chaque nom mène à la présentation figée au commit inspecté, ou à l’arborescence
lorsqu’il n’existe pas de README racine. Les versions sont celles du composant
nommé : une release de bibliothèque dans un monorepo n’est pas une release de
l’application complète.


### Applications

| Dépôt | Fonction | Maturité observée | Choix pour le homelab |
| --- | --- | --- | --- |
| [drive](https://github.com/suitenumerique/drive/blob/fbb76dc3fa1895a9e6ddcb647d2d6075bf0ae35a/README.md) | Fichiers, partage, bureautique via éditeurs externes | Produit publié ; v0.21.1 | Conserver Apoze/drive : espaces S3/NAS et quotas déjà qualifiés localement. Adapter les intégrations au modèle Ressource. |
| [docs](https://github.com/suitenumerique/docs/blob/3c1275c88da39abb71e045c7deaba3844ca9ac49/README.md) | Notes, wiki, documents structurés, coédition ; serveur Y séparé | Produit publié ; v5.6.1 | Intégrer. PostgreSQL, Redis, S3, workers et collaboration ; qualifier le Compose expérimental et les exports. |
| [meet](https://github.com/suitenumerique/meet/blob/adc74f846c11537798a50455ea33e98cf1517b02/README.md) | Visio sur LiveKit ; SDK, enregistrement et summary dans le même dépôt | Produit publié ; v1.30.0 | Intégrer. Configurer réseau WebRTC/TURN ; enregistrement, transcription et téléphonie en options distinctes. |
| [projects](https://github.com/suitenumerique/projects/blob/091591943c6dbd7ddb37951b2187d7485a0d4df5/README.md) | Projets, tableaux Kanban, tâches, pièces jointes ; Node/React | Produit publié ; v1.2.0 | Intégrer si gestion de projets souhaitée. OIDC, PostgreSQL, S3 possible ; liaison des pièces jointes Drive encore à développer. |
| [messages](https://github.com/suitenumerique/messages/blob/8e8d9e126172421fc55e7306be79a581c0b6721c/README.md) | Boîtes mail personnelles/partagées ; SMTP, web et mobile | Produit jeune ; application v0.9.0 | Intégrer pour le mail collaboratif web. PostgreSQL, Redis, stockage, MTA/filtrage ; pas de serveur IMAP/POP3, ni de serveur JMAP complet livré. |
| [calendars](https://github.com/suitenumerique/calendars/blob/9bb5200e2a6c9fd5a99a8f7e502eff8fb1cc416f/README.md) | Agendas, invitations, ressources ; Django et SabreDAV | Première version v0.1.0 | Intégrer après pilote. CalDAV et raccordement Messages existent ; corriger les défauts bloquants et qualifier clients, récurrences et droits. |
| [transfers](https://github.com/suitenumerique/transfers/blob/1d3c1eda9d2402fe6961cf0d7f0cbf8d10a50c9a/README.md) | Envois temporaires, expiration, multipart, modes chiffrés ; Django/React/S3 | Code actif ; aucune release GitHub publiée | Intégrer après correction du sélecteur Drive et qualification des modes de confidentialité. Ne pas doubler France Transfert sans besoin distinct. |
| [dictaphone](https://github.com/suitenumerique/dictaphone/blob/dea3b3f6aeefab5a643f1bbdee257f1bfbdedc9a/README.md) | Assistant Transcripts : enregistrements, transcription, web et mobile | Produit publié ; web/backend v0.12.2, mobile versionné séparément | Option utile. Dépend du pipeline summary de Meet, WhisperX, PostgreSQL, Redis et S3 ; dimensionner le traitement audio. |
| [conversations](https://github.com/suitenumerique/conversations/blob/4d6edc79be5ccfa34e57497a07311e8a1f2bba74/README.md) | Assistant IA ; outils, pièces jointes, export texte vers Docs | Développement précoce annoncé ; v0.0.22 | Intégrer comme module optionnel. Fournisseur LLM/embeddings à choisir ; Compose annoncé en préparation, API Docs déjà documentée. |
| [calc](https://github.com/suitenumerique/calc/blob/27a5a6d717a340e05f34533cc7457bb955bb741f/README.md) | Tableur basé sur Docs et IronCalc | Prototype explicite ; aucune release ; branche principale inchangée depuis juin 2025 | Différer. Collabora/ONLYOFFICE couvrent déjà les classeurs ; Grist couvre les données structurées. Reprise Calc = chantier produit, pas simple installation. |
| [hub](https://github.com/suitenumerique/hub/blob/ab2102e9a71cc91be5ab2a9915db3e0b55d4bd42/README.md) | Chat Matrix et convergence chat/visio | Explicitement non prêt pour production ; aucune release | Pilote isolé. Synapse, MAS et client Matrix de développement existent ; Drive, réunions, notifications et déchiffrement ont encore des tickets ouverts. |
| [messagerie](https://github.com/suitenumerique/messagerie/blob/03e3c36ff674b88fb64f4d22b1871a98088f186d/README.md) | Pointeur vers DIMAIL : Postfix, Dovecot, Open-Xchange | Dépôt documentaire : un seul fichier | Suivre la pile DIMAIL sur GitLab pour le mail IMAP et le groupware. Ne pas chercher une application Docker dans ce dépôt. |

### Socles

| Dépôt | Fonction | Maturité observée | Choix pour le homelab |
| --- | --- | --- | --- |
| [st-deploycenter](https://github.com/suitenumerique/st-deploycenter/blob/a5df8439bd78b5c5c8f79eb3398956e01153cec3/README.md) | Console opérateur : organisations, services, abonnements, droits, métriques | Code actif ; aucune release GitHub publiée | Conserver la version locale. Réutiliser catalogue/Gaufre et entitlements ; compléter les raccordements par application. Ne déploie pas lui-même toute la pile. |
| [people](https://github.com/suitenumerique/people/blob/5eafad1d7fb97efeb327b27ddcca0cf29c8182dc/README.md) | La Régie : annuaire, groupes, invitations, domaines et boîtes DIMAIL | v1.25.4 stable ; v1.26.0 prérelease | Intégrer les groupes/annuaire et DIMAIL si retenu. Définir les identifiants communs ; administration des organisations et provisioning des services encore partiels. |
| [accounts](https://github.com/suitenumerique/accounts/blob/2ad3342bb4e5a91cf39ad16dc875a13fff19b30c/README.md) | MonCompte : identité utilisateur fédérée et fournisseur OIDC intermédiaire | Explicitement non prêt pour production | Différer. Garder Keycloak ; invitations locales, MFA, profils et authentifications multiples restent des chantiers annoncés. |
| [menshen](https://github.com/suitenumerique/menshen/blob/fa0ccd565be2cba026c917f0e2fece24d2a5c425/README.md) | Serveur OAuth de délégation par échange de jetons, client et playgrounds | Avertissement bootstrap/non utilisable en production ; v0.2.0 | Différer sauf besoin de délégation démontré. Aucun remplacement de Keycloak ; les resource servers existants suffisent à plusieurs liaisons. |
| [find](https://github.com/suitenumerique/find/blob/025e6d02ea08c46ef831a70f0ae1a41036c5a7c9/README.md) | Recherche fédérée avec droits ; API Django, OpenSearch, indexeurs | Code et connecteurs Docs/Drive présents ; aucune release | Intégrer après identité et ACL. Vérifier indexation des ressources S3/NAS, suppressions, révocations et liens de résultat. |
| [integration](https://github.com/suitenumerique/integration/blob/5316093a071ddc6cf348994d9bdc30b5fdc256d8/README.md) | Gaufre, widgets, API de catalogue et documentation | Paquet integration-v1.0.2 ; widget v2 documenté | Réutiliser la navigation et les URLs locales, depuis un catalogue ST ou JSON. Ce menu ne constitue pas un contrôle des permissions. |
| [ui-kit](https://github.com/suitenumerique/ui-kit/blob/d18da07441801a63f710cb118d8b9aeb778a66e7/README.md) | Composants React, tokens et outil de migration | Référentiel UI canonique ; ui-components@1.1.0 | Réutiliser les packages. La fusion avec Cunningham est déjà faite dans ce dépôt ; migration de chaque application à vérifier séparément. |
| [cunningham](https://github.com/suitenumerique/cunningham/blob/a754c693bba3b30f6d60e97d07cb0e469ae48fa5/README.md) | Ancien dépôt du système de design et des tokens | Dernière version React 4.3.1 ; non archivé | Dépendance historique, désormais consolidée dans ui-kit. Ne pas démarrer un service ni entretenir deux nouveaux systèmes de design. |
| [django-lasuite](https://github.com/suitenumerique/django-lasuite/blob/c8b3dd963f4508b54bb6283d00c1e46c68b43079/README.md) | Bibliothèque Django commune : OIDC, resource server, logout, malware | Paquet v0.0.29 | Réutiliser dans les applications compatibles ; aucun service autonome. Ne pas réécrire les contrats OIDC communs. |
| [file-scanner](https://github.com/suitenumerique/file-scanner/blob/87c555e270a8d592201f0b51bb079ea27bf4e97d/README.md) | Service de scan synchrone/asynchrone ; moteurs ClamAV/exav/JCOP | Implémentation et documentation présentes ; sans release | Prévoir un service de scan commun avec moteur disponible localement. Connecteurs, quarantaine, limites et traitement des fichiers chiffrés à qualifier. |
| [st-ansible](https://github.com/suitenumerique/st-ansible/blob/258cd8f5d3ddc47894265f2b53e1eaef67d82555/README.md) | Collection Debian, Podman rootless/systemd, st-cli, sauvegarde/supervision | Déploiements documentés pour Drive, Docs, Meet, Messages, Projects, Keycloak | Référence opérationnelle utile. Ne pas substituer Podman à ton Docker par défaut ; reprendre paramètres, dépendances et runbooks pertinents. |
| [st-home](https://github.com/suitenumerique/st-home/blob/e8c20c686a76f7bd3e0751939076cf61e1498e59/README.md) | Vitrine territoriale, raccordement collectivités, traitements RPNT/OPNT | Site et traitements de données existants | Écarter du socle homelab. Ce portail territorial ne remplace ni ST ni une page utilisateur locale. |
| [helpcenter](https://github.com/suitenumerique/helpcenter/blob/c5288dd01db55c622dc982f280bb7080e6b3d473/README.md) | Centre d’aide public multisite alimenté par Docs ; Next.js/Redis | Code présent ; sans release | Optionnel pour publier une documentation publique. Sans authentification : ne pas y envoyer la documentation interne privée. |

### Extensions

| Dépôt | Fonction | Maturité observée | Choix pour le homelab |
| --- | --- | --- | --- |
| [roomkit-visio](https://github.com/suitenumerique/roomkit-visio/blob/31c7d65f46c545c8e0183ff7b9b654c71e0f28c1/README.md) | Passerelle salles SIP/PSTN vers Meet ; Kamailio, rtpengine, livekit-sip | Intégration matérielle documentée ; sans release | Seulement si salles SIP ou téléphonie nécessaires. Figer les branches vidéo indiquées, ports et dépendances ; pas requis pour la visio web. |
| [livekit-sip](https://github.com/suitenumerique/livekit-sip/blob/4c9cc19fbe598268c4464a7ac4284274a2d34e6f/README.md) | Fork du pont SIP vers LiveKit | Fork ; branches sip-video et sip-video-v2 présentes | Dépendance de téléphonie/Roomkit. La branche par défaut ne suffit pas à caractériser les ajouts vidéo. |
| [media-sdk](https://github.com/suitenumerique/media-sdk/tree/ffc0902069a6a65f442d899a6d3c6704da586610) | Fork Go de traitement audio/média LiveKit | Bibliothèque ; sans README racine ni release propre | Dépendance technique du média ; pas une application à installer séparément. |
| [meet-whisperx](https://github.com/suitenumerique/meet-whisperx/blob/46a15c7409a9cab9afed90a24c834491e05a370a/README.md) | API WhisperX : transcription, alignement, diarisation | Service implémenté ; sans release | Option de Meet/Dictaphone. Prévoir modèle, capacité de calcul, file d’attente et endpoint protégé. |
| [meet-kyutai-moshi-stt](https://github.com/suitenumerique/meet-kyutai-moshi-stt/blob/d00fbd84c0dfcaee051d359e6bd82003e67ec567/README.md) | Serveur STT temps réel Moshi/Kyutai et image GPU | Expérimentation spécialisée GPU | Seulement si sous-titrage temps réel retenu ; vérifier modèle et matériel. Ce n’est pas le même usage que la transcription différée WhisperX. |
| [meet-matting](https://github.com/suitenumerique/meet-matting/blob/fa9f16aa709196d4cbe8057f787b6c62c662670a/README.md) | Recherche sur la segmentation du fond vidéo | Explicitement expérimental | Ne pas déployer comme application. Réutiliser un résultat lorsqu’il est intégré et qualifié dans Meet. |
| [gallene-deployment](https://github.com/suitenumerique/gallene-deployment/blob/7d405389002093e70a042d960c12bd213fdd94db/README.md) | Image et chart Galène ; construction depuis galene-headless externe | Packaging exploratoire ; sans release | Alternative vidéo à évaluer, pas une dépendance de Meet/LiveKit. Garder une seule pile visio principale. |
| [gallene-sdk](https://github.com/suitenumerique/gallene-sdk/blob/4b02d7c7ac8c9480ee8ee396edb75fc6cd8a78f9/README.md) | API et jetons Galène ; sous-projet Python galene-api | SDK embryonnaire ; sans release | Uniquement avec Galène. Malgré la description frontend du dépôt, le code livré observé est un client Python. |

### Outillage

| Dépôt | Fonction | Maturité observée | Choix pour le homelab |
| --- | --- | --- | --- |
| [drive-migrator](https://github.com/suitenumerique/drive-migrator/blob/9ee4462a7bcfd2d08698b48280c5f1c8cb20961a/README.md) | Migration documentaire ; source actuellement centrée sur Resana vers Drive | Outil actif, backend et interface ; sans release | À utiliser seulement pour une migration réelle. Pas nécessaire pour le NAS existant ; versions et dossiers vides hors périmètre annoncé. |
| [encryption](https://github.com/suitenumerique/encryption/blob/09044d1e5f7a82b357e09f9e550aa821f64b8d8d/README.md) | Intention de mutualiser le chiffrement | Seulement README et LICENSE ; aucun code | Concept à suivre, rien à installer. Ne pas lui attribuer les mécanismes déjà développés dans Transfers ou Matrix. |
| [e2esdk](https://github.com/suitenumerique/e2esdk/blob/b75557f2c98402041aa0f4d3c64525fbee7435da/README.md) | Fork SocialGouv : SDK de chiffrement client et serveur de clés | Branche beta ; dernier commit hérité d’octobre 2023 | Ne pas ajouter au socle. Intégration cryptographique complète nécessaire ; aucune protection automatique des applications existantes. |
| [containers](https://github.com/suitenumerique/containers/blob/e75f960cc81e4d3942a9ea1fccc34ac682487b06/README.md) | Fork des images et templates RunPod | Packaging GPU ; branche feat/moshi référencée | Hors Docker applicatif du homelab, sauf recours explicite à ces images GPU. Ce dépôt ne contient pas le déploiement global de La Suite. |
| [helm-dev-backend](https://github.com/suitenumerique/helm-dev-backend/tree/52b02b6b684a1525ad9ceb275d078d09802717db) | Chart de dépendances de développement : DB, cache, Keycloak, S3, proxy | Chart 0.0.8 ; aucun README racine | Écarter du runtime Docker de production. Ne pas créer une seconde pile d’identité/stockage à partir de ce chart. |
| [buildpack](https://github.com/suitenumerique/buildpack/blob/6b1adb0357a84fe7b7922660c6bc27e9787bfaaa/README.md) | Construction Python/JS pour Scalingo et PaaS | Outil existant, sans release | Inutile pour ton déploiement Docker Compose. |
| [interop](https://github.com/suitenumerique/interop/blob/b1e8f45ca40f75e9e49355483332bb9f1abbaf36/README.md) | Banc commun de développement avec Keycloak et MinIO | Petit dépôt récent ; configuration dev uniquement | Référence d’interopérabilité. Ne pas confondre avec un orchestrateur complet ni démarrer ses dépendances en doublon. |
| [st-domain-parking](https://github.com/suitenumerique/st-domain-parking/blob/2c1a725e578d69abf8b99e9b4cbfa663adb0c95c/README.md) | Pages d’attente pour domaines de collectivités ; builder/Caddy/S3 | Code fonctionnel décrit, sans release | Seulement pour héberger des pages de domaines en attente. Aucun besoin pour les sous-domaines applicatifs déjà servis par ton proxy. |

### Documentation

| Dépôt | Fonction | Maturité observée | Choix pour le homelab |
| --- | --- | --- | --- |
| [docs-website](https://github.com/suitenumerique/docs-website/blob/171166ec1259fa0c74dd188227848ac63a8f71d5/README.md) | Vitrine Docs/Astro ; contenu et roadmap tirés de Docs | Site actif | Source pour les orientations et exemple de publication depuis Docs ; installation non nécessaire. |
| [documentation](https://github.com/suitenumerique/documentation/blob/af67a1003e17b7b8a27054a72e312afd6c05584b/README.md) | Catalogue historique des produits, dépendances et liens externes | Documentation générale, peu actualisée | Conserver comme source historique ; préférer versions, code et documentations produit actuels pour déployer. |
| [dev-handbook](https://github.com/suitenumerique/dev-handbook/blob/65cf006e31960dc71b201af0ff6f71c58ed053d8/README.md) | Pratiques de développement et de collaboration | Documentation | Référence contributive, aucun service à déployer. |
| [.github](https://github.com/suitenumerique/.github/blob/0890ba7e8991ddca680f0652792dc3f88dbebd6a/profile/README.md) | Profil public et liste officielle des produits | Documentation organisationnelle | Point de départ du catalogue ; les licences et la maturité se vérifient par produit. |
| [hackdays](https://github.com/suitenumerique/hackdays/blob/073c13188a209203dd874ac60b7faa3235932b6a/README.md) | Site vitrine de l’événement Hack Days | Site historique Next.js | Aucune application métier à déployer. |
| [hackdays2025](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/README.md) | Archive de propositions et démonstrateurs : 55 dossiers de soumission | Historique public, non archivé techniquement | Toutes les propositions sont classées en annexe. Présence dans ce dépôt ne vaut ni adoption ni engagement de maintenance. |
| [hackathon42](https://github.com/suitenumerique/hackathon42/blob/15ff7b80267ba1b7576b2e931fdebe8dbf10b84e/README.md) | Annonce d’un événement de contribution | README et LICENSE seulement | Rien à installer ; aucune nouvelle application livrée dans ce dépôt. |
| [planka](https://github.com/suitenumerique/planka/blob/bcea2f3425de5b95f5cf30259bc41d060f20638d/README.md) | Ancien fork Kanban | Seul dépôt archivé de l’organisation | Écarter au profit de Projects pour ce besoin ; conserver uniquement comme historique, sans déployer les deux. |

Points de version à ne pas confondre : People **v1.26.0 est une prérelease**,
la stable observée est v1.25.4 ; `jmap-email-0.3.0` est une bibliothèque de
Messages, dont la version applicative observée est v0.9.0. Calc n’a plus de
commit sur sa branche principale depuis juin 2025. Le commit par défaut du fork
e2esdk est hérité d’octobre 2023, antérieur à sa création dans l’organisation.

## 4. Produits externes faisant partie de l’écosystème

Le [profil officiel](https://github.com/suitenumerique/.github/blob/main/profile/README.md)
renvoie lui-même hors de l’organisation. S’arrêter à ses 49 dépôts manquerait
notamment Grist, Tchap et l’implémentation réelle de Messagerie.

| Produit et sources | Périmètre réel | Conséquence pour ton serveur |
| --- | --- | --- |
| [Grist Core](https://github.com/gristlabs/grist-core) | Tableur/base de données collaborative, documents, formulaires, API, contrôle d’accès. Application indépendante avec son stockage persistant. | Intégrer pour les données structurées. Les classeurs Excel complexes restent du ressort des éditeurs Office. Pas de classement natif universel dans Drive déjà livré. |
| [Tchap Web v4](https://github.com/tchapgouv/tchap-web-v4), [Synapse](https://github.com/tchapgouv/synapse), [Android X](https://github.com/tchapgouv/tchap-x-android), [iOS X](https://github.com/tchapgouv/tchap-x-ios) | Chat Matrix, serveurs et clients ; règles de déploiement propres au service public. | Choisir une pile Matrix maintenue et sa configuration d’identité. Ne pas supposer l’accès ni la fédération avec le Tchap de l’État ; ne pas repartir de l’ancien Web v2 archivé. |
| [Démonstrateur Tchap Docker](https://github.com/tchapgouv/tchap-docker-integration), [charts Tchap](https://github.com/tchapgouv/tchap-helm-charts) | Démo Matrix 2.0 avec Synapse, MAS, LiveKit et Element Call ; avertissement explicite de non-production. Le chart inspecté couvre le web, pas toute la pile. | Source d’intégration, pas livraison complète pour exploitation. Qualifier authentification, chiffrement, récupération des clés, notifications mobiles et sauvegarde. Ne pas doubler Meet pour les réunions générales sans besoin. |
| [France Transfert](https://github.com/numerique-gouv/francetransfert) | Application distincte d’échange temporaire : frontend Angular, services Java d’envoi/réception et traitements. | Alternative à Transfers, pas sa dépendance. Choisir un seul parcours principal et adapter domaine, expéditeur, expiration et stockage au homelab. |
| [DIMAIL Infra](https://gitlab.mim-libre.fr/dimail/dimail-infra), [DIMAIL API](https://gitlab.mim-libre.fr/dimail/dimail-api) | Véritable messagerie traditionnelle : Postfix, Dovecot, Open-Xchange, base de données, provisioning API et automatisation d’infrastructure. | À retenir si IMAP/groupware sont requis et insuffisamment couverts par Messages. C’est une pile supplémentaire importante, pas un simple backend interchangeable de Messages. |
| [Dicalso](https://gitlab.mim-libre.fr/dimail/dicalso) | Fork Cal.com dans le groupe DIMAIL : prise de rendez-vous. | Usage distinct de la tenue d’agenda ; option à qualifier, sans déduire une intégration terminée du seul README hérité. |
| [Galène](https://github.com/jech/galene) et [galene-headless](https://github.com/Paloys/galene-headless) | Autre famille de visioconférence ; le packaging `gallene-deployment` construit le fork headless référencé dans son Dockerfile. | Alternative expérimentale à Meet/LiveKit, pas composant nécessaire à Meet. |

**Grist et SSO :** sa documentation distingue l’OIDC natif avec clé d’activation
et l’authentification par en-têtes de proxy disponible dans toutes les éditions.
Choisir une édition/configuration explicite ; pour les en-têtes, le service doit
être accessible uniquement par le proxy de confiance qui supprime les en-têtes
entrants et injecte l’identité vérifiée.
[OIDC Grist](https://support.getgrist.com/install/oidc/),
[authentification par proxy](https://support.getgrist.com/install/forwarded-headers/).

Le groupe DIMAIL expose **22 projets publics**, recensés dans le manifeste.
Leur organisation précise le périmètre de `messagerie` :

| Ensemble | Dépôts recensés | Lecture pour l’intégration |
| --- | --- | --- |
| Infrastructure/provisioning | dimail-infra, dimail-infra-template, dimail-api, dimail-client, dimail-cli | Déploiement, configuration, API, SDK Python et CLI. People documente un raccordement à DIMAIL. |
| Interfaces/identité | dimail-ui, dimail-ui-8, dimail-login, dimail-oidc, dimail-alias, ohlala-ui, ohlala-api, ohlala-login | Personnalisations Open-Xchange/connexion et services associés ; plusieurs descriptions sont génériques ou incomplètes. Ne pas les présenter comme autant de produits autonomes prêts. |
| Politique et exploitation | policyd, policyd-rate-limit, dimail-stats, dimail-fastapi-mw, dimail-cyberwatch-container, renovate-configuration | Services/outillage de support ; choix exact dépendant de la recette DIMAIL retenue. |
| Rendez-vous et migration | dicalso, dicalso-builder, pst2ics | Rendez-vous Cal.com, packaging et conversion ; options conditionnées au besoin. |

### Autres services cités dans le catalogue et les documents historiques

Le catalogue de navigation contient aussi des services extérieurs au cœur de
suite. Les deux fichiers JSON ont été inspectés : leur drapeau `enabled` concerne
le menu correspondant, **pas l’existence ou l’arrêt du service**. Le catalogue
local de démonstration cite même Resana sous le nom « Stockage » : il ne faut
pas recopier ces URLs dans ton installation.
[integration · website/src/data/services.json](https://github.com/suitenumerique/integration/blob/5316093a071ddc6cf348994d9bdc30b5fdc256d8/website/src/data/services.json),
[integration · website/src/data/services-local.json](https://github.com/suitenumerique/integration/blob/5316093a071ddc6cf348994d9bdc30b5fdc256d8/website/src/data/services-local.json).

| Service | Périmètre et source | Décision homelab |
| --- | --- | --- |
| RDV Service Public | [Application externe](https://github.com/betagouv/rdv-service-public) de prise de rendez-vous entre administrations et usagers, API et notifications ; distincte d’un agenda général. | Facultatif, si gestion d’accueil/rendez-vous nécessaire ; comparer au besoin plus simple couvert par Cal.com/Dicalso. |
| Démarche numérique | [Application externe](https://github.com/demarche-numerique/demarche.numerique.gouv.fr), anciennement Démarches simplifiées : formulaires et instruction de dossiers administratifs. | Produit métier autonome ; ne pas ajouter pour de simples formulaires Grist. À retenir uniquement pour un véritable circuit de dossiers/instruction. |
| Pad / Notepad | [HedgeDoc hébergé par la DINUM](https://pad.numerique.gouv.fr/s/apropos), prise de notes Markdown collaborative. | Docs couvre le besoin principal ; alternative seulement pour un usage Markdown spécifique ou une migration existante. |
| Équipes / Desk | Ancienne entrée de gestion de groupes avec URL de staging dans le catalogue ; le code People conserve les noms internes Desk. | Rattacher au périmètre People ; ne pas démarrer une seconde application d’annuaire sur la foi de cet ancien libellé. |
| Webinaire | La documentation historique l’associe à BigBlueButton. | Option de webinaire/formation distincte ; pas nécessaire à une visio Meet ordinaire. |
| Webconf | La documentation historique l’associe à Jitsi Meet. | Alternative à Meet ; ne pas installer les deux pour le même besoin. |
| AudioConf | [Conférences par téléphone](https://audioconf.numerique.gouv.fr/questions-frequentes), et pas uniquement audio dans le navigateur. | Option téléphonique ; nécessite un raccordement SIP/opérateur si cet usage est retenu, pas un simple bouton Meet. |
| Resana | Plateforme propriétaire de collaboration ; [la DINUM annonce la fin de son financement au 31 décembre 2026, avec poursuite par Interstis](https://lasuite.numerique.gouv.fr/resana-en-2027). | Ne pas rechercher son code dans les 49 dépôts ni annoncer son extinction. Utiliser Drive/Docs/Projects selon les usages ; `drive-migrator` répond à la migration de contenus. |
| Osmose | Offre communautaire historiquement [fondée sur Jplatform/Jalios](https://www.numerique.gouv.fr/actualites/teletravail-osmose-et-plano-2-nouveaux-outils-numeriques-collaboratifs-pour-les-agents-de-letat/) : communautés, publications et échanges. | Pas de livraison homelab dans les dépôts inspectés. Les usages documentaires/chat ont des contreparties ; un véritable réseau communautaire serait un besoin supplémentaire. |
| ProConnect | Identité/fédération externe référencée dans les documentations et configurations destinées à l’État. | Keycloak reste le fournisseur local ; une fédération ProConnect est un choix distinct, pas un prérequis pour auto-héberger les applications compatibles OIDC. |

Sources du catalogue historique : [documentation · README.md](https://github.com/suitenumerique/documentation/blob/af67a1003e17b7b8a27054a72e312afd6c05584b/README.md) et
[people · README.md](https://github.com/suitenumerique/people/blob/5eafad1d7fb97efeb327b27ddcca0cf29c8182dc/README.md). Les remarques sur Webinaire/Webconf décrivent leurs bases
techniques référencées ; aucun arrêt de ces services n’est déduit de l’ancienneté
du catalogue.

## 5. Architecture d’intégration recommandée

### 5.1. Identité, annuaire et administration

**Exigence du propriétaire : indépendance du fournisseur d’identité.** Keycloak
est le fournisseur actuellement installé, pas une dépendance obligatoire de la
suite. La cible est une intégration OpenID Connect configurable, utilisable avec
Microsoft Entra ID (Azure AD), Authentik et les autres IdP compatibles. Elle ne
doit pas imposer un intermédiaire Keycloak ni ses APIs d’administration.
[Standard OIDC](https://openid.net/specs/openid-connect-core-1_0.html),
[Microsoft Entra ID](https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc),
[Authentik](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/).

Réutiliser les clients OIDC et bibliothèques des applications. Les paramètres
d’issuer, clients, audiences et correspondance des attributs sont configurables.
Les comptes applicatifs gardent une identité durable, associée aux identités
externes vérifiées (`iss`, `sub`) ; un changement d’email ou d’IdP ne doit pas
perdre les fichiers et droits. La migration des associations doit être explicite,
sans fusion automatique de comptes sur la seule adresse email. Les identifiants
`sub` pouvant varier entre clients, leur correspondance interapplications doit
être définie plutôt que supposée.
[Identifiants OIDC](https://openid.net/specs/openid-connect-core-1_0.html#ClaimStability).

Les groupes et la désactivation ne sont pas uniformisés par le seul login OIDC.
**Décision validée par le propriétaire : People est la source initiale des
groupes ; un mode d’import depuis un annuaire externe/IdP sera ensuite proposé.**
Chaque groupe importé aura une source faisant autorité et une correspondance
explicites, afin d’éviter des modifications concurrentes contradictoires.
Un connecteur de
provisioning/SCIM peut compléter le socle selon les capacités disponibles ; il
reste distinct de l’authentification. Fixer et vérifier le délai de révocation
des accès, y compris pour les sessions déjà ouvertes. Les rôles, espaces et
quotas applicatifs ne doivent pas dépendre des rôles propriétaires d’un IdP.

Authentik en conteneurs est autorisé pour la future qualification du changement
d’IdP. Cette décision ne lance ni son installation ni l’implémentation du socle ;
le propriétaire demande de terminer d’abord le nettoyage Docker.

| Responsabilité | Propriétaire recommandé | Travail restant |
| --- | --- | --- |
| Authentification, sessions, MFA | IdP configurable ; Keycloak dans l’environnement actuel | Contrat OIDC commun, clients distincts, attributs configurables, audience et redirections. Préserver les identités actuelles ; qualifier un second fournisseur sans réécrire les règles métier. |
| Groupes, invitations, domaines | People et source d’annuaire choisie, raccordés au socle d’identité/ST | Un identifiant stable et une source faisant autorité pour chaque champ. Mapper les groupes Django locaux de Drive ; propager retrait de groupe, suspension et changement d’adresse. |
| Catalogue, souscriptions, budgets | ST Deploy Center | Exposer les services locaux, droits d’activation et quotas applicatifs ; administration homelab sans dépendance obligatoire aux référentiels des collectivités. |
| Autorisation sur chaque ressource | Application qui possède la ressource, ou délégation explicite à Drive | Contrôles côté serveur, partage, révocation, invités et liens publics. La présence d’une vignette ST/Gaufre n’accorde aucun accès au contenu. |
| Navigation | Gaufre v2 et catalogue local | Réutiliser le menu existant ; un portail de liens suffit au départ. Tableau de bord de contenus récents seulement après APIs et droits cohérents. |

People documente encore des étapes incomplètes pour l’administration des
organisations et le provisioning de services. Accounts et Menshen indiquent
eux-mêmes qu’ils ne sont pas prêts pour la production. Les ajouter maintenant
ne résout pas automatiquement ces raccordements.
[people · docs/organizations.md](https://github.com/suitenumerique/people/blob/5eafad1d7fb97efeb327b27ddcca0cf29c8182dc/docs/organizations.md), [people · docs/serviceProviders.md](https://github.com/suitenumerique/people/blob/5eafad1d7fb97efeb327b27ddcca0cf29c8182dc/docs/serviceProviders.md),
[people · docs/models.md](https://github.com/suitenumerique/people/blob/5eafad1d7fb97efeb327b27ddcca0cf29c8182dc/docs/models.md), [accounts · README.md](https://github.com/suitenumerique/accounts/blob/2ad3342bb4e5a91cf39ad16dc875a13fff19b30c/README.md), [menshen · README.md](https://github.com/suitenumerique/menshen/blob/fa0ccd565be2cba026c917f0e2fece24d2a5c425/README.md).

ST possède déjà un catalogue pour la Gaufre : l’endpoint `lagaufre/services`
est public et filtre notamment par opérateur. N’y publier que des informations
de catalogue destinées à être publiques, jamais des connexions de stockage.
Les autorisations de souscription et les permissions de contenu restent deux
contrats séparés.
[st-deploycenter · src/backend/core/api/viewsets/lagaufre.py](https://github.com/suitenumerique/st-deploycenter/blob/a5df8439bd78b5c5c8f79eb3398956e01153cec3/src/backend/core/api/viewsets/lagaufre.py),
[integration · README.md](https://github.com/suitenumerique/integration/blob/5316093a071ddc6cf348994d9bdc30b5fdc256d8/README.md).

### 5.2. Stockage et quotas : conserver la séparation physique/virtuelle

Les espaces Drive restent la façade utilisateur commune des fichiers S3 et NAS.
Le stockage S3 natif passe par Django Storage ; le NAS par MountProvider.
Une authentification NAS peut alimenter plusieurs espaces/grants utilisateurs,
et plusieurs connexions NAS/S3 peuvent coexister. Les permissions du compte NAS
ne remplacent jamais les restrictions virtuelles de Drive.
[Contrat local](../../docs/agent-storage-contract.md),
[espaces unifiés](../../docs/unified-storage-spaces.md).

Les autres applications conservent leurs bases, fichiers internes et formats
natifs. Mutualiser un serveur PostgreSQL ou un service S3 est possible avec des
bases/comptes/buckets ou préfixes isolés ; cela ne signifie pas leur donner accès
au même espace interne ni faire passer toutes leurs écritures par MountProvider.

Pour Docs/Grist dans Drive, distinguer :

1. **Référence vers un document vivant** : identifiant stable, application,
   titre et accès ; l’application possède le contenu et la coédition.
2. **Export de fichier** : copie PDF, DOCX, XLSX, etc., stockée dans un espace
   Drive autorisé, comptabilisée et indépendante de l’original vivant.
3. **Intégration profonde** : Drive possède aussi classement, partage et
   corbeille ; l’application lui délègue explicitement ces responsabilités.
   Les prototypes Docs/Drive ci-dessous sont une base à évaluer pour cette cible,
   pas à fusionner tels quels. Préserver les ACL natives tant que cette délégation
   et la migration des droits ne sont pas terminées.

Les quotas doivent rester **applicatifs et indépendants du NAS** : ST définit
la politique, chaque service bloque ses propres écritures et suit sa consommation.
Pour un budget global de suite, commencer par des allocations par application
dont la somme ne dépasse pas le budget global. Un budget entièrement partagé
et dynamique exige ensuite des réservations atomiques communes ; une simple
somme de métriques périodiques ne bloque pas les dépassements concurrents.
Les écritures directes externes au NAS nécessitent inventaire/réconciliation ;
Drive peut restreindre ses écritures futures, pas empêcher une autre application
d’écrire hors de lui. Les plafonds physiques éventuellement exposés restent une
contrainte supplémentaire, pas la politique utilisateurs.

Pour Messages, des entitlements et métriques de stockage existent, mais leur
présence ne suffit pas à démontrer un refus systématique des écritures à quota
atteint. Qualifier SMTP entrant, import, pièces jointes, brouillons, duplication,
corbeille/rétention et boîtes partagées. Les PR de jauge ou de stockage ne sont
pas une preuve de ce contrôle. [messages · docs/entitlements.md](https://github.com/suitenumerique/messages/blob/8e8d9e126172421fc55e7306be79a581c0b6721c/docs/entitlements.md),
[messages · src/backend/core/entitlements/backends/deploycenter.py](https://github.com/suitenumerique/messages/blob/8e8d9e126172421fc55e7306be79a581c0b6721c/src/backend/core/entitlements/backends/deploycenter.py),
[demande de quotas](https://github.com/suitenumerique/messages/issues/246),
[évolution en cours](https://github.com/suitenumerique/messages/pull/764).

### 5.3. Liaisons applicatives : ce qui existe et ce qui manque

| Liaison | État observé | Raccordement à réaliser |
| --- | --- | --- |
| Messages ↔ Drive | API réelle d’import/export de pièces jointes ; accès centré sur les `items` fichiers créés par l’utilisateur. | Étendre aux ressources autorisées, y compris NAS et partages ; choix d’espace, droits et réservation de quota à destination. |
| Transfers ← Drive | Sélecteur SDK et import serveur à partir d’un permalink. | Retirer la nécessité de rendre le fichier source public ; autorisation déléguée, bornée et révocable, streaming, destination et quotas. |
| Docs ↔ Drive | Deux PR de preuve de concept pour documents pointeurs et délégation du partage/cycle de vie. | Adapter au modèle Ressource d’Apoze ; migration des droits existants, invitations, suppression/restauration idempotentes et authentification interservice limitée. |
| Grist ↔ Drive | Objectif de feuille de route ; proposition de prévisualisation statique distincte. | Références aux documents vivants puis contrat de création/partage/export. Un aperçu `.grist` ne livre pas toute l’intégration. |
| Meet → Drive | Prototype réel d’export d’enregistrement depuis le worker. | Autorisation survivant à un long enregistrement, reprise, transfert borné, déduplication, quotas et nettoyage après succès confirmé. |
| Meet/Dictaphone → transcription → Docs | Pipeline summary et export documentés, avec avertissements de maturité. | Partager le moteur lorsque les contrats concordent ; traitement asynchrone, accès aux enregistrements, modèle choisi et règles de conservation. |
| Conversations → Docs | Export texte existant via resource server et identité utilisateur ; nouveau document à chaque export. | Configurer les jetons/renouvellement ; ne pas promettre synchronisation bidirectionnelle ou transfert des pièces jointes. |
| Calendars ↔ Messages | Invitations et canaux de connexion documentés ; serveur CalDAV réel. | Qualifier réponses aux invitations, récurrences, fuseaux, calendriers partagés et accès des clients externes. |
| Find ← Docs/Drive | Indexeurs et recherche tenant compte des droits. | Adapter indexation des espaces/montages du fork ; garantir retrait des résultats et du contenu indexé après révocation/suppression. |
| Projects ↔ Drive | Gestion de pièces jointes propre à Projects. | Lien vers une ressource Drive ou copie explicitement demandée ; aucun accès indu par partage du tableau. |
| People ↔ autres applications | Modèles de groupes et interopérabilité documentés, raccordement DIMAIL. | Mapping effectif des groupes et révocation ; ne pas déduire une synchronisation universelle du seul login OIDC. |

Sources techniques : [messages · src/backend/core/api/viewsets/drive.py](https://github.com/suitenumerique/messages/blob/8e8d9e126172421fc55e7306be79a581c0b6721c/src/backend/core/api/viewsets/drive.py),
[transfers · src/frontend/src/features/transfers/components/DriveAttachButton.tsx](https://github.com/suitenumerique/transfers/blob/1d3c1eda9d2402fe6961cf0d7f0cbf8d10a50c9a/src/frontend/src/features/transfers/components/DriveAttachButton.tsx),
[conversations · docs/interoperabilities.md](https://github.com/suitenumerique/conversations/blob/4d6edc79be5ccfa34e57497a07311e8a1f2bba74/docs/interoperabilities.md), [meet · src/summary/README.md](https://github.com/suitenumerique/meet/blob/adc74f846c11537798a50455ea33e98cf1517b02/src/summary/README.md),
[calendars · docs/channels.md](https://github.com/suitenumerique/calendars/blob/9bb5200e2a6c9fd5a99a8f7e502eff8fb1cc416f/docs/channels.md), [find · README.md](https://github.com/suitenumerique/find/blob/025e6d02ea08c46ef831a70f0ae1a41036c5a7c9/README.md),
[people · docs/interoperability/dimail.md](https://github.com/suitenumerique/people/blob/5eafad1d7fb97efeb327b27ddcca0cf29c8182dc/docs/interoperability/dimail.md).

**Constat à traiter avant branchement de Transfers :** le SDK officiel Drive
transforme un partage non public en partage public lors du choix du fichier.
Le même mécanisme existe dans le fork local, dans `getSdkChooseUpdates` de
`sdkRuntime.ts`. Le fait qu’un utilisateur puisse choisir un document ne doit
pas rendre sa source accessible à tous. Prévoir une délégation réservée au
service importateur, avec ressource, utilisateur, opération, échéance et
révocation vérifiés côté serveur.
[drive · src/frontend/apps/drive/src/features/sdk/SdkPickerFooter.tsx](https://github.com/suitenumerique/drive/blob/fbb76dc3fa1895a9e6ddcb647d2d6075bf0ae35a/src/frontend/apps/drive/src/features/sdk/SdkPickerFooter.tsx),
[code local](../../src/frontend/apps/drive/src/features/sdk/sdkRuntime.ts).

Le guide spécialisé Transfers distingue chiffrement avec clé également détenue
par le serveur et mode confidentiel où le serveur ne reçoit pas la clé. Le README
général ne reflète pas entièrement ce fonctionnement. En particulier, en mode
confidentiel par email, la clé doit être transmise séparément. La purge physique
S3 peut être différée après expiration. Qualifier séparément l’import Drive :
un transfert serveur ne peut pas être présenté comme un chiffrement navigateur
de bout en bout sans démonstration du parcours. Un serveur ne peut pas scanner
en clair un contenu dont il ne possède pas la clé.
[transfers · docs/ENCRYPTION.md](https://github.com/suitenumerique/transfers/blob/1d3c1eda9d2402fe6961cf0d7f0cbf8d10a50c9a/docs/ENCRYPTION.md), [transfers · docs/S3.md](https://github.com/suitenumerique/transfers/blob/1d3c1eda9d2402fe6961cf0d7f0cbf8d10a50c9a/docs/S3.md).

## 6. Travaux prévus, prototypes et défauts à qualifier

### 6.1. Travaux actuels qui peuvent éviter de repartir de zéro

| Travail et preuve | État au 6 septembre | Décision recommandée |
| --- | --- | --- |
| [Drive #790](https://github.com/suitenumerique/drive/pull/790) + [Docs #2548](https://github.com/suitenumerique/docs/pull/2548) | Deux PR brouillons ouvertes. Drive devient propriétaire de l’arbre, du partage et de la corbeille ; Docs garde le contenu. Le côté Docs retire ses accès/invitations et les E2E ne sont pas adaptés. | Base d’architecture pertinente, mais reprise sélective après examen des permissions, migrations et contrat interservice. Ne pas importer la configuration de démonstration ni son jeton statique global. |
| [Meet #1557](https://github.com/suitenumerique/meet/pull/1557) + [Drive #796](https://github.com/suitenumerique/drive/pull/796) | PR ouvertes, Meet en brouillon. Export après enregistrement ; limite documentée : expiration du jeton utilisateur pendant les longues sessions. | Réutiliser le flux de transfert ; résoudre l’autorisation différée sans allonger indéfiniment les jetons de session. Menshen est envisagé par les auteurs, mais encore bootstrap. |
| [Messages #583](https://github.com/suitenumerique/messages/pull/583) | PR ouverte de pont IMAP/SMTP vers l’API Messages, mots de passe applicatifs et rôles. Pas fusionnée dans la branche principale inspectée. | Candidat prioritaire si clients mail classiques souhaités : peut éviter DIMAIL. Revue et pilote réels nécessaires, notamment dossiers/flags, pièces jointes, rotation et retrait d’accès. |
| [Messages #479](https://github.com/suitenumerique/messages/pull/479) | PR brouillon JMAP : l’auteur annonce un premier sous-ensemble, avec spécification et clients encore à tester. | Ne pas annoncer un serveur JMAP complet. Le résumé automatique de PR est plus affirmatif que le texte de l’auteur et n’est pas retenu comme preuve. |
| [Messages #764](https://github.com/suitenumerique/messages/pull/764), [#519](https://github.com/suitenumerique/messages/pull/519) | PR ouvertes sur stockage, jauges, rétention et entitlements ; certains mécanismes ont déjà des équivalents dans la branche principale. | Comparer le diff utile à la version retenue, puis vérifier le contrôle des écritures. Ne pas empiler aveuglément des implémentations qui se recouvrent. |
| [Drive #763](https://github.com/suitenumerique/drive/pull/763) | PR ouverte de groupes issus d’un claim OIDC configurable. | Piste légère pour Keycloak ; rapprocher du modèle de groupes local et de People, avec révocation vérifiée. |
| [Drive #292](https://github.com/suitenumerique/drive/pull/292) | Proposition d’aperçu statique Grist. | À distinguer de la coédition Grist et du classement des documents natifs. |
| [Drive #771](https://github.com/suitenumerique/drive/pull/771) | Brouillon de dépôt de fichiers sans droit de lecture ; interface et protections contre les abus explicitement hors de ce premier lot. | Option utile de collecte externe, pas parcours complet déjà disponible. |
| [Find #155](https://github.com/suitenumerique/find/issues/155) | Proposition de graphe de connaissances. | Recherche future ; ne pas compter dessus pour la première recherche fédérée. |

### 6.2. Feuilles de route et historique à distinguer

La [roadmap Drive](https://docs.numerique.gouv.fr/docs/eacaabdb-d92b-465d-bedf-75d28b397221/)
est datée du 3 septembre 2026 dans l’API publique. Elle annonce encore versions,
recherche hybride, liens éphémères et liaisons Docs/Grist/Meet/Messages/Assistant.
Certaines fonctions, notamment WOPI, stockage NAS et espaces/quota, existent déjà
dans Apoze Drive : il faut comparer les contrats et conserver les apports du fork.

La [roadmap Docs](https://docs.numerique.gouv.fr/docs/d1d3788e-c619-41ff-abe8-2d079da2f084/)
et sa [liste planifiée](https://docs.numerique.gouv.fr/docs/1e2a0b10-bc55-4b47-94f6-6b854acc3050/)
distinguent mentions/notifications, imports ODT, liens vers des blocs, recherche,
mathématiques/diagrammes et Docs dans Drive. Les imports DOCX/Markdown, le mode
présentation et l’API resource server sont déjà recensés parmi les réalisations
2026 ; le prototype d’import DOCX de 2025 n’est donc plus un chantier à reprendre
tel quel. Suggestions, véritable hors-ligne, publication et certaines fonctions
avancées restent des orientations ou demandes de financement, pas des promesses
de disponibilité. [Réalisations Docs 2026](https://docs.numerique.gouv.fr/docs/924009cb-7ee7-4b18-b872-a351e5f6d33c/).

| Tableau public | État | Éléments collectés | Brouillons sans issue |
| --- | --- | ---: | ---: |
| [LaSuite Docs A11y](https://github.com/orgs/suitenumerique/projects/19) | Ouvert | 140 | 0 |
| [Docx Import](https://github.com/orgs/suitenumerique/projects/12) | Fermé | 12 | 0 |
| [La Suite Drive](https://github.com/orgs/suitenumerique/projects/10) | Ouvert | 131 | 0 |
| [La Suite Messages](https://github.com/orgs/suitenumerique/projects/4) | Ouvert | 44 | 0 |
| [La Suite Meet](https://github.com/orgs/suitenumerique/projects/3) | Fermé | 10 | 10 |
| [LaSuite Docs](https://github.com/orgs/suitenumerique/projects/2) | Ouvert | 978 | 11 |

Les brouillons Docs ajoutent notamment application mobile, archivage, migrations
et contenus embarqués ; certains autres brouillons sont déjà marqués terminés
(exports ODT, favoris, sauts de page). Le tableau Meet fermé conserve dix idées,
dont agenda, transcription, enregistrement, chiffrement, téléphonie et Roomkit :
plusieurs ont depuis du code. Leur présence historique ne signifie pas qu’il
reste dix fonctions intégralement à développer. Les brouillons et leur état
exact sont conservés dans le manifeste.

### 6.3. Défauts rapportés à reproduire avant qualification

| Sujet | Source ouverte | Impact sur la suite |
| --- | --- | --- |
| Réponses RSVP et URL d’événement | [Messages #752](https://github.com/suitenumerique/messages/issues/752) | Risque de conflit ou duplication lors du raccordement agenda. |
| Suppression d’un agenda de boîte partagée | [Calendars #72](https://github.com/suitenumerique/calendars/issues/72) | Cycle de vie et administration incomplets selon le signalement. |
| Modification d’une occurrence récurrente | [Calendars #21](https://github.com/suitenumerique/calendars/issues/21) | Qualification impérative des séries et exceptions. |
| URLs locales codées pour le déploiement | [Calendars #44](https://github.com/suitenumerique/calendars/issues/44) | Vérifier domaine public, proxy et chemins DAV dans la version retenue. |
| Résumé Meet dépendant de la configuration analytique | [Meet #1610](https://github.com/suitenumerique/meet/issues/1610) | Vérifier le pipeline dans un homelab sans télémétrie obligatoire. |

Ce sont des signalements ouverts au moment de la collecte, **pas des pannes
reproduites sur ton serveur**. Calendars possède aussi des contrôles serveur
effectifs pour certaines opérations de collections CalDAV ; il serait faux de
conclure, à partir d’un ancien paragraphe de documentation, que toutes ses
restrictions ne sont vérifiées que dans l’interface.
[calendars · src/backend/core/api/viewsets_caldav.py](https://github.com/suitenumerique/calendars/blob/9bb5200e2a6c9fd5a99a8f7e502eff8fb1cc416f/src/backend/core/api/viewsets_caldav.py).

## 7. Déploiement cible et ordre de travail

Le but est de couvrir les usages, pas d’exécuter chaque dépôt. Docker Compose
reste la cible du homelab ; `st-ansible` utilise une autre recette, Podman rootless
et systemd. Reprendre les paramètres utiles et runbooks, sans ajouter Kubernetes,
Scalingo ou une seconde identité de démonstration pour installer leurs exemples.
[st-ansible · README.md](https://github.com/suitenumerique/st-ansible/blob/258cd8f5d3ddc47894265f2b53e1eaef67d82555/README.md), [interop · README.md](https://github.com/suitenumerique/interop/blob/b1e8f45ca40f75e9e49355483332bb9f1abbaf36/README.md).

| Lot | Livrable | Vérification minimale de sortie |
| --- | --- | --- |
| 0 — Socle préservé | Inventaire runtime, versions figées, sauvegarde et procédure de restauration de Drive/ST/Keycloak/S3/NAS ; domaines et capacité disponible relevés. | Parcours actuel conservé ; restauration d’un petit jeu de données isolé. Aucun arrêt/remplacement implicite de la pile existante. |
| 1 — Identité et catalogue indépendants de l’IdP | OIDC configurable, mapping des comptes/groupes, People, services locaux dans ST/Gaufre ; conservation des identités existantes. Valider le raccordement avec Docs comme première application supplémentaire. | Parcours Drive/ST/Docs avec Keycloak, puis mêmes scénarios sur une configuration isolée avec un second IdP, par exemple Authentik ; retrait de groupe, suspension et refus côté API dans un délai défini. |
| 2 — Docs et Grist | Instances persistantes et sauvegardables, domaines propres, SSO, documents partagés ; décision d’édition Grist. | Création/coédition/export, accès interdit à un tiers, redémarrage sans perte. |
| 3 — Ressources communes | Sélection Drive S3/NAS privée ; liaisons Messages/Transfers ; documents Docs/Grist référencés puis délégation de classement/droits là où elle est retenue. | Choisir un fichier privé sans le publier, refuser un tiers, copier/exporter dans un espace autorisé, quota et révocation effectifs. |
| 4 — Meet et audio | Meet/LiveKit, réseau WebRTC ; export d’enregistrement Drive ; transcription/Dictaphone optionnels. | Appel à deux navigateurs depuis les réseaux utiles, enregistrement dépassant la durée d’un jeton d’accès, reprise d’un export interrompu. |
| 5 — Courriel et agenda | Choix Messages seul, Messages avec pont qualifié, ou DIMAIL ; DNS mail, filtrage, livraison, Calendars/OX et People selon la cible. | Émission/réception réelles sur domaine contrôlé, client externe si prévu, invitation/réponse, exception récurrente, quota de boîte. |
| 6 — Projects, Transfers, chat | Applications utiles et clients retenus ; stockage, ACL, expiration et récupération des accès documentés. | Un flux par app + un refus pertinent ; expiration de transfert et récupération d’une session Matrix chiffrée. |
| 7 — Find et assistant | Recherche Docs/Drive adaptée aux espaces, Conversations et modèles choisis ; liens de résultats vers les apps. | Résultat autorisé trouvé ; résultat retiré après révocation ; réponse/export assistant ne transmettant pas de document inaccessible. |
| 8 — Exploitation cohérente | Inventaire des services, mise à jour/retour arrière, sauvegardes cohérentes, supervision, files de jobs et politiques de rétention. | Une restauration transversale d’un petit scénario lié ; contrôle de santé des services et suppression de tous les fichiers d’essai. |
| 9 — Extensions explicites | Tableau blanc, portail de contenus, SIP, rendez-vous, fonctionnalités Calc uniquement si besoin confirmé. | Critère métier précis avant tout développement ; ne pas ajouter une plateforme déjà couverte. |

**Prochain chantier recommandé : « Socle commun d’identité, d’accès et de
catalogue, indépendant de l’IdP ».** Commencer par le contrat et l’inventaire des
raccordements existants, puis les appliquer à Drive/ST/People. Introduire Docs
comme premier parcours interapplication réel pour vérifier le résultat. Ce lot
livre connexion commune, groupes, activation des services et navigation ;
l’intégration profonde des documents Docs dans l’arbre Drive reste le lot 3.
Grist vient ensuite, avec le même contrat, puis Meet et ses transferts.

La recette complète devra préciser pour chaque service : image et digest,
variables non secrètes, secrets distincts, ports internes/publics, volumes/bases,
workers, migrations, sauvegarde, dépendances au démarrage et procédure d’upgrade.
Partager les infrastructures compatibles ne doit pas partager leurs identifiants
ni coupler toutes leurs migrations. Redis/cache et OpenSearch ne remplacent pas
les bases faisant autorité ; les index doivent être reconstruisibles.

Pour le mail public, vérifier domaine/DNS, SPF/DKIM/DMARC, PTR et connectivité SMTP
dans l’infrastructure réellement utilisée ; choisir un relais si nécessaire.
Pour Meet, qualifier NAT/UDP/TURN avant d’attribuer les échecs à l’application.
Pour IA/audio, mesurer la charge réelle avant de choisir GPU, modèles et
concurrence ; cet inventaire ne fournit pas un dimensionnement matériel inventé.

Les contrôles proposés portent sur les comportements réels et les pertes
d’accès/données possibles. **Pas de tests recherchant des chaînes dans les
fichiers de code.** Pas de campagne exhaustive répétée : un parcours utile par
application, les refus critiques aux frontières et une restauration transversale.

### Doublons et composants à ne pas ajouter par défaut

- Planka avec Projects ; Calc avec les éditeurs Office et Grist sans manque précis.
- DIMAIL et Messages hébergeant chacun une copie indépendante de la même boîte.
- Calendars et Open-Xchange possédant chacun une copie maîtresse du même agenda.
- Transfers et France Transfert pour le même parcours d’envoi temporaire.
- Galène, BigBlueButton, WorkAdventure ou une seconde pile de visio sans usage
  distinct de Meet.
- Accounts comme remplacement prématuré de Keycloak ; Menshen uniquement pour
  avoir un composant de plus, avant d’avoir arrêté le besoin de délégation.
- Cunningham et ui-kit comme deux systèmes de design à développer en parallèle.
- Vitrines publiques, sites de hackathon, chart de développement, buildpacks et
  images RunPod comme s’il s’agissait d’applications métier indispensables.

Les licences se vérifient par composant et variante de build, pas sur une
affirmation générale du profil de l’organisation. Le CSV conserve le SPDX détecté
par GitHub, ou « non détecté ». Exemples : Projects/Planka AGPL, forks média
Apache ; Docs signale des fonctionnalités BlockNote à licence distincte et un
mode de build MIT. Cette lecture n’est pas une analyse juridique de distribution.
[docs · README.md](https://github.com/suitenumerique/docs/blob/3c1275c88da39abb71e045c7deaba3844ca9ac49/README.md), [ui-kit · README.md](https://github.com/suitenumerique/ui-kit/blob/d18da07441801a63f710cb118d8b9aeb778a66e7/README.md).

## 8. Annexe — les 55 propositions Hack Days 2025

Toutes les soumissions sont couvertes. **Démonstrateur ou idée de 2025 ne signifie
pas produit officiel actuel.** Certains formulaires conservent un champ de code
non renseigné ; cela ne prouve pas qu’aucun code n’existe ailleurs. Les décisions
ci-dessous évaluent leur utilité pour ce homelab, pas la qualité de chaque équipe.

| Soumission | Proposition | Décision / état à retenir |
| --- | --- | --- |
| [airgrist](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/airgrist/README.md) | Migration Airtable vers Grist. | Outil utile uniquement pour une migration existante. |
| [albert-ai](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/albert-ai/README.md) | Canvas Docs dans une conversation Albert. | Prototype ; comparer à l’export Docs de Conversations déjà disponible, sans confondre export et canvas vivant. |
| [baller](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/baller/README.md) | Gestion de listes de diffusion publiques. | Usage optionnel distinct des boîtes personnelles/partagées ; produit à qualifier. |
| [bib4win](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/bib4win/README.md) | Citations et bibliographie Docs, DOI/Zotero. | Extension utile à la rédaction scientifique ; pas une dépendance du socle. |
| [big-blue-button](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/big-blue-button/README.md) | Docs intégré à BigBlueButton, transcription/résumé. | Alternative pour des usages de webinaire ; Meet reste la visio principale proposée. |
| [cacai](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/cacai/README.md) | Recherche INRIA/COAST autour de MUTE et du chiffrement de groupe MLS. | Travail de recherche ; aucun chiffrement universel prêt à brancher. |
| [comparia](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/comparia/README.md) | Comparaison de modèles IA, interopérabilité et impact environnemental. | Option d’évaluation ; pas nécessaire pour utiliser Conversations. |
| [cristal](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/cristal/README.md) | Interface XWiki Cristal au-dessus de Docs. | Alternative de présentation wiki ; pas requise pour Docs. |
| [data-ai-macif](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/data-ai-macif/README.md) | CIVA, assistant et graphe/RAG métier. | Proposition spécialisée ; lien de code non renseigné dans la soumission. |
| [dbt](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/dbt/README.md) | FactVerifAI, vérification de faits dans Docs. | Proposition ; lien de code non renseigné, pas un service livré à intégrer. |
| [decision-makers](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/decision-makers/README.md) | Convene, conduite chronométrée de décisions dans Meet. | Extension métier de réunion, facultative. |
| [devoteam](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/devoteam/README.md) | Drive/diapositives et génération IA. | Proposition ; lien de code non renseigné dans la soumission. |
| [dgnum-experts](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/dgnum-experts/README.md) | Packaging Debian du backend Docs. | Autre mode de déploiement ; inutile pour la cible Docker. |
| [dgnum-x-nix-community](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/dgnum-x-nix-community/README.md) | SuiteOS et distribution NixOS sécurisée. | Proposition d’environnement ; lien de code non renseigné. |
| [dgnum-x-nixos-community](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/dgnum-x-nixos-community/README.md) | Packaging concret Docs/Meet pour NixOS. | Alternative au déploiement Docker, pas application métier supplémentaire. |
| [doc-spec](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/doc-spec/README.md) | Prototype d’import DOCX dans Docs. | Fonction désormais livrée en amont ; ne pas reprendre le démonstrateur comme chantier neuf. |
| [doca-team](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/doca-team/README.md) | Prez, diapositives Polotno et IA à partir de Drive. | Prototype ; présentation simple déjà couverte par Docs/Office, usage natif avancé à préciser. |
| [docs-to-git](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/docs-to-git/README.md) | Synchronisation de Markdown Docs avec Git. | Connecteur facultatif pour documentation versionnée ; droits et conflits à traiter. |
| [dringdringtuttut](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/dringdringtuttut/README.md) | Passerelle téléphonique Tchap. | Proposition ; lien de code non renseigné, besoin SIP à définir. |
| [element](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/element/README.md) | Aurora, prototype web Matrix/Element X avec SDK Rust. | Suivre les clients maintenus actuels ; ne pas figer la pile sur une branche de démonstration 2025. |
| [ergonogrist](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/ergonogrist/README.md) | Aides Grist, visites guidées, formulaires et navigation Gaufre personnalisée. | Améliorations d’usage à comparer au Grist et au widget Gaufre actuels. |
| [eu-os](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/eu-os/README.md) | Poste de travail Linux pour le secteur public. | Proposition d’OS client, hors applications serveur ; code non renseigné. |
| [euos](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/euos/README.md) | EU OS, bootc/KDE et administration de postes. | Projet de poste de travail ; distinct de l’installation de la suite sur le serveur. |
| [grist-3-ia](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/grist-3-ia/README.md) | Widget Grist connecté à Albert. | Extension IA facultative ; aligner fournisseur et autorisations avec Conversations. |
| [handi-access](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/handi-access/README.md) | Améliorations d’accessibilité Docs. | À retrouver dans les versions actuelles et le tableau A11y ; pas d’application autonome. |
| [haxathon](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/haxathon/README.md) | Mathématiques/LaTeX et graphiques Docs. | Extension à rapprocher du chantier mathématiques/diagrammes actuel. |
| [incubateur-educnat](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/incubateur-educnat/README.md) | Fichiers Drive vers Albert puis résumé Docs. | Proposition sans code renseigné ; parcours à couvrir avec les connecteurs retenus. |
| [incubator-for-ai](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/incubator-for-ai/README.md) | Recherche hybride Drive, MCP et liens Slack. | Prototype ; privilégier Find/Conversations comme base avant un nouveau moteur RAG. |
| [interstis](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/interstis/README.md) | RAG/Albert dans la plateforme Resana. | Code signalé non public ; pas de solution libre déployable démontrée par ce dossier. |
| [ironcalc](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/ironcalc/README.md) | La Suite Calc, tableur natif collaboratif. | Correspond au dépôt officiel calc ; CRDT, XLSX et intégrations restent des axes de reprise produit. |
| [jeu-twake-et-match](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/jeu-twake-et-match/README.md) | Cozy/Twake, pont Docs et RAGondin. | Plateforme alternative complète ; ne pas ajouter une seconde couche documentaire sans besoin. |
| [la-suite-portal](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/la-suite-portal/README.md) | Portail utilisateur : documents récents, réunions, chat. | Prototype de tableau de bord ; base éventuelle après SSO/APIs/ACL, catalogue simple d’abord. |
| [la-suite-territoriale](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/la-suite-territoriale/README.md) | Pièces jointes Messages ↔ Drive. | Du code existe aujourd’hui ; adapter le sélecteur, les accès privés et le NAS du fork. |
| [la-suite-ui](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/la-suite-ui/README.md) | Co1ors, génération de palettes accessibles. | Outil de design, pas service métier ; conserver ui-kit et le style actuel. |
| [lin-phone](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/lin-phone/README.md) | Téléphonie Tchap/Linphone. | Option SIP/PSTN ; choisir un seul raccordement pour le besoin réel. |
| [matrix-preview](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/matrix-preview/README.md) | Aperçus de liens privés côté client Matrix Android. | Recherche côté client ; ne pas ajouter un serveur qui lirait tous les liens privés. |
| [mosa-cloud](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/mosa-cloud/README.md) | Launchpad/Épicentre, portail personnel et widgets IA. | Prototype facultatif ; recouvrement avec le portail utilisateur et le catalogue. |
| [one-point](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/one-point/README.md) | Ideas, tableau blanc tldraw connecté à Meet/Drive. | Véritable usage distinct ; prototype avec authentification/droits à compléter avant intégration. |
| [onet](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/onet/README.md) | Déploiement Kubernetes de la suite et interface d’administration. | Autre cible d’infrastructure ; recouvrement avec ST, pas à superposer au Docker existant. |
| [openova](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/openova/README.md) | Pipeline RAG sur Drive. | Prototype ; rapprocher de Find/Conversations et du contrôle d’accès unifié. |
| [openproject-hacking-borders](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/openproject-hacking-borders/README.md) | Documents Docs dans les work packages OpenProject. | Option si gestion de projets avancée nécessaire ; Projects suffit au Kanban simple. |
| [panographix](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/panographix/README.md) | Tables et graphiques Grist embarqués dans Docs. | Connecteur utile futur ; permissions, rafraîchissement et exports à définir. |
| [parula](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/parula/README.md) | Application de bureau et tableau de bord regroupant la suite. | Proposition ; lien de code non renseigné, hors socle serveur. |
| [pycrdt](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/pycrdt/README.md) | CRDT Python pour Docs/Jupyter. | Proposition technique sans code renseigné ; bibliothèque/interop, pas application utilisateur. |
| [sentinel](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/sentinel/README.MD) | Classification de données personnelles dans Drive. | Option de politique documentaire ; ne remplace pas l’antivirus et exige validation des résultats. |
| [sovereign42](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/sovereign42/README.md) | MailGuard, détection IA d’hameçonnage dans Open-Xchange. | Extension possible si DIMAIL/OX retenu ; pas un prérequis à Messages. |
| [team94](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/team94/README.md) | Catalogue de modèles Docs et installateur Windows. | Modèles facultatifs ; packaging Windows non nécessaire au serveur Docker. |
| [the-gr](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/the-gr/README.md) | Interface IA transformant le langage naturel en opérations SQL d’administration. | Expérimentation ; ne pas donner un accès direct d’administration DB à un assistant par défaut. |
| [the-importers](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/the-importers/README.md) | Import Notion vers Docs. | Outil conditionné à une migration Notion réelle. |
| [vopenia](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/vopenia/README.md) | Transcription Meet en temps réel. | Comparer aux extensions STT actuelles ; éviter un second pipeline équivalent. |
| [vort-x](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/vort-x/README.md) | Moodle/Docs et assistance IA pédagogique. | Intégration métier éducation, hors suite générale ; code non renseigné. |
| [vrc-team](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/vrc-team/README.md) | Passerelle média SIP vers Meet. | Comparer à roomkit-visio/livekit-sip actuels avant tout nouveau développement. |
| [workadventure](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/workadventure/README.md) | Bureaux virtuels 2D avec Docs et Grist embarqués. | Plateforme optionnelle, pas dépendance de la collaboration documentaire. |
| [xiv0](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/xiv0/README.md) | Téléphonie XiVO/Tchap. | Autre raccordement SIP ; à retenir seulement selon le système téléphonique utilisé. |
| [yunohosters](https://github.com/suitenumerique/hackdays2025/blob/9fc784bb4d6dd650d897c5818ad0589e4e6440a9/submissions/yunohosters/README.md) | Packaging Docs pour YunoHost. | Autre mode d’installation ; inutile pour la cible Docker existante. |

Les nouvelles familles réellement distinctes sont notamment tableau blanc,
portail personnel, listes de diffusion, références bibliographiques et certains
connecteurs métier. Aucune n’impose d’abandonner le socle actuel. Le reste relève
largement de fonctions déjà absorbées, d’alternatives complètes, de packaging
pour d’autres environnements ou de prototypes IA à rapprocher de Find et
Conversations avant de lancer un nouveau service.

## 9. Maintenir cet état des lieux

Ce document est la référence de recherche ; les décisions d’implémentation
futures devront en dériver des lots, avec versions et critères précis.
Avant chaque lot, rafraîchir la pagination des dépôts et les PR qui le concernent,
vérifier les changements depuis les SHA du manifeste et requalifier les
interfaces utilisées. Revoir notamment les couples Docs/Drive, Meet/Drive et
le pont IMAP Messages avant de redévelopper leurs mécanismes.

Aucune application supplémentaire n’a été installée ou redémarrée pour cette
recherche. Les conclusions d’intégration sont proposées, pas présentées comme
des tests de fonctionnement déjà passés.
