"""Register the two LAN consumers without changing existing applications or users."""

import argparse
import json
from pathlib import Path
import subprocess
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from prepare_local import write_private
from prepare_mail import prepare


def shell(container, code, payload, diagnostic):
    result = subprocess.run(
        ["docker", "exec", "-i", container, "python", "manage.py", "shell", "-c", code],
        input=json.dumps(payload), text=True, capture_output=True,
    )
    write_private(diagnostic, result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("Provisioning failed; diagnostic retained privately")
    return json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith("RESULT ")))


PEOPLE = '''import json,sys,hashlib
from django.db import transaction
from core.models import ServiceProvider
from suite_directory.models import Consumer,OrganizationMapping
p=json.load(sys.stdin)
with transaction.atomic():
 mapping=OrganizationMapping.objects.get(suite_id=p['organization_id'])
 sp,_=ServiceProvider.objects.get_or_create(audience_id=p['client_id'],defaults={'name':'Suite — '+p['app']})
 mapping.organization.service_providers.add(sp)
 defaults={'service_provider':sp,'approved_issuers':[p['issuer']],
  'key_digest':hashlib.sha256(p['read_key'].encode()).hexdigest(),
  'logout_key_digest':hashlib.sha256(p['mutation_key'].encode()).hexdigest()}
 consumer,created=Consumer.objects.get_or_create(organization=mapping,app_id=p['app'],defaults=defaults)
 if not created and (any(getattr(consumer,k)!=v for k,v in defaults.items() if k!='approved_issuers')
                     or p['issuer'] not in consumer.approved_issuers):raise ValueError('Consumer conflict or unapproved issuer')
print('RESULT '+json.dumps({'created':created}))
'''

ST = '''import json,sys,uuid
from django.db import transaction
from core.models import Service,ServiceSubscription,SuiteAccessPolicy,SuiteAccessRule
from suite_identity.models import GroupMapping
p=json.load(sys.stdin);org=p['organization_id']
with transaction.atomic():
 baseline=ServiceSubscription.objects.get(organization_id=org,service__config__suite_app_id='drive')
 service=Service.objects.filter(config__suite_app_id=p['app']).first()
 if service is None:
  service=Service.objects.create(type=p['app'],name=p['app'].title(),instance_name='Suite locale',url=p['origin'],is_active=True,hidden=True,
   config={'suite_app_id':p['app'],'allowed_organization_ids':[org],'entitlements_api_key':p['policy_key']})
 if service.config['entitlements_api_key']!=p['policy_key']:raise ValueError('Policy credential conflict')
 subscription,_=ServiceSubscription.objects.get_or_create(service=service,organization_id=org,defaults={'operator':baseline.operator,'is_active':True})
 policy,created=SuiteAccessPolicy.objects.get_or_create(subscription=subscription,defaults={'allow_all':False})
 if created:
  group=GroupMapping.objects.get(pk=uuid.uuid5(uuid.UUID(org),'suite-members'),organization_id=org)
  SuiteAccessRule.objects.create(policy=policy,group=group,allow=True)
print('RESULT '+json.dumps({'policy_service_id':str(service.pk)}))
'''

CALENDARS = '''import json,sys
from core.models import Organization,Channel,uuid_to_urlsafe
p=json.load(sys.stdin)
org,created=Organization.objects.get_or_create(pk=p['organization_id'],defaults={
 'external_id':p['organization_id'],'name':'Apoze','default_sharing_level':'none'})
if org.external_id!=p['organization_id']:raise ValueError('Organization conflict')
c,_=Channel.objects.get_or_create(name='Suite Messages — calendar actions',type='caldav',scope_level='global',defaults={
 'organization':org,'settings':{'suite_peer':'messages','scopes':['calendars:read','events:read','events:write']},
 'encrypted_settings':{'token':p['calendar_messages_token']}})
if c.organization_id!=org.pk or not c.verify_token(p['calendar_messages_token']):raise ValueError('Calendar channel conflict')
print('RESULT '+json.dumps({'calendar_messages_credentials':uuid_to_urlsafe(c.pk)+p['calendar_messages_token']}))
'''

