#!/usr/bin/env python3
"""
grade_cases.py — compares answers.jsonl against cases.jsonl's grading
criteria and prints a pass/fail table.

Usage:
    python3 scripts/grade_cases.py cases.jsonl answers.jsonl

Grading, per case:
  - route:            answers.jsonl's "route" must equal cases.jsonl's
                       "expected_route" exactly.
  - must_include:     each entry is a regex (case-insensitive, re.search)
                       that must match somewhere in the answer text. Entries
                       often encode alternatives via "|" (e.g. "2 weeks|14
                       days"). Every entry in the list must match.
  - must_not_include: same regex semantics, but none may match.

A case passes only if all three checks pass. Not part of the core
run_cases.py contract — supporting dev tooling only.
"""

import argparse
import json
import re
import sys


def load_jsonl(path):
    rows = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rows[row["id"]] = row
    return rows


def grade_case(case, answer):
    problems = []

    if answer is None:
        return False, ["no answer for this case id"]

    expected_route = case.get("expected_route")
    actual_route = answer.get("route")
    if actual_route != expected_route:
        problems.append(f"route: expected {expected_route!r}, got {actual_route!r}")

    answer_text = answer.get("answer", "")

    for pattern in case.get("must_include", []):
        if not re.search(pattern, answer_text, re.I):
            problems.append(f"must_include not found: {pattern!r}")

    for pattern in case.get("must_not_include", []):
        if re.search(pattern, answer_text, re.I):
            problems.append(f"must_not_include matched: {pattern!r}")

    return (len(problems) == 0), problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases_path")
    ap.add_argument("answers_path")
    args = ap.parse_args()

    cases = load_jsonl(args.cases_path)
    answers = load_jsonl(args.answers_path)

    results = []
    for case_id, case in cases.items():
        answer = answers.get(case_id)
        passed, problems = grade_case(case, answer)
        results.append((case_id, passed, problems))

    id_width = max((len(cid) for cid, _, _ in results), default=2)
    header = f"{'ID':<{id_width}}  {'RESULT':<6}  DETAILS"
    print(header)
    print("-" * len(header))
    for case_id, passed, problems in results:
        status = "PASS" if passed else "FAIL"
        if not problems:
            print(f"{case_id:<{id_width}}  {status:<6}")
        else:
            print(f"{case_id:<{id_width}}  {status:<6}  {problems[0]}")
            for extra in problems[1:]:
                print(f"{'':<{id_width}}  {'':<6}  {extra}")

    extra_answer_ids = sorted(set(answers) - set(cases))
    if extra_answer_ids:
        print()
        print(f"Note: {len(extra_answer_ids)} answer id(s) with no matching case: {extra_answer_ids}")

    total = len(results)
    passed_count = sum(1 for _, passed, _ in results if passed)
    print()
    print(f"{passed_count}/{total} passed")

    sys.exit(0 if passed_count == total else 1)


if __name__ == "__main__":
    main()
