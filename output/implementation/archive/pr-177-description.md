# Description historique — livraison Drive/ST, PR 177

Archive de la description de
[Apoze/drive PR 177](https://github.com/Apoze/drive/pull/177).
Ce texte décrit une livraison antérieure, pas l’état actuel du stockage
ni le plan d’identité. Voir [l’index des plans](../../../docs/plans/README.md).

## Summary

- connect the local Drive stack reproducibly to ST Deploy Center quota data
- expose the demo SIRET through Keycloak 26 using a managed user-profile field
- accept valid integer-valued decimal usage metrics while rejecting malformed values
- display the applicable storage state in Drive and preserve trusted public quota reasons
- block new uploads server-side when user or organization quotas are exceeded
- isolate backend tests from local OIDC claim settings

## Why

Drive needs to consume the quotas administered in ST Deploy Center, show the
applicable state to users, and keep the backend authoritative when an upload is
not allowed.

Tracks Apoze/drive#169, Apoze/drive#170, Apoze/drive#171, Apoze/drive#172,
Apoze/drive#173, and Apoze/drive#174.

## Validation

- deterministic repository gates: pass
- backend lint: Ruff pass, Pylint 10/10
- backend suite: 2200 passed, 12 warnings
- focused authentication suite after the realm correction: 25 passed
- frontend lint: pass
- isolated Keycloak 26.3.2 realm import: pass
- live ST → Drive flow: 5 GB displayed; 1 MB user limit blocked import with
  the personal-quota message; 1 MB organization limit locked storage and
  blocked import with the organization-quota message; both demo quotas restored
- git diff check, gitlint, changelog policy, and tracked backend debug-print checks: pass
- one unrelated user-list test failed intermittently on the first full run,
  passed in isolation, and the complete rerun passed

## Notes

- regular Drive storage remains separate from MountProvider capacity
- no secret, token, cookie, authorization header, signed URL, or file content
  is added or logged
- this PR targets the Apoze fork only
