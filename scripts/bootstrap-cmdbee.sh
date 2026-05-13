#!/usr/bin/env bash
# scripts/bootstrap-cmdbee.sh — one-time setup for the cmdbee (GKE staging) tier.
#
# Idempotent. Safe to re-run; later runs will only do work that's still pending
# (e.g. provision new claims, re-populate ting-secrets if claim outputs moved).
#
# Steps:
#   1. Verify kubectl context (defaults to current; require GKE-like name unless --force)
#   2. Verify Mimir Crossplane XRDs are installed in the cluster
#   3. Create the ting namespace + a placeholder ting-secrets Secret if missing
#   4. Apply the cmdbee kustomize overlay
#   5. Wait for PostgreSQLInstance + ValkeyCluster claims to be Ready
#   6. Derive real database_url + valkey_url from claim outputs; update ting-secrets
#   7. Rollout restart deploy/ting; wait for Ready
#   8. Run `ting migrate` + `ting seed seeds/example.yaml`
#   9. Print smoke URLs
#
# Environment knobs (override at invocation time, e.g. KCTX=... ./scripts/...):
#   KCTX        — kubectl context (default: current context)
#   NS          — namespace in the GKE cluster (default: ting)
#   COHORT      — cohort to use for the example seed (default: from seeds/example.yaml)
#   SEED        — seed YAML path inside the pod (default: /app/seeds/example.yaml)
#   HOST        — public hostname to smoke-test (default: ting.cmdbee.org)
#   CLAIM_TIMEOUT — max seconds to wait for both Mimir claims (default: 900 = 15 min)

set -euo pipefail

# --- Config ---------------------------------------------------------------

: "${KCTX:=$(kubectl config current-context)}"
: "${NS:=ting}"
: "${SEED:=/app/seeds/example.yaml}"
: "${HOST:=ting.cmdbee.org}"
: "${CLAIM_TIMEOUT:=900}"

KCTL=(kubectl --context "$KCTX")

# --- Helpers --------------------------------------------------------------

log()  { printf '\033[36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[33m!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

urlencode() {
  python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"
}

# --- 1. Context check -----------------------------------------------------

log "Using kubectl context: $KCTX"
if [[ "$KCTX" != *gke* ]] && [[ "${FORCE:-0}" != "1" ]]; then
  die "Context name does not contain 'gke'. If this is intentional, re-run with FORCE=1."
fi

# --- 2. Mimir XRDs --------------------------------------------------------

log "Checking Mimir XRDs are installed..."
for xrd in xpostgresqls.database.example.org xvalkeyclusters.mimir.siliconsaga.org; do
  if ! "${KCTL[@]}" get xrd "$xrd" >/dev/null 2>&1; then
    die "Missing XRD $xrd. Bootstrap Mimir on this cluster first."
  fi
done
ok "XRDs present"

# --- 3. Namespace + placeholder secret ------------------------------------

log "Ensuring namespace $NS exists..."
"${KCTL[@]}" get ns "$NS" >/dev/null 2>&1 || "${KCTL[@]}" create ns "$NS" >/dev/null
ok "namespace $NS"

# Generate a session_secret if the secret doesn't already exist. We don't want
# to rotate session_secret on every bootstrap (that would invalidate all live
# sessions), so preserve any existing value.
if ! "${KCTL[@]}" get secret ting-secrets -n "$NS" >/dev/null 2>&1; then
  log "Creating placeholder ting-secrets (real values populated later)..."
  # 36 raw bytes → 48 base64 chars; tr strips the trailing newline. Avoids
  # the openssl|head SIGPIPE failure under set -o pipefail.
  SESSION_SECRET="$(openssl rand -base64 36 | tr -d '\n')"
  "${KCTL[@]}" create secret generic ting-secrets -n "$NS" \
    --from-literal=database_url="postgresql+psycopg://placeholder:placeholder@placeholder:5432/ting" \
    --from-literal=valkey_url="redis://placeholder:6379/0" \
    --from-literal=session_secret="$SESSION_SECRET" \
    >/dev/null
  ok "placeholder ting-secrets created"
else
  ok "ting-secrets already exists; leaving session_secret intact"
fi

# --- 4. Apply the overlay -------------------------------------------------

OVERLAY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)/k8s/overlays/cmdbee"
log "Applying $OVERLAY ..."
"${KCTL[@]}" apply -k "$OVERLAY" >/dev/null
ok "manifests applied"

# --- 5. Wait for claims ---------------------------------------------------

wait_claim_ready() {
  local kind="$1" name="$2" deadline=$((SECONDS + CLAIM_TIMEOUT))
  log "Waiting for $kind/$name to be Ready (timeout ${CLAIM_TIMEOUT}s)..."
  while :; do
    local ready
    ready=$("${KCTL[@]}" get "$kind" "$name" -n "$NS" \
      -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)
    if [[ "$ready" == "True" ]]; then
      ok "$kind/$name Ready"
      return 0
    fi
    (( SECONDS > deadline )) && die "$kind/$name not Ready after ${CLAIM_TIMEOUT}s"
    printf '.'
    sleep 10
  done
}

