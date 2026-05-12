# Deployment

Ting has four deploy tiers, all sharing the same container image and
env-var-driven configuration.

| Tier | Where | Postgres / Valkey | Hostname | Cert | Use |
|---|---|---|---|---|---|
| **dev** | Anywhere with Docker | docker-compose | `localhost:8000` | none | Inner-loop development |
| **localk8s** | k3d / Rancher Desktop with Mimir | Mimir Crossplane Claims | `ting.local` | self-signed | Validate the same manifests we ship to GKE |
| **cmdbee** | GKE | Mimir Claims | `ting.cmdbee.org` | Let's Encrypt **staging** | Staging / pilot |
| **frontstate** | GKE | Mimir Claims | `ting.frontstate.org` | Let's Encrypt **production** | Production |

## Image build

`.github/workflows/image.yml` builds on every push to `main` and
publishes to `ghcr.io/siliconsaga/ting:<sha>` and `:latest`. Both tags
are public — no `imagePullSecret` is required in any cluster. **Verify
the GHCR package's visibility is set to Public** the first time it
publishes (`https://github.com/orgs/SiliconSaga/packages/container/ting/settings`).

## Mimir claims

Both tiers above `dev` use Crossplane claims served by the workspace's
Mimir component:

**Postgres** — `apiVersion: database.example.org/v1alpha1`,
`kind: PostgreSQLInstance`. Composes a Percona Postgres cluster with a
pgbouncer pooler. The composition publishes credentials in a
`<claim>-pg-user-secret` (host, port, user, password, dbname,
pgbouncer URI variants).

**Valkey** — `apiVersion: mimir.siliconsaga.org/v1alpha1`,
`kind: ValkeyCluster`. Composes an OT-Container-Kit Valkey deployment
(leader + follower). Lives in the `valkey` namespace; reach via FQDN
across namespaces.

⚠ The Valkey composition's `-master` Service has no endpoints in
the current OT-container-kit revision. Use `-leader` instead when
populating `ting-secrets`. (Reported in the design doc operator notes.)

## The `ting-secrets` Secret

The Deployment expects a `Secret` named `ting-secrets` in the `ting`
(or `ting-local`) namespace with three keys:

- `database_url` — `postgresql+psycopg://<user>:<urlencoded-pass>@<svc>:5432/<dbname>`
- `valkey_url` — `redis://<valkey-leader-svc>:6379/0`
- `session_secret` — 32+ random bytes (use `openssl rand -base64 48`)

The driver string **must** be `postgresql+psycopg://` not
`postgresql://` — the codebase pins psycopg v3.

The DB password from the Percona-issued secret can contain characters
that URL-encode (`@`, `{`, `?`, etc.). Encode before assembling the
URL — see `make` targets in the localk8s walkthrough below.

## Walkthrough: deploying to localk8s

```bash
# 1. Switch context
kubectl config use-context k3d-nordri-test

# 2. Build + import image
make build
make import

# 3. Create namespace + placeholder secret (claim outputs not ready yet)
kubectl create namespace ting-local
kubectl create secret generic ting-secrets -n ting-local \
  --from-literal=database_url='postgresql+psycopg://placeholder' \
  --from-literal=valkey_url='redis://placeholder' \
  --from-literal=session_secret="$(openssl rand -base64 48 | head -c 48)"

# 4. Apply manifests
kubectl apply -k k8s/overlays/localk8s

# 5. Wait for the PostgreSQLInstance claim to be Ready (5–15 min first time)
kubectl get postgresqlinstance ting-pg -n ting-local -w

# 6. Once Ready, populate ting-secrets with the real connection URLs.
#    The Percona composition publishes credentials in <claim>-pg-user-secret:
PG_PASS=$(kubectl get secret ting-pg-user-secret -n ting-local \
  -o jsonpath='{.data.password}' | base64 -d)
PYENC=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1], safe=''))" "$PG_PASS")
DB_URL="postgresql+psycopg://ting:${PYENC}@ting-pg-pgbouncer.ting-local.svc.cluster.local:5432/ting"
VK_URL="redis://ting-valkey-ggvmh-leader.valkey.svc.cluster.local:6379/0"
SESSION_SECRET=$(openssl rand -base64 48 | head -c 48)

kubectl create secret generic ting-secrets -n ting-local \
  --from-literal=database_url="$DB_URL" \
  --from-literal=valkey_url="$VK_URL" \
  --from-literal=session_secret="$SESSION_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl rollout restart deployment/ting -n ting-local

# 7. Migrate + seed + populate demo data
kubectl exec -n ting-local deploy/ting -- ting migrate
kubectl exec -n ting-local deploy/ting -- ting seed /app/seeds/example.yaml
kubectl exec -n ting-local deploy/ting -- ting demo populate --cohort MPE-2026-spring-pilot --count 30
```

Smoke test from the workspace root: `make smoke`.

## Walkthrough: deploying to cmdbee (GKE)

Same shape as localk8s, with three differences:

1. `kubectl config use-context gke_<project>_<zone>_<cluster>` first
2. `kubectl apply -k k8s/overlays/cmdbee` (instead of `localk8s`)
3. DNS for `ting.cmdbee.org` already resolves via cmdbee.org's wildcard
   A record at the Traefik LB — no DNS work required

The `letsencrypt-gateway-staging` ClusterIssuer signs the staging cert.
Browsers will show "untrusted cert" — that's expected for the pilot.

## Walkthrough: deploying to frontstate (production)

⚠ Gated on operator approval after the cmdbee pilot demo.

1. Apply the frontstate overlay: `kubectl apply -k k8s/overlays/frontstate`
2. Point `ting.frontstate.org` DNS at the Traefik LB IP (one-time)
3. Wait for `letsencrypt-gateway` (production) cert to issue
4. Regenerate any printed-for-distribution QR codes with
   `--base-url https://ting.frontstate.org` before envelopes ship

## CronJobs (not yet wired)

- `ting snapshot` is intended to run nightly (and ad-hoc around BoE
  meetings) via a k8s CronJob. The Job manifest isn't in the repo yet;
  add when the time-series UI lands in iteration 2.

## Uptime monitoring (not yet wired)

Kuma uptime monitoring with paging is on the post-distribution
checklist. The plan is to add it after the `5/22` backpack
distribution round when real users start hitting the URL.
