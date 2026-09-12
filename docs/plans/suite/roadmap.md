# Roadmap de la suite Apoze

Mise à jour : **12 septembre 2026**. Vue courte des chantiers restants ;
l'ordre ci-dessous ne fixe pas leur priorité et n'autorise pas leur exécution.
Chaque chantier retenu aura son plan détaillé et des tests réels minimaux.

## Déjà intégrés sur le LAN

Drive (espaces S3/NAS et bureautique), Docs, People/IdP, ST, Meet,
Messages, Calendars, Projects, Transfers et Chat (Synapse/MAS/Element Web).
Element X Android est qualifié sur émulateur ; le code iOS est livré.
Les plans et preuves de livraison sont accessibles dans l'[index des plans](../README.md).

## Chantiers restants

| Chantier | Objectif | Statut |
| --- | --- | --- |
| Chat mobile — validation différée | Compiler iOS sur Mac, signer les applications et qualifier téléphones/APNs/FCM. | Code livré ; Android 36 testé ; [checklist §14](transfers-element-chat-integration-plan.md#14-recette-mobile-différée--à-reprendre-ultérieurement) |
| Find | Recherche commune respectant les droits et les espaces S3/NAS. | À planifier |
| ClipSync | Intégrer la solution personnelle du propriétaire à la suite. | À planifier ; périmètre à préciser avec lui au démarrage |
| Grist Community | Tableaux de données et formulaires. | **En pause ; reprise uniquement sur demande spécifique du propriétaire** |
| Conversations | Assistant IA connecté aux contenus autorisés. | Optionnel |
| Portail utilisateur enrichi | Documents récents, tâches, réunions et notifications au-delà du catalogue. | Optionnel |
| Exploitation globale | Consolider les sauvegardes, la restauration globale, la supervision et les mises à jour des forks. | À planifier à partir des outils déjà livrés |
| Passage au WAN | Domaines, certificats, accès extérieur, mail Internet et réseau Meet. | **Différé à la demande du propriétaire ; LAN pour le moment** |

## Options hors du périmètre actuel

Chat : invités et fédération différés. Code Android/iOS livré ; recette sur
téléphones, compilation iOS sans Mac et remise APNs/FCM reportées à la demande
du propriétaire. [Livraison et limites](../../../output/implementation/transfers-element-chat/validation-final.md).

Dictaphone, enregistrements/transcriptions Meet, tableau blanc et Calc :
ajout uniquement après décision spécifique. Calc recouvre en partie les
éditeurs Office déjà présents ; sa nécessité devra être précisée.

## Suivi

- Mettre cette roadmap à jour à chaque livraison ou décision de périmètre.
- Conserver les détails et preuves dans les plans et rapports correspondants.
- [Grist : plan mis en pause](../paused/suite/grist-community-integration-plan.md).
- [Inventaire de référence et recherches](../../../output/research/README.md)
  : constats datés, à actualiser pour le chantier choisi.
- [Roadmap historique des fonctionnalités Drive](../../drive-feature-roadmap.md)
  : périmètre distinct, état à requalifier avant toute reprise.
