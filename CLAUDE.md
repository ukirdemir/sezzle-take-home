# CLAUDE.md

You are the engineering assistant for Sezzle's shopper support platform.
This file orients you to the codebase — read it before making changes, and
keep it current as the project evolves.

## Project

An LLM-powered support assistant for BNPL shoppers. Contract (don't change):
`run_cases.py <cases.jsonl> <answers.jsonl>` reads `{id, question, user_id}`
and writes `{id, route, answer}` per line. `route` ∈
`policy | tool | both | escalate`.

Full design rationale lives in `DECISIONS.md` (3 records) — read it before
proposing a different architecture.

## Setup

**Step 0 (first session only):** if `./tmp` exists, it holds the 16 raw
uploaded files unsorted. Run `bash scripts/bootstrap_layout.sh` once to lay
them out — it's idempotent and reports any leftover files whose names didn't
match what it expected, rather than silently dropping them. If `./tmp`
doesn't exist, the layout is already done — skip this.

`run_cases.py` loads `.env` automatically via `python-dotenv` at startup and
exits with a clear error if `ANTHROPIC_API_KEY` is still missing. An
`export`-ed shell variable also works and takes priority over `.env` if both
are set — `.env` is just the default path so the key doesn't need re-exporting
in every new terminal.

## Commands

```
python3 run_cases.py cases/golden_visible.jsonl answers_v1.jsonl --transcripts-dir transcripts/v1
python3 scripts/grade_cases.py cases/golden_visible.jsonl answers_v1.jsonl   # not yet built
python3 run_cases.py cases/golden_visible.jsonl answers_final.jsonl --transcripts-dir transcripts/final
```

## File layout

```
tmp/                      # transient — raw uploads before Step 0 runs; should not exist after
scripts/bootstrap_layout.sh  # one-time layout script, see Setup Step 0
scripts/grade_cases.py       # supporting dev tooling, not part of the core contract — not yet built
brief/PROMPT.md           # product/requirements reference — do NOT confuse with PROMPTS.md
brief/SUBMISSION.md       # process reference
.env                     # real ANTHROPIC_API_KEY — gitignored, never commit
.env.example             # template for the above, safe to commit
system_prompt.md      # deployed assistant's system prompt — production content, not dev config
tool_schemas.json      # 4 tools: get_orders, get_order_detail, get_policy, escalate_to_human
DECISIONS.md            # 3 decision records — locked, see below
run_cases.py            # MUST stay at repo root — the contract invokes it as
                          # `python3 run_cases.py <cases> <answers>`, no path prefix
PROMPTS.md               # log of prompts used to build this — append to it, don't rewrite it
data/orders.json
data/policies/*.md      # 12 policy docs, inconsistent filename format — see gotcha below
cases/golden_visible.jsonl
```

## Locked decisions — do not relitigate without new evidence

1. `route` is derived from the tool-call trace in `run_cases.py`, never
   self-reported by the model.
2. `user_id` for tool calls comes only from the harness's case-row argument,
   never from model-supplied tool input. This is the authorization boundary.
3. Policy retrieval is a closed 12-topic enum, not embedding search. Model
   tiering (cheap model for common cases, escalate to larger for `both`) is
   the intended production design but not implemented in this harness —
   leave as a documented simplification, don't silently add complexity here.

## Known gaps (priority order)

1. Verify `TOPIC_TO_FILE`'s regex actually resolves all 12 policy files —
   `POLICY_-_01-...` has an extra underscore vs. `POLICY_-02-...` onward.
2. The `MODEL`: `claude-sonnet-5`, thinking disabled,
   `max_tokens=2048`. See comments in `run_cases.py` for the reasoning.
3. Build `scripts/grade_cases.py`: compare `answers.jsonl` against
   `cases.jsonl`'s `expected_route` / `must_include` / `must_not_include`
   (regex, case-insensitive), print pass/fail per case.
4. Run `run_cases.py` for real against `golden_visible.jsonl` →
   `answers_v1.jsonl` + `transcripts/v1/`. This must be a genuine run, not
   reconstructed after the fact.
5. Diagnose real failures from the transcripts, fix root causes, rerun →
   `answers_final.jsonl` + `transcripts/final/`. Write `ITERATION.md` from
   the actual diff, grouped into a failure taxonomy — not a per-case list.
6. Hostile-input pass: order IDs that aren't the caller's, nonexistent order
   IDs, fee-waiver demands, "ignore your instructions" injections. Not yet
   tested against the harness.
7. `README.md` — keep it to about half a page. Two required parts:
   - **How to run it**: setup steps (Step 0 bootstrap if needed, `.env`,
     `pip install`), then the exact commands to reproduce
     `answers_v1.jsonl` and `answers_final.jsonl`. Someone unfamiliar with
     this repo should be able to follow it start to finish without asking
     a question.
   - **What's honestly unfinished**: pull directly from this file's Known
     gaps and Locked decisions #3 (single model, not tiered) — state
     plainly what's not done and why, rather than implying completeness.
     Understating gaps is worse than listing them.
   - Some commands about environment for the users:

      ```
      pip install anthropic python-dotenv
      cp .env.example .env   # then fill in the real ANTHROPIC_API_KEY
      ```
      When .env is created, the credentials for the LLM support can be submitted into `.env` file.

## Rules for this repo

- `.env` must be in `.gitignore` before the first commit — verify this, don't
  assume it. If a real key ever gets committed, treat it as compromised and
  regenerate it in the console rather than just removing it from a later commit.
- `tmp/` should also be gitignored as a safety net, in case Step 0 hasn't run
  yet or was interrupted partway through when a commit happens.
- Don't edit `system_prompt.md`'s substance casually — it's production
  content, not internal config. Flag proposed changes rather than silently
  rewriting.
- Don't write `ITERATION.md` or `answers_final.jsonl` without a real run
  behind them — fabricated iteration evidence undermines the entire point of
  tracking iteration in the first place.
- Append to `PROMPTS.md`, don't regenerate it — it's a running log of real
  prompts, including this file's own history.