ADMINISTRATION = '''import json,sys,uuid
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Permission
from suite_identity.models import GroupMapping
p=json.load(sys.stdin)
User=get_user_model()
user,created=User.objects.get_or_create(sub='suite-recovery-'+p['app'],defaults={
 'admin_email':'suite-recovery@'+p['app']+'.invalid','is_staff':True,'is_superuser':True,
 'password':make_password(p['recovery_password']),
 **({'organization_id':p['organization_id']} if p['app']=='calendars' else {})})
if created:
 user.set_password(p['recovery_password']);user.save()
if p['app']=='calendars':
 group=GroupMapping.objects.get(group_id=uuid.uuid5(uuid.UUID(p['organization_id']),'suite-administrators'),active=True)
 group.local_group.permissions.add(Permission.objects.get(content_type__app_label='core',codename='change_organization'))
print('RESULT '+json.dumps({'recovery_created':created,'native_admin_configured':True}))
'''

MESSAGES = '''import json,sys,hashlib
from core.models import Channel,MailDomain
from django.core.files.storage import storages
from botocore.exceptions import ClientError
p=json.load(sys.stdin)
domain,_=MailDomain.objects.get_or_create(name=p['mail_domain'],defaults={'oidc_autojoin':False,'identity_sync':False})
if domain.custom_attributes.get('suite_organization_id')!=p['organization_id']:raise ValueError('Mail domain conflict')
digest=hashlib.sha256(p['messages_calendar_key'].encode()).hexdigest()
c,_=Channel.objects.get_or_create(name='Suite Calendars — mailbox directory',type='api_key',scope_level='global',defaults={
 'settings':{'scopes':['mailboxes:read','messages:send'],'suite_organization_id':p['organization_id']},
 'encrypted_settings':{'api_key_hashes':[digest]}})
if c.settings.get('suite_organization_id')!=p['organization_id'] or digest not in c.encrypted_settings.get('api_key_hashes',[]):raise ValueError('Channel conflict')
c.settings['scopes']=['mailboxes:read','messages:send']
c.save(update_fields=['settings'])
for name in ('message-imports','message-blobs'):
 storage=storages[name];client=storage.connection.meta.client
 try:client.head_bucket(Bucket=storage.bucket_name)
 except ClientError as exc:
  if exc.response['ResponseMetadata']['HTTPStatusCode']!=404:raise
  client.create_bucket(Bucket=storage.bucket_name)
from core.suite.storage import synchronize_storage
synchronize_storage()
print('RESULT '+json.dumps({'messages_calendar_channel_id':str(c.pk)}))
'''


