# Seed YAML schema

Reference for the YAML format that `ting seed <file>` accepts.

The loader is idempotent for `schools`, `cohort`, `proposals`,
`surveys`, and `questions` (upsert by their slug/name/code).
**Bulletins always append** on every run.

## Top-level keys

```yaml
schools: [...]      # optional list, but at least one school must exist
                    # before the cohort is created
cohort: {...}       # exactly one cohort per seed file
surveys: [...]      # list; each survey contains its own questions
proposals: [...]    # cross-cohort, persistent
bulletins: [...]    # appended on every seed run
```

## Schools

```yaml
schools:
  - code: MPE                                # 3 chars, used as code prefix
    name: Mount Pleasant Elementary
    district: West Orange School District
```

## Cohort

Exactly one per seed file. The `school_code` must match a school in
the `schools` block (or pre-existing in the DB).

```yaml
cohort:
  name: MPE-2026-spring-pilot
  description: First pilot cohort
  school_code: MPE
  batch_number: 1                            # 1..99, unique per school
  expires_at: 2027-08-31T23:59:59Z           # optional; null = open-ended
```

## Surveys

A list. Each survey carries its own questions.

```yaml
surveys:
  - slug: spring-pilot-general
    title: General priorities and trust
    intro: A quick read on how families are feeling.
    display_order: 1
    questions:
      - slug: rank-priorities
        type: ranking
        prompt: Rank these in order of importance to your family
        display_order: 1
        payload:
          proposal_slugs: [retain-paras, hvac-maintenance, ...]
          pick_top_n: null                   # null = rank all; integer = top-N
          required: true

      - slug: nps-boe
        type: nps
        prompt: How likely are you to recommend the Board of Education to other parents?
        display_order: 2
        payload:
          subject: the Board of Education

      - slug: agree-supp-funding
        type: likert
        prompt: How strongly do you agree?
        display_order: 3
        payload:
          statement: The school should accept supplemental community funding to retain positions, where legally permitted.
```

### Question types

| Type | Required `payload` keys | Optional |
|---|---|---|
| `ranking` | `proposal_slugs` (list of proposal slugs) | `pick_top_n` (int), `required` (bool) |
| `nps` | `subject` (str) | — |
| `likert` | `statement` (str) | — |

## Proposals

Cross-cohort, persistent. Survives spring → fall → next year.

```yaml
proposals:
  - slug: retain-paras
    title: Retain paraprofessionals in-house
    body: Retain in-house staffing instead of outsourcing.
    status: active                           # "active" or "archived"
```

## Bulletins

Always appended on each `ting seed` run. Use to send a message to all
codes in active cohorts.

```yaml
bulletins:
  - body: Welcome to the example pilot.
    posted_by: example-admin
```

## Validation

```bash
ting seed --dry-run seeds/your-file.yaml
```

Reports schema errors without writing. Then re-run without `--dry-run`
to apply.
