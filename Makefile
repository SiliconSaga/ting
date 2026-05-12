# ting — developer Makefile
# Component-local conveniences for the inner dev loop (build, deploy to local
# k3d, wipe/seed data, logs, smoke). Higher-level workspace ops (ws test, ws
# commit, ws push) stay through the ws CLI. Run from this directory.

# --- Configuration -----------------------------------------------------------

IMAGE       ?= ting:dev
KCTX        ?= k3d-nordri-test
K3D_CLUSTER ?= nordri-test
NS          ?= ting-local
HOST        ?= ting.local
LB_IP       ?= 192.168.97.2
COHORT      ?= MPE-2026-spring-pilot
SEED        ?= /app/seeds/example.yaml
DEMO_COUNT  ?= 30

KEXEC := kubectl --context $(KCTX) exec -n $(NS) deploy/ting --

# --- Help --------------------------------------------------------------------

.DEFAULT_GOAL := help

help: ## Show this help.
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ { printf "  %-18s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# --- Test + lint -------------------------------------------------------------

test: ## Run pytest via ws-test adapter (auto-allowed, no permission prompts).
	cd ../.. && bash scripts/ws test ting

lint: ## Ruff via ws-lint adapter.
	cd ../.. && bash scripts/ws lint ting

# --- Image + deploy (local k3d) ---------------------------------------------

build: ## Build the ting:dev image with the current source.
	docker build -t $(IMAGE) .

import: build ## Build then load the image into the k3d cluster.
	k3d image import $(IMAGE) -c $(K3D_CLUSTER)

deploy: import ## Build, import, roll the Deployment, wait for Ready.
	kubectl --context $(KCTX) rollout restart deployment/ting -n $(NS)
	@until kubectl --context $(KCTX) rollout status deployment/ting -n $(NS) --timeout=60s >/dev/null 2>&1; do sleep 2; done
	@echo "ting pod ready"

# --- Data lifecycle ----------------------------------------------------------

wipe: ## Drop + recreate the ting schema (Postgres). Destructive.
	$(KEXEC) python -c "from ting.db import get_engine; from ting.models import Base; eng=get_engine(); Base.metadata.drop_all(eng); Base.metadata.create_all(eng); print('schema wiped + recreated')"

seed: ## Load the example seed YAML.
	$(KEXEC) ting seed $(SEED)

demo: ## Generate $(DEMO_COUNT) demo codes with synthetic responses.
	$(KEXEC) ting demo populate --cohort $(COHORT) --count $(DEMO_COUNT)

bust-cache: ## Clear Valkey summary cache so /summary recomputes immediately.
	$(KEXEC) python -c "from ting.valkey import get_valkey; vk=get_valkey(); [vk.delete(k) for k in vk.scan_iter('summary:*')]; print('cache cleared')"

reseed: wipe seed demo bust-cache ## Full data reset: wipe → seed → demo → cache.
	@echo "data reset complete"

codes: ## Generate 3 fresh codes for browser testing. Use COHORT=... to override.
	$(KEXEC) ting codes generate --cohort $(COHORT) --count 3

# --- Composite ---------------------------------------------------------------

cycle: deploy bust-cache ## Quick redeploy + bust cache (no data wipe).

full: deploy reseed ## Deploy fresh image + reset all data + 30 demo respondents.

# --- Observability -----------------------------------------------------------

logs: ## Tail the ting pod logs.
	kubectl --context $(KCTX) logs -f deploy/ting -n $(NS)

smoke: ## Hit /healthz, /, /summary against the local LB. Quick reachability check.
	@curl -sS -H "Host: $(HOST)" "http://$(LB_IP)/healthz" && echo "  /healthz ok"
	@curl -sS -H "Host: $(HOST)" "http://$(LB_IP)/" -o /dev/null -w "  /         %{http_code}\n"
	@curl -sS -H "Host: $(HOST)" "http://$(LB_IP)/summary" -o /dev/null -w "  /summary  %{http_code}\n"

shell: ## Drop into a python shell inside the ting pod.
	kubectl --context $(KCTX) exec -it -n $(NS) deploy/ting -- python

psql: ## Drop into psql via pgbouncer (uses the in-cluster credentials).
	kubectl --context $(KCTX) exec -it -n $(NS) deploy/ting -- python -c "from ting.config import get_settings; import os; s=get_settings(); os.execvp('psql', ['psql', s.database_url.replace('postgresql+psycopg://', 'postgresql://')])"

.PHONY: help test lint build import deploy wipe seed demo bust-cache reseed codes cycle full logs smoke shell psql
