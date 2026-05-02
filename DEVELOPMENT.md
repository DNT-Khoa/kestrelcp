# Sheikah — Development

Internal docs for working on the extension itself: dev loop, testing, CI, release.

For user-facing docs, see [README.md](./README.md).

---

## 📁 Repo layout

```
sheikah/
├── package.json              ← extension manifest (incl. marketplace icon)
├── tsconfig.json
├── src/
│   ├── extension.ts          ← commands + activation
│   ├── tree.ts               ← sidebar tree view (Playground + platforms)
│   └── runner.ts             ← terminal helper
├── scripts/                  ← bundled new.py / test.py / commit.py
├── tests/
│   └── canary.py             ← scraper canary (run by CI)
├── media/
│   ├── icon.svg              ← Sheikah emblem source
│   └── icon.png              ← 256×256 marketplace logo
├── .vscode/{launch,tasks}.json   ← F5 to debug
└── .github/workflows/
    ├── release-extension.yml ← tag v* → builds .vsix → makes release
    └── scraper-canary.yml    ← weekly check that Kattis/CF/LC scrapers still work
```

The `scripts/` directory is the canonical source of truth for the Python scripts. Edits there flow into the next packaged release.

---

## 🛠️ Develop

```bash
npm install
npm run compile
# F5 in VS Code → launches a dev instance with the extension loaded
```

In the dev instance: open any folder → **Sheikah: Initialize Workspace** → scaffolds scripts and platform dirs → ready to test.

### Manual test plan

Use this checklist after any code change to verify everything still works end-to-end.

1. **Launch the dev instance**
   - In the sheikah repo window, press **F5** (or **Run** → *Start Debugging*).
   - A new VS Code window titled **[Extension Development Host]** opens with the extension active.

2. **Open a test workspace**
   - **File → Open Folder…** → pick a fresh empty folder (e.g. `~/tmp/sheikah-test`). Don't reuse the sheikah repo itself — it'll get cluttered with `kattis/`, `codeforces/`, etc.

3. **Initialize and check the sidebar**
   - **Cmd+Shift+P** → **Sheikah: Initialize Workspace**.
   - Click the 🚀 rocket in the activity bar. The Problems sidebar should show:
     ```
     🧪 Playground       ← inline ▶ on hover
     📁 kattis
     📁 codeforces
     📁 leetcode
     ```

4. **Test the playground**

   | Action | Expected |
   |---|---|
   | Click the **Playground** label | `playground/Playground.java` opens with the `main` template |
   | Hover the row → click ▶ | A `Sheikah` terminal runs `( cd playground && javac *.java && java Playground )` and prints `Hello from Sheikah playground.` |
   | Edit `Playground.java`, save, click ▶ again | Recompiles and prints the new output |
   | Add a `playground/Helper.java` class, call it from `Playground.main`, click ▶ | Both compile; `java Playground` uses `Helper` |
   | Cmd+Shift+P → **Sheikah: Run Playground** | Same as the ▶ button |

5. **Test problem flows** (regression check)
   - **Sheikah: New Problem** → pick a platform, paste a URL or slug → folder + sample tests scaffolded.
   - Click a problem in the sidebar → `Solution.java` opens.
   - Hover the problem → click ▶ → tests run.
   - **Sheikah: Run Tests for Current File** with `Solution.java` open → tests run.

6. **Test AI commit** (requires `ANTHROPIC_API_KEY`)
   - Stage some changes in Source Control.
   - **Sheikah: AI Commit** → terminal proposes a Conventional Commit message; respond with `y` / `n` / `e`.

7. **Test refetch (bulk repair flow)**
   - Scaffold 2–3 problems across different platforms (e.g. `645/A` on Codeforces, `oddecho` on Kattis).
   - Edit one `Solution.java` with a recognizable comment so you can verify it survives.
   - Manually corrupt one or more `*.in` files (overwrite their contents with any junk string, e.g. `bogus`) to simulate the old-buggy-scraper state.
   - **Cmd+Shift+P → Sheikah: Refetch All Sample Tests**.
   - A confirmation modal should show the per-platform problem counts.
   - Confirm. Terminal should iterate over every problem and end with `Sheikah: refetch complete.`
   - Verify: corrupted `*.in` files restored to correct content, `Solution.java` still has your comment, `notes.md` untouched.
   - Edge case: with no problems scaffolded, the command should show `Sheikah: no problems to refetch.` instead of running the loop.

### Iterating

Run `npm run watch` in a terminal so `out/` stays fresh. After each edit in `src/`, hit **Cmd+R** ("Reload Window") in the dev instance — no need to kill and restart F5.

### Quick sanity check (no F5 needed)

```bash
npm run compile
```

If `tsc` is clean and F5 still fails, it's a launch-config problem, not a code problem.

---

## 🐦 Scraper canary (CI)

The bundled scrapers (`new.py`) depend on Kattis / Codeforces / LeetCode HTML and GraphQL — these change without notice. The **Scraper Canary** workflow ([`.github/workflows/scraper-canary.yml`](.github/workflows/scraper-canary.yml)) runs weekly (Monday 06:00 UTC) and on-demand to catch breakage early.

It runs [`tests/canary.py`](tests/canary.py), which fetches one stable problem per platform and asserts:

- `1.in` and `1.out` exist and are non-empty
- `1.in` has at least the expected number of non-empty lines (per-platform `min_input_lines` in the `CANARIES` list) — guards against silent collapse where multi-line input gets joined onto a single line, e.g. Codeforces `<br>` tags being dropped by the parser

On failure, it opens or comments on a GitHub issue tagged `scraper-broken` with the failing platform and a link to the run logs. Three retries per platform absorb transient flakes.

Run it locally before pushing scraper changes:

```bash
pip install requests beautifulsoup4
python3 tests/canary.py
```

---

## 📦 Release

Tag the repo with `vX.Y.Z` and push:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The **Release VS Code Extension** workflow builds `sheikah-X.Y.Z.vsix` and attaches it to a GitHub release. Keep the repo private to limit access; install with:

```bash
code --install-extension sheikah-X.Y.Z.vsix
```

> **Distribution model**: VS Code Marketplace is all-or-nothing public, so private extensions live on GitHub Releases. Auto-updates aren't supported for sideloaded extensions — re-install for new versions, or graduate to a self-hosted private marketplace ([`coder/code-marketplace`](https://github.com/coder/code-marketplace)) if that becomes painful.
