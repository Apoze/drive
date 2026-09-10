# ADR 0003 — Identité durable et accès communs de la suite

Date : 8 septembre 2026. Décision appliquée ; recette finale qualifiée.

## Décision

People porte la personne (`User.id`, UUID durable) et les groupes
(`Team.external_id`). ST porte l'organisation (`Organization.id`), les
souscriptions, les politiques d'accès aux applications et les budgets existants.
Chaque application conserve ses utilisateurs locaux, leurs clés primaires,
leurs propriétaires et leurs ACL. Une association additive relie un utilisateur
local au principal People ; elle ne déplace aucun fichier.

L'identité externe est une association explicitement vérifiée entre issuer,
subject opaque, consommateur OIDC et personne. L'email, le nom et le SIRET ne
sont pas des clés d'identité. Les subjects différents selon le client sont
associés séparément. Une connexion inconnue crée une demande à approuver dans
People ; elle ne reçoit pas de droits avant validation.

L'IdP authentifie. People gère initialement les groupes. Un annuaire externe
peut devenir l'autorité d'un groupe importé par SCIM, après aperçu et transfert
explicites dans People. Un groupe importé homonyme ne récupère pas les droits
d'un groupe supprimé. Les ACL de contenu restent dans Drive ou Docs : l'accès
à une application et l'accès à un document sont deux décisions distinctes.

## Mise en œuvre

Un petit paquet Python commun contient les associations, la validation OIDC,
les contrôles de session, le catalogue et la synchronisation. Les adaptations
métier restent dans les quatre applications. Une wheel locale reproductible
est intégrée à leurs dépendances natives, sans `PYTHONPATH` spécifique au socle
sur le LAN et sans nouveau microservice d'authentification.

Les workers et ordonnanceurs Celery natifs lisent People puis les politiques
ST toutes les 30 secondes. Les révisions sont monotones ; une lecture partielle
ou obsolète n'efface pas une projection complète. La décision positive cesse
d'être utilisable après 90 secondes sans vérification. La borne publiée de
révocation est de 120 secondes, sous réserve des flux déjà acceptés.

Les API machine emploient des credentials dédiés par consommateur et usage,
indépendants des sessions humaines : pas de dépendance circulaire de bootstrap.
Les demandes de rattachement et de déconnexion globale disposent de credentials
de mutation distincts des clés de lecture.

Les sessions OIDC ont une preuve authentifiée de 15 minutes au maximum.
L'epoch local de session permet une déconnexion commune même lorsque l'IdP
n'expose pas de déconnexion globale. Dans ce cas, l'interface explique que sa
session IdP peut rester ouverte. Une nouvelle preuve est requise pour revenir.

Docs conserve son modèle documentaire, ses ACL et sa coédition. Son S3 est
privé et distinct du stockage Drive. La réutilisation initialement prévue du
serveur SeaweedFS Drive a été écartée après reproduction du défaut CopyObject
versionné de sa version 4.12. Un service Docs 4.46 figé, sans port publié et
avec un volume persistant séparé, corrige cette incompatibilité sans mise à
jour imposée au stockage Drive. [Correctif amont](https://github.com/seaweedfs/seaweedfs/pull/10594).

## Limites explicites

- Une organisation configurée par déploiement consommateur ; aucun hébergement
  multi-organisations implicite par lecture de claims IdP.
- Keycloak et Authentik directs qualifiés ; Entra et les autres IdP suivent le
  contrat OIDC/SCIM documenté mais ne sont pas déclarés testés sans leur tenant.
- Une révocation ne rappelle ni les octets téléchargés, ni un flux déjà accepté.
  Les liens publics autonomes ont leur propre cycle de vie.
- Les quotas Drive/ST existants sont conservés. Aucun quota dynamique global
  partagé entre Docs et toutes les applications n'est annoncé par ce lot.
- HTTP LAN conserve les origines de développement existantes. DNS/TLS et
  exposition publique demandent une configuration d'exploitation distincte.

Voir le [guide d'installation](../installation/suite-identity-and-docs.md),
le [guide d'exploitation](../operations/suite-identity-access.md) et
le [plan et ses critères](../plans/suite/identity-access-catalogue-docs-plan.md).
