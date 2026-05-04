#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""
Usage: ./test.py <platform> <problem>
Example: ./test.py kattis oddecho
"""

import argparse
import glob
import os
import subprocess
import sys
import tempfile

try:
    import argcomplete
except ImportError:
    argcomplete = None

TIMEOUT = 5
WORKSPACE = os.getcwd()
PLATFORMS = ["kattis", "codeforces", "leetcode"]


def problem_completer(prefix, parsed_args, **kwargs):
    platform = getattr(parsed_args, "platform", None)
    if not platform:
        return []
    platform_dir = os.path.join(WORKSPACE, platform)
    if not os.path.isdir(platform_dir):
        return []
    return [d for d in os.listdir(platform_dir) if os.path.isdir(os.path.join(platform_dir, d))]


def normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines() if line.strip())


def compile_java(solution_java: str, out_dir: str) -> None:
    print(f"Compiling... ", end="", flush=True)
    result = subprocess.run(
        ["javac", "-d", out_dir, solution_java],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("FAILED")
        print(result.stderr)
        sys.exit(1)
    print("OK\n")


def run_case(classpath: str, in_file: str) -> tuple[str | None, str]:
    try:
        with open(in_file) as f:
            result = subprocess.run(
                ["java", "-cp", classpath, "Solution"],
                stdin=f, capture_output=True, text=True, timeout=TIMEOUT,
            )
        if result.returncode != 0:
            return None, f"error:{result.returncode}"
        return result.stdout, "ok"
    except subprocess.TimeoutExpired:
        return None, "timeout"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="test.py",
        description="Compile/run and test a competitive programming solution.",
        usage="./test.py <platform> <problem>",
    )
    parser.add_argument("platform", choices=PLATFORMS)
    parser.add_argument("problem").completer = problem_completer

    if argcomplete:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()
    platform = args.platform
    problem = args.problem
    problem_dir = os.path.join(WORKSPACE, platform, problem)
    solution_java = os.path.join(problem_dir, "Solution.java")

    if not os.path.isfile(solution_java):
        print(f"No Solution.java found in: {problem_dir}")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as out_dir:
        compile_java(solution_java, out_dir)

        in_files = sorted(glob.glob(os.path.join(problem_dir, "*.in")))
        if not in_files:
            print(f"No *.in files found in {problem_dir}")
            sys.exit(1)

        passed = failed = no_expected = 0

        for in_file in in_files:
            case = os.path.splitext(os.path.basename(in_file))[0]
            out_file = in_file[:-3] + ".out"

            actual, status = run_case(out_dir, in_file)

            if status == "timeout":
                print(f"Test {case}: TIMEOUT (>{TIMEOUT}s)")
                failed += 1
                continue
            if status.startswith("error:"):
                print(f"Test {case}: RUNTIME ERROR (exit {status.split(':')[1]})")
                failed += 1
                continue

            if not os.path.isfile(out_file) or os.path.getsize(out_file) == 0:
                print(f"Test {case}: (no expected output — actual output:)")
                print(actual)
                no_expected += 1
                continue

            with open(out_file) as f:
                expected = f.read()

            if normalize(actual) == normalize(expected):
                print(f"Test {case}: PASS")
                passed += 1
            else:
                print(f"Test {case}: FAIL")
                print("  --- expected ---")
                for line in expected.splitlines()[:10]:
                    print(f"  {line}")
                print("  --- actual ---")
                for line in actual.splitlines()[:10]:
                    print(f"  {line}")
                failed += 1

        suffix = f", {no_expected} without expected output" if no_expected else ""
        print(f"\nResults: {passed} passed, {failed} failed{suffix}")
        sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()