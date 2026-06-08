#!/usr/bin/env python3
"""
Run a LeetCode Solution.java against its sample tests via LeetCode's own judge.

Why this exists
---------------
LeetCode problems take typed method arguments (int[], TreeNode, etc.), not
stdin lines. We cannot run them with javac+java the way Kattis/Codeforces
problems work. Instead, we POST the source to LeetCode's interpret_solution
endpoint — the same one that powers the "Run Code" button in their web
editor — and the official judge runs it for us.

Rate-limit note
---------------
LeetCode rate-limits this endpoint hard (~1 request per few seconds per
account). To stay within the limit we concatenate every *.in file into a
single data_input and send ONE request. The judge runs all cases in the
same container and returns parallel code_answer / expected_code_answer
arrays.

Per-case rendering
------------------
- Sample case (LeetCode supplies expected): PASS/FAIL. We honor the judge's
  overall verdict (status_msg == "Accepted") when string equality disagrees,
  so multi-valid-answer problems (e.g. two-sum returning [1,0] vs [0,1])
  don't get false FAILs.
- Custom input (a <N>.in the user added that LeetCode has no reference for):
  shown without a verdict — local <N>.out files are deliberately not used
  for comparison because LeetCode is the only source of truth.

Usage:
  ./test_leetcode.py <problem-slug>

The script expects LEETCODE_SESSION and LEETCODE_CSRF in env.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import leetcode_auth as auth

BASE = "https://leetcode.com"
POLL_INTERVAL = 0.5
POLL_MAX_WAIT = 30


def read_inputs(problem_dir: str) -> list[tuple[int, str]]:
    """Returns [(case_num, in_content), ...] sorted by num.

    Local <N>.out files are intentionally NOT read. LeetCode's judge is the
    only source of truth: for sample inputs it supplies the expected output
    (and we trust its overall Accepted verdict for multi-valid-answer
    problems); for custom inputs the user invents, the judge has no
    reference, and we just display the output.
    """
    inputs: list[tuple[int, str]] = []
    for fname in os.listdir(problem_dir):
        if not fname.endswith(".in"):
            continue
        stem = fname[:-3]
        try:
            n = int(stem)
        except ValueError:
            continue
        with open(os.path.join(problem_dir, fname)) as fh:
            inputs.append((n, fh.read().rstrip("\n")))
    inputs.sort()
    return inputs


def fetch_question_id(session, slug: str) -> str:
    r = session.post(
        f"{BASE}/graphql/",
        json={
            "operationName": "questionId",
            "variables": {"titleSlug": slug},
            "query": "query questionId($titleSlug: String!) { question(titleSlug: $titleSlug) { questionId } }",
        },
        timeout=auth.HTTP_TIMEOUT_SECONDS,
    )
    if r.status_code != 200:
        raise auth.classify_response_error(r.status_code, r.text, r.headers.get("Retry-After"))
    q = (r.json().get("data") or {}).get("question")
    if not q:
        raise auth.AuthError(f"no public problem '{slug}' (premium-only?)", reason="other")
    return q["questionId"]


def run_batch(session, slug: str, question_id: str, code: str, data_input: str) -> dict:
    r = session.post(
        f"{BASE}/problems/{slug}/interpret_solution/",
        json={
            "lang": "java",
            "question_id": question_id,
            "typed_code": code,
            "data_input": data_input,
        },
        timeout=auth.HTTP_TIMEOUT_SECONDS,
    )
    if r.status_code != 200:
        raise auth.classify_response_error(r.status_code, r.text, r.headers.get("Retry-After"))
    interpret_id = r.json().get("interpret_id")
    if not interpret_id:
        raise auth.AuthError(f"no interpret_id in response: {r.text[:200]}", reason="other")

    deadline = time.time() + POLL_MAX_WAIT
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        cr = session.get(
            f"{BASE}/submissions/detail/{interpret_id}/check/",
            timeout=auth.HTTP_TIMEOUT_SECONDS,
        )
        if cr.status_code != 200:
            raise auth.classify_response_error(cr.status_code, cr.text, cr.headers.get("Retry-After"))
        data = cr.json()
        if data.get("state") == "SUCCESS":
            return data
    raise auth.AuthError(f"timed out waiting for judge after {POLL_MAX_WAIT}s", reason="other")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a LeetCode Solution.java via the official judge.")
    ap.add_argument("problem", help="LeetCode problem slug (the folder name)")
    args = ap.parse_args()

    workspace = os.getcwd()
    problem_dir = os.path.join(workspace, "leetcode", args.problem)
    solution_path = os.path.join(problem_dir, "Solution.java")

    if not os.path.isfile(solution_path):
        print(f"Not found: {solution_path}", file=sys.stderr)
        return 1

    with open(solution_path) as fh:
        code = fh.read()

    cases = read_inputs(problem_dir)
    if not cases:
        print(f"No *.in files in {problem_dir}", file=sys.stderr)
        return 1
    case_nums = [n for n, _ in cases]
    inputs = [text for _, text in cases]

    try:
        sess_info = auth.load_session_from_env()
    except auth.AuthError as e:
        auth.fail(e)

    session = auth.make_requests_session(sess_info, referer_path=f"/problems/{args.problem}/")

    print(f"Fetching questionId for '{args.problem}'...", flush=True)
    try:
        question_id = fetch_question_id(session, args.problem)
    except auth.AuthError as e:
        auth.fail(e)

    data_input = "\n".join(inputs)
    print(f"Running {len(cases)} case(s) via LeetCode judge (batch)...", flush=True)

    t0 = time.time()
    try:
        result = run_batch(session, args.problem, question_id, code, data_input)
    except auth.AuthError as e:
        auth.fail(e)
    elapsed = time.time() - t0

    status_msg = result.get("status_msg", "?")
    compile_err = (result.get("compile_error") or "").strip()
    runtime_err = (result.get("runtime_error") or "").strip()
    your = result.get("code_answer") or []
    expect = result.get("expected_code_answer") or []
    stdout_per_case = result.get("code_output") or []
    # The judge's overall verdict. True means every sample case passed —
    # even if our string equality below would disagree, because some problems
    # (two-sum, etc.) accept multiple valid orderings or permutations.
    judge_accepted = bool(result.get("correct_answer")) or status_msg == "Accepted"

    print()
    print(f"Judge status: {status_msg}  ({elapsed:.2f}s)")

    if compile_err:
        print()
        print("Compile error:")
        print(compile_err)
        return 1

    if runtime_err:
        print()
        print("Runtime error:")
        print(runtime_err)

    pass_count = 0
    fail_count = 0
    custom_count = 0
    for i, n in enumerate(case_nums):
        y = your[i].strip() if i < len(your) else ""
        e = expect[i].strip() if i < len(expect) else ""
        if not y and not e:
            continue

        if not e:
            # Custom input — LeetCode has no canonical answer to compare
            # against. We don't support pass/fail for custom cases.
            custom_count += 1
            print(f"\nTest {n}: (custom input — LeetCode has no reference; eyeball the output)")
            print(f"  input:    {inputs[i]!r}")
            print(f"  output:   {y}")
            if i < len(stdout_per_case) and stdout_per_case[i]:
                print(f"  stdout:   {stdout_per_case[i]}")
            continue

        # Sample case: defer to the judge's overall verdict when Accepted —
        # otherwise multi-valid-answer problems (two-sum returning [1,0]
        # instead of [0,1], "return any valid permutation", etc.) would be
        # falsely flagged FAIL by string equality.
        if judge_accepted:
            ok = True
            note = "" if y == e else "  (judge accepted equivalent answer)"
        else:
            ok = y == e
            note = ""
        mark = "PASS" if ok else "FAIL"
        if ok:
            pass_count += 1
        else:
            fail_count += 1
        print(f"\nTest {n}: {mark}{note}")
        print(f"  input:    {inputs[i]!r}")
        print(f"  your:     {y}")
        print(f"  expected: {e}")
        if i < len(stdout_per_case) and stdout_per_case[i]:
            print(f"  stdout:   {stdout_per_case[i]}")

    print()
    suffix = f", {custom_count} custom case(s) shown without verdict" if custom_count else ""
    print(f"Summary: {pass_count} passed, {fail_count} failed{suffix}")
    return 0 if fail_count == 0 and not runtime_err else 1


if __name__ == "__main__":
    sys.exit(main())
