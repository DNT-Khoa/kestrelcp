#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""
Usage:
  ./new.py <platform> <url>                       # derive folder from URL + fetch tests
  ./new.py <platform> <problem-name>              # just scaffold (slug-fetch for leetcode)
  ./new.py <platform> <problem-name> <url>        # scaffold + fetch tests (explicit)

Examples:
  ./new.py kattis https://open.kattis.com/problems/oddecho
  ./new.py codeforces https://codeforces.com/problemset/problem/1/A
  ./new.py leetcode https://leetcode.com/problems/two-sum/
  ./new.py leetcode two-sum                       # slug-only shorthand
  ./new.py kattis oddecho                         # scaffold without fetch
"""

import argparse
import os
import re
import sys

try:
    import argcomplete
except ImportError:
    argcomplete = None

WORKSPACE = os.getcwd()

SOLUTION_TEMPLATE = """\
import java.util.*;

public class Solution {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        // your code here
    }
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


def derive_problem_name(platform: str, url: str) -> str:
    """Extract a folder-safe problem name from a problem URL."""
    if platform in ("kattis", "leetcode"):
        m = re.search(r"/problems/([^/?#]+)", url)
        if m:
            return m.group(1)
    elif platform == "codeforces":
        m = re.search(r"/(?:problemset/problem|contest)/(\d+)/(?:problem/)?([A-Za-z0-9]+)", url)
        if m:
            return f"{m.group(1)}{m.group(2)}"
    raise ValueError(f"could not derive problem name from URL: {url}")


def fetch_leetcode(url: str) -> tuple[list[tuple[str, str]], str]:
    """Returns (samples, description_md) from a LeetCode problem page.

    Uses LeetCode's public GraphQL endpoint. `exampleTestcases` is already
    newline-separated, one value per parameter — grouped by params count from
    `metaData` to form each `.in` file. Outputs are parsed from `<pre>` blocks
    in the rendered `content` HTML.
    """
    import json
    import requests
    from bs4 import BeautifulSoup

    m = re.search(r"/problems/([^/]+)", url)
    if not m:
        raise ValueError(f"could not extract slug from {url}")
    slug = m.group(1)

    query = """
    query questionData($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        content
        exampleTestcases
        metaData
      }
    }
    """
    r = requests.post(
        "https://leetcode.com/graphql/",
        json={"query": query, "variables": {"titleSlug": slug}, "operationName": "questionData"},
        headers={**HEADERS, "Content-Type": "application/json", "Referer": url},
        timeout=10,
    )
    r.raise_for_status()
    question = (r.json().get("data") or {}).get("question")
    if not question:
        raise ValueError(f"no public problem found for slug '{slug}' (premium?)")

    raw_inputs = question.get("exampleTestcases") or ""
    meta = json.loads(question.get("metaData") or "{}")
    n_params = max(1, len(meta.get("params", [])))

    lines = raw_inputs.split("\n") if raw_inputs else []
    inputs = []
    for i in range(0, len(lines), n_params):
        chunk = lines[i:i + n_params]
        if len(chunk) == n_params:
            inputs.append("\n".join(chunk))

    content_html = question.get("content") or ""
    soup = BeautifulSoup(content_html, "html.parser")

    outputs = []
    for pre in soup.select("pre"):
        t = pre.get_text("\n")
        mo = re.search(r"Output:\s*(.+?)(?:\n\s*Explanation|\Z)", t, re.DOTALL)
        if mo:
            outputs.append(mo.group(1).strip())

    samples = list(zip(inputs, outputs))

    desc_lines = []
    for el in soup.find_all(["p", "li"]):
        if el.find_parent("pre"):
            continue
        t = el.get_text(" ", strip=True)
        if t:
            desc_lines.append(t if el.name == "p" else f"- {t}")
    description = "\n\n".join(desc_lines)

    return samples, description


