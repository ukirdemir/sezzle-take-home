# PROMPTS.md

Running log of the prompts used to direct Claude Code while building and
iterating on this project. Append-only per CLAUDE.md — new entries get added
to the bottom, existing entries don't get rewritten.

**Note on scope:** `system_prompt.md`, `tool_schemas.json`, `DECISIONS.md`,
`run_cases.py`, and `cases/golden_visible.jsonl` already existed (as raw
uploads in `./tmp`) before this log starts. The prompts that produced that
first pass aren't available to reconstruct honestly, so this log begins with
the first Claude Code session that iterated on the harness — bootstrap
through the hostile-input pass and this README/PROMPTS.md work.

## Session 1 — 2026-07-20

### Prompt 1 — session kickoff (checkpointed gap-list walkthrough)

> You have CLAUDE.md loaded as project context — treat it as ground truth for
> structure, locked decisions, and the priority-ordered gap list. My goal for
> this session: work through that gap list in order, but stop for my review
> at each checkpoint below rather than running straight through to the end.
>
> Cost/execution rule, from CLAUDE.md: scripts/bootstrap_layout.sh and
> scripts/grade_cases.py are local-only — build and run these freely.
> run_cases.py makes real, billed calls to the live Anthropic API — build and
> edit it freely, but do not run it over the full case set more than once
> without checking in with me first. If a run fails or looks wrong, diagnose
> from the saved transcripts/ output before re-running — don't retry blind.
>
> 1. If ./tmp still exists, run Step 0 (scripts/bootstrap_layout.sh). Show me
>    what landed where and flag anything that didn't move as expected.
> 2. Gap #1: verify TOPIC_TO_FILE's regex in run_cases.py actually resolves
>    all 12 policy files in data/policies/. Show me the resolved mapping.
> 3. Gap #3: build scripts/grade_cases.py — compares answers.jsonl against
>    cases.jsonl's expected_route/must_include/must_not_include and prints a
>    pass/fail table. Show me its output format on a tiny dummy input before
>    moving on.
> 4. Gap #4: run run_cases.py once against cases/golden_visible.jsonl,
>    producing answers_v1.jsonl and transcripts/v1/. This is the one live-API
>    run authorized for this step — an actual run, not simulated. Stop here
>    and show me the pass/fail summary from grade_cases.py. Do not diagnose
>    failures, fix anything, or re-run, even partially, without me confirming
>    first.
>
> Wait for my go-ahead after step 4 before touching gap #5 (diagnosis, fixes,
> final run, ITERATION.md) — I want to review the real v1 results myself
> first, and the final run is a second live-API run that also needs my
> go-ahead when we get there. Don't edit system_prompt.md's substance without
> flagging it to me first. If anything in CLAUDE.md turns out to be wrong
> once you're actually working in the code, tell me rather than silently
> working around it.

**Result:** found `scripts/bootstrap_layout.sh` didn't exist yet (the script
was at repo root, not under `scripts/` as CLAUDE.md's Setup section says) —
flagged it and the user chose "move script into `scripts/`" over the two
alternatives offered. Ran bootstrap, resolved and verified all 12
`TOPIC_TO_FILE` mappings against `tool_schemas.json`'s enum, built
`scripts/grade_cases.py` and demoed it on a hand-built dummy case/answer
pair, installed `anthropic`/`python-dotenv`, then ran the one authorized live
run → `answers_v1.jsonl` / `transcripts/v1/` (7/10 passed) and stopped.

### Prompt 2 — diagnosis input for gap #5

> I checked the failed cases. Continue with gap #5. The failings can happen
> due to these reasons:
> 1. v06 case: The topic *dispute* defined correctly but the policy is not
>    applied as shown in the `POLICY_-05-disputes.md`. According to the
>    policy, the user should be referred to the human agent, no matter what.
>    It can cause `reason[enum]` or `internal_summary[description]` under
>    `escalate_to_human` in `tool_schemas.json`.
> 2. v07 case: Even the support assistant doesn't pledge waivers, it mentions
>    in the text. The assistant told the policy to the user clearly but the
>    mentioning the words such as *waive* or related to making decisions must
>    be avoided.
> 3. v10 case: The text written by assistant doesn't include words such as
>    *remaining, unpaid, outstanding or balance*. The emphasized terms given
>    in the policy files can be mentioned in the generated texts.

**Result:** read the actual `transcripts/v1/{v06,v07,v10}.json` traces to
verify each hypothesis against real tool-call evidence (all three held up),
also surfaced that `DECISIONS.md #2`'s described keyword pre-classifier
doesn't exist in the code. Proposed three exact wording additions to
`system_prompt.md` (rules #2, #3, #4) and paused for approval before editing
production prompt content, per the standing CLAUDE.md rule — user approved
as worded. Applied the edits, ran the second authorized live run →
`answers_final.jsonl` / `transcripts/final/` (9/10 passed), and wrote
`ITERATION.md` from the real v1→final diff grouped by root cause. v06's
route was fixed but the fix caused a new, smaller issue (the reply dropped
policy detail it had fetched) — flagged as a residual gap; user chose "leave
as documented known gap" over redrafting the prompt or spending a third live
run.

### Prompt 3 — continue to gaps #6 and #7

> Continue with the gap #6 and gap #7.

**Result:** built `cases/hostile.jsonl` (8 cases: unauthorized cross-account
order access, nonexistent order IDs, fee-waiver demands, prompt-injection
attempts), grounded in real rows from `data/orders.json` and the actual
`failed_payments` policy text. Ran it live after checking in → 7/8 on first
grade; one case (`h04`) was a test-authoring error on my part (the model gave
a well-grounded answer my regex didn't anticipate), fixed the test case
in-place rather than the model → 8/8. Wrote `README.md` (~half page: exact
run/grade commands, honest unfinished list). Also flagged two more
documented-vs-actual mismatches found along the way: `DECISIONS.md #3`'s
described prompt-caching for the 12 policy docs isn't implemented, and
`DECISIONS.md #2`'s keyword pre-classifier still isn't implemented (same gap
noted under Prompt 2).

### Prompt 4 — README addition

> Include into the `README.md` file how the AI tool is directed using files
> such as `CLAUDE.md` or `system_prompt.md`. Mention concisely, the files are
> already seen on the root dir.

**Result:** drafted a "How the AI is directed" section for `README.md`
pointing to `system_prompt.md` and `CLAUDE.md`. User rejected the first
attempt with `include tool_schemas.json as well` — revised to a three-item
list (`system_prompt.md`, `tool_schemas.json`, `CLAUDE.md`) noting all three
already exist at the repo root rather than duplicating their content in the
README.