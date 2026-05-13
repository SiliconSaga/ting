# `ting` CLI reference

The `ting` CLI handles all admin operations: schema migrations, seed
loading, code generation, cohort lifecycle, bulletins, snapshots, and
the local dev server. It's a Typer app exposed as the `ting`
console-script (created by `pip install -e '.[dev]'`).

## Which tier are you targeting?

The CLI has **no idea which deployment tier it's talking to** — it
just connects to whatever `TING_DATABASE_URL` + `TING_VALKEY_URL`
point at. Three common invocation forms, three different databases:

| Form | Target | When to use |
|---|---|---|
| **`./scripts/ting <cmd>`** (from this component dir) | Dev tier — your laptop's docker-compose Postgres | Local development; the dev-server flow |
| **`make codes` / `make demo` / etc.** (from `components/ting/`) | Whatever cluster your kubectl context points at — defaults to `k3d-nordri-test` | Operator commands against a running k8s deploy |
| **`kubectl exec ... -- ting <cmd>`** | The specific cluster + namespace you pass | Production / staging GKE tiers |

The `./scripts/ting` wrapper has a guard: if you run it without
`.env` or `TING_*` env vars set, it prints a hint explaining the
three options. (You're probably hitting that if you got
`command not found: ting` or a `ValidationError: 3 validation errors
for Settings`.)

---

## Quick reference: "I want to…"

| Goal | Command |
|---|---|
| Generate 5 fresh codes for browser testing | `ting codes generate --cohort MPE-2026-spring-pilot --count 5` |
| Print 400 codes for backpack distribution | `ting codes export --cohort MPE-2026-spring-pilot --format html --base-url https://ting.frontstate.org --out codes.html` then open in browser → print to PDF |
| Wipe + reseed the local DB after schema edits | `ting migrate` then `ting seed seeds/example.yaml` (in the pod, or against the dev tier) |
| Load 30 fake respondents to exercise widgets | `ting demo populate --cohort MPE-2026-spring-pilot --count 30` |
| Run dev server with hot reload | `ting dev` |
| Capture a time-series snapshot | `ting snapshot` |
| Generate the BoE one-pager | `ting report --cohort MPE-2026-spring-pilot --out summary.html` |
| Retire a cohort (reads ok, writes blocked) | `ting cohort retire MPE-2026-spring-pilot` |
| Post a broadcast to all codes in active cohorts | `ting bulletin post --body "..." --as cervator` |

---

## Full surface

```text
ting healthcheck                       # DB + Valkey check, prints version
ting migrate [direction]               # up (default) | head | down
ting dev [--host H] [--port P] [--no-reload]

ting seed <file.yaml> [--dry-run]

ting school add --code MPE --name "Mount Pleasant Elementary" --district "..."

ting cohort retire <name>

ting survey add --cohort <name> --slug <slug> --title "..."

ting codes generate --cohort <name> --count N
ting codes export   --cohort <name>
                   [--format csv|html]            # default csv
                   [--base-url <url>]              # url encoded into QR / printable
                   [--only-unprinted]              # skip codes already exported
                   [--out <path>]                  # default stdout

ting bulletin post --body "..." --as <admin-handle>

ting report --cohort <name> [--out <path>] [--base-url <url>]
                                            # fetches /summary?print=true via loopback

ting snapshot                              # writes a row in summary_snapshots
                                           # for each non-empty (cohort, survey)

ting demo populate --cohort <name> --count N
                                           # generates N codes + synthesizes responses
                                           # across all surveys, with realistic
                                           # distributions
```

---

## Notes by command

### `ting codes generate`

Code format: `<school_code><batch_number padded to 2 digits>-XXXX-XXXX`,
e.g. `MPE01-XK7M-N3PQ`. The prefix is *derived from the cohort row* —
you don't pass it. Looks up the cohort's `school_code` and
`batch_number`, composes the prefix automatically.

The 8-char body uses a Crockford-style alphabet (no `0/1/I/L/O`) to
minimize manual-entry errors. 23⁸ ≈ 78 billion combinations per
batch — plenty.

### `ting codes export`

`--format csv` emits one column (`code_str`) for mail-merge into
Word/Pages. `--format html` emits a self-contained printable A4/Letter
page with one cell per code: inline-SVG QR code, the full URL
(`<base_url>/r/<code>?src=qr`), and the code in large monospace as a
manual-entry backup. Open in a browser, print to PDF or paper.

`--only-unprinted` filters to codes whose `printed_at` is null;
running `codes export` flips that field, so re-running with the flag
gives you only newly-generated codes. Useful for incremental
distribution rounds.

### `ting seed`

Idempotent for `schools`, `cohort`, `proposals`, `surveys`, `questions`
(upsert by slug/name/code). **Bulletins append** on every run —
re-running creates fresh bulletin rows. `--dry-run` validates the YAML
shape without writing.

Seed YAML schema lives in [`../seeds/schema.md`](../seeds/schema.md);
see also [data-model.md](data-model.md) for the underlying tables.

### `ting demo populate`

Generates `N` codes through the normal `generate_codes` path, then
synthesizes responses for each one:

- **Rankings** — shuffled proposal slugs with mild positional bias
- **NPS** — Gaussian-ish distribution skewed slightly *negative* for
  governance bodies (BoE, district admin), slightly *positive* for the
  PTA and the site itself
- **Likert** — bell around 3.5 (σ ≈ 1)
- **Comments** — ~30 % of codes post a canned comment
- **Endorsements** — each code endorses 0–3 existing comments
- **Pledges** — ~30 % of codes pledge; exponentially distributed
  dollars (5–100/mo) and hours (0.5–4/wk)

The synthetic responses use the same DB writes a real user's actions
would trigger, so they exercise the production code paths.

### `ting snapshot`

Idempotent per (cohort, survey) per minute — running twice in quick
succession is safe; the second call skips. Designed to run on a
schedule (k8s CronJob) so the `summary_snapshots` table grows over
time. The time-series viewer that consumes these is iteration-2 work
(see Thalamus note on session-aware analytics).

### `ting report`

Fetches `/summary?cohort=<name>&survey=<first>&print=true` via
loopback HTTP and saves the response HTML. The print-mode CSS forces
a light, low-contrast, image-free layout for photocopier output.
Operator workflow: `ting report ... --out summary.html` → open in
browser → print-to-PDF → email to BoE members ahead of the meeting.

---

## Operator quick-start examples

**Fresh local dev setup**

```bash
make build && make deploy        # build + push image into k3d + roll
make reseed                      # wipe + seed example.yaml + populate 30 demo codes + clear cache
make codes                       # print 3 fresh codes for browser testing
```

**Generate the production printed batch**

```bash
# In the live cmdbee or frontstate pod:
ting codes generate --cohort MPE-2026-spring-pilot --count 400
ting codes export --cohort MPE-2026-spring-pilot \
  --format html \
  --base-url https://ting.frontstate.org \
  --only-unprinted \
  --out /tmp/codes.html
# kubectl cp the file out, open in browser, print
```

**End the cohort and start the next year**

```bash
ting cohort retire MPE-2026-spring-pilot
# edit seeds/<new>.yaml, then:
ting seed seeds/MPE-2026-fall.yaml
ting codes generate --cohort MPE-2026-fall --count 400
```
