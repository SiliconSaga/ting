# Ting — Parent Advocacy Pilot

Structured-input parent advocacy site. Code-based auth, anonymous-but-
verified, survey (ranking + NPS + Likert) + endorsable comments +
pledges.

Design and implementation plan upstream in the yggdrasil workspace:

- [Design](https://github.com/SiliconSaga/yggdrasil/blob/main/docs/plans/2026-05-10-ting-pilot-design.md)
- [Implementation plan](https://github.com/SiliconSaga/yggdrasil/blob/main/docs/plans/2026-05-10-ting-pilot-plan.md)
- Public framing: [`schools/next-year.md`](https://github.com/SiliconSaga/schools/blob/main/next-year.md)

## Quickstart (dev tier — no k8s)

Requires Docker + Python 3.12.

```bash
cp .env.example .env
docker compose up -d
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
./scripts/ting migrate
./scripts/ting seed seeds/example.yaml
./scripts/ting dev
```

Open <http://localhost:8000>.

## Other deploy tiers

- `localk8s` — k3d / Rancher Desktop with Mimir installed; apply
  `k8s/overlays/localk8s`
- `cmdbee` — GKE staging (`ting.cmdbee.org`); apply
  `k8s/overlays/cmdbee`
- `frontstate` — GKE production (`ting.frontstate.org`); apply
  `k8s/overlays/frontstate` (gated on operator approval post-demo)

See [`docs/operations.md`](docs/operations.md) for the deploy walkthrough.

## Testing

```bash
ws test ting          # pytest unit + integration
ws lint ting          # ruff
```

## License

MIT — see [LICENSE](LICENSE).
