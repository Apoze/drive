"""Register Chat as a closed suite consumer and provision its dedicated databases."""

import argparse
import json
from pathlib import Path

from prepare_chat import prepare
from prepare_local import write_private
from provision_mail_local import PEOPLE, provision_databases, register_current_keycloak, shell
from provision_transfers_local import ST


def provision(state, suite, repos, *, server_name, qa=False, keycloak_adapter=False):
    config = prepare(state, suite, repos, server_name=server_name, qa=qa)
    shell('suite-local-people-1', PEOPLE, config | {'app': 'chat'}, state / 'people-registration.log')
    config.update(shell('st-deploycenter-backend-dev-1', ST, config | {'app': 'chat'}, state / 'st-registration.log'))
    write_private(state / 'settings.json', json.dumps(config, indent=2) + '\n')
    databases = {'apps': {config['db_name']: {'db_password': config['db_password'], 'database_locale': 'C'}, config['mas_db_name']: {'db_password': config['mas_db_password']}}}
    provision_databases(databases, state, apps=tuple(databases['apps']))
    if keycloak_adapter:
        register_current_keycloak(config | {'apps': {'chat': config | {'origin': config['auth_origin']}}}, deployment='chat-qa' if qa else 'chat', callback='/upstream/callback/' + config['provider_id'], logout_callback='/')
    return prepare(state, suite, repos, server_name=server_name, qa=qa)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path('data/chat-local'))
    parser.add_argument('--suite', type=Path, default=Path('data/suite-local/settings.json'))
    parser.add_argument('--repos', type=Path, default=Path('..'))
    parser.add_argument('--server-name', required=True)
    parser.add_argument('--qa', action='store_true')
    parser.add_argument('--register-current-keycloak', action='store_true')
    args = parser.parse_args()
    provision(args.state, args.suite, args.repos, server_name=args.server_name, qa=args.qa, keycloak_adapter=args.register_current_keycloak)
    print('Chat registered closed; no durable QA identity should be retained.')
