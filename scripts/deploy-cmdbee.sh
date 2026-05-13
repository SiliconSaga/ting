#!/usr/bin/env bash
# scripts/deploy-cmdbee.sh — recurring deploy to the cmdbee (GKE staging) tier.
#
# Runs after a new image lands at ghcr.io/siliconsaga/ting:latest. The
# Deployment spec uses `imagePullPolicy: Always`, so a rollout restart
# fetches the new image. Also re-applies the kustomize overlay (cheap; picks
# up any manifest changes) and runs migrations.
#
# Idempotent. Run after every push to main once the image build finishes.
#
# Environment knobs:
#   KCTX        — kubectl context (default: current context)
#   NS          — namespace (default: ting)
#   HOST        — hostname to smoke-test (default: ting.cmdbee.org)
#   SKIP_MIGRATE=1   — skip the `ting migrate` step
#   SKIP_SMOKE=1     — skip the curl smoke

set -euo pipefail

: "${KCTX:=$(kubectl config current-context)}"
: "${NS:=ting}"
: "${HOST:=ting.cmdbee.org}"

KCTL=(kubectl --context "$KCTX")

log()  { printf '\033[36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m✓\033[0m %s\n' "$*"; }
die()  { printf '\033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

log "Using kubectl context: $KCTX"
if [[ "$KCTX" != *gke* ]] && [[ "${FORCE:-0}" != "1" ]]; then
  die "Context name does not contain 'gke'. If this is intentional, re-run with FORCE=1."
fi

# 1. Re-apply manifests (no-op when unchanged; picks up any overlay edits).
OVERLAY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)/k8s/overlays/cmdbee"
log "kubectl apply -k $OVERLAY ..."
"${KCTL[@]}" apply -k "$OVERLAY" >/dev/null
ok "manifests applied"

# 2. Rollout — :latest with imagePullPolicy=Always pulls the new image.
log "Rolling deploy/ting..."
"${KCTL[@]}" rollout restart deployment/ting -n "$NS" >/dev/null
"${KCTL[@]}" rollout status deployment/ting -n "$NS" --timeout=120s >/dev/null
ok "pod Ready"

# 3. Migrate (idempotent: no-op at head). Skip with SKIP_MIGRATE=1.
if [[ "${SKIP_MIGRATE:-0}" != "1" ]]; then
  log "Running migrations..."
  "${KCTL[@]}" exec -n "$NS" deploy/ting -- ting migrate >/dev/null
  ok "migrations at head"
fi

# 4. Bust the summary cache so the next /summary load reflects this version.
"${KCTL[@]}" exec -n "$NS" deploy/ting -- python -c "
from ting.valkey import get_valkey
vk = get_valkey()
n = sum(1 for _ in [vk.delete(k) for k in vk.scan_iter('summary:*')])
print(f'cleared {n} cached summary entries')
" 2>&1 | tail -1

# 5. Smoke.
if [[ "${SKIP_SMOKE:-0}" != "1" ]]; then
  log "Smoke test: GET https://$HOST/healthz ..."
  # -f fails on non-2xx; the regex is whitespace-tolerant.
  if curl -ksSf --max-time 10 "https://$HOST/healthz" \
      | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"'; then
    ok "https://$HOST/healthz returns ok"
  else
    die "https://$HOST/healthz did not return ok"
  fi
fi

ok "deploy-cmdbee complete"
