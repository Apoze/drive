# Chat Apoze — exploitation du socle en cours d’intégration

État au 11 septembre 2026 : serveur et administration qualifiés sur une identité
jetable. **La livraison complète reste ouverte** dans le
[plan Transfers/Chat](../plans/suite/transfers-element-chat-integration-plan.md).
Les liens aux autres applications, les mobiles et la restauration isolée ne
sont pas encore livrés. Grist reste en pause.

## Services et identité

Synapse porte les salons et médias ; MAS les sessions OAuth des clients Matrix.
L’IdP authentifie, People rattache `(issuer, subject)` à l’UUID durable et porte
les groupes. ST attribue l’accès Chat et les budgets. Aucun rapprochement par
email, aucun compte partagé pour les personnes.

Le serveur de recette `chat-qa.invalid` ne doit accueillir aucun vrai utilisateur.
Son nom ne pourra pas être renommé pour passer en production. Le nom durable
contrôlé par le propriétaire reste à choisir ; il peut être résolu seulement
sur le LAN. Les URL d’accès peuvent évoluer indépendamment des identifiants
Matrix si la découverte et les retours OAuth sont correctement migrés.

Profil de recette actuel :

- Element/Matrix : `https://192.168.10.123:8954`.
- MAS : `https://192.168.10.123:8955`.
- État privé : `data/chat-qa/`, avec certificats, clés et configurations.
- Médias : `data/chat-qa/media/`, distincts des stockages Drive.
- Bases : `chat_qa` et `mas_qa` sur PostgreSQL de la suite.
- Contrats : [ADR Matrix](../adr/0004-matrix-sessions-and-authorization.md).

Ne pas désactiver TLS ou la vérification des certificats pour connecter un
client. Installer la CA LAN publique du profil sur le poste concerné ; ne pas
copier sa clé privée. La distribution aux appareils mobiles reste à préparer.

## Commandes du profil existant

Depuis `Apoze/drive`, ces commandes ne modifient pas le script de démarrage Drive :

```sh
python3 docker/suite/prepare_chat.py \
  --state data/chat-qa --server-name chat-qa.invalid --qa
python3 docker/suite/build_element_local.py

docker compose -f data/chat-qa/compose.json up -d
docker compose -f data/chat-qa/compose.json ps
docker compose -f data/chat-qa/compose.json stop
```

Le générateur conserve les secrets existants et refuse un changement d’identité
sur le même état. Il ne provisionne pas de comptes métier à lui seul.
`provision_chat_local.py` enregistre les consommateurs People/ST fermés et les
bases dédiées. Son adaptateur `--register-current-keycloak` est facultatif :
les règles d’autorisation ne dépendent pas de Keycloak. Une autre configuration
OIDC s’ajoute via les déclarations natives MAS `oidc_providers` de l’état privé,
après approbation de l’issuer dans le consommateur Chat de People.

Un changement du proxy exige son rechargement, même si Compose n’a pas recréé
le conteneur :

```sh
docker compose -f data/chat-qa/compose.json exec -T edge nginx -s reload
```

## Compilation sur le serveur partagé

Utiliser `build_element_local.py`, pas le builder Docker par défaut pour Element.
Le worker `apoze-suite` est dédié, figé et limité à **3 Gio, deux CPU, sans swap**.
Le script vérifie 3,5 Gio disponibles et les limites réelles du conteneur.
Il ne change pas le builder Docker par défaut et ne stoppe aucun service métier.
L’image communautaire est construite depuis le fork et son lockfile ; aucune
branche SDK distante flottante n’est incorporée implicitement.

