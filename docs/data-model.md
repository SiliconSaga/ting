# Data model

Quick tour of the database. Tables in dependency order; foreign keys
noted inline.

## Entity overview

```
schools ─── cohorts ─── codes ─── responses ─── questions ─── surveys ─── (back to cohorts)
                  └─ proposals ────┐
                                   ├─── pledges ── codes
                                   ├─── comments ── codes
                                   │        └─── endorsements ── codes
                  └─ bulletins
                  └─ summary_snapshots ── surveys
```

## Tables

### `schools`

The schools using Ting. Small reference table.

| Column | Type | Notes |
|---|---|---|
| `school_code` | str(3) PK | e.g. `"MPE"`, `"RVL"` — also used as the code prefix |
| `name` | text | `"Mount Pleasant Elementary"` |
| `district` | text | `"West Orange School District"` |
| `created_at` | timestamp tz | |

### `cohorts`

One *printed batch of codes* — typically one batch per school per
academic cycle. Adding a mid-year reaction-survey doesn't require a
new cohort; it just adds a survey to the existing cohort.

| Column | Type | Notes |
|---|---|---|
| `cohort_id` | UUID PK | |
| `name` | text unique | `"MPE-2026-spring-pilot"` |
| `school_code` | FK → schools | |
| `batch_number` | smallint | 1..99 |
| `description` | text | |
| `created_at` | timestamp tz | |
| `retired_at` | timestamp tz nullable | Set by `ting cohort retire <name>`. Blocks writes. |
| `expires_at` | timestamp tz nullable | Soft cutoff for writes |

UNIQUE `(school_code, batch_number)` — each batch number is unique
within a school.

### `codes`

The auth tokens distributed in envelopes.

| Column | Type | Notes |
|---|---|---|
| `code_id` | UUID PK | |
| `code_str` | text unique indexed | `"MPE01-XK7M-N3PQ"` |
| `cohort_id` | FK → cohorts | |
| `printed_at` | timestamp tz nullable | Set by `ting codes export` |
| `first_used_at` | timestamp tz nullable | Set on first `/r/<code>` redemption |
| `advocate_grade` | smallint nullable | 0=K, 1=1st, …, 12=12th |
| `created_at` | timestamp tz | |

The `code_str` is generated as `<school_code><batch_number:02d>-<4 chars>-<4 chars>`
from a no-confusion Crockford alphabet.

### `proposals`

Persistent advocacy items. Cross-cohort — a proposal like "retain
paraprofessionals" survives across spring/fall pilots.

| Column | Type | Notes |
|---|---|---|
| `proposal_id` | UUID PK | |
| `slug` | text unique indexed | `"retain-paras"` |
| `title` | text | |
| `body` | text | |
| `status` | text | `"active"`, `"archived"` |
| `created_at` | timestamp tz | |

### `surveys`

A named set of questions within a cohort. One cohort can have many
surveys (general pilot + reaction surveys + mini-polls).

| Column | Type | Notes |
|---|---|---|
| `survey_id` | UUID PK | |
| `slug` | text unique indexed | `"spring-pilot-general"` |
| `title` | text | |
| `intro` | text | Short hint shown on the survey page |
| `cohort_id` | FK → cohorts | |
| `display_order` | int | |
| `created_at` | timestamp tz | |

### `questions`

One question, of type `ranking | nps | likert`. JSONB payload carries
type-specific config (ranking has `proposal_slugs`, NPS has `subject`,
Likert has `statement`).

| Column | Type | Notes |
|---|---|---|
| `question_id` | UUID PK | |
| `slug` | text unique indexed | `"rank-priorities"` |
| `type` | text | `ranking`, `nps`, `likert` |
| `prompt` | text | The user-facing question text |
| `payload` | JSONB | Type-specific config |
| `display_order` | int nullable | Set to null to hide from rendering without losing data |
| `survey_id` | FK → surveys | |
| `created_at` | timestamp tz | |

### `responses`

One row per `(code, question)`. Updates **replace**; revisits don't
stack. The unique constraint enforces this at the DB level.

| Column | Type | Notes |
|---|---|---|
| `code_id` | FK → codes | |
| `question_id` | FK → questions | |
| `payload` | JSONB | Type-specific answer (`{"order": [...]}`, `{"score": N}`) |
| `updated_at` | timestamp tz | |

