# /!\ /!\ /!\ /!\ /!\ /!\ /!\ DISCLAIMER /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\
#
# This Makefile is only meant to be used for DEVELOPMENT purpose as we are
# changing the user id that will run in the container.
#
# PLEASE DO NOT USE IT FOR YOUR CI/PRODUCTION/WHATEVER...
#
# /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\
#
# Note to developers:
#
# While editing this file, please respect the following statements:
#
# 1. Every variable should be defined in the ad hoc VARIABLES section with a
#    relevant subsection
# 2. Every new rule should be defined in the ad hoc RULES section with a
#    relevant subsection depending on the targeted service
# 3. Rules should be sorted alphabetically within their section
# 4. When a rule has multiple dependencies, you should:
#    - duplicate the rule name to add the help string (if required)
#    - write one dependency per line to increase readability and diffs
# 5. .PHONY rule statement should be written after the corresponding rule
# ==============================================================================
# VARIABLES

BOLD := \033[1m
RESET := \033[0m
GREEN := \033[1;32m


# -- Database

DB_HOST                 = postgresql
DB_PORT                 = 5432

# -- Docker
# Get the current user ID to use for docker run and docker exec commands
DOCKER_UID              = $(shell id -u)
DOCKER_GID              = $(shell id -g)
DOCKER_USER             = $(DOCKER_UID):$(DOCKER_GID)
DATA_ENV_SUFFIX         = $(if $(strip $(ENV_OVERRIDE)),$(strip $(ENV_OVERRIDE)),local)
E2E_RUN_TOKEN           = $(subst /,-,$(subst .,-,$(strip $(E2E_RUN_ID))))
COMPOSE_PROJECT_NAME_EFFECTIVE ?= $(if $(E2E_RUN_TOKEN),drive-e2e-$(E2E_RUN_TOKEN),)
LASUITE_NETWORK_NAME    ?= $(if $(E2E_RUN_TOKEN),lasuite-network-$(E2E_RUN_TOKEN),lasuite-network)
POSTGRESQL_DATA_DIR     ?= $(if $(E2E_RUN_TOKEN),./data/e2e/$(E2E_RUN_TOKEN)/postgresql,./data/postgresql.$(DATA_ENV_SUFFIX))
SEAWEED_MASTER_DATA_DIR ?= $(if $(E2E_RUN_TOKEN),./data/e2e/$(E2E_RUN_TOKEN)/seaweedfs/master,./data/seaweedfs/master)
SEAWEED_VOLUME_DATA_DIR ?= $(if $(E2E_RUN_TOKEN),./data/e2e/$(E2E_RUN_TOKEN)/seaweedfs/volume,./data/seaweedfs/volume)
SEAWEED_FILER_DATA_DIR  ?= $(if $(E2E_RUN_TOKEN),./data/e2e/$(E2E_RUN_TOKEN)/seaweedfs/filer,./data/seaweedfs/filer)
STATIC_DATA_DIR         ?= $(if $(E2E_RUN_TOKEN),./data/e2e/$(E2E_RUN_TOKEN)/static,./data/static)
POSTGRESQL_PORT         ?= $(if $(strip $(E2E_PORT_OFFSET)),$(shell expr 6434 + $(E2E_PORT_OFFSET)),6434)
REDIS_PORT              ?= $(if $(strip $(E2E_PORT_OFFSET)),$(shell expr 6379 + $(E2E_PORT_OFFSET)),6379)
MAILCATCHER_PORT        ?= $(if $(strip $(E2E_PORT_OFFSET)),$(shell expr 1081 + $(E2E_PORT_OFFSET)),1081)
SEAWEED_S3_PORT         ?= $(if $(strip $(E2E_PORT_OFFSET)),$(shell expr 9000 + $(E2E_PORT_OFFSET)),9000)
APP_DEV_PORT            ?= $(if $(strip $(E2E_PORT_OFFSET)),$(shell expr 8071 + $(E2E_PORT_OFFSET)),8071)
NGINX_PORT              ?= $(if $(strip $(E2E_PORT_OFFSET)),$(shell expr 8083 + $(E2E_PORT_OFFSET)),8083)
FRONTEND_DEV_PORT       ?= $(if $(strip $(E2E_PORT_OFFSET)),$(shell expr 3000 + $(E2E_PORT_OFFSET)),3000)
KC_POSTGRESQL_PORT      ?= $(if $(strip $(E2E_PORT_OFFSET)),$(shell expr 6433 + $(E2E_PORT_OFFSET)),6433)
KEYCLOAK_PORT           ?= $(if $(strip $(E2E_PORT_OFFSET)),$(shell expr 8080 + $(E2E_PORT_OFFSET)),8080)
COLLABORA_PORT          ?= $(if $(strip $(E2E_PORT_OFFSET)),$(shell expr 9980 + $(E2E_PORT_OFFSET)),9980)
ONLYOFFICE_PORT         ?= $(if $(strip $(E2E_PORT_OFFSET)),$(shell expr 9981 + $(E2E_PORT_OFFSET)),9981)
COMPOSE_ENV             = DOCKER_USER=$(DOCKER_USER) \
                          LASUITE_NETWORK_NAME=$(LASUITE_NETWORK_NAME) \
                          POSTGRESQL_DATA_DIR=$(POSTGRESQL_DATA_DIR) \
                          SEAWEED_MASTER_DATA_DIR=$(SEAWEED_MASTER_DATA_DIR) \
                          SEAWEED_VOLUME_DATA_DIR=$(SEAWEED_VOLUME_DATA_DIR) \
                          SEAWEED_FILER_DATA_DIR=$(SEAWEED_FILER_DATA_DIR) \
                          STATIC_DATA_DIR=$(STATIC_DATA_DIR) \
                          POSTGRESQL_PORT=$(POSTGRESQL_PORT) \
                          REDIS_PORT=$(REDIS_PORT) \
                          MAILCATCHER_PORT=$(MAILCATCHER_PORT) \
                          SEAWEED_S3_PORT=$(SEAWEED_S3_PORT) \
                          APP_DEV_PORT=$(APP_DEV_PORT) \
                          NGINX_PORT=$(NGINX_PORT) \
                          FRONTEND_DEV_PORT=$(FRONTEND_DEV_PORT) \
                          KC_POSTGRESQL_PORT=$(KC_POSTGRESQL_PORT) \
                          KEYCLOAK_PORT=$(KEYCLOAK_PORT) \
                          COLLABORA_PORT=$(COLLABORA_PORT) \
                          ONLYOFFICE_PORT=$(ONLYOFFICE_PORT)
ifneq ($(strip $(COMPOSE_PROJECT_NAME_EFFECTIVE)),)
COMPOSE_ENV             += COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME_EFFECTIVE)
endif
COMPOSE                 = $(COMPOSE_ENV) docker compose
COMPOSE_EXEC            = $(COMPOSE) exec
COMPOSE_EXEC_APP        = $(COMPOSE_EXEC) app-dev
COMPOSE_RUN             = $(COMPOSE) run --rm
COMPOSE_RUN_APP         = $(COMPOSE_RUN) app-dev
COMPOSE_RUN_APP_NO_DEPS = $(COMPOSE_RUN) --no-deps app-dev 

COMPOSE_RUN_CROWDIN     = $(COMPOSE_RUN) crowdin crowdin

# -- Backend
MANAGE              	= $(COMPOSE_RUN_APP) python manage.py
MANAGE_EXEC         	= $(COMPOSE_EXEC_APP) python manage.py
MAIL_YARN           	= $(COMPOSE_RUN) -w /app/src/mail node yarn
PSQL_E2E 				= ./bin/postgres_e2e

# -- Frontend
PATH_FRONT          	= ./src/frontend
PATH_FRONT_DRIVE  		= $(PATH_FRONT)/apps/drive
FRONT_YARN           	= $(COMPOSE_RUN) -w /app/src/frontend node yarn

# -- E2E
# Default to the LAN dev stack (see AGENTS.md "Dev environment (LAN)").
E2E_LAN_HOST ?= 192.168.10.123
E2E_LOOPBACK_HOST ?= 127.0.0.1
E2E_PORT_OFFSET ?= 0
E2E_NETWORK_MODE ?= host
PLAYWRIGHT_WORKERS ?= 4
E2E_S2S_TOKEN_RESOLVER ?= ./bin/resolve_e2e_s2s_token.sh
E2E_TOKEN_REQUIRED_GOALS = \
                 bootstrap-e2e \
                 run-backend-e2e \
                 run-tests-e2e \
                 run-tests-e2e-readiness \
                 run-tests-e2e-full \
                 run-tests-e2e-full-chromium \
                 run-tests-e2e-benchmark-local \
                 run-tests-e2e-ci-browser \
                 run-tests-e2e-ci-browser-experiment \
                 run-tests-e2e-ci-pr \
                 run-tests-e2e-ci-pr-workers1-control \
                 run-tests-e2e-ci-pr-workers2-experiment \
                 run-tests-e2e-full-sharded \
                 run-tests-e2e-from-scratch \
                 run-tests-e2e-from-scratch-chromium
E2E_BASE_URL ?= http://$(E2E_LAN_HOST):3000
E2E_API_ORIGIN ?= http://$(E2E_LAN_HOST):8071
E2E_EDGE_ORIGIN ?= http://$(E2E_LAN_HOST):8083
E2E_S3_ORIGIN ?= http://$(E2E_LAN_HOST):9000
E2E_MANUAL_BASE_URL ?= http://$(E2E_LOOPBACK_HOST):$(FRONTEND_DEV_PORT)
E2E_MANUAL_API_ORIGIN ?= http://$(E2E_LOOPBACK_HOST):$(APP_DEV_PORT)
E2E_MANUAL_EDGE_ORIGIN ?= http://$(E2E_LOOPBACK_HOST):$(NGINX_PORT)
E2E_MANUAL_S3_ORIGIN ?= http://$(E2E_LOOPBACK_HOST):$(SEAWEED_S3_PORT)
E2E_MANUAL_ENV = E2E_NETWORK_MODE=manual \
                 E2E_BASE_URL=$(E2E_MANUAL_BASE_URL) \
                 E2E_API_ORIGIN=$(E2E_MANUAL_API_ORIGIN) \
                 E2E_EDGE_ORIGIN=$(E2E_MANUAL_EDGE_ORIGIN) \
                 E2E_S3_ORIGIN=$(E2E_MANUAL_S3_ORIGIN)
E2E_BENCHMARK_CHROMIUM_SPECS = \
                 __tests__/app-drive/left-bar.spec.ts \
                 __tests__/app-drive/config-custom-assets.spec.ts \
                 __tests__/app-drive/release-note.spec.ts \
                 __tests__/app-drive/pdf-preview-layout.spec.ts \
                 __tests__/app-drive/heic-file-preview.spec.ts \
                 __tests__/app-drive/create-folder.spec.ts \
                 __tests__/app-drive/delete-item.spec.ts \
                 __tests__/app-drive/move-item.spec.ts \
                 __tests__/app-drive/upload.spec.ts \
                 __tests__/app-drive/starred.spec.ts \
                 __tests__/app-drive/context-menu.spec.ts \
                 __tests__/app-drive/item/right-content-info.spec.ts \
                 __tests__/app-drive/url-file-preview.spec.ts \
                 __tests__/app-drive/viewer-routing.spec.ts \
                 __tests__/app-drive/breadcrumbs-from-page.spec.ts \
                 __tests__/app-drive/redirect-401.spec.ts \
                 __tests__/app-drive/language-sync.spec.ts \
                 __tests__/app-drive/share.spec.ts \
                 __tests__/app-drive/search.spec.ts \
                 __tests__/app-drive/wopi.spec.ts \
                 __tests__/app-drive/wopi-onlyoffice-editnew.spec.ts \
                 __tests__/app-drive/create-file-from-template.spec.ts \
                 __tests__/app-drive/mounts-basic.spec.ts \
                 __tests__/app-drive/mounts-preview-cycles.spec.ts

# Allow passing Playwright args after the Make target:
#   make run-tests-e2e -- __tests__/... --project chromium
#   make run-tests-e2e-from-scratch -- __tests__/... --project chromium
ifneq (,$(filter run-tests-e2e run-tests-e2e-from-scratch run-tests-e2e-full-sharded,$(firstword $(MAKECMDGOALS))))
  RUN_E2E_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
  # Support `--project=<browser>` which GNU make interprets as a VAR=VALUE assignment.
  # GitHub workflows use this form.
  ifneq (,$(strip $(--project)))
    RUN_E2E_ARGS += --project $(--project)
  endif
  ifneq (,$(strip $(--shard)))
    RUN_E2E_ARGS += --shard $(--shard)
  endif
  $(eval $(RUN_E2E_ARGS):;@:)
endif
ifneq (,$(filter $(E2E_TOKEN_REQUIRED_GOALS),$(MAKECMDGOALS)))
  E2E_RESOLVED_S2S_TOKEN := $(shell $(E2E_S2S_TOKEN_RESOLVER) 2>&1)
  E2E_RESOLVED_S2S_STATUS := $(.SHELLSTATUS)
  ifneq ($(E2E_RESOLVED_S2S_STATUS),0)
    $(error $(E2E_RESOLVED_S2S_TOKEN))
  endif
  export DRIVE_E2E_S2S_TOKEN := $(E2E_RESOLVED_S2S_TOKEN)
  export DJANGO_SERVER_TO_SERVER_API_TOKENS := $(E2E_RESOLVED_S2S_TOKEN)
  export E2E_S2S_TOKEN := $(E2E_RESOLVED_S2S_TOKEN)
endif

# ==============================================================================
# RULES

default: help

data/media:
	@mkdir -p data/media

data/static:
	@mkdir -p "$(STATIC_DATA_DIR)"

e2e-run-data-dirs:
	@mkdir -p "$(POSTGRESQL_DATA_DIR)"
	@mkdir -p "$(SEAWEED_MASTER_DATA_DIR)"
	@mkdir -p "$(SEAWEED_VOLUME_DATA_DIR)"
	@mkdir -p "$(SEAWEED_FILER_DATA_DIR)"
	@mkdir -p "$(STATIC_DATA_DIR)"
.PHONY: e2e-run-data-dirs

# -- Project

create-env-local-files: ## create env.local files in env.d/development
create-env-local-files: 
	@touch env.d/development/crowdin.local
	@touch env.d/development/common.local
	@touch env.d/development/postgresql.local
	@touch env.d/development/kc_postgresql.local
.PHONY: create-env-local-files

create-docker-network: ## create the docker network if it doesn't exist
	@docker network create $(LASUITE_NETWORK_NAME) || true
.PHONY: create-docker-network

bootstrap: ## Prepare Docker images for the project
bootstrap: \
	data/media \
	data/static \
	create-env-local-files \
	build \
	create-docker-network \
	migrate \
	back-i18n-compile \
	mails-install \
	mails-build \
	run
.PHONY: bootstrap

# -- Docker/compose
build: cache ?= --no-cache
build: ## build the project containers
	@$(MAKE) build-backend cache=$(cache)
	@$(MAKE) build-frontend cache=$(cache)
.PHONY: build

build-backend: cache ?=
build-backend: ## build the app-dev container
	@$(COMPOSE) build app-dev $(cache)
.PHONY: build-backend

build-frontend: cache ?=
build-frontend: ## build the frontend container
	@$(COMPOSE) build frontend-dev $(cache)
.PHONY: build-frontend-development

down: ## stop and remove containers, networks, images, and volumes
	@$(COMPOSE) down
	rm -rf data/postgresql.*
.PHONY: down

logs: ## display app-dev logs (follow mode)
	@$(COMPOSE) logs -f app-dev
.PHONY: logs

run-backend: ## start the backend containers
	@$(COMPOSE) up --force-recreate -d celery-dev
	@$(COMPOSE) up --force-recreate -d nginx
.PHONY: run-backend

bootstrap-e2e: ## bootstrap the backend container for e2e tests, without frontend
bootstrap-e2e: \
	data/media \
	data/static \
	e2e-run-data-dirs \
	create-env-local-files \
	build-backend \
	build-frontend \
	create-docker-network \
	back-i18n-compile \
	run-backend-e2e
bootstrap-e2e: export ENV_OVERRIDE = e2e
.PHONY: bootstrap-e2e

clear-db-e2e: ## quickly clears the database for e2e tests, used in the e2e tests
	$(PSQL_E2E) -c "$$(cat bin/clear_db_e2e.sql)"
.PHONY: clear-db-e2e

run-backend-e2e: ## start the backend container for e2e tests, always reset the postgresql.e2e data dir first
	@$(MAKE) stop
	@# Keycloak realm import only happens on fresh DB; drop its containers/volumes for from-scratch E2E determinism.
	@ENV_OVERRIDE=e2e $(COMPOSE) rm -fsv kc_postgresql keycloak >/dev/null 2>&1 || true
	@ENV_OVERRIDE=e2e $(COMPOSE) run --rm -T --no-deps -u 0:0 --entrypoint sh postgresql -lc "rm -rf /var/lib/postgresql/data/*"
	@ENV_OVERRIDE=e2e $(MAKE) run-backend
	@ENV_OVERRIDE=e2e $(MAKE) migrate
	@ENV_OVERRIDE=e2e $(MAKE) configure-wopi
run-backend-e2e: export ENV_OVERRIDE = e2e
.PHONY: run-backend-e2e

run-frontend-e2e: ## start the frontend container for e2e tests against the current e2e project
	@$(COMPOSE) up -d frontend-dev
run-frontend-e2e: export ENV_OVERRIDE = e2e
.PHONY: run-frontend-e2e

run-tests-e2e: ## run the e2e tests against an already-running stack (runner container only)
	@$(COMPOSE) run --rm -T --no-deps \
	  -e E2E_NETWORK_MODE="$(E2E_NETWORK_MODE)" \
	  -e E2E_ENABLE_MOUNTS=$(E2E_ENABLE_MOUNTS) \
	  -e E2E_READYNESS_SMOKE="$(E2E_READYNESS_SMOKE)" \
	  -e PLAYWRIGHT_WORKERS="$(PLAYWRIGHT_WORKERS)" \
	  -e PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE="$(PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE)" \
	  -e PLAYWRIGHT_BLOB_OUTPUT_DIR="$(PLAYWRIGHT_BLOB_OUTPUT_DIR)" \
	  -e PLAYWRIGHT_BLOB_OUTPUT_NAME="$(PLAYWRIGHT_BLOB_OUTPUT_NAME)" \
	  -e PLAYWRIGHT_HTML_OUTPUT_DIR="$(PLAYWRIGHT_HTML_OUTPUT_DIR)" \
	  -e PWTEST_BLOB_DO_NOT_REMOVE="$(PWTEST_BLOB_DO_NOT_REMOVE)" \
	  -e E2E_BASE_URL="$(E2E_BASE_URL)" \
	  -e E2E_API_ORIGIN="$(E2E_API_ORIGIN)" \
	  -e E2E_EDGE_ORIGIN="$(E2E_EDGE_ORIGIN)" \
	  -e E2E_S3_ORIGIN="$(E2E_S3_ORIGIN)" \
	  -e E2E_PROXY_API="$(E2E_PROXY_API)" \
	  -e E2E_PROXY_UPSTREAM="$(E2E_PROXY_UPSTREAM)" \
	  -e E2E_S2S_TOKEN \
	  -e CI="$(CI)" \
	  e2e-playwright bash -lc "\
	    set -euo pipefail; \
	    corepack enable; \
	    corepack prepare yarn@1.22.22 --activate; \
	    cd /work/src/frontend/apps/e2e; \
	    (cd /work/src/frontend && yarn install --frozen-lockfile --non-interactive) || { echo \"[e2e] yarn install failed\" >&2; exit 1; }; \
	    : > /tmp/_loopback-proxies.log; \
	    if [ \"$$E2E_NETWORK_MODE\" = \"compose\" ] || [ \"$$E2E_NETWORK_MODE\" = \"manual\" ]; then \
	      node ./scripts/loopback-proxies.js >/tmp/_loopback-proxies.log 2>&1 & \
	      PROXY_PID=$$!; \
	      trap 'kill $$PROXY_PID 2>/dev/null || true' EXIT; \
	      if ! node -e '\
	        const baseUrl = process.env.E2E_BASE_URL || \"http://127.0.0.1:3000\"; \
	        const apiOrigin = process.env.E2E_API_ORIGIN || \"http://127.0.0.1:8071\"; \
	        const edgeOrigin = process.env.E2E_EDGE_ORIGIN || \"http://127.0.0.1:8083\"; \
	        const s3Origin = process.env.E2E_S3_ORIGIN || \"http://127.0.0.1:9000\"; \
	        const apiOriginTrimmed = apiOrigin.endsWith(\"/\") ? apiOrigin.slice(0, -1) : apiOrigin; \
	        const apiConfigUrl = apiOriginTrimmed + \"/api/v1.0/config/\"; \
	        const checks = [ \
	          { url: baseUrl, ok: (status) => status >= 200 && status < 400 }, \
	          { url: apiConfigUrl, ok: (status) => status >= 200 && status < 300 }, \
	          { url: edgeOrigin, ok: (status) => status >= 200 && status < 400 }, \
	          { url: s3Origin, ok: (status) => status >= 200 && status < 500 }, \
	        ]; \
	        const http = require(\"http\"); \
	        const deadline = Date.now() + 60_000; \
	        const checkOne = ({ url, ok }) => new Promise((resolve, reject) => { \
	          const req = http.get(url, (res) => { \
	            const status = res.statusCode || 0; \
	            res.resume(); \
	            if (ok(status)) { \
	              resolve(); \
	              return; \
	            } \
	            reject(new Error(url + \" returned status \" + status)); \
	          }); \
	          req.on(\"error\", reject); \
	        }); \
	        const tick = async () => { \
	          try { \
	            for (const check of checks) await checkOne(check); \
	            process.exit(0); \
	          } catch { \
	            if (Date.now() > deadline) process.exit(1); \
	            setTimeout(tick, 250); \
	          } \
	        }; \
	        tick();'; \
	      then \
	        echo \"[e2e] healthcheck failed (E2E_NETWORK_MODE=$$E2E_NETWORK_MODE)\" >&2; \
	        pwd >&2; \
	        ls -la /work/src/frontend/apps/e2e >&2 || true; \
	        ls -la /tmp/_loopback-proxies.log >&2 || true; \
	        tail -n 200 /tmp/_loopback-proxies.log 2>/dev/null || echo \"(no loopback proxy log)\"; \
	        exit 1; \
	      fi; \
	      echo \"[e2e] healthcheck ok (E2E_NETWORK_MODE=$$E2E_NETWORK_MODE)\" >&2; \
	    fi; \
	    echo \"[e2e] starting playwright $(RUN_E2E_ARGS)\" >&2; \
	    if ! yarn test $(RUN_E2E_ARGS); then \
	      echo \"[e2e] playwright failed (E2E_NETWORK_MODE=$$E2E_NETWORK_MODE)\" >&2; \
	      pwd >&2; \
	      ls -la /work/src/frontend/apps/e2e >&2 || true; \
	      ls -la /tmp/_loopback-proxies.log >&2 || true; \
	      tail -n 200 /tmp/_loopback-proxies.log 2>/dev/null || echo \"(no loopback proxy log)\"; \
	      exit 1; \
	    fi \
	  "
.PHONY: run-tests-e2e

run-tests-e2e-readiness: ## validate the real app-drive preamble before the full E2E campaign
	@E2E_READYNESS_SMOKE=1 \
	  $(E2E_MANUAL_ENV) \
	  $(MAKE) run-tests-e2e -- __tests__/app-drive/e2e-ready-smoke.spec.ts --project chromium
run-tests-e2e-readiness: export ENV_OVERRIDE = e2e
.PHONY: run-tests-e2e-readiness

run-tests-e2e-full: ## run the full e2e campaign against an already-running e2e stack
	@$(MAKE) run-tests-e2e-readiness
	@$(E2E_MANUAL_ENV) \
	  $(MAKE) run-tests-e2e -- --project chromium
	@$(E2E_MANUAL_ENV) \
	  $(MAKE) run-tests-e2e -- --project webkit
	@$(E2E_MANUAL_ENV) \
	  $(MAKE) run-tests-e2e -- --project firefox
run-tests-e2e-full: export ENV_OVERRIDE = e2e
.PHONY: run-tests-e2e-full

run-tests-e2e-full-chromium: ## run readiness then the full Chromium campaign on the current e2e stack
	@$(MAKE) run-tests-e2e-readiness
	@E2E_ENABLE_MOUNTS=1 \
	  $(E2E_MANUAL_ENV) \
	  $(MAKE) run-tests-e2e -- --project chromium
run-tests-e2e-full-chromium: export ENV_OVERRIDE = e2e
.PHONY: run-tests-e2e-full-chromium

run-tests-e2e-benchmark-local: ## run the representative local Chromium benchmark batch on the current e2e stack
	@$(E2E_MANUAL_ENV) \
	  $(MAKE) run-tests-e2e -- $(E2E_BENCHMARK_CHROMIUM_SPECS) --project chromium
run-tests-e2e-benchmark-local: export ENV_OVERRIDE = e2e
run-tests-e2e-benchmark-local: export E2E_ENABLE_MOUNTS = 1
.PHONY: run-tests-e2e-benchmark-local

run-tests-e2e-ci-browser: ## run readiness then one conservative CI browser on the current e2e stack
	@test -n "$(E2E_BROWSER)" || { echo "E2E_BROWSER is required" >&2; exit 1; }
	@$(MAKE) run-tests-e2e-readiness
	@PLAYWRIGHT_WORKERS=1 \
	  E2E_ENABLE_MOUNTS=1 \
	  $(E2E_MANUAL_ENV) \
	  $(MAKE) run-tests-e2e -- --project $(E2E_BROWSER)
run-tests-e2e-ci-browser: export ENV_OVERRIDE = e2e
.PHONY: run-tests-e2e-ci-browser

run-tests-e2e-ci-browser-experiment: ## run readiness then one opt-in CI browser experiment on the current e2e stack
	@test -n "$(E2E_BROWSER)" || { echo "E2E_BROWSER is required" >&2; exit 1; }
	@test -n "$(PLAYWRIGHT_EXPERIMENTAL_WORKERS)" || { echo "PLAYWRIGHT_EXPERIMENTAL_WORKERS is required" >&2; exit 1; }
	@$(MAKE) run-tests-e2e-readiness
	@PLAYWRIGHT_WORKERS=$(PLAYWRIGHT_EXPERIMENTAL_WORKERS) \
	  PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE=1 \
	  E2E_ENABLE_MOUNTS=1 \
	  $(E2E_MANUAL_ENV) \
	  $(MAKE) run-tests-e2e -- --project $(E2E_BROWSER)
run-tests-e2e-ci-browser-experiment: export ENV_OVERRIDE = e2e
.PHONY: run-tests-e2e-ci-browser-experiment

run-tests-e2e-ci-pr: ## run the conservative PR E2E policy on the current e2e stack
	@$(MAKE) run-tests-e2e-ci-browser E2E_BROWSER=chromium
run-tests-e2e-ci-pr: export ENV_OVERRIDE = e2e
.PHONY: run-tests-e2e-ci-pr

run-tests-e2e-ci-pr-workers1-control: ## run the workflow-dispatch Chromium PR CI control at workers=1 on the current e2e stack
	@$(MAKE) run-tests-e2e-ci-pr
run-tests-e2e-ci-pr-workers1-control: export ENV_OVERRIDE = e2e
.PHONY: run-tests-e2e-ci-pr-workers1-control

run-tests-e2e-ci-pr-workers2-experiment: ## run the opt-in Chromium PR CI experiment at workers=2 on the current e2e stack
	@$(MAKE) run-tests-e2e-ci-browser-experiment E2E_BROWSER=chromium PLAYWRIGHT_EXPERIMENTAL_WORKERS=2
run-tests-e2e-ci-pr-workers2-experiment: export ENV_OVERRIDE = e2e
.PHONY: run-tests-e2e-ci-pr-workers2-experiment

run-tests-e2e-full-sharded: ## run readiness then a single browser shard against an already-running e2e stack
	@test -n "$(E2E_BROWSER)" || { echo "E2E_BROWSER is required" >&2; exit 1; }
	@test -n "$(E2E_SHARD)" || { echo "E2E_SHARD is required" >&2; exit 1; }
	@test -n "$(E2E_TOTAL_SHARDS)" || { echo "E2E_TOTAL_SHARDS is required" >&2; exit 1; }
	@$(MAKE) run-tests-e2e-readiness
	@$(E2E_MANUAL_ENV) \
	  $(MAKE) run-tests-e2e -- $(RUN_E2E_ARGS) --project $(E2E_BROWSER) --shard=$(E2E_SHARD)/$(E2E_TOTAL_SHARDS)
run-tests-e2e-full-sharded: export ENV_OVERRIDE = e2e
.PHONY: run-tests-e2e-full-sharded

run-tests-e2e-merge-reports: ## merge Playwright blob reports into an HTML report
	@test -n "$(PLAYWRIGHT_BLOB_OUTPUT_DIR)" || { echo "PLAYWRIGHT_BLOB_OUTPUT_DIR is required" >&2; exit 1; }
	@test -n "$(PLAYWRIGHT_HTML_OUTPUT_DIR)" || { echo "PLAYWRIGHT_HTML_OUTPUT_DIR is required" >&2; exit 1; }
	@$(COMPOSE) run --rm -T --no-deps \
	  -e PLAYWRIGHT_HTML_OUTPUT_DIR="$(PLAYWRIGHT_HTML_OUTPUT_DIR)" \
	  -e PLAYWRIGHT_HTML_OPEN="never" \
	  e2e-playwright bash -lc "\
	    set -euo pipefail; \
	    corepack enable; \
	    corepack prepare yarn@1.22.22 --activate; \
	    cd /work/src/frontend/apps/e2e; \
	    (cd /work/src/frontend && yarn install --frozen-lockfile --non-interactive) || { echo \"[e2e] yarn install failed\" >&2; exit 1; }; \
	    ./node_modules/.bin/playwright merge-reports --reporter html \"$(PLAYWRIGHT_BLOB_OUTPUT_DIR)\" \
	  "
run-tests-e2e-merge-reports: export ENV_OVERRIDE = e2e
.PHONY: run-tests-e2e-merge-reports

run-tests-e2e-from-scratch: ## stop/reset/start the e2e stack, then run the e2e tests
	@$(MAKE) run-backend-e2e
	@$(COMPOSE) up -d frontend-dev
	@$(MAKE) run-tests-e2e-full
run-tests-e2e-from-scratch: export ENV_OVERRIDE = e2e
.PHONY: run-tests-e2e-from-scratch

run-tests-e2e-from-scratch-chromium: ## stop/reset/start the e2e stack, then run the full Chromium campaign
	@$(MAKE) run-backend-e2e
	@$(COMPOSE) up -d frontend-dev
	@$(MAKE) run-tests-e2e-full-chromium
run-tests-e2e-from-scratch-chromium: export ENV_OVERRIDE = e2e
.PHONY: run-tests-e2e-from-scratch-chromium

backend-exec-command: ## execute a command in the backend container
	@args="$(filter-out $@,$(MAKECMDGOALS))" && \
	$(MANAGE_EXEC) $${args}
.PHONY: backend-exec-command

run: ## start the development server and frontend development
run: 
	@$(MAKE) run-backend
	@$(MAKE) migrate
	@$(MAKE) configure-wopi
	@$(COMPOSE) up --force-recreate -d frontend-dev
.PHONY: run

status: ## an alias for "docker compose ps"
	@$(COMPOSE) ps
.PHONY: status

stop: ## stop the development server using Docker
	@$(COMPOSE) stop
.PHONY: stop

# -- Backend

demo: ## flush db then create a demo for load testing purpose
	@$(MAKE) resetdb
	@$(MANAGE) create_demo
.PHONY: demo

index: ## index all files to remote search
	@$(MANAGE) index
.PHONY: index

# Nota bene: Black should come after isort just in case they don't agree...
lint: ## lint back-end python sources
lint: \
  lint-ruff-format \
  lint-ruff-check-fix \
  lint-pylint
.PHONY: lint

lint-ruff-format: ## format back-end python sources with ruff
	@echo 'lint:ruff-format started…'
	@$(COMPOSE_RUN_APP_NO_DEPS) ruff format .
.PHONY: lint-ruff-format

lint-ruff-check: ## lint back-end python sources with ruff
	@echo 'lint:ruff-check started…'
	@$(COMPOSE_RUN_APP_NO_DEPS) ruff check .
.PHONY: lint-ruff-check

lint-ruff-check-fix: ## fix back-end python sources with ruff
	@echo 'lint:ruff-check-fix started…'
	@$(COMPOSE_RUN_APP_NO_DEPS) ruff check . --fix
.PHONY: lint-ruff-check-fix

lint-pylint: ## lint back-end python sources with pylint only on changed files from main
	@echo 'lint:pylint started…'
	bin/pylint --diff-only=origin/main
.PHONY: lint-pylint

test: ## run project tests
	@$(MAKE) test-back-parallel
.PHONY: test

test-back: ## run back-end tests
	@args="$(filter-out $@,$(MAKECMDGOALS))" && \
	bin/pytest $${args:-${1}}
.PHONY: test-back

test-back-parallel: ## run all back-end tests in parallel
	@args="$(filter-out $@,$(MAKECMDGOALS))" && \
	bin/pytest -n auto $${args:-${1}}
.PHONY: test-back-parallel

makemigrations:  ## run django makemigrations for the drive project.
	@echo "$(BOLD)Running makemigrations$(RESET)"
	@$(COMPOSE) up -d postgresql
	@$(MANAGE) makemigrations
.PHONY: makemigrations

migrate:  ## run django migrations for the drive project.
	@echo "$(BOLD)Running migrations$(RESET)"
	@$(COMPOSE) up -d postgresql
	@$(MANAGE) migrate
.PHONY: migrate

superuser: ## Create an admin superuser with password "admin"
	@echo "$(BOLD)Creating a Django superuser$(RESET)"
	@$(MANAGE) createsuperuser --email admin@example.com --password admin
.PHONY: superuser

configure-wopi: ## configure the wopi settings
	@$(MANAGE) trigger_wopi_configuration
.PHONY: configure-wopi

back-i18n-compile: ## compile the gettext files
	@$(MANAGE) compilemessages --ignore=".venv/**/*"
.PHONY: back-i18n-compile

back-i18n-generate: ## create the .pot files used for i18n
	@$(MANAGE) makemessages -a --keep-pot --all
.PHONY: back-i18n-generate

shell: ## connect to django shell
	@$(MANAGE) shell #_plus
.PHONY: dbshell

# -- Database

dbshell: ## connect to database shell
	docker compose exec app-dev python manage.py dbshell
.PHONY: dbshell

resetdb: FLUSH_ARGS ?=
resetdb: ## flush database and create a superuser "admin"
	@echo "$(BOLD)Flush database$(RESET)"
	@$(MANAGE) flush $(FLUSH_ARGS)
	@${MAKE} superuser
.PHONY: resetdb

# -- Internationalization

crowdin-download: ## Download translated message from crowdin
	@$(COMPOSE_RUN_CROWDIN) download -c crowdin/config.yml
.PHONY: crowdin-download

crowdin-download-sources: ## Download sources from Crowdin
	@$(COMPOSE_RUN_CROWDIN) download sources -c crowdin/config.yml
.PHONY: crowdin-download-sources

crowdin-upload: ## Upload source translations to crowdin
	@$(COMPOSE_RUN_CROWDIN) upload sources -c crowdin/config.yml
.PHONY: crowdin-upload

i18n-compile: ## compile all translations
i18n-compile: \
	back-i18n-compile \
	frontend-i18n-compile
.PHONY: i18n-compile

i18n-generate: ## create the .pot files and extract frontend messages
i18n-generate: \
	back-i18n-generate \
	frontend-i18n-generate
.PHONY: i18n-generate

i18n-download-and-compile: ## download all translated messages and compile them to be used by all applications
i18n-download-and-compile: \
  crowdin-download \
  i18n-compile
.PHONY: i18n-download-and-compile

i18n-generate-and-upload: ## generate source translations for all applications and upload them to Crowdin
i18n-generate-and-upload: \
  i18n-generate \
  crowdin-upload
.PHONY: i18n-generate-and-upload

# -- Mail generator

mails-build: ## Convert mjml files to html and text
	@$(MAIL_YARN) build
.PHONY: mails-build

mails-build-html-to-plain-text: ## Convert html files to text
	@$(MAIL_YARN) build-html-to-plain-text
.PHONY: mails-build-html-to-plain-text

mails-build-mjml-to-html:	## Convert mjml files to html and text
	@$(MAIL_YARN) build-mjml-to-html
.PHONY: mails-build-mjml-to-html

mails-install: ## install the mail generator
	@$(MAIL_YARN) install
.PHONY: mails-install


# -- Misc
clean: ## restore repository state as it was freshly cloned
	git clean -idx
.PHONY: clean

clean-media: ## remove all media files
	rm -rf data/media/*
.PHONY: clean-media

help:
	@echo "$(BOLD)drive Makefile"
	@echo "Please use 'make $(BOLD)target$(RESET)' where $(BOLD)target$(RESET) is one of:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-30s$(RESET) %s\n", $$1, $$2}'
.PHONY: help

# Front
frontend-development-install: ## install the frontend locally
	cd $(PATH_FRONT_DRIVE) && yarn
.PHONY: frontend-development-install

frontend-lint: ## run the frontend linter
	@$(FRONT_YARN) install --frozen-lockfile --non-interactive
	@$(FRONT_YARN) lint
.PHONY: frontend-lint

run-frontend-development: ## Run the frontend in development mode
	@$(COMPOSE) stop frontend-dev
	cd $(PATH_FRONT_DRIVE) && yarn dev
.PHONY: run-frontend-development

frontend-i18n-extract: ## Extract the frontend translation inside a json to be used for crowdin
	cd $(PATH_FRONT) && yarn i18n:extract
.PHONY: frontend-i18n-extract

frontend-i18n-generate: ## Generate the frontend json files used for crowdin
frontend-i18n-generate: \
	crowdin-download-sources \
	frontend-i18n-extract
.PHONY: frontend-i18n-generate

frontend-i18n-compile: ## Format the crowin json files used deploy to the apps
	cd $(PATH_FRONT) && yarn i18n:deploy
.PHONY: frontend-i18n-compile

# -- K8S
build-k8s-cluster: ## build the kubernetes cluster using kind
	./bin/start-kind.sh
.PHONY: build-k8s-cluster

start-tilt: ## start the kubernetes cluster using kind
	tilt up -f ./bin/Tiltfile
.PHONY: build-k8s-cluster
