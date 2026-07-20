#!/usr/bin/env bash
# One-time setup: moves the 16 raw uploaded files from ./tmp into the layout
# CLAUDE.md and run_cases.py expect. Safe to re-run — uses `mv -n` (no
# clobber) and skips anything already moved, so a partial or repeat run
# won't overwrite or error out.
set -euo pipefail

TMP_DIR="tmp"

if [ ! -d "$TMP_DIR" ]; then
  echo "No ./tmp directory found — nothing to bootstrap (already done, or files were placed manually)."
  exit 0
fi

mkdir -p data/policies cases brief

# 12 policy docs
for f in "$TMP_DIR"/POLICY_-*.md; do
  [ -e "$f" ] || continue
  mv -n "$f" data/policies/
done

# Orders data — exact filename required, run_cases.py hardcodes this path
if [ -e "$TMP_DIR/DATA-orders.json" ]; then
  mv -n "$TMP_DIR/DATA-orders.json" data/orders.json
fi

# Golden cases — renamed to match the paths used in CLAUDE.md's example commands
if [ -e "$TMP_DIR/CASES_-_golden_visible.jsonl" ]; then
  mv -n "$TMP_DIR/CASES_-_golden_visible.jsonl" cases/golden_visible.jsonl
fi

# Assignment brief — kept separate from the deliverable PROMPTS.md at the root
if [ -e "$TMP_DIR/PROMPT.md" ]; then
  mv -n "$TMP_DIR/PROMPT.md" brief/PROMPT.md
fi
if [ -e "$TMP_DIR/SUBMISSION.md" ]; then
  mv -n "$TMP_DIR/SUBMISSION.md" brief/SUBMISSION.md
fi

# Report anything left over rather than silently dropping it — a leftover
# file usually means its name didn't match one of the patterns above.
remaining=$(find "$TMP_DIR" -type f 2>/dev/null | wc -l | tr -d ' ')
if [ "$remaining" -eq 0 ]; then
  rmdir "$TMP_DIR" 2>/dev/null || true
  echo "Bootstrap complete — tmp/ emptied and removed."
else
  echo "Bootstrap finished with $remaining file(s) still in tmp/ — check these names against the expected patterns:"
  find "$TMP_DIR" -type f
fi
