# Local Network Development Setup

This guide documents the Apoze Drive LAN development mode. Use it when the app
must be reachable from another device on the same local network, such as a
phone or tablet.

The supported LAN mode is:

```bash
ENV_OVERRIDE=local
```

## Expected LAN Origins

The current checked-in contract uses the host IP `192.168.10.123`:

- UI: `http://192.168.10.123:3000`
- API: `http://192.168.10.123:8071`
- Edge: `http://192.168.10.123:8083`
- S3 gateway: `http://192.168.10.123:9000`

If your workstation has a different LAN IP, mirror the same ports with that
address in your gitignored local override file.

## Local Override File

Create or update `env.d/development/common.local`. This file is gitignored and
must stay local. Do not commit local secrets or private endpoints.

The LAN file should provide the browser-facing URLs:

```env
AWS_S3_DOMAIN_REPLACE=http://192.168.10.123:9000
MEDIA_BASE_URL=http://192.168.10.123:8083
OIDC_OP_AUTHORIZATION_ENDPOINT=http://192.168.10.123:8083/realms/drive/protocol/openid-connect/auth
OIDC_OP_URL=http://192.168.10.123:8083/realms/drive
LOGIN_REDIRECT_URL=http://192.168.10.123:3000
LOGIN_REDIRECT_URL_FAILURE=http://192.168.10.123:3000
LOGOUT_REDIRECT_URL=http://192.168.10.123:3000
OIDC_REDIRECT_ALLOWED_HOSTS="localhost:8083,localhost:3000,192.168.10.123:8083,192.168.10.123:3000"
CSRF_TRUSTED_ORIGINS=http://192.168.10.123:3000,http://192.168.10.123:8071,http://192.168.10.123:8083
```

Keep OIDC token, userinfo, JWKS, logout, and introspection endpoints on the
Compose network if they are only called server-side. The browser-facing
authorization endpoint and redirect URLs must use the LAN origin.

## Start The Stack

Start or restart the development stack with the LAN override selected:

```bash
ENV_OVERRIDE=local docker compose up -d
```

When switching between environment overrides, check that the expected Postgres
data directory and local env files exist for the selected mode.

## Browser And Device Check

From a device on the same network, open:

```text
http://192.168.10.123:3000
```

Then verify:

1. The login flow completes without an invalid redirect URI.
2. Browser redirects do not point back to localhost.
3. A small upload uses `http://192.168.10.123:9000`.
4. API item URLs use `http://192.168.10.123:8083`.

## Troubleshooting

If login fails, confirm that `OIDC_REDIRECT_ALLOWED_HOSTS` contains the LAN UI
and Edge origins. If unsafe-origin errors appear on API requests, confirm that
`CSRF_TRUSTED_ORIGINS` includes the LAN UI, API, and Edge origins with the
`http://` scheme.

If uploads fail from another device, confirm that `AWS_S3_DOMAIN_REPLACE`
points to the LAN S3 gateway and not to a loopback address.

See `docs/env_freeze_report.md` for the full LAN vs E2E environment contract.
