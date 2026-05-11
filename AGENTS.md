# Ting — Agent Guidance

Tier-3 component in the realm-siliconsaga ecosystem. Parent advocacy
pilot per the upstream
[design doc](https://github.com/SiliconSaga/yggdrasil/blob/main/docs/plans/2026-05-10-ting-pilot-design.md)
and [implementation plan](https://github.com/SiliconSaga/yggdrasil/blob/main/docs/plans/2026-05-10-ting-pilot-plan.md).

## Key Commands

- `ws test ting` — pytest unit + integration suite
- `ws lint ting` — ruff
- `./scripts/ting --help` — admin operations (seed, codes, cohort,
  bulletin, report, healthcheck, migrate, dev)

## Local Development

Use the dev tier — Docker only, no homelab dependency. See
[`README.md`](README.md) Quickstart. The dev tier brings up Postgres 16
and Valkey 7 in containers via `docker compose`; the app runs locally
via `uvicorn` with hot reload.

## Deployment

Four kustomize overlays under `k8s/overlays/`:

- `dev` — local Docker, no k8s
- `localk8s` — Rancher Desktop / k3d with Mimir
- `cmdbee` — GKE staging (canonical) — `ting.cmdbee.org`
- `frontstate` — GKE production — gated on manual approval post-pilot-demo

## Conventions

- Branch naming: `feat/<slug>` for new work, `fix/<slug>` for bug
  fixes, `chore/<slug>` for non-code maintenance
- Commits use `ws commit ting <bodyfile>` from the workspace root
- Co-Authored-By trailer is added by `ws commit` automatically