Si la capacité manque, différer la compilation ou libérer les seuls outils de
recette. Garder le navigateur hors des compilations lourdes. Réduire la
minification à un worker a permis de tenir dans la limite. Un échec de build ne
remplace pas l’image déjà chargée et ne constitue pas une validation.
Les limites utilisent le
[driver Docker officiel](https://docs.docker.com/build/builders/drivers/docker-container/).

## Administration depuis le Web

1. **People** : identités liées, noms et groupes. Désactiver une ancienne liaison
   IdP lorsqu’elle ne doit plus authentifier ; le journal ne fusionne jamais
   deux sujets sur leur email.
2. **ST** : autorisation de l’application Chat et budgets utilisateur,
   organisation et instance. Zéro/absence de plafond signifie illimité ; le
   blocage de croissance est distinct. Diminuer un quota ne supprime rien.
3. **Paramètres du salon → Rôles et permissions → Accès de la suite** : activer
   la gestion People en conservant les membres, attribuer groupes/droits directs
   et rôles. Les sources sont cumulées ; un retrait ne supprime pas un droit
   encore donné par une autre source. Garder un responsable actif.
4. **Paramètres du compte → Stockage du chat** : consulter usage et capacité,
   sélectionner les fichiers, prévisualiser puis confirmer une suppression.
   Les administrateurs People voient tous les comptes et peuvent transférer
   la responsabilité de stockage après vérification du quota destinataire.
5. **Paramètres du compte → Administration des salons** : rechercher un salon,
   consulter ses accès et son journal, puis reprendre un salon orphelin avec
   un nouveau responsable et un motif. L’appartenance préalable n’est pas
   nécessaire à cette administration ; elle ne donne pas les clés E2EE.

L’administration repose sur le groupe People durable `suite-administrators`.
Elle n’expose pas les API Admin globales Synapse/MAS. Les opérations ordinaires
n’exigent ni SQL ni clé machine copiée dans un navigateur.

Une réattribution de média change le compte facturé et le droit de suppression.
Elle ne change ni auteur Matrix d’origine, ni destinataires, ni chiffrement.
Les fichiers en cours d’envoi sont exclus. Une suppression confirmée retire
la copie serveur pour tous ; aucun effacement des copies déjà téléchargées
n’est promis. Les noms de fichiers chiffrés peuvent être inconnus du serveur.

Le plafond d’envoi Chat est 100 Mio, miniatures comprises dans le budget.
Le quota médias ne mesure pas toute la base de messages et de clés. Une réserve
instance de 384 Mio couvre l’entrée HTTP ; un plancher disque de 5 Gio protège
les écritures. Une purge incomplète reste facturée jusqu’à suppression confirmée.

## Révocation, salons et appareils

Les autorisations expirent après au plus 90 secondes sans lecture People/ST
valide. Une panne suspend l’accès ; elle ne transforme pas une ancienne décision
en autorisation permanente. MAS garde rotation et sessions natives, avec borne
absolue de 30 jours ; les 15 minutes concernent le login IdP initial.

Le profil crée des salons privés chiffrés v11 : propriétaire transférable,
historique limité aux membres, sans invités ni fédération. Un upgrade natif
ne transfère pas les grants People et est refusé avant ses effets de bord.
Les versions à créateurs implicites indélogeables devront être qualifiées avant
une migration gouvernée, pas activées via une simple option de client.

Pour un salon orphelin, l’ancienne autorité native nécessaire à la reprise peut
rester techniquement jointe tout en étant privée de lecture et de sync. La
reprise explicite affecte le nouveau responsable puis retire cette ancienne
présence. Les caches sync ne doivent jamais restituer les anciens droits.

Les pushers sont natifs et liés à un appareil : passerelle HTTPS exacte par
app ID, format opaque `event_id_only`, autorité People inchangée et durée bornée.
Le profil actuel n’a **aucune passerelle mobile de production configurée**.
Une révocation confirmée supprime le pusher ; un salon retiré ne doit plus
produire de notification en attente. Les credentials/APNs/FCM et la livraison
sur appareil ne sont pas validés par la recette serveur d’inscription/retrait.

## Vérifications ciblées et reprise

Les checks natifs réutilisables se trouvent dans `Apoze/synapse/contrib/apoze/` :
`check_media.py`, `check_media_administration.py`, `check_room_revocation.py`.
Lire leur aide avant usage ; les tokens temporaires restent dans des fichiers
privés et les checks ne doivent viser que les comptes/salons de recette prévus.
Le journal du chantier distingue chaque commande réellement exécutée des
scénarios seulement préparés.

Sauvegarde/restauration isolée, upgrade opérationnel complet et nettoyage final
restent à réaliser en TC11/TC12. Ne pas utiliser un simple dump SQL comme preuve
que les médias, clés MAS, signature Synapse et journal d’autorité sont restaurés.