def fetch_codeforces(url: str) -> tuple[list[tuple[str, str]], str]:
    """Returns (samples, description_md) from a Codeforces problem page."""
    import requests
    from bs4 import BeautifulSoup

    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    inputs = [pre.get_text(separator="\n") for pre in soup.select("div.input pre")]
    outputs = [pre.get_text(separator="\n") for pre in soup.select("div.output pre")]
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
    problem_dir = os.path.join(WORKSPACE, platform, problem)

    if os.path.isdir(problem_dir):
        print(f"Already exists: {problem_dir}")
        sys.exit(1)

    os.makedirs(problem_dir)

    if url is None and platform == "leetcode":
        url = f"https://leetcode.com/problems/{problem}/"

    # Write Solution.java
    solution_path = os.path.join(problem_dir, "Solution.java")
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

    print(f"\nNext: open {os.path.join(platform, problem, 'Solution.java')} and click the ▶ button on the problem in the KestrelCP sidebar to run tests.")


def fetch_page(platform: str, url: str) -> tuple[list[tuple[str, str]], str]:
    try:
        if platform == "kattis":
            return fetch_kattis(url)
        elif platform == "codeforces":
            return fetch_codeforces(url)
        elif platform == "leetcode":
            return fetch_leetcode(url)
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


def _read_url_from_notes(problem_dir: str) -> str | None:
    notes_path = os.path.join(problem_dir, "notes.md")
    if not os.path.exists(notes_path):
        return None
    with open(notes_path) as fh:
        for line in fh:
            m = re.match(r"\[Problem\]\((https?://[^)]+)\)", line.strip())
            if m:
                return m.group(1)
    return None


def refetch_samples(platform: str, problem: str, url: str | None = None) -> None:
    """Re-fetch sample tests for an existing problem.

    Overwrites *.in / *.out files, leaves Solution.java and notes.md untouched.
    Use this to repair problems whose samples were saved by an older buggy
    scraper, without losing in-progress solution code.
    """
    problem_dir = os.path.join(WORKSPACE, platform, problem)
    if not os.path.isdir(problem_dir):
        print(f"Not found: {problem_dir}", file=sys.stderr)
        sys.exit(1)

    if url is None:
        url = _read_url_from_notes(problem_dir)
        if not url:
            print(
                f"Could not find a [Problem](url) line in {problem_dir}/notes.md. "
                f"Add one (e.g. `[Problem](https://...)`) and re-run KestrelCP: Refetch All Sample Tests.",
                file=sys.stderr,
            )
            sys.exit(1)

    samples, _ = fetch_page(platform, url)
    if not samples:
        print(f"No samples fetched from {url} — aborting (existing files left alone)", file=sys.stderr)
        sys.exit(1)

    for f in os.listdir(problem_dir):
        if f.endswith(".in") or f.endswith(".out"):
            os.remove(os.path.join(problem_dir, f))

    for i, (inp, out) in enumerate(samples, start=1):
        in_path = os.path.join(problem_dir, f"{i}.in")
        out_path = os.path.join(problem_dir, f"{i}.out")
        with open(in_path, "w") as fh:
            fh.write(inp if inp.endswith("\n") else inp + "\n")
        with open(out_path, "w") as fh:
            fh.write(out if out.endswith("\n") else out + "\n")

    print(f"Refetched {len(samples)} sample test(s) from {url}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="new.py",
        description="Scaffold a new competitive programming problem.",
        usage="./new.py <platform> <problem> [url]",
    )
    parser.add_argument("platform", choices=["kattis", "codeforces", "leetcode"])
    parser.add_argument("problem_or_url", help="problem name/slug OR a full problem URL")
    parser.add_argument("url", nargs="?", help="problem page URL (omit if first arg is a URL)")
    parser.add_argument(
        "--refetch",
        action="store_true",
        help="re-fetch sample tests for an existing problem (overwrites *.in/*.out only)",
    )

    if argcomplete:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()

    if args.refetch:
        if args.problem_or_url.startswith(("http://", "https://")):
            parser.error("--refetch expects a problem name as the second arg, not a URL")
        refetch_samples(args.platform, args.problem_or_url, args.url)
        return

    if args.problem_or_url.startswith(("http://", "https://")):
        if args.url is not None:
            parser.error("when first arg is a URL, do not pass a second URL")
        url = args.problem_or_url
        try:
            problem = derive_problem_name(args.platform, url)
        except ValueError as e:
            parser.error(str(e))
    else:
        problem = args.problem_or_url
        url = args.url

    scaffold(args.platform, problem, url)


if __name__ == "__main__":
    main()