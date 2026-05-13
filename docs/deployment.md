# Deployment

Ting has four deploy tiers, all sharing the same container image and
env-var-driven configuration.

| Tier | Where | Postgres / Valkey | Hostname | Cert | Use |
|---|---|---|---|---|---|
| **dev** | Anywhere with Docker | docker-compose | `localhost:8000` | none | Inner-loop development |
| **localk8s** | k3d / Rancher Desktop with Mimir | Mimir Crossplane Claims | `ting.local` | self-signed | Validate the same manifests we ship to GKE |
| **cmdbee** | GKE | Mimir Claims | `ting.cmdbee.org` | Let's Encrypt **staging** | Staging / pilot |
| **frontstate** | GKE | Mimir Claims | `ting.frontstate.org` | Let's Encrypt **production** | Production |

## One-time vs recurring

Most of the apparent complexity of a remote-tier deploy is **one-time per
environment**. After the first run, ongoing deploys are a single command.

**One-time per environment** (run by `bootstrap-<tier>`):
- Create the namespace
- Create a placeholder `ting-secrets` Secret (preserves any existing
  `session_secret` on re-runs so live sessions don't invalidate)
- Apply the kustomize overlay
- Wait 5–15 min for the Mimir `PostgreSQLInstance` claim to provision
- Read the claim's published credentials, build the real `database_url`
  and `valkey_url`, update `ting-secrets`
- Run `ting migrate` and `ting seed seeds/example.yaml` once

**Recurring after each push to `main`** (run by `deploy-<tier>`):
- `kubectl apply -k overlays/<tier>` (no-op when manifests unchanged)
- `kubectl rollout restart deployment/ting` — picks up the new
  `ghcr.io/siliconsaga/ting:latest` because the Deployment uses
  `imagePullPolicy: Always`
- `ting migrate` (idempotent at head)
- Bust the Valkey summary cache

**On-demand operator commands** (any time, against any tier):
- `ting codes generate --cohort … --count N` — print a new batch
- `ting codes export --cohort … --format html --base-url https://…` — printable sheet
- `ting bulletin post --body "…"` — broadcast
- `ting cohort retire <name>` — close out a batch
- `ting demo populate --cohort … --count N` — synthesize demo data (dev only)

## Image build

`.github/workflows/image.yml` builds on every push to `main` and publishes
to `ghcr.io/siliconsaga/ting:<sha>` plus `:latest`. The package needs to be
**Public** in GHCR for clusters to pull without an `imagePullSecret`.
First-time visibility flip:
<https://github.com/SiliconSaga/ting/pkgs/container/ting> → "Package
settings" → Change visibility → Public.

The build uses `docker/setup-buildx-action@v3` to enable GHA cache export;
without that step the default Docker driver rejects `cache-to: type=gha`.

## Mimir claims

Both k8s tiers use Crossplane claims served by the workspace's Mimir
component:

**Postgres** — `apiVersion: database.example.org/v1alpha1`,
`kind: PostgreSQLInstance`. Composes a Percona Postgres cluster with a
pgbouncer pooler. Credentials are published in `<claim>-pg-user-secret`.

**Valkey** — `apiVersion: mimir.siliconsaga.org/v1alpha1`,
`kind: ValkeyCluster`. Composes an OT-Container-Kit Valkey deployment
(leader + follower). Lives in the `valkey` namespace; reach via FQDN
across namespaces.

⚠ The Valkey composition's `-master` Service has no endpoints in the
current OT-container-kit revision. Use `-leader` instead when populating
`ting-secrets`. The bootstrap script discovers the leader Service name
dynamically (it has a generated suffix like `ting-valkey-ggvmh-leader`).

## The `ting-secrets` Secret

The Deployment expects a `Secret` named `ting-secrets` in the deployment
namespace with three keys:

- `database_url` — `postgresql+psycopg://<user>:<urlencoded-pass>@<svc>:5432/<dbname>`
- `valkey_url` — `redis://<valkey-leader-svc>:6379/0`
- `session_secret` — 32+ random bytes (use `openssl rand -base64 48`)

The driver string **must** be `postgresql+psycopg://` not `postgresql://`
— the codebase pins psycopg v3. Passwords can contain `@`, `{`, `?` etc.
and must be URL-encoded before being inserted into the URI.

The bootstrap script handles all of this. The recipe below is what it does
internally; only run by hand if you're debugging.

## Walkthrough: cmdbee (the typical GKE path)

```bash
# Once per cluster — usually ~10 minutes wall-clock (most of it waiting
# for the Mimir Postgres claim to finish provisioning).
kubectl config use-context gke_<project>_<zone>_<cluster>
cd components/ting
make bootstrap-cmdbee
```

When the script finishes, `https://ting.cmdbee.org/healthz` is live (after
~30s of cert-manager issuing the staging cert).

Subsequent deploys, after any push to `main` has produced a new image at
`ghcr.io/siliconsaga/ting:latest`:

```bash
make deploy-cmdbee
```

That's it. Both targets are idempotent and safe to re-run.

### Knobs you can override

```bash
# Different context:
make bootstrap-cmdbee KCTX=gke_other-project_zone_cluster

# Skip the smoke / skip migrate (during noisy debug sessions):
SKIP_SMOKE=1 SKIP_MIGRATE=1 make deploy-cmdbee
```

## Walkthrough: localk8s (k3d / Rancher Desktop with Mimir)

```bash
kubectl config use-context k3d-nordri-test
cd components/ting
make full   # build + k3d import + deploy + wipe + seed + 30 demo respondents
```

The localk8s flow imports a locally-built image into k3d; it does **not**
go through GHCR. That's the difference from the GKE tiers.

For the manual long-form walkthrough (useful when debugging Mimir provision
issues), see the bootstrap script `scripts/bootstrap-cmdbee.sh` — its
inline comments explain every step. localk8s has the same shape, with
`KCTX=k3d-nordri-test NS=ting-local OVERLAY=localk8s` substitutions.

## Walkthrough: frontstate (production)

⚠ Gated on operator approval after the cmdbee pilot demo.

Same shape as cmdbee, but the overlay differs (prod cert issuer, prod
hostname). When ready:

1. Point `ting.frontstate.org` DNS at the Traefik LB IP (one-time)
2. Add a `scripts/bootstrap-frontstate.sh` (copy of `bootstrap-cmdbee.sh`
   with the overlay path pointed at `k8s/overlays/frontstate` and HOST
   default flipped to `ting.frontstate.org`) plus a matching `make
   bootstrap-frontstate` target. The current scripts hardcode the
   cmdbee overlay; a frontstate variant is a deliberate, separate
   artifact rather than an env-var override so the production path is
   visible in `git diff` and in `make help`.
3. Regenerate any printed-for-distribution QR codes with
   `--base-url https://ting.frontstate.org` before envelopes ship

## SDLC automation roadmap

The current flow is "push lands at GHCR; operator runs `make
deploy-cmdbee`." Two longer-term improvements, both ready to land when
needed:

**GitHub Actions deploy job.** A `.github/workflows/deploy.yml` triggered
on push to main / on tag could run `make deploy-cmdbee` against a
kubeconfig pulled from a GH Actions Secret. Pros: zero operator-side work
after merge. Cons: requires a kubeconfig credential stored in GH; a leak
gives the world the cluster. Worth doing for cmdbee (low-risk staging)
once we have a dedicated CI service-account; not appropriate for
frontstate (production should require explicit human action).

**ArgoCD (the workspace's intended direction).** The k8s cluster watches
this repo's `k8s/overlays/<tier>` paths and applies any changes
automatically. No CI-side credentials. The workspace already runs ArgoCD
for the platform layer (nidavellir's app-of-apps); adding ting is a
single `Application` manifest in nidavellir. Listed as iteration-1.5 in
the design plan; expected before the production cutover.

## CronJobs (not yet wired)

- `ting snapshot` is intended to run nightly (and ad-hoc around BoE
  meetings) via a k8s CronJob. Manifest will land alongside the
  time-series UI in iteration 2.

## Uptime monitoring (not yet wired)

Kuma uptime monitoring with paging is on the post-distribution checklist
— added after the `5/22` backpack distribution round when real users
start hitting the URL.
