#!/usr/bin/env bash
set -euo pipefail

template_path="/etc/onlyoffice/documentserver/local-production-linux.json.tmpl"
target_path="/etc/onlyoffice/documentserver/local-production-linux.json"

python3 - "$template_path" "$target_path" <<'PY'
import json
import os
import sys

template_path = sys.argv[1]
target_path = sys.argv[2]

with open(template_path, encoding="utf-8") as f:
    config = json.load(f)

wopi = config.setdefault("wopi", {})
wopi["host"] = os.environ.get("ONLYOFFICE_WOPI_HOST", "http://localhost:9981")

with open(target_path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=4)
    f.write("\n")
PY

log4js_override="/etc/onlyoffice/documentserver/log4js/production.json.override"
log4js_target="/etc/onlyoffice/documentserver/log4js/production.json"
if [ -f "$log4js_override" ]; then
  cp -f "$log4js_override" "$log4js_target"
fi

exec /app/ds/run-document-server.sh
