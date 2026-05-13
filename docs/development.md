# Development

## Prerequisites

- **Docker** (any flavor — Docker Desktop, OrbStack, Rancher Desktop)
- **Python 3.12+** (3.13 is fine; the Dockerfile pins 3.12 for the
  built image regardless)
- **make** — the inner dev loop hangs off Makefile targets
- *(Optional)* `kubectl` + a local k8s cluster (k3d / Rancher Desktop)
  if you want to exercise the `localk8s` tier with real Mimir claims

No homelab dependency. The *dev tier* is just Docker.

## First-time setup (dev tier)

```bash
cd components/ting
cp .env.example .env

# Bring up Postgres 16 + Valkey 7 in containers
docker compose up -d

# Python env
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Create schema + load the example seed
./scripts/ting migrate
./scripts/ting seed seeds/example.yaml

# Boot the app with hot reload
./scripts/ting dev
```

Open <http://localhost:8000>. Enter any code from
`ting codes generate --cohort example-pilot --count 3` to log in.

## Running tests

```bash
# From workspace root: the auto-allowed path through the ws CLI.
ws test ting     # = pytest tests/unit tests/integration -v
ws lint ting     # = ruff check src/ tests/
```

Both also work directly:

```bash
make test
make lint
```

Integration tests spin up an ephemeral Postgres in a container via
`testcontainers-postgres`. CI uses a service container instead — see
`.github/workflows/ci.yml`.

## Make targets (inner dev loop)

The full list is in `make help`. The frequent ones:

| Target | What it does |
|---|---|
| `make test` / `make lint` | pytest / ruff via the `ws` adapter |
| `make build` | `docker build -t ting:dev .` |
| `make import` | `build` + `k3d image import` into `nordri-test` |
| `make deploy` | `import` + `rollout restart` + wait for Ready |
| `make cycle` | `deploy` + clear Valkey summary cache (typical "I changed code, see it" loop) |
| `make full` | `deploy` + full data reset (wipe + seed + 30 demo respondents + cache clear) |
| `make wipe` | Drop + recreate the schema (destructive) |
| `make seed` | Load `seeds/example.yaml` |
| `make demo` | Generate `DEMO_COUNT=30` codes with synthetic responses |
| `make reseed` | `wipe` + `seed` + `demo` + cache clear (data-only reset) |
| `make codes` | Generate 3 fresh codes for browser testing |
| `make smoke` | Hit `/healthz`, `/`, `/summary` against the local LB |
| `make logs` | Tail the ting pod's logs |
| `make shell` | Drop into a Python REPL inside the pod |
| `make psql` | Open psql against the in-cluster Postgres |

Variables are overridable, e.g. `make demo DEMO_COUNT=100`,
`make codes COHORT=MPE-2026-fall`.

## When to use `ws exec` vs `make`

If you're in `components/ting/` and want to run something quick: `make
<target>`. If you're at the workspace root and want to do the same:
`ws exec ting <cmd>`. The two are equivalent — `ws exec` cd's into the
component dir and runs the command. (The `ws test` / `ws lint`
adapter-driven forms above are slightly different — they go through
the realm's adapter YAML, which auto-allowlists them.)

## Editing the data model

1. Edit `src/ting/models/*.py`
2. Generate a migration: `alembic revision --autogenerate -m "your message"`
   (requires a running Postgres reachable at `TING_DATABASE_URL`)
3. Inspect `migrations/versions/<hash>_<message>.py` — autogen is good
   but not perfect; review carefully for unintended drops
4. Apply: `./scripts/ting migrate` (or in a deploy: `ting migrate` in
   the pod)
5. Update tests if shape changed

The current baseline is `migrations/versions/6d7670f9f395_baseline_v2_schools_surveys.py`
(post the schools/surveys/snapshots refactor). For the dev tier you
can always `make wipe && make seed` to drop + recreate.

## Editing the seed YAML

Schema reference: `seeds/schema.md`. Validate with `--dry-run`:

```bash
./scripts/ting seed --dry-run seeds/example.yaml
```

Re-run without `--dry-run` to apply. Proposals / surveys / questions
upsert by slug; the cohort row upserts by name. Bulletins always
*append* — if you re-seed and your bulletin keeps growing, that's why.

## Committing

The workspace mandates `ws commit`, never raw `git add` / `git commit`.
Write a bodyfile under `.commits/` (gitignored) and run from yggdrasil
root:

```bash
bash scripts/ws commit ting .commits/<descriptive-name>.md
```

The bodyfile's frontmatter declares the commit message and the file
list (`add:` and `remove:`). Co-Authored-By trailers are appended
automatically.
