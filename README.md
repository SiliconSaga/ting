# Ting — Parent Advocacy Pilot

<p align="center">
  <img src="assets/TingBackground.png" alt="A Viking thingstead: rune stones on a grassy hill above a harbor with longships, at sunrise" width="720">
</p>

> *From Old Norse <em>þing</em> — the open-air assemblies of early
> medieval Scandinavia where free people gathered to debate and decide.
> The most famous is Iceland's Althing (Alþingi), established 930 CE,
> one of the oldest continuously functioning legislative bodies in the
> world.*

Ting is a structured-input parent-advocacy site for one school's
worth of families. It channels the energy that already shows up at PTA
and Board of Education meetings into a form the board (and everyone
else) can read on one page.

- **Anonymous but verified** — every voter has a code from a sealed
  envelope, never an account; no IPs, no emails, no PII
- **Forced prioritization** — ranking, NPS, agreement scales; no
  "everything is important"
- **Public aggregate** — survey results live at `/summary` for anyone
  to read; no entry can be traced back to an envelope or a person

## Quickstart (dev tier — no k8s needed)

Requires Docker + Python 3.12+.

```bash
cp .env.example .env
docker compose up -d                # postgres + valkey in containers

python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

./scripts/ting migrate
./scripts/ting seed seeds/example.yaml
./scripts/ting demo populate --cohort MPE-2026-spring-pilot --count 30
./scripts/ting dev
```

Open <http://localhost:8000>. Generate a code to log in:

```bash
./scripts/ting codes generate --cohort MPE-2026-spring-pilot --count 1
```

## Other deploy tiers

| Tier | Where | Hostname |
|---|---|---|
| `dev` | Docker only, no k8s | `localhost:8000` |
| `localk8s` | k3d / Rancher Desktop with Mimir | `ting.local` |
| `cmdbee` | GKE staging | `ting.cmdbee.org` |
| `frontstate` | GKE production | `ting.frontstate.org` |

See [`docs/deployment.md`](docs/deployment.md) for the full walkthrough
including Mimir Crossplane claims and the `ting-secrets` Secret shape.

## Developer docs

- [`docs/`](docs/) — start with [`docs/index.md`](docs/index.md)
- [`docs/cli.md`](docs/cli.md) — every `ting` subcommand with examples
- [`docs/development.md`](docs/development.md) — local dev, Make
  targets, ws CLI, editing the data model
- [`docs/deployment.md`](docs/deployment.md) — the four tiers, Mimir,
  GHCR
- [`docs/data-model.md`](docs/data-model.md) — schema tour, privacy
  guarantees, aggregation semantics

Upstream in the workspace:

- [Design doc](https://github.com/SiliconSaga/yggdrasil/blob/main/docs/plans/2026-05-10-ting-pilot-design.md)
  — the *why* and the tradeoffs
- [Implementation plan](https://github.com/SiliconSaga/yggdrasil/blob/main/docs/plans/2026-05-10-ting-pilot-plan.md)
  — the *how*

## Testing

```bash
ws test ting           # = pytest tests/unit tests/integration -v
ws lint ting           # = ruff check src/ tests/
```

Or `make test` / `make lint` from inside `components/ting/`.

## Contributing

Use `ws commit` (never raw `git add`/`git commit`) — see
[`docs/development.md`](docs/development.md#committing).

## License

MIT — see [`LICENSE`](LICENSE).