def provision_databases(config, state):
    """Create only missing dedicated databases/roles; never rotate another role."""
    container = "suite-local-suite-postgres-1"
    runtime = json.loads(subprocess.check_output(["docker", "inspect", container]))[0]
    env = dict(item.split("=", 1) for item in runtime["Config"]["Env"] if "=" in item)
    for app in ("messages", "calendars", "caldav"):
        password = (config["caldav_db_password"] if app == "caldav" else config["apps"][app]["db_password"])
        escaped = password.replace("'", "''")
        sql = (
            f"SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', '{app}', '{escaped}') "
            f"WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{app}')\\gexec\n"
            f"SELECT format('CREATE DATABASE %I OWNER %I', '{app}', '{app}') "
            f"WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{app}')\\gexec\n"
        )
        result = subprocess.run(["docker", "exec", "-i", container, "psql", "-Xq",
                                 "-v", "ON_ERROR_STOP=1", "-U", env.get("POSTGRES_USER", "postgres"),
                                 "-d", "postgres"], input=sql, text=True, capture_output=True)
        write_private(state / f"{app}-database.log", result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("Database provisioning failed; private diagnostic retained")


def register_current_keycloak(config):
    """Deployment adapter only; application authentication remains generic OIDC."""
    runtime = json.loads(subprocess.check_output(["docker", "inspect", "drive-keycloak-1"]))[0]
    env = dict(value.split("=", 1) for value in runtime["Config"]["Env"] if "=" in value)
    issuer = urlsplit(config["issuer"])
    base = f"{issuer.scheme}://{issuer.netloc}"
    realm = issuer.path.rsplit("/", 1)[-1]
    body = urlencode({"client_id": "admin-cli", "grant_type": "password",
                      "username": env["KEYCLOAK_ADMIN"], "password": env["KEYCLOAK_ADMIN_PASSWORD"]}).encode()
    with urlopen(Request(base + "/realms/master/protocol/openid-connect/token", data=body), timeout=10) as r:
        token = json.load(r)["access_token"]

    def api(path, data=None):
        request = Request(base + "/admin/realms/" + realm + path,
                          data=json.dumps(data).encode() if data is not None else None,
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read() or "null")

    for app, values in config["apps"].items():
        matches = api("/clients?" + urlencode({"clientId": values["client_id"]}))
        if matches:
            client = matches[0]
            if client.get("attributes", {}).get("apoze.suite") != "messages-calendars":
                raise ValueError("Existing client is not owned by this deployment")
            if api("/clients/" + client["id"] + "/client-secret")["value"] != values["client_secret"]:
                raise ValueError("OIDC credential conflict")
            continue
        origin = f"http://{config['host']}:{values['port']}"
        api("/clients", {"clientId": values["client_id"], "name": "Apoze " + app.title(),
             "secret": values["client_secret"], "protocol": "openid-connect", "publicClient": False,
             "enabled": True, "standardFlowEnabled": True, "directAccessGrantsEnabled": False,
             "serviceAccountsEnabled": False, "redirectUris": [origin + "/api/v1.0/callback/"],
             "webOrigins": [origin], "defaultClientScopes": ["basic", "web-origins", "acr", "profile", "email"],
             "attributes": {"apoze.suite": "messages-calendars", "pkce.code.challenge.method": "S256",
                            "post.logout.redirect.uris": origin + "/api/v1.0/logout-callback/"}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--suite-settings", type=Path, required=True)
    parser.add_argument("--repos", type=Path, default=Path("/root/Apoze"))
    parser.add_argument("--register-current-keycloak", action="store_true")
    parser.add_argument("--databases-only", action="store_true")
    parser.add_argument("--bootstrap-apps", action="store_true")
    args = parser.parse_args()
    config = prepare(args.state, args.suite_settings, args.repos)
    if args.databases_only:
        provision_databases(config, args.state)
        print("Dedicated database roles and databases ready.")
        return
    for app, values in config["apps"].items():
        payload = {key: config[key] for key in ("host", "issuer", "organization_id")} | values | {
            "app": app, "origin": f"http://{config['host']}:{values['port']}"}
        shell("suite-local-people-1", PEOPLE, payload, args.state / f"{app}-people.log")
        values.update(shell("st-deploycenter-backend-dev-1", ST, payload, args.state / f"{app}-st.log"))
        write_private(args.state / "settings.json", json.dumps(config, indent=2))
    if args.register_current_keycloak:
        register_current_keycloak(config)
    if args.bootstrap_apps:
        config.update(shell("suite-mail-calendars-1", CALENDARS, config, args.state / "organization-bootstrap.log"))
        config.update(shell("suite-mail-messages-1", MESSAGES, config, args.state / "mail-bootstrap.log"))
        for app, values in config['apps'].items():
            shell('suite-mail-'+app+'-1', ADMINISTRATION,
                  {'app': app, 'organization_id': config['organization_id'],
                   'recovery_password': values['recovery_password']},
                  args.state / (app+'-administration.log'))
        write_private(args.state / "settings.json", json.dumps(config, indent=2))
    prepare(args.state, args.suite_settings, args.repos)
    print("Consumers registered, catalogue entries hidden pending qualification; existing identities unchanged.")


if __name__ == "__main__":
    main()
