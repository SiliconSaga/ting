# Ting — Developer Documentation

<p align="center">
  <img src="../assets/TingBackground.png" alt="A Viking thingstead: rune stones on a grassy hill above a harbor with longships, at sunrise" width="640">
</p>

Ting is a structured-input parent-advocacy site. Code-based auth,
anonymous-but-verified, survey + endorsable comments + pledges, public
aggregate results.

The site itself lives at `/` (landing), `/survey` (after code redemption),
`/summary` (public results), `/cohort/<name>` (cohort overview),
`/about`, `/privacy`. This `docs/` directory is for developers and
operators of the platform.

## Where to start

| You are… | Read |
|---|---|
| **Running this locally for the first time** | [development.md](development.md) — Docker compose, venv, `make` shortcuts |
| **Looking for a specific `ting` CLI command** | [cli.md](cli.md) — the full reference (codes, seed, demo, snapshot…) |
| **Deploying to a real cluster** | [deployment.md](deployment.md) — the four tiers, Mimir claims, GHCR |
| **Trying to understand the data shape** | [data-model.md](data-model.md) — schools, cohorts, surveys, responses, the lot |
| **Curious about the *why* / design tradeoffs** | [Design doc upstream in yggdrasil](https://github.com/SiliconSaga/yggdrasil/blob/main/docs/plans/2026-05-10-ting-pilot-design.md) |
| **Curious about the implementation roadmap** | [Implementation plan upstream](https://github.com/SiliconSaga/yggdrasil/blob/main/docs/plans/2026-05-10-ting-pilot-plan.md) |

## What lives where in the repo

```
components/ting/
├── README.md              ← public-facing "what is this + how do I run it"
├── Makefile               ← inner dev loop (make help)
├── docker-compose.yml     ← dev tier: postgres + valkey
├── Dockerfile             ← multi-stage container build
├── pyproject.toml         ← dependencies
├── alembic.ini
├── docs/                  ← this directory
├── assets/                ← source images (logo, background) for re-export
├── seeds/
│   ├── example.yaml       ← ships with the repo; used by `ting seed`
│   └── schema.md          ← seed YAML format reference
├── scripts/
│   └── ting               ← bash wrapper for the Python CLI
├── src/ting/
│   ├── app.py             ← FastAPI factory + exception handlers
│   ├── cli.py             ← Typer entry point
│   ├── config.py          ← Pydantic settings (env-var driven)
│   ├── codes.py, auth.py, ratelimit.py, valkey.py, db.py, aggregation.py
│   ├── models/            ← SQLAlchemy ORM (one file per table)
│   ├── routes/            ← FastAPI routers: public, survey, summary
│   ├── services/          ← seed_loader, code_service, summary_service
│   ├── templates/         ← Jinja
│   └── static/            ← CSS, htmx/alpine/sortable, img/
├── migrations/            ← Alembic versions
├── k8s/
│   ├── base/              ← namespace + deployment + service + Mimir claims + Gateway HTTPRoute
│   └── overlays/{localk8s,cmdbee,frontstate}
└── tests/
    ├── unit/
    ├── integration/       ← testcontainers-postgres
    └── e2e/               ← KUTTL manifest tests
```

## License

MIT — see [`LICENSE`](../LICENSE).
