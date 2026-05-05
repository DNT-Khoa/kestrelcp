#!/usr/bin/env python3
"""
Scraper canary for KestrelCP.

Runs scripts/new.py against a known-stable problem on each platform and
verifies the produced 1.in / 1.out files are non-empty. If any platform's
sample fetch is empty, the scraping logic is likely broken (site HTML / API
changed) and CI will fail.

Run locally:
    python3 tests/canary.py

Run from the project root.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time

# (platform, target, min_input_lines) — min_input_lines guards against the
# silent-collapse failure mode where scraping returns non-empty but joined-on-
# one-line content (e.g. Codeforces using <br> between sample input rows).
CANARIES: list[tuple[str, str, int]] = [
    ("kattis", "https://open.kattis.com/problems/oddecho", 1),
    ("codeforces", "https://codeforces.com/problemset/problem/645/A", 4),
    ("leetcode", "two-sum", 2),
]

MAX_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = 10


def run_canary(workspace: str, platform: str, target: str, min_input_lines: int) -> list[str]:
    """Returns list of failure messages (empty list = pass)."""
    last_stderr = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = subprocess.run(
            ["./new.py", platform, target],
            cwd=workspace,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            break
        last_stderr = result.stderr.strip() or result.stdout.strip()
        print(
            f"  attempt {attempt}/{MAX_ATTEMPTS} failed (rc={result.returncode}): "
            f"{last_stderr.splitlines()[-1] if last_stderr else '<no output>'}",
            flush=True,
        )
        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_SLEEP_SECONDS)
    else:
        return [
            f"{platform}: new.py exited non-zero after {MAX_ATTEMPTS} attempts. "
            f"Last error: {last_stderr or '<empty>'}"
        ]

    platform_dir = os.path.join(workspace, platform)
    if not os.path.isdir(platform_dir):
        return [f"{platform}: no `{platform}/` directory created"]

    problem_dirs = sorted(
        d for d in os.listdir(platform_dir)
        if os.path.isdir(os.path.join(platform_dir, d))
    )
    if not problem_dirs:
        return [f"{platform}: no problem subdirectory created"]

    problem_path = os.path.join(platform_dir, problem_dirs[0])
    failures: list[str] = []

    for fname in ("1.in", "1.out"):
        fpath = os.path.join(problem_path, fname)
        if not os.path.exists(fpath):
            failures.append(f"{platform}: {fname} was not created")
        elif os.path.getsize(fpath) == 0:
            failures.append(
                f"{platform}: {fname} is empty — scrape likely broken "
                f"(target site changed its HTML / API)"
            )

    in_path = os.path.join(problem_path, "1.in")
    if os.path.exists(in_path) and os.path.getsize(in_path) > 0:
        with open(in_path) as fh:
            line_count = sum(1 for line in fh if line.strip())
        if line_count < min_input_lines:
            failures.append(
                f"{platform}: 1.in has {line_count} non-empty line(s), expected >= "
                f"{min_input_lines} — multi-line input may have collapsed onto a single line "
                f"(e.g. <br> tags ignored by parser)"
            )

    return failures


def main() -> int:
    project_root = os.getcwd()
    new_py = os.path.join(project_root, "scripts", "new.py")
    if not os.path.isfile(new_py):
        print(f"ERROR: cannot find scripts/new.py from cwd={project_root}", file=sys.stderr)
        return 2

    workspace = tempfile.mkdtemp(prefix="kestrelcp-canary-")
    try:
        shutil.copy(new_py, workspace)
        os.chmod(os.path.join(workspace, "new.py"), 0o755)

        all_failures: list[str] = []
        for platform, target, min_input_lines in CANARIES:
            print(f"\n=== Canary: {platform} ({target}) ===", flush=True)
            fails = run_canary(workspace, platform, target, min_input_lines)
            if fails:
                for f in fails:
                    print(f"  FAIL  {f}", flush=True)
                all_failures.extend(fails)
            else:
                print(f"  PASS", flush=True)

        print()
        if all_failures:
            print("--- Summary: FAILED ---")
            for f in all_failures:
                print(f"  - {f}")

            gh_output = os.environ.get("GITHUB_OUTPUT")
            if gh_output:
                with open(gh_output, "a") as fh:
                    fh.write("failures<<EOF\n")
                    for f in all_failures:
                        fh.write(f"- {f}\n")
                    fh.write("EOF\n")
            return 1

        print("--- Summary: all canaries passed ---")
        return 0
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
