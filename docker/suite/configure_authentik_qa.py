"""Configure synthetic Authentik/People fixtures; never target the LAN environment."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / "data/suite-authentik-qa"


def run(container, code, data, label):
    command = ["docker", "exec", "-i", container]
    if "authentik" in container:
        command += ["ak", "shell", "-c", code]
    else:
        command += ["python", "manage.py", "shell", "-c", code]
    result = subprocess.run(
        command, input=json.dumps(data), text=True, capture_output=True, timeout=120
    )
    log = PRIVATE / (label + ".private.log")
    log.write_text(result.stdout + result.stderr)
    log.chmod(0o600)
    if result.returncode:
        raise RuntimeError(f"{label} failed; private diagnostic: {log}")
    lines = [
        line[len("QA_RESULT ") :]
        for line in result.stdout.splitlines()
        if line.startswith("QA_RESULT ")
    ]
    if len(lines) != 1:
        raise RuntimeError(f"{label}: missing qualification result")
    return json.loads(lines[0])


AUTHENTIK = """
import json, sys
from django.db import transaction
from authentik.core.models import Application, Group, User
from authentik.crypto.models import CertificateKeyPair
from authentik.flows.models import Flow
from authentik.policies.models import PolicyBinding
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping
from authentik.providers.scim.models import SCIMProvider, SCIMMapping
payload = json.load(sys.stdin)
with transaction.atomic():
    users = {}
    for name in ("alice", "bob", "outsider", "suite-imported"):
        user, _ = User.objects.get_or_create(username=name, defaults={"name": name.title() + " Qualification", "email": name + "@suite-qa.invalid"})
        user.set_password(payload["passwords"][name])
        user.save()
        users[name] = user
    group, _ = Group.objects.get_or_create(name="Suite QA imported editors")
    group.users.set([users["alice"], users["bob"]])
    provider, _ = SCIMProvider.objects.update_or_create(name="Suite QA People SCIM", defaults={
        "url": payload["base"] + ":19103/api/v1.0/suite-scim", "token": payload["scim"],
        "dry_run": True, "discovery_enabled": False, "exclude_users_service_account": True,
    })
    mapping, _ = SCIMMapping.objects.update_or_create(name="Suite QA People user profile", defaults={"expression": 'return {"userName": request.user.username, "displayName": request.user.name, "active": request.user.is_active, "emails": [{"value": request.user.email, "primary": True}] if request.user.email else []}'})
    provider.property_mappings.set([mapping])
    provider.property_mappings_group.set(SCIMMapping.objects.filter(managed="goauthentik.io/providers/scim/group"))
    provider.group_filters.set([group])
    application, _ = Application.objects.get_or_create(slug="suite-qa-provisioning", defaults={"name": "Suite QA provisioning"})
    provider.backchannel_application = application
    provider.save()
    for i, user in enumerate(users.values()):
        PolicyBinding.objects.get_or_create(target=application, user=user, defaults={"order": i})
    oidc = {}
    signing = CertificateKeyPair.objects.filter(name="authentik Self-signed Certificate").first()
    assert signing is not None
    for index, app in enumerate(("drive", "st", "people", "docs")):
        oidc_provider, _ = OAuth2Provider.objects.update_or_create(name="Suite QA " + app, defaults={
            "authorization_flow": Flow.objects.get(slug="default-provider-authorization-implicit-consent"),
            "authentication_flow": Flow.objects.get(slug="default-authentication-flow"),
            "invalidation_flow": Flow.objects.get(slug="default-provider-invalidation-flow"),
            "client_id": "suite-" + app, "client_secret": payload["clients"][app],
            "client_type": "confidential", "grant_types": ["authorization_code", "refresh_token"],
            "signing_key": signing, "sub_mode": "user_uuid" if app == "docs" else "hashed_user_id",
            "issuer_mode": "per_provider", "include_claims_in_id_token": True,
            "_redirect_uris": [
                {"matching_mode": "strict", "url": payload["base"] + ":" + str(19101 + index) + "/api/v1.0/" + path, "redirect_uri_type": kind}
                for path, kind in (("callback/", "authorization"), ("logout-callback/", "logout"))
            ],
        })
        oidc_provider.property_mappings.set(ScopeMapping.objects.filter(scope_name__in=["openid", "email", "profile"]))
        Application.objects.update_or_create(slug="suite-qa-" + app, defaults={"name": "Suite QA " + app, "provider": oidc_provider})
        oidc[app] = {"issuer": payload["base"] + ":19190/application/o/suite-qa-" + app + "/", "subjects": {name: str(user.uuid) if app == "docs" else user.uid for name, user in users.items()}}
    result = {"provider": provider.pk, "group": str(group.pk), "users": {name: {"external_id": user.uid, "id": user.pk} for name, user in users.items()}, "oidc": oidc}