UNIQUE `(code_id, question_id)`. Implemented as a real DB constraint
*so even out-of-order writes can't double-record*.

### `comments`

Free-text discussion on a proposal.

| Column | Type | Notes |
|---|---|---|
| `comment_id` | UUID PK | |
| `proposal_id` | FK → proposals | |
| `author_code_id` | FK → codes | |
| `body` | text | |
| `created_at` | timestamp tz | |
| `hidden_at` | timestamp tz nullable | Admin soft-hide |

Per-code comment cap is enforced in app code (`max_comments_per_code`
setting, default 5).

### `endorsements`

One row per `(code, comment)` — "I agree with this comment."

| Column | Type | Notes |
|---|---|---|
| `code_id` | FK → codes | composite PK |
| `comment_id` | FK → comments | composite PK |
| `created_at` | timestamp tz | |

### `pledges`

One row per `(code, proposal)` — "I'd give $X/month + Y hrs/week to
this." Updates replace.

| Column | Type | Notes |
|---|---|---|
| `code_id` | FK → codes | composite PK |
| `proposal_id` | FK → proposals | composite PK |
| `amount_dollars` | numeric(10,2) | |
| `hours_per_week` | numeric(6,2) | |
| `updated_at` | timestamp tz | |

### `bulletins`

Admin broadcast posts visible to all codes in active cohorts.

| Column | Type | Notes |
|---|---|---|
| `bulletin_id` | UUID PK | |
| `body` | text | |
| `posted_at` | timestamp tz | |
| `posted_by` | text | Admin handle (free-text, no auth surface yet) |

### `summary_snapshots`

Time-series capture of `build_summary()` output. Written by
`ting snapshot`.

| Column | Type | Notes |
|---|---|---|
| `snapshot_id` | UUID PK | |
| `cohort_id` | FK → cohorts | |
| `survey_id` | FK → surveys | |
| `captured_at` | timestamp tz | |
| `payload` | JSONB | The full summary dict — same shape `/summary` renders from |

UNIQUE `(cohort_id, survey_id, captured_at)`.

### `metrics_events`

Thin analytics events log (currently only `survey_completed` is
written; older event types like `pledge_added` etc. were dropped when
we removed the Mark-Complete button).

| Column | Type | Notes |
|---|---|---|
| `event_id` | UUID PK | |
| `event` | text | `"survey_completed"`, etc. |
| `code_id` | FK → codes nullable | |
| `duration_seconds` | int nullable | |
| `recorded_at` | timestamp tz | |

## Privacy guarantees encoded in the schema

- **No IPs.** Anywhere. The only IP-derived value used at runtime is
  an HMAC hash stored in Valkey with a TTL — never persisted to disk.
- **No PII.** No name, no email, no phone, no address. The closest we
  come is `codes.advocate_grade` which records *what grade-level your
  child attends*, optional and grade-only (no name, no class).
- **One step removed from identity.** The mapping from envelope to
  code to family is *not retained* by the operators — codes are
  printed, sealed, and distributed without recording which envelope
  went to whom.

## Aggregation semantics

`summary_service.build_summary(cohort_name, survey_slug, grade_filter)`
returns a single dict with:

- **`priorities`** — list of `{prompt, slug, n, bars[{slug, score,
  max_possible, normalized}]}` per ranking question. `normalized` is
  out of 100 absolute (100 = every voter put this first), not out of
  the leader.
- **`nps`** — list of `{prompt, slug, subject, n, detractors, passives,
  promoters, nps}` per NPS question.
- **`likert`** — list of `{prompt, slug, statement, counts, n, mean,
  agree_pct}` per Likert question. `counts` is a `dict[str, int]`
  keyed `"1".."5"` (JSON-safe).
- **`pledges`** — totals per proposal: `{slug, title, dollars_per_month,
  hours_per_week, n}`.
- **`top_comments`** — top 5 system-wide endorsed comments.
- **`n_respondents`** — distinct codes with any response.

The `/summary` route caches this in Valkey for 60 s.

## Time-series

`summary_snapshots` rows are written by `ting snapshot`. Querying them
to render trend lines is iteration-2 work — the data is being captured
now so it exists when we build the UI.
