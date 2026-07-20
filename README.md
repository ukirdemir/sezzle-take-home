# Sezzle Shopper Support Assistant

## How to run it

```
pip install anthropic python-dotenv
cp .env.example .env   # then fill in the real ANTHROPIC_API_KEY
```

If `./tmp` still exists (first checkout only), lay out the raw files first:

```
bash scripts/bootstrap_layout.sh
```

Reproduce this project's two required runs (each is a real, billed API call):

```
python3 run_cases.py cases/golden_visible.jsonl answers_v1.jsonl --transcripts-dir transcripts/v1
python3 run_cases.py cases/golden_visible.jsonl answers_final.jsonl --transcripts-dir transcripts/final
```

Grade either run against its expected route / must_include / must_not_include checks:

```
python3 scripts/grade_cases.py cases/golden_visible.jsonl answers_v1.jsonl
python3 scripts/grade_cases.py cases/golden_visible.jsonl answers_final.jsonl
```

An 8-case hostile-input set (unauthorized order access, nonexistent order IDs,
fee-waiver demands, prompt-injection attempts) lives in `cases/hostile.jsonl`
and runs/grades the same way, against `answers_hostile.jsonl` /
`transcripts/hostile/`. See `ITERATION.md` for what changed between the v1 and
final runs, grouped by root cause rather than per-case (to be honest, it is done to satisfy my curiosity).

## How the AI is directed

Three files at the repo root steer the model, at different layers — all
already exist here, see them directly rather than duplicating their content:
- `system_prompt.md` — the production system prompt sent to the shopper-facing
  model on every case (grounding, escalation, anti-injection rules).
- `tool_schemas.json` — the 4 tools the model can call (`get_orders`,
  `get_order_detail`, `get_policy`, `escalate_to_human`), including the
  per-tool descriptions and enums that shape which tool it picks and how.
- `CLAUDE.md` — steers the AI coding assistant that builds/maintains this
  repo (setup, file layout, locked decisions), not the shopper-facing model.

`PROMPTS.md` is the append-only log of the actual prompts used to direct
Claude Code through this build — not something the model reads at runtime,
but the record of how the human directed the AI coding assistant.

## What's honestly unfinished

- **Single model, not tiered.** Every case runs on `claude-sonnet-5` with
  thinking disabled. The tiered design (cheap model for common single-tool
  cases, escalate to a larger model for `both`/failed-validation cases) is
  documented as the intended production shape for the 100k/day, ~$50/day
  budget (Locked Decision #3) but is **not implemented** in this harness.
- **Prompt caching is documented but not wired up.** DECISIONS.md #3 describes
  the 12 policy docs as "sent once and marked for prompt caching." In the
  actual code, policy text is fetched on demand per `get_policy` call, and
  `run_cases.py` never sets `cache_control` anywhere in the API request. The
  cost-saving mechanism described in the decision record doesn't exist yet.
- **The keyword/topic pre-classifier described in DECISIONS.md #2 doesn't
  exist.** The doc describes a deterministic safety net that flags hardship,
  fraud, and decline-reason questions for escalation independent of the
  model's tool choice. The only structural guardrail actually implemented is
  `validate_output`'s post-hoc regex check for forbidden phrases once the
  model has already claimed the `escalate` route.
- **One known-open case in the visible set (v06).** After fixing the routing
  bug (dispute questions weren't reliably calling `escalate_to_human`), the
  fix introduced a new, smaller issue: the escalation reply now sometimes
  omits policy detail (filing windows, pause-during-investigation) it had
  already fetched. Routing/authorization is correct; the reply is just less
  informative than it should be. See `ITERATION.md` for the full writeup —
  left as a documented gap rather than chasing a third live run this session.
- **Only 10 visible + 8 self-authored hostile cases have been run for real.**
  The brief mentions a hidden grading set in the same format; this harness
  hasn't seen it and could surface failure modes the visible/hostile sets
  don't cover.
- **Policy retrieval is a closed 12-topic enum, not embedding search** — a
  deliberate simplification for a fixed, small doc set (Locked Decision #3),
  not something scaled for a larger or free-text policy corpus.
