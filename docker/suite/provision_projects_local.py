"""Register only Projects; keep catalogue hidden and initial access denied."""

import argparse
import json
import subprocess
from pathlib import Path

from prepare_local import write_private, write_storage_config
from prepare_projects import prepare
from provision_mail_local import PEOPLE, provision_databases, register_current_keycloak, shell

ST = '''import json,sys
from django.db import transaction
from core.models import Service,ServiceSubscription,SuiteAccessPolicy,Entitlement
p=json.load(sys.stdin);org=p['organization_id']
with transaction.atomic():
 baseline=ServiceSubscription.objects.get(organization_id=org,service__config__suite_app_id='drive')
 service=Service.objects.filter(config__suite_app_id='projects').first()
 if service is None:
  service=Service.objects.create(type='projects',name='Projects',instance_name='Suite locale',url=p['origin'],is_active=True,hidden=True,
   config={'suite_app_id':'projects','allowed_organization_ids':[org],'entitlements_api_key':p['policy_key']})
 if service.config['entitlements_api_key']!=p['policy_key']:raise ValueError('Projects credential conflict')
 subscription,_=ServiceSubscription.objects.get_or_create(service=service,organization_id=org,defaults={'operator':baseline.operator,'is_active':True})
 for scope in ('organization','user'):
  Entitlement.objects.get_or_create(service_subscription=subscription,type='projects_storage',account_type=scope,account=None,defaults={'config':{'max_storage':20_000_000_000}})
 SuiteAccessPolicy.objects.get_or_create(subscription=subscription,defaults={'allow_all':False})
print('RESULT '+json.dumps({'policy_service_id':str(service.pk),'operator_id':str(subscription.operator_id)}))
'''


def provision_storage(config, suite, state):
    installation = json.loads(suite.read_text())
    consumers = installation.setdefault('storage_consumers', {})
    identity = {'bucket': config['bucket'], 'access_key': config['s3_access'], 'secret_key': config['s3_secret']}
    if 'projects' in consumers and consumers['projects'] != identity:
        raise ValueError('Existing Projects storage credential conflict')
    consumers['projects'] = identity
    write_private(suite, json.dumps(installation, indent=2) + '\n')
    write_storage_config(suite.parent, installation)
    subprocess.run(['docker', 'kill', '--signal=HUP', 'suite-local-docs-s3-1'], check=True, stdout=subprocess.DEVNULL)
    script = """import json,sys,boto3
from botocore.exceptions import ClientError
p=json.load(sys.stdin)
s3=boto3.client('s3',endpoint_url=p['endpoint'],aws_access_key_id=p['access_key'],aws_secret_access_key=p['secret_key'],region_name='us-east-1')
try:s3.head_bucket(Bucket=p['bucket'])
except ClientError as e:
 if e.response['Error']['Code'] not in ('404','NoSuchBucket'):raise
 s3.create_bucket(Bucket=p['bucket'])
print('RESULT '+json.dumps({'bucket_ready':True}))
"""
    shell('suite-local-docs-1', script, installation['s3_admin'] | {'endpoint': installation['s3']['endpoint'], 'bucket': config['bucket']}, state / 'storage-registration.log')


def provision(state, suite, repo, *, keycloak_adapter=False):
    config = prepare(state, suite, repo)
    payload = config | {'app': 'projects', 'origin': f"http://{config['host']}:{config['port']}"}
    shell('suite-local-people-1', PEOPLE, payload, state / 'people-registration.log')
    config.update(shell('st-deploycenter-backend-dev-1', ST, payload, state / 'st-registration.log'))
    write_private(state / 'settings.json', json.dumps(config, indent=2) + '\n')
    provision_storage(config, suite, state)
    registration = config | {'apps': {'projects': config}}
    provision_databases(registration, state, apps=('projects',))
    if keycloak_adapter:
        register_current_keycloak(registration, deployment='projects', callback='/oidc-callback', logout_callback='/login')
    prepare(state, suite, repo)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path('data/projects-local'))
    parser.add_argument('--suite', type=Path, default=Path('data/suite-local/settings.json'))
    parser.add_argument('--repo', type=Path, default=Path('../projects'))
    parser.add_argument('--register-current-keycloak', action='store_true')
    args = parser.parse_args()
    provision(args.state, args.suite, args.repo, keycloak_adapter=args.register_current_keycloak)
    print('Projects DB and consumers registered; catalogue hidden; initial access denied.')
