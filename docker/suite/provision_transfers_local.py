"""Register Transfers closed by default, using the existing suite infrastructure."""

import argparse
import json
from pathlib import Path

from prepare_local import write_private
from prepare_transfers import prepare
from provision_mail_local import PEOPLE, provision_databases, register_current_keycloak, shell
from provision_projects_local import provision_storage

ST = '''import json,sys
from django.db import transaction
from core.models import Service,ServiceSubscription,SuiteAccessPolicy,Entitlement,OperatorServiceConfig
p=json.load(sys.stdin);org=p['organization_id'];app=p['app']
if app not in ('transfers','chat'):raise ValueError('Unsupported media service')
with transaction.atomic():
 baseline=ServiceSubscription.objects.get(organization_id=org,service__config__suite_app_id='drive')
 service=Service.objects.filter(config__suite_app_id=app).first()
 if service is None:
  service=Service.objects.create(type=app,name=app.title(),instance_name='Suite locale',url=p['origin'],is_active=True,hidden=True,
   config={'suite_app_id':app,'allowed_organization_ids':[org],'entitlements_api_key':p['policy_key']})
 if service.config['entitlements_api_key']!=p['policy_key']:raise ValueError('Transfers credential conflict')
 subscription,_=ServiceSubscription.objects.get_or_create(service=service,organization_id=org,defaults={'operator':baseline.operator,'is_active':True})
 OperatorServiceConfig.objects.get_or_create(service=service,operator=subscription.operator)
 SuiteAccessPolicy.objects.get_or_create(subscription=subscription,defaults={'allow_all':False})
 for scope in ('organization','user'):
  Entitlement.objects.get_or_create(service_subscription=subscription,type=app+'_storage',account_type=scope,account=None,defaults={'config':{'max_storage':20_000_000_000}})
print('RESULT '+json.dumps({'policy_service_id':str(service.pk),'operator_id':str(subscription.operator_id)}))
'''


def provision(state, suite, repo, *, keycloak_adapter=False):
    config = prepare(state, suite, repo)
    shell('suite-local-people-1', PEOPLE, config | {'app': 'transfers'}, state / 'people-registration.log')
    config.update(shell('st-deploycenter-backend-dev-1', ST, config | {'app': 'transfers'}, state / 'st-registration.log'))
    write_private(state / 'settings.json', json.dumps(config, indent=2) + '\n')
    provision_storage(config, suite, state, app='transfers')
    registration = config | {'apps': {'transfers': config}}
    provision_databases(registration, state, apps=('transfers',))
    if keycloak_adapter:
        register_current_keycloak(registration, deployment='transfers')
    prepare(state, suite, repo)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path('data/transfers-local'))
    parser.add_argument('--suite', type=Path, default=Path('data/suite-local/settings.json'))
    parser.add_argument('--repo', type=Path, default=Path('../transfers'))
    parser.add_argument('--register-current-keycloak', action='store_true')
    args = parser.parse_args()
    provision(args.state, args.suite, args.repo, keycloak_adapter=args.register_current_keycloak)
    print('Transfers registered; access closed and catalogue hidden pending qualification.')
