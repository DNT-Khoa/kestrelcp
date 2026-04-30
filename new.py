#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""
Usage:
  ./new.py <platform> <problem-name>             # just scaffold
  ./new.py <platform> <problem-name> <url>       # scaffold + fetch sample tests

Examples:
  ./new.py kattis oddecho
  ./new.py kattis oddecho https://open.kattis.com/problems/oddecho
  ./new.py codeforces 1A https://codeforces.com/problemset/problem/1/A
  ./new.py leetcode two-sum
"""

import argparse
import os
import re
import sys

try:
    import argcomplete
except ImportError:
    argcomplete = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SOLUTION_TEMPLATE = """\
#include <iostream>
using namespace std;

int main() {
    // your code here
}
"""

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def fetch_kattis(url: str) -> tuple[list[tuple[str, str]], str]:
    """Returns (samples, description_md) from a Kattis problem page."""
    import requests
    from bs4 import BeautifulSoup

    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    samples = []
    for table in soup.select("table.sample"):
        pres = table.select("pre")
        if len(pres) >= 2:
            samples.append((pres[0].get_text(), pres[1].get_text()))

    body = soup.select_one("div.problembody")
    description = ""
    if body:
        lines = []
        for el in body.find_all(["h2", "h3", "p", "li"]):
            if el.find_parent("table"):
                continue
            if el.name in ("h2", "h3"):
                lines.append(f"\n### {el.get_text(strip=True)}\n")
            elif el.name == "p":
                if el.find_parent("li"):
                    continue
                text = el.get_text(" ", strip=True)
                if text:
                    lines.append(text)
            elif el.name == "li":
                lines.append(f"- {el.get_text(' ', strip=True)}")
        description = "\n\n".join(line for line in lines if line.strip())
        description = re.sub(r"\$([^$]+)\$", r"\1", description)

    return samples, description


def fetch_codeforces(url: str) -> tuple[list[tuple[str, str]], str]:
    """Returns (samples, description_md) from a Codeforces problem page."""
    import requests
    from bs4 import BeautifulSoup

    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    inputs = [pre.get_text() for pre in soup.select("div.input pre")]
    outputs = [pre.get_text() for pre in soup.select("div.output pre")]
    samples = list(zip(inputs, outputs))

    stmt = soup.select_one("div.problem-statement")
    description = ""
    if stmt:
        lines = []
        for el in stmt.children:
            if not hasattr(el, "name") or not el.name:
                continue
            classes = el.get("class", [])
            if "header" in classes:
                continue
            if el.name == "p":
                text = el.get_text(" ", strip=True)
                if text:
                    lines.append(text)
            elif any(c in classes for c in ("input-specification", "output-specification", "note")):
                title_el = el.select_one(".title")
                if title_el:
                    lines.append(f"\n### {title_el.get_text(strip=True)}\n")
                for p in el.find_all("p"):
                    if "title" in p.get("class", []):
                        continue
                    text = p.get_text(" ", strip=True)
                    if text:
                        lines.append(text)
        description = "\n\n".join(line for line in lines if line.strip())

    return samples, description


def scaffold(platform: str, problem: str, url: str | None = None) -> None:
    problem_dir = os.path.join(SCRIPT_DIR, platform, problem)

    if os.path.isdir(problem_dir):
        print(f"Already exists: {problem_dir}")
        sys.exit(1)

    os.makedirs(problem_dir)

    # Write solution.cpp
    solution_path = os.path.join(problem_dir, "solution.cpp")
    with open(solution_path, "w") as f:
        f.write(SOLUTION_TEMPLATE)
    print(f"Created: {solution_path}")

    # Fetch samples if URL provided
    samples = []
    if url:
        samples, _ = fetch_page(platform, url)

    # Write notes.md
    notes_path = os.path.join(problem_dir, "notes.md")
    link_line = f"[Problem]({url})\n\n" if url else ""
    with open(notes_path, "w") as f:
        f.write(f"# {problem}\n\n{link_line}")
    print(f"Created: {notes_path}")

    # Write sample tests
    if url:
        if samples:
            for i, (inp, out) in enumerate(samples, start=1):
                in_path = os.path.join(problem_dir, f"{i}.in")
                out_path = os.path.join(problem_dir, f"{i}.out")
                with open(in_path, "w") as f:
                    f.write(inp if inp.endswith("\n") else inp + "\n")
                with open(out_path, "w") as f:
                    f.write(out if out.endswith("\n") else out + "\n")
            print(f"Fetched {len(samples)} sample test(s) from {url}")
        else:
            print(f"Warning: no sample tests found at {url}")
            _touch_empty_tests(problem_dir)
    else:
        _touch_empty_tests(problem_dir)
        print("Tip: pass a URL as 3rd argument to auto-fetch sample tests")

    print(f"\nRun: ./test.py {platform} {problem}")


def fetch_page(platform: str, url: str) -> tuple[list[tuple[str, str]], str]:
    try:
        if platform == "kattis":
            return fetch_kattis(url)
        elif platform == "codeforces":
            return fetch_codeforces(url)
        else:
            print(f"Note: auto-fetch not supported for '{platform}', skipping.")
            return [], ""
    except Exception as e:
        print(f"Warning: could not fetch page ({e})")
        return [], ""


def _touch_empty_tests(problem_dir: str) -> None:
    open(os.path.join(problem_dir, "1.in"), "w").close()
    open(os.path.join(problem_dir, "1.out"), "w").close()
    print("Created empty 1.in / 1.out — paste sample tests manually")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="new.py",
        description="Scaffold a new competitive programming problem.",
        usage="./new.py <platform> <problem> [url]",
    )
    parser.add_argument("platform", choices=["kattis", "codeforces", "leetcode"])
    parser.add_argument("problem", help="problem name / slug")
    parser.add_argument("url", nargs="?", help="problem page URL to auto-fetch sample tests")

    if argcomplete:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()
    scaffold(args.platform, args.problem, args.url)


if __name__ == "__main__":
    main()
