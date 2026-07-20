#!/usr/bin/env python3
"""
run_cases.py — Sezzle support assistant harness.

Usage:
    python3 run_cases.py <cases.jsonl> <answers.jsonl> [--transcripts-dir DIR]

Contract (PROMPT.md): reads a JSONL of {id, question, user_id} and writes
answers.jsonl of {id, route, answer}. `route` is DERIVED from the tool-call
trace, never self-reported by the model (DECISIONS.md #1). `user_id` is the
only source of authorization scope for tool calls (DECISIONS.md #2) — it is
threaded through explicitly and never taken from model-supplied tool input.

Expects, relative to this file:
    system_prompt.md
    tool_schemas.json
    data/orders.json
    data/policies/POLICY_-NN-<topic-slug>.md   (12 files)

Requires: pip install anthropic python-dotenv
ANTHROPIC_API_KEY must be set — either exported in your shell, or placed in a
.env file at the project root (see .env.example). .env is loaded below via
python-dotenv; it never overrides a variable already set in the shell, so an
`export`-ed value always wins if both are present. .env must stay out of
version control (see .gitignore) — it holds the real API key.
Swap MODEL/THINKING or `call_model` for a different provider (OpenAI, Ollama
via llm.py) if you go that route instead — everything else in this file is
provider-agnostic.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # populates os.environ from .env if present; no-op if the file is absent

import anthropic

if not os.environ.get("ANTHROPIC_API_KEY"):
    sys.exit(
        "ANTHROPIC_API_KEY is not set. Either `export ANTHROPIC_API_KEY=...` "
        "in your shell, or copy .env.example to .env and fill it in."
    )

# claude-sonnet-5 — confirmed exact API model ID (no date suffix) as of
# July 2026. Chosen over a cheaper tier for this harness because reliable
# tool-use and instruction-following matter most for the authorization/
# escalation guardrails (DECISIONS.md #2) — the few dozen cases here cost
# fractions of a cent regardless of model, so cost isn't the deciding factor
# at this scale. The tiered cheap/expensive split in DECISIONS.md #3 remains
# the intended production design, not implemented here.
MODEL = os.environ.get("SEZZLE_MODEL", "claude-sonnet-5")

# Sonnet 5 runs with adaptive thinking ON by default, and max_tokens is a
# hard cap on thinking + response text combined. This task is bounded
# tool-routing, not open-ended reasoning, so thinking is disabled for
# latency/cost (aligns with the p95 ≤ 3s target in DECISIONS.md #3) rather
# than left on the default. max_tokens is bumped from a bare-minimum value
# to leave headroom, since Sonnet 5's new tokenizer produces ~30% more
# tokens than Sonnet 4.6 for the same text.
THINKING = {"type": "disabled"}
MAX_TOKENS = 2048
MAX_TOOL_ROUNDS = 4

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
POLICY_DIR = DATA_DIR / "policies"
ORDERS_PATH = DATA_DIR / "orders.json"
SYSTEM_PROMPT_PATH = ROOT / "system_prompt.md"
TOOL_SCHEMAS_PATH = ROOT / "tool_schemas.json"

client = anthropic.Anthropic()

# ---------- static data ----------

with open(ORDERS_PATH) as f:
    _DB = json.load(f)

ORDERS = {o["order_id"]: o for o in _DB["orders"]}

# Map schema enum values (e.g. "rescheduling_payments") to policy files
# (e.g. POLICY_-02-rescheduling-payments.md) by parsing the leading number
# and slug out of each filename, rather than hardcoding 12 paths.
TOPIC_TO_FILE = {}
for p in POLICY_DIR.glob("*.md"):
    m = re.search(r"(\d{2})[-_]?([a-z0-9\-]+)\.md$", p.name, re.I)
    if m:
        TOPIC_TO_FILE[m.group(2).replace("-", "_").lower()] = p

with open(SYSTEM_PROMPT_PATH) as f:
    SYSTEM_PROMPT = f.read()

with open(TOOL_SCHEMAS_PATH) as f:
    TOOL_SCHEMAS = json.load(f)

# ---------- tool implementations ----------
# Every tool takes `session_user_id` as an explicit argument supplied by the
# harness (from the case row), never from `tool_input`. This is the
# authorization guardrail from DECISIONS.md #2 — the model cannot escape its
# own scope no matter what it puts in a tool call's arguments.


def _orders_for_user(session_user_id):
    return [o for o in ORDERS.values() if o["user_id"] == session_user_id]


def tool_get_orders(session_user_id, tool_input):
    merchant = (tool_input.get("merchant_filter") or "").lower()
    status = tool_input.get("status_filter", "any")
    rows = _orders_for_user(session_user_id)
    if merchant:
        rows = [o for o in rows if merchant in o["merchant"].lower()]
    if status and status != "any":
        rows = [o for o in rows if o["status"] == status]
    return [
        {
            "order_id": o["order_id"],
            "merchant": o["merchant"],
            "status": o["status"],
            "order_date": o["order_date"],
            "total": o["total"],
        }
        for o in rows
    ]


def tool_get_order_detail(session_user_id, tool_input):
    order = ORDERS.get(tool_input.get("order_id"))
    if not order or order["user_id"] != session_user_id:
        # Same response whether the order doesn't exist or belongs to someone
        # else — never confirm the existence of another shopper's order.
        return {"error": "not_found"}
    return order


def tool_get_policy(session_user_id, tool_input):
    topic = tool_input.get("topic")
    path = TOPIC_TO_FILE.get(topic)
    if not path:
        return {"error": f"unknown_topic: {topic}"}
    return {"topic": topic, "text": path.read_text()}


def tool_escalate_to_human(session_user_id, tool_input):
    return {
        "escalated": True,
        "reason": tool_input.get("reason"),
        "internal_summary": tool_input.get("internal_summary"),
    }


TOOL_IMPLS = {
    "get_orders": tool_get_orders,
    "get_order_detail": tool_get_order_detail,
    "get_policy": tool_get_policy,
    "escalate_to_human": tool_escalate_to_human,
}

# ---------- output validation (structural guardrail, not just prompt wording) ----------

FORBIDDEN_ON_ESCALATE = [
    re.compile(r"\bi(?:'ve| have) (?:paused|waived|refunded|reschedul\w*)\b", re.I),
    re.compile(r"\byour (?:exact )?limit is\b", re.I),
    re.compile(r"\bexact limit is\b", re.I),
]


def validate_output(route, answer_text):
    """Returns a list of violation strings; empty = clean."""
    violations = []
    if route == "escalate":
        for pat in FORBIDDEN_ON_ESCALATE:
            if pat.search(answer_text):
                violations.append(f"forbidden phrase on escalate route: {pat.pattern}")
    return violations


# ---------- route derivation ----------


def derive_route(tool_names_called):
    used = set(tool_names_called)
    if "escalate_to_human" in used:
        return "escalate"
    used_policy = "get_policy" in used
    used_lookup = bool(used & {"get_orders", "get_order_detail"})
    if used_policy and used_lookup:
        return "both"
    if used_lookup:
        return "tool"
    if used_policy:
        return "policy"
    # No tools called at all. The system prompt should make this rare for
    # in-scope questions, but pure small talk / out-of-scope questions could
    # land here. Known gap: currently mislabeled as "policy" — flagging
    # rather than silently pretending this case is handled correctly.
    return "policy"


# ---------- agent loop ----------


def run_one(case):
    user_id = case["user_id"]
    question = case["question"]

    messages = [{"role": "user", "content": question}]
    tool_trace = []
    tool_names_called = []
    answer_text = None

    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking=THINKING,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        tool_use_blocks = [b for b in resp.content if b.type == "tool_use"]
        if not tool_use_blocks:
            answer_text = "".join(b.text for b in resp.content if b.type == "text").strip()
            break

        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in tool_use_blocks:
            impl = TOOL_IMPLS.get(block.name)
            output = impl(user_id, block.input) if impl else {"error": f"unknown_tool: {block.name}"}
            tool_trace.append({"name": block.name, "input": block.input, "output": output})
            tool_names_called.append(block.name)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(output)}
            )
        messages.append({"role": "user", "content": tool_results})

    if answer_text is None:
        # Hit MAX_TOOL_ROUNDS without a final text turn — treat as a pipeline
        # failure and force a safe, honest response rather than a silent guess.
        answer_text = "I'm having trouble completing this request — let me connect you with a human agent."
        tool_names_called.append("escalate_to_human")
        tool_trace.append(
            {"name": "escalate_to_human", "input": {"reason": "pipeline_incomplete"}, "output": {}}
        )

    route = derive_route(tool_names_called)
    violations = validate_output(route, answer_text)
    if violations:
        # Structural guardrail caught a leak the prompt alone didn't prevent.
        # Fail safe rather than ship the violating text.
        answer_text = "Let me connect you with a human agent who can help with this."
        route = "escalate"

    return route, answer_text, tool_trace, violations


# ---------- main ----------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases_path")
    ap.add_argument("answers_path")
    ap.add_argument(
        "--transcripts-dir",
        default=None,
        help="If set, write one JSON transcript per case here, e.g. transcripts/v1",
    )
    args = ap.parse_args()

    if args.transcripts_dir:
        Path(args.transcripts_dir).mkdir(parents=True, exist_ok=True)

    with open(args.cases_path) as f:
        cases = [json.loads(line) for line in f if line.strip()]

    with open(args.answers_path, "w") as out:
        for case in cases:
            case_id = case["id"]
            try:
                route, answer, trace, violations = run_one(case)
            except Exception as e:
                route, answer, trace, violations = (
                    "escalate",
                    "Something went wrong on our end — let me connect you with a human agent.",
                    [],
                    [f"exception: {e!r}"],
                )

            out.write(json.dumps({"id": case_id, "route": route, "answer": answer}) + "\n")

            if args.transcripts_dir:
                transcript = {
                    "id": case_id,
                    "user_id": case["user_id"],
                    "question": case["question"],
                    "route": route,
                    "answer": answer,
                    "tool_trace": trace,
                    "validation_violations": violations,
                }
                with open(Path(args.transcripts_dir) / f"{case_id}.json", "w") as tf:
                    json.dump(transcript, tf, indent=2)

    print(f"Wrote {len(cases)} answers to {args.answers_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
