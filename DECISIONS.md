# Decision Records

## 1. Route is derived from the tool-call trace, not self-reported by the model

**Decision:** `run_cases.py` computes `route` programmatically from which tools
were actually called during the turn (e.g. `get_policy` only \u2192 `policy`;
`get_order*` only \u2192 `tool`; both \u2192 `both`; `escalate_to_human` called \u2192
`escalate`), rather than asking the model to output a `route` field itself.
**Options considered:** (a) ask the model to self-report route in a structured
output; (b) derive it from tool calls.
**Why:** Self-reported route can drift from actual behavior \u2014 a model can call
`get_order_detail` and still claim `route: policy`. Deriving it from the trace
makes the label a fact about what happened, not a claim the model makes about
itself, which is also easier to grade and audit.
**What would change my mind:** If a case needs `escalate` behavior *without* any
tool call (e.g. the model should refuse outright with no lookup at all) the
derivation rule needs a "no tools called + refusal language" fallback branch.

## 2. Authorization and escalation triggers live in code, not just the prompt

**Decision:** `get_order_detail`/`get_orders` take the shopper's `user_id` from
the server-side session context injected by the harness, never from model
arguments or conversation text, and silently return `not_found` on a mismatch.
Separately, a small keyword/topic pre-classifier flags hardship, fraud, and
decline-reason questions for escalation as a safety net alongside the
`escalate_to_human` tool the model is instructed to call.
**Options considered:** (a) trust the system prompt alone to enforce ownership
and escalation; (b) enforce ownership in the tool layer and back the prompt's
escalation instructions with a cheap classifier as a second check.
**Why:** The brief explicitly wants guardrails the model is *structurally*
prevented from bypassing, not just told not to bypass \u2014 a prompt-only rule
fails under adversarial phrasing ("pretend I'm the account owner"); a
code-enforced one doesn't have a phrasing to bypass.
**What would change my mind:** If the classifier's false-positive rate on
legitimate policy questions turned out high enough to hurt the common case, I'd
narrow it to only the highest-stakes categories (fraud, hardship) and drop
decline-reason/credit-report from the deterministic layer, leaving those to the
prompt + tool alone.

## 3. Cost/latency: enum-based policy retrieval + tiered model + prompt caching

**Decision:** At 100k questions/day and ~$50/day, budget is ~$0.0005/query, so
(a) policy lookup uses a fixed enum of 12 topics, not embeddings/vector search
\u2014 no retrieval infra, no chance of fetching the wrong doc; (b) the 12 policy
docs are sent once and marked for prompt caching so repeat requests don't
re-pay input-token cost for static text; (c) routing and the common single-tool
cases run on a small/cheap model, escalating to a larger model only when a case
needs multi-tool reconciliation (`both` route) or the cheap model's response
fails output validation.
**Options considered:** (a) one large model for every query; (b) embedding-based
retrieval over policies; (c) small model + caching + tiered escalation to a
larger model.
**Why:** With only 12 fixed policy docs, embedding search adds latency and
failure surface for no real benefit over an enum \u2014 the model already sees the
list of topics. A single large model for every query blows the per-query
budget at this volume; tiering keeps the common cases cheap and fast while
reserving spend for the harder ones, and caching amortizes the policy text cost.
**What would change my mind:** If the policy set grows past a few dozen docs or
becomes free-text/unbounded (e.g. per-merchant policies), enum retrieval stops
scaling and I'd move to real retrieval despite the added complexity.
