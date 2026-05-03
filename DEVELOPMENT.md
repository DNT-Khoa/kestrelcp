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
└── .github/
    ├── workflows/
    │   ├── bump-version.yml      ← manual: bumps package.json + pushes vX.Y.Z tag
    │   ├── release-extension.yml ← tag v* → builds .vsix → makes release
    │   └── scraper-canary.yml    ← weekly check that Kattis/CF/LC scrapers still work
    └── scripts/
        └── release_notes.py      ← AI-curated release notes (called by release workflow)
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

Releases are driven by two chained workflows — no local tagging required.

1. Push your changes to `main`.
2. GitHub → **Actions** → **Bump version and tag** → **Run workflow**, branch `main`, pick `patch` / `minor` / `major`.
   - Bumps `version` in `package.json`, commits as `chore: release vX.Y.Z`, creates tag `vX.Y.Z`, pushes both.
3. The pushed tag triggers **Release VS Code Extension**, which builds `sheikah-X.Y.Z.vsix` and attaches it to a new GitHub release.

### One-time PAT setup (required for chained triggering)

GitHub deliberately does **not** fire downstream workflows when an action uses the default `GITHUB_TOKEN` to push. Without a PAT, the bump workflow creates the tag but `release-extension.yml` never runs. Setup:

1. https://github.com/settings/personal-access-tokens → **Generate new token (fine-grained)**.
2. **Repository access** → only `DNT-Khoa/sheikah`.
3. **Permissions** → **Contents: Read and write**. Nothing else needed.
4. Set an expiration that fits your renewal cadence (e.g. 1 year).
5. Copy the token, then in the repo: **Settings → Secrets and variables → Actions → New repository secret**, name `RELEASE_PAT`, paste the value.

The bump workflow ([`.github/workflows/bump-version.yml`](.github/workflows/bump-version.yml)) checks out and pushes using `${{ secrets.RELEASE_PAT }}`, so the tag push counts as a "human" event and triggers the release workflow.

Pull `main` afterward to get the bump commit locally.

```bash
code --install-extension sheikah-X.Y.Z.vsix
```

### Manual fallback

If the bump workflow ever can't push (e.g. branch protection rules added later), tag locally:

```bash
npm version patch -m "chore: release v%s"   # bumps package.json, commits, tags
git push --follow-tags
```

The tag push still triggers the release workflow.

### AI-curated release notes

The release workflow calls [`.github/scripts/release_notes.py`](.github/scripts/release_notes.py), which sends the commit log + file-stat diff for the new version's range to Claude and asks for structured markdown release notes (grouped into ✨ Features / 🐛 Fixes / 📝 Documentation / 🔧 CI / Tooling sections).

**Setup** — add the API key as a repo secret (one-time):

1. **Settings → Secrets and variables → Actions → New repository secret**.
2. Name: `ANTHROPIC_API_KEY`. Value: your `sk-ant-…` key.

**Fallback behavior** — if the secret is missing, the API call fails, or the network blips, the workflow falls back to a plain commit list (the previous behavior) and the release still ships. The fallback reason is logged in the workflow output.

**Local preview** — run the script directly to see what Claude will produce for a given range:

```bash
export ANTHROPIC_API_KEY=sk-ant-…
pip install anthropic
python3 .github/scripts/release_notes.py v0.2.0 0.3.0
```

The first arg is the previous tag (or empty string for the initial release); the second is the version being released (no leading `v`).

> **Distribution model**: Sheikah currently ships as a `.vsix` on GitHub Releases. Sideloaded extensions don't auto-update — users re-install for new versions. Publishing to the [VS Code Marketplace](https://code.visualstudio.com/api/working-with-extensions/publishing-extension) is the natural next step once usage justifies it; that gives users in-editor auto-updates and discovery.