# Discover exactly one ting-valkey-*-leader Service. Multiple matches are
# almost certainly a leftover from a botched re-bootstrap; we'd rather fail
# fast than silently wire ting-secrets to whichever happens to sort first.
# Returns the leader Service name on stdout, or empty when no match exists
# yet (caller polls).
find_unique_valkey_leader() {
  local leaders
  mapfile -t leaders < <(
    "${KCTL[@]}" get svc -n valkey \
      -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null \
      | grep -E '^ting-valkey-[a-z0-9]+-leader$' || true
  )
  if (( ${#leaders[@]} > 1 )); then
    die "Multiple Valkey leader Services found in 'valkey' namespace (${leaders[*]}). Clean up the stale ones before bootstrapping."
  fi
  printf '%s\n' "${leaders[0]:-}"
}

wait_claim_ready postgresqlinstance ting-pg

# Valkey's Crossplane composite Ready condition has been observed to lag the
# actual data plane (composition reports Creating while the leader pod is
# already serving). The leader Service having endpoints is the real signal we
# need, so poll that directly.
log "Waiting for Valkey leader Service to have endpoints (timeout ${CLAIM_TIMEOUT}s)..."
vk_deadline=$((SECONDS + CLAIM_TIMEOUT))
while :; do
  leader="$(find_unique_valkey_leader)"
  if [[ -n "$leader" ]]; then
    eps=$("${KCTL[@]}" get endpoints "$leader" -n valkey \
      -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null || true)
    if [[ -n "$eps" ]]; then
      ok "Valkey leader $leader serving (endpoints: $eps)"
      break
    fi
  fi
  (( SECONDS > vk_deadline )) && die "Valkey leader Service has no endpoints after ${CLAIM_TIMEOUT}s"
  printf '.'
  sleep 10
done

# --- 6. Derive real URLs + update ting-secrets ----------------------------

log "Reading Postgres credentials from ting-pg-user-secret..."
PG_PASS="$("${KCTL[@]}" get secret ting-pg-user-secret -n "$NS" -o jsonpath='{.data.password}' | base64 -d)"
[[ -n "$PG_PASS" ]] || die "Could not read PG password from ting-pg-user-secret"
PG_PASS_ENC="$(urlencode "$PG_PASS")"
DB_URL="postgresql+psycopg://ting:${PG_PASS_ENC}@ting-pg-pgbouncer.${NS}.svc.cluster.local:5432/ting"
ok "database_url assembled"

log "Discovering Valkey leader Service..."
VK_LEADER="$(find_unique_valkey_leader)"
[[ -n "$VK_LEADER" ]] || die "Could not find ting-valkey-*-leader Service in 'valkey' namespace"
VK_URL="redis://${VK_LEADER}.valkey.svc.cluster.local:6379/0"
ok "valkey_url: $VK_URL"

# Preserve the existing session_secret so we don't invalidate live sessions.
SESSION_SECRET="$("${KCTL[@]}" get secret ting-secrets -n "$NS" -o jsonpath='{.data.session_secret}' | base64 -d)"
[[ -n "$SESSION_SECRET" ]] || die "Could not read existing session_secret"

log "Updating ting-secrets with real connection URLs..."
"${KCTL[@]}" create secret generic ting-secrets -n "$NS" \
  --from-literal=database_url="$DB_URL" \
  --from-literal=valkey_url="$VK_URL" \
  --from-literal=session_secret="$SESSION_SECRET" \
  --dry-run=client -o yaml | "${KCTL[@]}" apply -f - >/dev/null
ok "ting-secrets updated"

# --- 7. Restart + wait for pod Ready --------------------------------------

log "Rolling deploy/ting..."
"${KCTL[@]}" rollout restart deployment/ting -n "$NS" >/dev/null
"${KCTL[@]}" rollout status deployment/ting -n "$NS" --timeout=120s >/dev/null
ok "pod Ready"

# --- 8. Migrate + seed ----------------------------------------------------

log "Running alembic migrations..."
"${KCTL[@]}" exec -n "$NS" deploy/ting -- ting migrate >/dev/null
ok "migrations at head"

log "Loading $SEED ..."
"${KCTL[@]}" exec -n "$NS" deploy/ting -- ting seed "$SEED" >/dev/null
ok "seed loaded"

# --- 9. Smoke + report ----------------------------------------------------

log "Smoke test: GET https://$HOST/healthz ..."
# -f fails on non-2xx; the regex is whitespace-tolerant.
if curl -ksSf --max-time 10 "https://$HOST/healthz" \
    | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"'; then
  ok "https://$HOST/healthz returns ok"
else
  warn "https://$HOST/healthz did not return ok yet — cert issuance can take a minute; retry shortly"
fi

cat <<EOF

──────────────────────────────────────────────────────────────────────
Bootstrap complete.

  Site:        https://$HOST/
  Summary:     https://$HOST/summary
  Healthz:     https://$HOST/healthz

  Cert issuance status (cert-manager):
    ${KCTL[@]} get certificate -n $NS

  Tail pod logs:
    ${KCTL[@]} logs -f deploy/ting -n $NS

  Generate codes (replace cohort name):
    ${KCTL[@]} exec -n $NS deploy/ting -- \\
      ting codes generate --cohort MPE-2026-spring-pilot --count 5

──────────────────────────────────────────────────────────────────────
EOF