print("QA_RESULT " + json.dumps(result))
"""

PEOPLE = """
import json, sys
from django.db import transaction
from suite_directory.models import DirectorySource, OrganizationMapping, ProvisionedUser, ProvisionedGroup, ExternalIdentity, Consumer
from core.models import Team
payload = json.load(sys.stdin)
with transaction.atomic():
    organization = OrganizationMapping.objects.get(suite_id=payload["fixture"]["organization_id"])
    source, _ = DirectorySource.objects.get_or_create(organization=organization, name="Authentik qualification")
    source.set_key(payload["scim"])
    source.save()
    for person in payload["fixture"]["principals"]:
        name = person["name"]
        record, created = ProvisionedUser.objects.get_or_create(principal_id=person["id"], defaults={"source": source, "external_id": payload["authentik"]["users"][name]["external_id"], "username": name})
        assert record.source_id == source.pk and record.external_id == payload["authentik"]["users"][name]["external_id"]
        for app, oidc in payload["authentik"]["oidc"].items():
            consumer = Consumer.objects.get(organization=organization, app_id=app)
            consumer.approved_issuers = sorted(set(consumer.approved_issuers + [oidc["issuer"]]))
            consumer.save(update_fields=["approved_issuers"])
            identity, _ = ExternalIdentity.objects.get_or_create(consumer=consumer, issuer=oidc["issuer"], subject=oidc["subjects"][name], defaults={"principal_id": person["id"]})
            assert str(identity.principal_id) == person["id"]
    existing = ProvisionedGroup.objects.filter(source=source, external_id=payload["authentik"]["group"]).select_related("team").first()
    team = existing.team if existing else Team.objects.get(name="Qualification editors", organization=organization.organization)
    group, _ = ProvisionedGroup.objects.get_or_create(team=team, defaults={"source": source, "external_id": payload["authentik"]["group"]})
    assert group.source_id == source.pk and group.external_id == payload["authentik"]["group"]
print("QA_RESULT " + json.dumps({"source": str(source.pk), "team": str(team.external_id), "mode": group.mode}))
"""

ACTIVATE = """
import json, sys
from authentik.core.models import User, Group
from authentik.providers.scim.models import SCIMProvider
payload = json.load(sys.stdin)
provider = SCIMProvider.objects.get(pk=payload["provider"])
SCIMProvider.objects.filter(pk=provider.pk).update(dry_run=False)
provider.refresh_from_db()
for name in payload["users"]:
    connection, _ = provider.client_for_model(User).write(User.objects.get(username=name))
    assert connection is not None
connection, _ = provider.client_for_model(Group).write(Group.objects.get(pk=payload["group"]))
assert connection is not None
print("QA_RESULT " + json.dumps({"users_written": len(payload["users"]), "group_written": True}))
"""


def configure(host):
    ipaddress.ip_address(host)
    secret_path = PRIVATE / "secrets.json"
    secret = json.loads(secret_path.read_text())
    secret.setdefault("scim", secrets.token_urlsafe(40))
    secret.setdefault("suite-imported", secrets.token_urlsafe(32))
    secret_path.write_text(json.dumps(secret, indent=2))
    qa = json.loads((ROOT / "data/suite-identity-qa/secrets.json").read_text())
    fixture = json.loads(
        (ROOT / "data/suite-identity-qa/fixture-private.json").read_text()
    )
    result = run(
        "suite-identity-authentik-qa-server-1",
        AUTHENTIK,
        {
            "base": f"http://{host}",
            "scim": secret["scim"],
            "passwords": {name: qa[name] for name in ("alice", "bob", "outsider")}
            | {"suite-imported": secret["suite-imported"]},
            "clients": {
                app: qa["oidc_" + app] for app in ("drive", "st", "people", "docs")
            },
        },
        "configure-authentik",
    )
    people = run(
        "suite-identity-qa-people-1",
        PEOPLE,
        {"scim": secret["scim"], "fixture": fixture, "authentik": result},
        "associate-people",
    )
    (PRIVATE / "fixture-private.json").write_text(
        json.dumps(result | {"people": people}, indent=2)
    )
    proof = run(
        "suite-identity-authentik-qa-server-1", ACTIVATE, result, "provision-people"
    )
    print(json.dumps(proof | {"existing_team_mode": people["mode"]}))


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    configure(parser.parse_args().host)
