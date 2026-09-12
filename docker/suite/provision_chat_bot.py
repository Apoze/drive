"""Provision one visible Projects bot using People, ST and native MAS sessions."""

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
from uuid import uuid4

from prepare_local import write_private
from provision_mail_local import shell


PEOPLE = '''import json,sys
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from suite_directory.models import OrganizationMapping,Principal,ExternalIdentity
p=json.load(sys.stdin)
with transaction.atomic():
 org=OrganizationMapping.objects.get(suite_id=p['organization_id'])
 user,created=get_user_model().objects.get_or_create(pk=p['principal_id'],defaults={
  'sub':'technical-'+p['principal_id'],'password':make_password(None),'name':'Projects — bot de notifications',
  'is_device':True,'organization':org.organization})
 if not user.is_device or user.organization_id!=org.organization_id:raise ValueError('Technical identity collision')
 if created:user.set_unusable_password();user.save()
 principal,_=Principal.objects.get_or_create(user=user,defaults={'organization':org})
 if principal.organization_id!=org.pk or ExternalIdentity.objects.filter(principal=principal).exists():raise ValueError('Bot must not have an external login')
print('RESULT {}')
'''

ST = '''import json,sys
from core.models import SuiteAccessPolicy,SuiteAccessRule
from suite_identity.directory import synchronize
p=json.load(sys.stdin)
synchronize()
policy=SuiteAccessPolicy.objects.get(subscription__service_id=p['policy_service_id'],subscription__organization_id=p['organization_id'])
rule,created=SuiteAccessRule.objects.get_or_create(policy=policy,principal_id=p['principal_id'],defaults={'allow':True})
if not rule.allow:raise ValueError('Bot access was revoked; restore explicitly in ST')
print('RESULT {}')
'''

MAS = '''import json,sys
from pathlib import Path
from synapse.apoze_suite.directory import Directory
from synapse.apoze_suite.mas import Accounts
p=json.load(sys.stdin)
config=json.loads(Path('/data/homeserver.yaml').read_text())['modules'][0]['config']
accounts=Accounts(Directory(config));accounts.login()
if p.get('session_id'):
 result=accounts.request('/api/admin/v1/personal-sessions/'+p['session_id']+'/regenerate',{'expires_in':2592000})
else:
 username='p'+p['principal_id'].replace('-','')
 user=accounts.request('/api/admin/v1/users/by-username/'+username,optional=True)
 if user is None:user=accounts.request('/api/admin/v1/users',{'username':username,'displayname':'Projects — bot de notifications'})
 result=accounts.request('/api/admin/v1/personal-sessions',{'actor_user_id':user['data']['id'],
  'human_name':'Projects notifications — explicit rooms only',
  'scope':'urn:matrix:client:api:* urn:matrix:client:device:'+p['device_id'],'expires_in':2592000})
sys.stdout.write(json.dumps(result))
'''


def provision(state, renew=False):
    os.umask(0o077)
    state = state.resolve()
    path = state / 'settings.json'
    config = json.loads(path.read_text())
    bot = config.get('projects_bot')
    if bot is None:
        if renew:
            raise ValueError('Provision the bot before rotating its credential')
        bot = {'principal_id': str(uuid4()), 'device_id': 'APOZE_PROJECTS_BOT',
               'room_key': secrets.token_urlsafe(40), 'projects_key': secrets.token_urlsafe(40),
               'store_key': secrets.token_urlsafe(40)}
        config['projects_bot'] = bot
        write_private(path, json.dumps(config, indent=2) + '\n')
    if 'control_key' not in bot:
        bot['control_key'] = secrets.token_urlsafe(40)
        write_private(path, json.dumps(config, indent=2) + '\n')
    shell('suite-local-people-1', PEOPLE, config | bot, state / 'bot-people.log')
    shell('st-deploycenter-backend-dev-1', ST, config | bot, state / 'bot-st.log')
    directory = state / 'bot'
    directory.mkdir(mode=0o700, exist_ok=True)
    os.chown(directory, 991, 991)
    session_file = directory / 'session.json'
    expected_user = '@p' + bot['principal_id'].replace('-', '') + ':' + config['server_name']
    if session_file.exists():
        previous = json.loads(session_file.read_text())
        if previous.get('user_id') != expected_user or previous.get('device_id') != bot['device_id']:
            raise ValueError('Bot identity differs; never overwrite an existing crypto identity')
    if not session_file.exists() or renew:
        name = 'suite-chat-qa-synapse-1' if config['qa'] else 'suite-chat-synapse-1'
        result = subprocess.run(['docker', 'exec', '-i', name, 'python', '-c', MAS],
                                input=json.dumps(bot), capture_output=True, text=True)
        if result.returncode:
            write_private(state / 'bot-mas-error.log', result.stderr)
            raise RuntimeError('Bot MAS provisioning failed; inspect private diagnostic')
        data = json.loads(result.stdout)['data']
        # Native MAS JSON:API response; no token ever enters stdout or argv.
        attributes = data['attributes']
        session = {'user_id': '@p' + bot['principal_id'].replace('-', '') + ':' + config['server_name'],
                   'device_id': bot['device_id'], 'access_token': attributes['access_token'], 'refresh_token': None}
        write_private(session_file, json.dumps(session) + '\n', uid=991)
        bot['session_id'] = data['id']
        write_private(path, json.dumps(config, indent=2) + '\n')
    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path('data/chat-local'))
    parser.add_argument('--renew', action='store_true')
    args = parser.parse_args()
    provision(args.state, args.renew)
    print('Bot identity prepared privately; regenerate Chat/Projects configuration before starting it.')
