#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export ENV_OVERRIDE="${ENV_OVERRIDE:-local}"
export DOCKER_USER="${DOCKER_USER:-$(id -u):$(id -g)}"
export QA_ONLYOFFICE_CONVERT_JWT_SECRET="${QA_ONLYOFFICE_CONVERT_JWT_SECRET:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')}"

echo "[qa-lan-conversion] restoring LAN QA base stack"
make qa-lan-ready

echo "[qa-lan-conversion] enabling dev-only OnlyOffice conversion override"
echo "[qa-lan-conversion] generated local JWT secret is not printed"
docker compose \
  -f compose.yaml \
  -f docker/compose.qa-conversion.yaml \
  up -d --force-recreate \
  onlyoffice \
  app-dev \
  nginx \
  celery-dev \
  celery-beat-dev \
  frontend-dev

bin/qa_lan_conversion_preflight.py
