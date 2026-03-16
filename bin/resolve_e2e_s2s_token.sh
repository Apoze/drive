#!/usr/bin/env bash
set -euo pipefail

canonical_token="${DRIVE_E2E_S2S_TOKEN:-}"
backend_token="${DJANGO_SERVER_TO_SERVER_API_TOKENS:-}"
runner_token="${E2E_S2S_TOKEN:-}"

canonical_help() {
  cat >&2 <<'EOF'
[e2e] Missing server-to-server token contract.
[e2e] Export DRIVE_E2E_S2S_TOKEN for local E2E commands.
[e2e] Temporary compatibility: if you still rely on legacy names, export both
[e2e] DJANGO_SERVER_TO_SERVER_API_TOKENS and E2E_S2S_TOKEN with the same value.
EOF
}

legacy_help() {
  cat >&2 <<'EOF'
[e2e] Legacy server-to-server token state is invalid.
[e2e] Export DRIVE_E2E_S2S_TOKEN instead.
[e2e] Temporary compatibility only accepts both legacy variables present and equal:
[e2e] DJANGO_SERVER_TO_SERVER_API_TOKENS == E2E_S2S_TOKEN
EOF
}

if [ -n "$canonical_token" ]; then
  if [ -n "$backend_token" ] && [ "$backend_token" != "$canonical_token" ]; then
    echo "[e2e] DRIVE_E2E_S2S_TOKEN and DJANGO_SERVER_TO_SERVER_API_TOKENS disagree." >&2
    legacy_help
    exit 1
  fi
  if [ -n "$runner_token" ] && [ "$runner_token" != "$canonical_token" ]; then
    echo "[e2e] DRIVE_E2E_S2S_TOKEN and E2E_S2S_TOKEN disagree." >&2
    legacy_help
    exit 1
  fi
  printf '%s\n' "$canonical_token"
  exit 0
fi

if [ -z "$backend_token" ] && [ -z "$runner_token" ]; then
  canonical_help
  exit 1
fi

if [ -z "$backend_token" ] || [ -z "$runner_token" ]; then
  echo "[e2e] Only one legacy server-to-server token variable is set." >&2
  legacy_help
  exit 1
fi

if [ "$backend_token" != "$runner_token" ]; then
  echo "[e2e] Legacy server-to-server token variables disagree." >&2
  legacy_help
  exit 1
fi

printf '%s\n' "$backend_token"
