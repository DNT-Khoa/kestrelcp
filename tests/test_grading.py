#!/usr/bin/env python3
"""
Regression tests for the per-case grading logic in scripts/test_leetcode.py.

Locks in the fix for the false-PASS bug where every sample case was marked
PASS as long as the user's code ran. The old logic combined a batch-level
`status_msg` / `correct_answer` truthiness check into the per-case verdict;
the new logic uses LeetCode's per-case `compare_result` bitmap and only falls
back to string equality when that field is absent.

Run from the project root:
    python3 tests/test_grading.py
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from test_leetcode import grade_case  # noqa: E402


CASES: list[tuple[str, str, str, str | None, bool, bool]] = [
    # (name, your, expected, compare_bit, want_ok, want_note)
    (
        "wrong answer with judge bit '0' must FAIL (the regression)",
        "BAN", "BANC", "0", False, False,
    ),
    (
        "exact match with judge bit '1' is PASS, no note",
        "BANC", "BANC", "1", True, False,
    ),
    (
        "multi-valid-answer: judge bit '1' overrides string mismatch, note added",
        "[1,0]", "[0,1]", "1", True, True,
    ),
    (
        "judge bit missing + string equal -> PASS, no note",
        "a", "a", None, True, False,
    ),
    (
        "judge bit missing + string unequal -> FAIL, no note",
        "BAN", "BANC", None, False, False,
    ),
    (
        "judge bit '0' beats string equality (shouldn't happen, but trust judge)",
        "x", "x", "0", False, False,
    ),
]


def main() -> int:
    failures: list[str] = []
    for name, your, expected, bit, want_ok, want_note in CASES:
        ok, note = grade_case(your, expected, bit)
        has_note = bool(note)
        if ok != want_ok or has_note != want_note:
            failures.append(
                f"{name}\n"
                f"    grade_case({your!r}, {expected!r}, {bit!r})\n"
                f"    got  ok={ok}, note={note!r}\n"
                f"    want ok={want_ok}, note={'non-empty' if want_note else 'empty'}"
            )
            print(f"  FAIL  {name}", flush=True)
        else:
            print(f"  PASS  {name}", flush=True)

    print()
    if failures:
        print("--- Summary: FAILED ---")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"--- Summary: all {len(CASES)} grading tests passed ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
