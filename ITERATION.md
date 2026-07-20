# Iteration: v1 → final

- v1: 7/10 passed — `answers_v1.jsonl`, `transcripts/v1/`
- final: 9/10 passed — `answers_final.jsonl`, `transcripts/final/`
- One residual failure remains after this iteration (v06 — see below). Not
  fixed here; flagging rather than claiming full resolution.

Between runs, three targeted additions were made to `system_prompt.md`
(rules #2, #3, #4) based on reading the actual `transcripts/v1/*.json` tool
traces, not just the grading output. No other files changed behavior.

## Failure taxonomy (grouped by root cause, not per-case)

### 1. Escalation deferred pending clarification (rule-precedence conflict)

**Symptom:** the model fetched policy text confirming an action is
human-only, but withheld the `escalate_to_human` call while it asked the
shopper a clarifying question, planning to escalate "next turn" — a turn
that never arrives in this single-shot harness. `route` is derived from the
tool trace (DECISIONS.md #1), so a promise in prose ("I'll escalate it")
that never becomes a tool call doesn't count.

**Case:** v06 (Bloom & Vine dispute, two orders matched the merchant filter).

**Root cause:** `system_prompt.md` rule #1 ("ask, or list the candidates...
and let them pick" when an order is ambiguous) had no stated precedence
over rule #3 ("escalate... even if you could technically compute or guess
an answer"). The model treated resolving order ambiguity as a prerequisite
to escalating, rather than as something the human agent could resolve.

**Fix applied:** added to rule #3 — escalate in the same turn regardless of
order ambiguity, note the ambiguity in `internal_summary`, and still ask
the shopper to clarify in the reply text if useful.

**Result:** route now correctly derives to `escalate` for v06. This fix
also introduced a new, distinct issue — see "Known residual issue" below.

### 2. Specific-remedy language read as an implied promise

**Symptom:** escalate-route answers listed the exact human-decidable
remedies verbatim from policy text (e.g. "waived fees," "paused payment").
The model wasn't promising anything — it attributed the remedies to what a
human agent *might* set up — but naming the remedy risks a shopper reading
a described option as a decision, and the grading `must_not_include` check
(a bare substring match) can't distinguish "possible outcome" from
"promise" either.

**Case:** v07 (hardship / job loss).

**Fix applied:** added to rule #4 — describe human-only remedies
generically ("relief options," "possible adjustments") instead of naming
them.

**Result:** fixed. v07 now passes; the answer no longer names specific
remedies while still explaining that hardship relief is possible and that
a human agent decides the specifics.

### 3. Policy rule cited without explaining why it doesn't apply to this order

**Symptom:** when an order's specific state made a general policy rule not
apply as written (refund policy: "applied to remaining unpaid installments
first," but this order had zero unpaid installments), the model reached
the correct conclusion but never stated the general rule or why it
diverged. The answer was factually correct but not traceable back to the
fetched policy text.

**Case:** v10 (Circuit City Lights refund).

**Fix applied:** added to rule #2 — when the order's state means a general
rule doesn't apply as written, state the rule and explain why it doesn't
apply here, rather than skipping straight to the conclusion.

**Result:** fixed. v10's final answer now explicitly cites "applied to
remaining unpaid installments first," explains the order has none, and
only then gives the payment-method conclusion.

### 4. Grading check can't distinguish quoting a rule from claiming it applies

**Symptom:** `must_not_include` entries are bare substrings/regex with no
way to represent "unless it's describing policy, not making a promise."
v03's own `why` field in `cases/golden_visible.jsonl` already documents
this same limitation for its own (deliberately relaxed) `must_not_include`.
v07 hit the same limitation in v1 before the rule #4 fix removed the
trigger word from the model's vocabulary entirely.

**Not changed this iteration** — `scripts/grade_cases.py` mirrors the
documented contract (regex, case-insensitive) exactly as specified in
CLAUDE.md's gap list; the fix went into assistant behavior (#2 above)
instead, which resolves the grading failure without needing regex changes.
Flagging as a known grading-tool limitation, not fixing it here.

## Known residual issue (final run, not fixed)

v06 still fails grading in the final run, but the failure mode changed:

- **v1:** wrong route (`both` instead of `escalate`) — tool trace shows
  `escalate_to_human` was never called.
- **final:** right route (`escalate`), but the answer text dropped the
  dispute-eligibility details it had already fetched via `get_policy` (the
  90-day filing window, the 15-day merchant-response wait, and the fact
  installments pause during investigation). `must_include` now fails on
  all three specifics — the answer shrank from a detailed explanation to
  "I've flagged this... please reach out to Bloom & Vine directly... let
  me know which order."

**Likely cause:** the rule #3 addition ("escalate in the same turn even if
ambiguous") combined with the rule #4 addition ("use generic language for
human-only remedies, don't name specifics") appears to have pushed the
model toward a terser escalation reply that defers *all* topic detail to
the human agent, not just the specific remedy. Rule #3 already permits
explaining eligibility rules in the same reply ("You may still explain the
general policy/eligibility rules around the topic in the same reply —
explaining is not the same as deciding") — the model simply didn't
exercise that permission on this run.

**Why this wasn't chased further:** fixing it would mean either refining
rule #3/#4 wording again (risk of another round-trip regression, given the
last two additions to those same rules is what caused this one) or a third
live API run to verify any further change — both need a check-in before
proceeding, per the run budget for this session.
