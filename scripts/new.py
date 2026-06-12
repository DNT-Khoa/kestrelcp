#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""
Usage:
  ./new.py <platform> <url>                       # derive folder from URL + fetch tests

Examples:
  ./new.py kattis https://open.kattis.com/problems/oddecho
  ./new.py codeforces https://codeforces.com/problemset/problem/1/A
  ./new.py leetcode https://leetcode.com/problems/two-sum/
"""

import argparse
import os
import re
import sys
import time

HTTP_TIMEOUT_SECONDS = 25
TRANSIENT_EXC_NAMES = {"Timeout", "ReadTimeout", "ConnectTimeout", "ConnectionError"}

try:
    import argcomplete
except ImportError:
    argcomplete = None

WORKSPACE = os.getcwd()

COMPLEXITY_JAVADOC = """\
/**
 * <b>Time complexity:</b> O(?)
 *
 * <p><b>Space complexity:</b> O(?)
 *
 * <p><b>Notes:</b>
 * <ul>
 *   <li></li>
 * </ul>
 */
"""

SOLUTION_TEMPLATE = f"""\
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintWriter;

{COMPLEXITY_JAVADOC}public class Solution {{
    public static void main(String[] args) throws Exception {{
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        PrintWriter pw = new PrintWriter(System.out);
        // your code here

        pw.close();
    }}
}}
"""


def _inject_complexity_javadoc(code: str) -> str:
    """Insert COMPLEXITY_JAVADOC directly above the `class Solution` declaration.

    LeetCode's codeSnippets sometimes carry a leading `/** Definition for ... */`
    block describing helper types (ListNode, TreeNode); we want the header to sit
    on the user's class, not above those.
    """
    pattern = re.compile(r"^((?:public\s+|final\s+)*class\s+Solution\b)", re.MULTILINE)
    m = pattern.search(code)
    if not m:
        return COMPLEXITY_JAVADOC + code
    return code[:m.start()] + COMPLEXITY_JAVADOC + code[m.start():]

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

    r = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
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


def fetch_leetcode(url: str) -> tuple[list[tuple[str, str]], str, str | None]:
    """Returns (samples, description_md, java_template) from a LeetCode problem.

    LeetCode does not render full problem HTML on a single fetch — but the
    public GraphQL endpoint hands us everything in one shot without auth:
      - exampleTestcases: newline-separated inputs, one param per line
      - metaData:        param count + types, used to group lines into cases
      - content:         HTML problem statement (also has expected outputs)
      - codeSnippets:    per-language starter code (we use the Java one)

    Outputs aren't in exampleTestcases — we best-effort scrape them from the
    HTML content. If that fails the local *.out files end up empty; the real
    pass/fail still comes from the judge's expected_code_answer at test time.
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
        codeSnippets { langSlug code }
      }
    }
    """
    r = requests.post(
        "https://leetcode.com/graphql/",
        json={
            "query": query,
            "variables": {"titleSlug": slug},
            "operationName": "questionData",
        },
        headers={**HEADERS, "Content-Type": "application/json", "Referer": url},
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    r.raise_for_status()
    question = (r.json().get("data") or {}).get("question")
    if not question:
        raise ValueError(
            f"no public problem found for slug '{slug}' (premium-only?). "
            f"KestrelCP cannot scaffold premium problems — they need a LeetCode subscription."
        )

    raw_inputs = question.get("exampleTestcases") or ""
    meta = json.loads(question.get("metaData") or "{}")
    n_params = max(1, len(meta.get("params", [])))

    lines = raw_inputs.split("\n") if raw_inputs else []
    inputs: list[str] = []
    for i in range(0, len(lines), n_params):
        chunk = lines[i:i + n_params]
        if len(chunk) == n_params:
            inputs.append("\n".join(chunk))

    content_html = question.get("content") or ""
    soup = BeautifulSoup(content_html, "html.parser")

    outputs: list[str] = []
    # New LeetCode HTML (2024+): each example wrapped in <div class="example-block">
    # with <p><strong>Output:</strong> <span class="example-io">...</span></p>
    for block in soup.select("div.example-block"):
        for p in block.find_all("p"):
            strong = p.find("strong")
            if not strong or "Output" not in strong.get_text():
                continue
            span = p.find("span", class_="example-io")
            if span:
                outputs.append(span.get_text("\n").strip())
            else:
                txt = p.get_text(" ", strip=True)
                mo = re.match(r"^Output:\s*(.+)$", txt)
                if mo:
                    outputs.append(mo.group(1).strip())
            break
    # Legacy format: <pre>Input: ...\nOutput: ...\nExplanation: ...</pre>
    if not outputs:
        for pre in soup.select("pre"):
            t = pre.get_text("\n")
            mo = re.search(r"Output:\s*(.+?)(?:\n\s*Explanation|\Z)", t, re.DOTALL)
            if mo:
                outputs.append(mo.group(1).strip())

    # Pad outputs with empty strings if we found fewer than inputs.
    while len(outputs) < len(inputs):
        outputs.append("")
    samples = list(zip(inputs, outputs[: len(inputs)]))

    desc_lines = []
    for el in soup.find_all(["p", "li"]):
        if el.find_parent("pre") or el.find_parent("div", class_="example-block"):
            continue
        t = el.get_text(" ", strip=True)
        if t:
            desc_lines.append(t if el.name == "p" else f"- {t}")
    description = "\n\n".join(desc_lines)

    java_template = None
    for snip in question.get("codeSnippets") or []:
        if snip.get("langSlug") == "java":
            java_template = snip.get("code")
            break

    return samples, description, java_template


def fetch_codeforces(url: str) -> tuple[list[tuple[str, str]], str]:
    """Returns (samples, description_md) from a Codeforces problem page."""
    import requests
    from bs4 import BeautifulSoup

    r = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
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


def scaffold(platform: str, problem: str, url: str) -> None:
    problem_dir = os.path.join(WORKSPACE, platform, problem)

    if os.path.isdir(problem_dir):
        print(f"Already exists: {problem_dir}")
        sys.exit(1)

    os.makedirs(problem_dir)

    samples, _, java_template = fetch_page(platform, url)

    solution_path = os.path.join(problem_dir, "Solution.java")
    solution_code = _inject_complexity_javadoc(java_template) if java_template else SOLUTION_TEMPLATE
    with open(solution_path, "w") as f:
        f.write(solution_code)
        if not solution_code.endswith("\n"):
            f.write("\n")
    print(f"Created: {solution_path}")

    notes_path = os.path.join(problem_dir, "notes.md")
    with open(notes_path, "w") as f:
        f.write(f"# {problem}\n\n[Problem]({url})\n\n")
    print(f"Created: {notes_path}")

    if samples:
        for i, (inp, out) in enumerate(samples, start=1):
            _write_sample(os.path.join(problem_dir, f"{i}.in"), inp)
            _write_sample(os.path.join(problem_dir, f"{i}.out"), out)
        print(f"Fetched {len(samples)} sample test(s) from {url}")
    else:
        print(f"Warning: no sample tests found at {url}")
        _touch_empty_tests(problem_dir)

    print(f"\nNext: open {os.path.join(platform, problem, 'Solution.java')} and click the ▶ button in the editor toolbar to run tests.")


def fetch_page(platform: str, url: str) -> tuple[list[tuple[str, str]], str, str | None]:
    """(samples, description_md, java_template_or_none)

    java_template is non-None only for LeetCode — its codeSnippets field gives
    us the exact starter code from the editor, with the right method signature.
    """
    if platform == "leetcode":
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                return fetch_leetcode(url)
            except Exception as e:
                last_exc = e
                if type(e).__name__ not in TRANSIENT_EXC_NAMES or attempt == 2:
                    break
                wait = 2 * (attempt + 1)
                print(f"Warning: fetch attempt {attempt + 1} failed ({e}); retrying in {wait}s...")
                time.sleep(wait)
        print(f"Warning: could not fetch page ({last_exc})")
        return [], "", None

    fetchers = {
        "kattis": fetch_kattis,
        "codeforces": fetch_codeforces,
    }
    fn = fetchers[platform]

    last_exc = None
    for attempt in range(3):
        try:
            samples, description = fn(url)
            return samples, description, None
        except Exception as e:
            last_exc = e
            if type(e).__name__ not in TRANSIENT_EXC_NAMES or attempt == 2:
                break
            wait = 2 * (attempt + 1)
            print(f"Warning: fetch attempt {attempt + 1} failed ({e}); retrying in {wait}s...")
            time.sleep(wait)
    print(f"Warning: could not fetch page ({last_exc})")
    return [], "", None


def _touch_empty_tests(problem_dir: str) -> None:
    open(os.path.join(problem_dir, "1.in"), "w").close()
    open(os.path.join(problem_dir, "1.out"), "w").close()
    print("Created empty 1.in / 1.out — paste sample tests manually")


def _write_sample(path: str, text: str) -> None:
    text = text.lstrip("\n")
    if not text.endswith("\n"):
        text += "\n"
    with open(path, "w") as f:
        f.write(text)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="new.py",
        description="Scaffold a new competitive programming problem.",
        usage="./new.py <platform> <url>",
    )
    parser.add_argument("platform", choices=["kattis", "codeforces", "leetcode"])
    parser.add_argument("url", help="full problem URL")

    if argcomplete:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()

    if not args.url.startswith(("http://", "https://")):
        parser.error("expected a full URL (e.g. https://leetcode.com/problems/two-sum/)")

    try:
        problem = derive_problem_name(args.platform, args.url)
    except ValueError as e:
        parser.error(str(e))

    scaffold(args.platform, problem, args.url)


if __name__ == "__main__":
    main()