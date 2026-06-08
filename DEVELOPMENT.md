# KestrelCP — Development & Architecture

Internal docs for working on the extension itself: a walkthrough of how it's built, how to iterate locally, how to test it, and how it ships to users. For user-facing docs see [README.md](./README.md).

---

## Table of Contents

1. [Quick start](#1-quick-start)
2. [What is a VS Code extension?](#2-what-is-a-vs-code-extension)
3. [Repo layout](#3-repo-layout)
4. [Manifest — package.json](#4-manifest--packagejson)
5. [TypeScript source — src/](#5-typescript-source--src)
6. [Python scripts — scripts/](#6-python-scripts--scripts)
7. [Security decisions](#7-security-decisions)
8. [Design decisions & trade-offs](#8-design-decisions--trade-offs)
9. [End-to-end flows](#9-end-to-end-flows)
10. [Manual test plan](#10-manual-test-plan)
11. [Scraper canary (CI)](#11-scraper-canary-ci)
12. [Build, debug & package](#12-build-debug--package)
13. [Release process](#13-release-process)

---

## 1. Quick start

```bash
npm install
npm run compile
# F5 in VS Code → launches a dev instance with the extension loaded
```

In the dev instance: open any folder → **KestrelCP: Initialize Workspace** → creates `kattis/` / `codeforces/` / `leetcode/` / `playground/Playground.java` → ready to test. The Python scripts run from the extension's install dir, not from the workspace, so there's nothing to copy.

### Iterating

Run `npm run watch` in a terminal so `out/` stays fresh. After each edit in `src/`, hit **Cmd+R** ("Reload Window") in the dev instance — no need to kill and restart F5.

### Quick sanity check (no F5 needed)

```bash
npm run compile
```

If `tsc` is clean and F5 still fails, it's a launch-config problem, not a code problem.

---

## 2. What is a VS Code extension?

A VS Code extension is a Node.js package that VS Code loads into its process. At its core, you need:

- **`package.json`** — the _manifest_. Declares everything the extension contributes to VS Code: commands, views, settings, menus, activation triggers, and metadata. VS Code reads this file _before_ running any of your code to know what your extension provides.
- **An entry point** (typically `out/extension.js`) — a JavaScript / TypeScript module that exports an `activate()` function. VS Code calls this when your extension needs to start up.
- **`tsconfig.json`** — TypeScript configuration. Extensions are almost always written in TypeScript and compiled to JavaScript.

The extension runs in VS Code's **Extension Host** process — a separate Node.js process that VS Code manages. Your code has access to the full VS Code API (`vscode` module) but runs isolated from the editor's UI thread.

---

## 3. Repo layout

```
kestrelcp/
├── package.json              ← extension manifest (incl. marketplace icon)
├── tsconfig.json
├── src/
│   ├── extension.ts          ← commands + activation + editor-toolbar context keys
│   ├── daily.ts              ← LeetCode Daily Challenge sidebar widget
│   └── runner.ts             ← terminal helper
├── scripts/
│   ├── new.py                ← problem scaffolding + scraping (all platforms)
│   ├── test.py               ← compile & run Java solutions locally (Kattis / Codeforces)
│   ├── test_leetcode.py      ← run LeetCode solutions via the official judge
│   ├── submit_leetcode.py    ← submit a LeetCode solution for judging
│   ├── leetcode_auth.py      ← shared LeetCode auth helpers (JWT decode, error classifier)
│   └── commit.py             ← AI-generated git commit messages via Claude
├── tests/
│   └── canary.py             ← scraper canary (run by CI)
├── media/
│   ├── icon.svg              ← KestrelCP icon source (Rubik's cube)
│   ├── icon-sidebar.svg      ← Activity bar icon (24×24 monochrome)
│   └── icon.png              ← 256×256 marketplace logo
├── .vscode/{launch,tasks}.json   ← F5 to debug
├── .github/
│   ├── workflows/
│   │   ├── bump-version.yml      ← manual: bumps package.json + pushes vX.Y.Z tag
│   │   ├── release-extension.yml ← tag v* → builds .vsix → makes release
│   │   └── scraper-canary.yml    ← weekly check that scrapers still work
│   └── scripts/
│       └── release_notes.py      ← AI-curated release notes (called by release workflow)
├── README.md                 ← user-facing docs
└── DEVELOPMENT.md            ← this file
```

The `scripts/` directory ships in the `.vsix` and the extension invokes those scripts directly from the install location (`~/.vscode/extensions/khoa-doan.kestrelcp-X.Y.Z/scripts/`) — they are **not** copied into user workspaces. That means script fixes flow to users automatically as soon as they upgrade the extension; no per-workspace re-init needed.

**Why two languages?** The TypeScript code handles VS Code integration (commands, UI, settings). The Python scripts handle the heavy lifting (web scraping, process management, AI calls). This split exists because:

- Web scraping libraries (`requests`, `beautifulsoup4`) are mature and battle-tested in Python.
- The `anthropic` Python SDK is first-class.
- Competitive programmers commonly have Python installed already.

---

## 4. Manifest — package.json

VS Code reads this file _before_ executing any code, to understand what the extension contributes.

### Metadata

```json
{
  "name": "kestrelcp",
  "displayName": "KestrelCP",
  "publisher": "khoa-doan",
  "main": "./out/extension.js",
  "engines": { "vscode": "^1.85.0" }
}
```

- **`name`** — npm-style package name (lowercase, no spaces). Combined with `publisher` to form the extension ID: `khoa-doan.kestrelcp`.
- **`main`** — compiled JavaScript entry point. TypeScript compiles `src/extension.ts` → `out/extension.js`.
- **`engines.vscode`** — minimum VS Code version required. Controls which VS Code APIs you can use.

### Activation events

```json
"activationEvents": ["onStartupFinished"]
```

VS Code is lazy — it doesn't load your extension until it's needed. **Activation events** declare _when_ to load. Options include `onCommand:`, `onView:`, `onStartupFinished`, etc.

**Decision:** KestrelCP uses `onStartupFinished` because the editor-toolbar buttons need to be wired up as soon as the user opens a `Solution.java`, which requires the context-key updater to be installed. The LeetCode Daily sidebar also needs to fetch on startup. Using a more targeted event like `onView:` would defer this until the user explicitly opens the sidebar; `onStartupFinished` is simpler and the extension is lightweight enough that the startup cost is negligible.

### Commands

Each command has a unique ID (e.g. `kestrelcp.runTestsForCurrent`), a `title` shown in the palette, and optionally an `icon` from VS Code's [Codicon set](https://microsoft.github.io/vscode-codicons/) via `$(iconName)` syntax. Declaring a command in `package.json` _only registers it in the UI_; the actual handler is registered in `extension.ts` via `vscode.commands.registerCommand()`.

### Views (Sidebar)

```json
"viewsContainers": {
  "activitybar": [{ "id": "kestrelcp", "title": "KestrelCP", "icon": "media/icon-sidebar.svg" }]
},
"views": {
  "kestrelcp": [{ "id": "kestrelcp.daily", "name": "LeetCode Daily" }]
}
```

This creates the cube icon in the activity bar and a single "LeetCode Daily" panel inside it, populated by `DailyChallengeProvider` in [daily.ts](src/daily.ts).

**Decision:** The activity bar entry exists primarily for marketplace discoverability. The view itself is intentionally tiny (one row showing today's LeetCode Daily Challenge) because real action commands live on the **editor toolbar** instead, where they're closest to the code being edited.

### Menus

```json
"menus": {
  "commandPalette": [
    { "command": "kestrelcp.runTestsForCurrent", "when": "kestrelcp.activeIsProblem" },
    { "command": "kestrelcp.submitLeetcode",     "when": "kestrelcp.activeIsLeetcode" },
    { "command": "kestrelcp.runPlayground",      "when": "kestrelcp.activeIsPlayground" }
  ],
  "editor/title": [
    { "command": "kestrelcp.runTestsForCurrent", "when": "kestrelcp.activeIsProblem",   "group": "navigation@1" },
    { "command": "kestrelcp.submitLeetcode",     "when": "kestrelcp.activeIsLeetcode",  "group": "navigation@2" },
    { "command": "kestrelcp.runPlayground",      "when": "kestrelcp.activeIsPlayground", "group": "navigation@1" }
  ],
  "view/title": [
    { "command": "kestrelcp.refreshDaily", "when": "view == kestrelcp.daily", "group": "navigation@1" }
  ]
}
```

- **`commandPalette`** — gates context-sensitive commands behind `when` clauses, so the palette doesn't surface "Submit to LeetCode" when you're editing a CSS file. Commands without an entry here are visible unconditionally; `"when": "false"` hides them entirely.
- **`editor/title`** with `"group": "navigation"` — adds icon buttons to the top-right of the editor toolbar. Visibility depends on the three `activeIs*` context keys (set whenever the active editor changes). That's how the ▶ Run button only appears for `Solution.java`, the ☁️ Submit button only appears for LeetCode `Solution.java`, and the ▶ Run Playground button only appears for `Playground.java`.
- **`view/title`** — the 🔄 refresh button on the LeetCode Daily sidebar's header.
- **`@1`, `@2`** — ordering suffixes within a menu group.

#### Context keys

KestrelCP sets three custom context keys to drive menu visibility:

```typescript
function updateActiveContext() {
  // ... derive isProblem / isLeetcode / isPlayground from active editor's path
  vscode.commands.executeCommand("setContext", "kestrelcp.activeIsProblem",   isProblem);
  vscode.commands.executeCommand("setContext", "kestrelcp.activeIsLeetcode",  isLeetcode);
  vscode.commands.executeCommand("setContext", "kestrelcp.activeIsPlayground", isPlayground);
}
```

Context keys are VS Code's standard mechanism for conditional UI. Setting them via `setContext` makes them available to `when` clauses in `package.json`. More robust than regex matches on `resourcePath` because we can encode any logic in TypeScript instead of trying to express it as a JSON regex.

### Configuration (settings)

```json
"configuration": {
  "title": "KestrelCP",
  "properties": {
    "kestrelcp.commitModel": {
      "type": "string",
      "default": "claude-haiku-4-5",
      "description": "Anthropic model used to generate commit messages."
    }
  }
}
```

**Decision:** Only non-sensitive values live in settings. Two other things you might expect here are deliberately handled differently:

1. **Secrets** (Anthropic API key, LeetCode session cookies) go in `SecretStorage`, managed by `KestrelCP: Set ...` commands. See [Secrets in SecretStorage, not settings](#secrets-in-secretstorage-not-settings).
2. **Python interpreter path** isn't configurable — KestrelCP invokes `python3` and expects it on `PATH`. On activation, `checkPython3()` spawns `python3 --version` and shows an error if it fails. Users who need a virtualenv should activate it before launching VS Code.

---

## 5. TypeScript source — src/

### extension.ts — entry point & commands

The brain of the extension. Exports two functions VS Code calls: `activate(context)` once on startup, and `deactivate()` on unload (empty — nothing to clean up).

**The ExtensionContext.** `context.extensionPath` gives the absolute path where the extension is installed (e.g. `~/.vscode/extensions/khoa-doan.kestrelcp-X.Y.Z/`) — this is how `bundledScript()` locates the Python scripts. `context.subscriptions` is a disposal array; anything pushed gets automatically cleaned up on deactivate, preventing resource leaks.

**Command registration.** Each `registerCommand` call connects a command ID (from `package.json`) to a TypeScript handler. Action commands derive their target problem from the **active editor's path** (via `activeProblem()`), which keeps handlers context-free and lets the same handler serve both the editor toolbar button and the command palette entry.

**FileSystemWatcher.** A single narrow watcher:

```typescript
const watcher = vscode.workspace.createFileSystemWatcher(
  "**/{kattis,codeforces,leetcode}/*/Solution.java",
);
watcher.onDidCreate((uri) => vscode.commands.executeCommand("vscode.open", uri));
```

Detects when a new `Solution.java` is created inside any `<platform>/<problem>/` directory and opens it. Watching for the file create event is more reliable than `setTimeout`-ing the open after the scaffold script — the terminal API is fire-and-forget and the watcher reacts to the actual file write.

**Active-editor context keys.** `updateActiveContext()` runs once on activation and again whenever the active editor changes. `isProblem` is true when the active editor is `Solution.java` inside `<platform>/<problem>/`; `isLeetcode` is the narrower case where `<platform>` is `leetcode`; `isPlayground` is true for `playground/Playground.java`.

**Shell quoting (security).**

```typescript
function shellQuote(s: string): string {
  return "'" + s.replace(/'/g, "'\\''") + "'";
}
```

All values interpolated into terminal commands go through `shellQuote()`, which wraps the string in POSIX single quotes and escapes any embedded single quotes. This prevents shell injection — without it, a problem URL like `` `whoami` `` or `$(rm -rf .)` pasted into the input box would be executed as a shell command. The POSIX technique: end the current single-quoted string (`'`), insert an escaped literal single quote (`\'`), then start a new single-quoted string. `it's` becomes `'it'\''s'`.

```typescript
function bundledScript(name: string): string {
  return `python3 ${shellQuote(path.join(extensionRoot, "scripts", name))}`;
}
```

The script path is shell-quoted because the extension install path could contain spaces (e.g. `/Users/John Smith/.vscode/extensions/...`). `python3` itself has no special characters and runs through the shell's `PATH` lookup.

**Key command handlers.**

- **`initWorkspace`** — Creates the platform directories and the playground scaffold. The only command that doesn't go through `requireInit()`, since it _is_ the initialization step.
- **`newProblem`** — Calls `requireInit()`, prompts via `showQuickPick(platforms)` + `showInputBox(URL)`, then dispatches to `new.py`. The FileSystemWatcher handles opening the newly-created `Solution.java`.
- **`runTestsForCurrent`** — Derives `platform` and `problem` from the active editor's path using `path.relative()`. If the file is at `<workspace>/codeforces/645A/Solution.java`, the relative path splits into `['codeforces', '645A', 'Solution.java']`. Dispatches to `test.py` or `test_leetcode.py` based on platform.
- **`aiCommit`** — Dispatches `commit.py`. The script handles all interaction (prompts, editing).

### daily.ts — LeetCode Daily Challenge sidebar

Shows exactly one thing: today's LeetCode Daily Challenge. Click the row to scaffold (or open the existing `Solution.java` if you started it earlier today). This is the only persistent UI panel KestrelCP contributes — every other action lives on the editor toolbar or in the command palette.

**Why so minimal?** Earlier versions of KestrelCP had a tree of all problems grouped by platform, but in practice users navigate by file (Cmd+P → `Solution.java`) and trigger actions from the editor toolbar or palette. The sidebar was rarely glanced at. The Daily Challenge is the one piece of *new* information worth surfacing without context-switching.

**State machine.**

```typescript
type State =
  | { kind: "loading" }
  | { kind: "loaded"; question: DailyQuestion; scaffolded: boolean }
  | { kind: "error"; message: string }
  | { kind: "none" }
```

Each state maps to one tree item with a distinct icon:

- **loading** — `$(loading~spin)` "Loading daily challenge..."
- **loaded** — `$(target)` "Two Sum II" with description `"Medium · 42.1% AC"`; on click, calls `kestrelcp.openOrScaffoldDaily`. If `leetcode/<slug>/Solution.java` already exists, the icon switches to `$(file-code)` (signalling "you have this locally" — deliberately not `$(check)`, which would imply the problem is solved/passed) and the tooltip flips from "Scaffold ..." to "Open existing ...".
- **error** — `$(error)` with the error message; clicking calls `kestrelcp.refreshDaily`.
- **none** — `$(info)` "No daily challenge available" (rare edge case).

**Fetching.** `fetchDailyChallenge()` POSTs to `https://leetcode.com/graphql/` with the `questionOfToday` operation — the `activeDailyCodingChallengeQuestion` field is public (no auth needed). The fetch runs once on activation, again whenever the FileSystemWatcher fires (so the icon flips to scaffolded), and on demand via the 🔄 button. There's **no automatic refresh on date change** — if you leave VS Code open across midnight, hit 🔄 or reload the window.

**Why a TreeDataProvider for one item?** VS Code's sidebar contributions are either WebviewView (custom HTML) or TreeView (list of items). A TreeView is significantly less code than a WebviewView for this case, and the only thing a Webview would gain is richer styling — which would defeat the "tiny, native-feeling status panel" goal.

### runner.ts — terminal management

```typescript
let cachedTerminal: vscode.Terminal | undefined;
let cachedEnvKey: string | undefined;

export async function runInTerminal(
  cmd: string,
  env: Record<string, string> = {},
): Promise<void> { ... }
```

VS Code's Terminal API lets you create terminals and send text to them. The key constraint: **it's fire-and-forget**. You can send a command, but you cannot wait for it to finish, read its output, or get its exit code. This is why all the "heavy" logic (compilation, test comparison, scraping) lives in the Python scripts — they handle their own output and exit codes.

`runner.ts` is intentionally **dumb**: takes a command string and an env dict, that's it. It doesn't read settings or secrets. The caller (`extension.ts`) decides what env to pass — typically via the `fullEnv()` helper which pulls the Anthropic key from `SecretStorage` and merges in any extra env (like LeetCode cookies) provided by the command handler. Keeping this concern in `extension.ts` means `runner.ts` has zero coupling to specific secrets.

**Terminal caching.** Creating a terminal is expensive (spawns a shell process), so the extension reuses a single "KestrelCP" terminal. It creates a new one only when:

1. No terminal exists yet
2. The previous terminal was closed (`exitStatus !== undefined`)
3. **Any env value changed** — `env` is baked in at terminal creation time, so a stored-secret change (Anthropic key rotated, LeetCode cookies re-pasted) requires recreating the terminal. The cache key is `JSON.stringify(env)`.

**Environment variables.** `extension.ts` builds the env dict via `fullEnv()`:

```typescript
async function fullEnv(extra: Record<string, string> = {}): Promise<Record<string, string>> {
  const env: Record<string, string> = { ...extra };
  const apiKey = await extensionContext.secrets.get(ANTHROPIC_KEY);
  if (apiKey) env["ANTHROPIC_API_KEY"] = apiKey;
  return env;
}
```

For LeetCode commands, the caller also calls `leetcodeEnv()` (which adds `LEETCODE_SESSION` / `LEETCODE_CSRF` from SecretStorage) and passes the result as `extra`. The resulting dict goes to `runInTerminal`, which forwards it to `vscode.window.createTerminal({ env })`. That's how secrets get from VS Code's encrypted `SecretStorage` into the bundled Python scripts' process env — without ever being logged, echoed, or written to disk.

---

## 6. Python scripts — scripts/

### new.py — problem scaffolding & scraping

The largest script. Given `<platform> <url>`, it:

1. Creates the `<platform>/<problem>/` directory.
2. Writes `Solution.java` from a template (Kattis / Codeforces use a stdin BufferedReader template; LeetCode uses the editor's `codeSnippets` Java entry as-is, so the user starts with the exact method signature).
3. Writes `notes.md` with a link to the problem URL.
4. Fetches sample test cases and writes `1.in` / `1.out`, `2.in` / `2.out`, etc.

#### Platform-specific scrapers

- **Kattis** — HTML scraping. Samples are in `table.sample > pre` elements.
- **Codeforces** — HTML scraping. Samples are in `div.input pre` and `div.output pre`.
- **LeetCode** — GraphQL `question(titleSlug)` query returns `exampleTestcases`, `metaData` (param count + types), `content` (HTML statement), and `codeSnippets` (per-language starter code). No auth needed.

**Decision:** HTML scraping is inherently fragile — if the site changes its markup, the scraper breaks. This is why the canary CI test exists (see section 11). The scrapers use `requests` with browser-like headers to avoid being blocked. LeetCode's GraphQL is more stable than HTML but is still an unofficial API — the canary covers it too.

#### URL derivation

```python
def derive_problem_name(platform: str, url: str) -> str:
```

Extracts a folder-safe problem name:

- Kattis: `/problems/oddecho` → `oddecho`
- Codeforces: `/problemset/problem/645/A` → `645A`
- LeetCode: `/problems/two-sum/` → `two-sum`

#### Argument parsing

```bash
./new.py <platform> <url>
```

`platform` is one of `kattis` / `codeforces` / `leetcode`; `url` is the full problem URL. The `argcomplete` integration (optional) provides tab completion in shells that support it.

### test.py — test runner (Kattis / Codeforces)

A straightforward compile-and-compare script:

1. **Compile**: `javac -d <tmpdir> Solution.java` — compiles to a temp directory so `.class` files don't litter the problem folder.
2. **Run each test**: For every `*.in` file, runs `java -cp <tmpdir> Solution < N.in` and captures stdout.
3. **Compare**: If `N.out` exists and is non-empty, normalizes both (strip trailing whitespace, drop blank lines) and compares. Reports PASS / FAIL / TIMEOUT / RUNTIME ERROR.

**Decision:** Using `tempfile.TemporaryDirectory()` as a context manager ensures the compiled `.class` files are always cleaned up, even on errors. The 5-second timeout prevents infinite loops from hanging the test runner.

**Output normalization.**

```python
def normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
```

Competitive programming judges are lenient about trailing whitespace and blank lines — this normalizer matches that behavior.

### test_leetcode.py — LeetCode test runner

LeetCode problems take typed method arguments (`int[]`, `TreeNode`, …), not stdin lines. They can't be compiled and run locally the way Kattis / Codeforces problems work. Instead, `test_leetcode.py` POSTs the source to LeetCode's `interpret_solution` endpoint — the same one that powers the "Run Code" button in the web editor.

**Flow:**

1. Read every `<N>.in` file in the problem directory, concatenate them with newlines into a single `data_input`.
2. Look up the `questionId` via the GraphQL `question(titleSlug)` query (the run/submit endpoints want a numeric ID, not the slug).
3. POST to `https://leetcode.com/problems/<slug>/interpret_solution/` with `{ lang: "java", question_id, typed_code, data_input }`. Returns an `interpret_id`.
4. Poll `GET /submissions/detail/<interpret_id>/check/` every 500ms until `state == "SUCCESS"`. Response has `code_answer` (user output per case), `expected_code_answer` (judge's reference per case, empty for non-sample inputs), `compile_error`, `runtime_error`, `status_msg`, and `correct_answer` (the judge's overall verdict).
5. Render per-case PASS / FAIL.

**Honoring the judge's verdict (multi-valid answers).** Some problems accept multiple valid answers (two-sum's `[0,1]` vs `[1,0]`, "return any valid permutation", etc.). For sample cases the script trusts `correct_answer` / `status_msg == "Accepted"` over naive string equality:

```python
judge_accepted = bool(result.get("correct_answer")) or status_msg == "Accepted"
...
if judge_accepted:
    ok = True
    note = "" if y == e else "  (judge accepted equivalent answer)"
else:
    ok = y == e
```

Without this, every multi-valid problem would false-FAIL when your code returns a permutation different from LeetCode's canonical one. The `(judge accepted equivalent answer)` note keeps the difference visible.

**Custom inputs (no verdict).** You can drop a `<N>.in` for an input LeetCode hasn't seen — the judge still runs your code, but `expected_code_answer[i]` comes back empty. We print the input + your output without a verdict so you can eyeball it. Custom inputs are deliberately **not** pass/fail-able from a local `<N>.out` — LeetCode's web UI does the same thing (it doesn't compute references for arbitrary inputs).

**Why batch?** LeetCode rate-limits this endpoint hard — empirically ~1 request per few seconds. Sending one request per `<N>.in` triggers 429 on the second case. Batching all cases into one request stays under the limit and is also faster: the cost is dominated by judge container spin-up (~1s), so adding cases is nearly free.

**Auth.** Even though `interpret_solution` doesn't count as a submission, it requires `LEETCODE_SESSION` + `csrftoken` cookies because it spins up a sandboxed code execution container — that's expensive infrastructure LeetCode protects behind login. See `leetcode_auth.py`.

### submit_leetcode.py — LeetCode submission

A thinner sibling. POSTs to `https://leetcode.com/problems/<slug>/submit/` (real submission, shows up in history, affects acceptance rate) and polls `/submissions/detail/<submission_id>/check/`. The verdict response includes `status_msg` ("Accepted" / "Wrong Answer" / "Time Limit Exceeded" / "Compile Error" / "Runtime Error"); on success also `status_runtime`, `status_memory`, `runtime_percentile`, `memory_percentile`.

Asks for a confirmation prompt before submitting (submissions are not undoable). Skipped with `--yes`.

### leetcode_auth.py — shared LeetCode auth

Used by `test_leetcode.py` and `submit_leetcode.py`. Two responsibilities:

1. **`load_session_from_env()`** — reads `LEETCODE_SESSION` + `LEETCODE_CSRF` from env. Decodes the session JWT and checks the `exp` claim — if expired, fails fast with a precise message rather than making a doomed network call. JWT decode is base64 + JSON parsing; we deliberately don't validate the signature because LeetCode signs with its own key and we just need to know when it expires.

2. **`classify_response_error(status_code, body_text, retry_after)`** — turns an HTTP error into a typed `AuthError` with `.reason` set to `session` / `csrf` / `rate_limit` / `other`. Django's CSRF middleware runs before auth, so a `403` containing `"CSRF"` is unambiguously a CSRF problem. A `403` without it (or a `401`) means the session was rejected — typically server-side revocation (logout elsewhere, password change), since the JWT exp check ran clean before the call. A `429` is rate-limiting. This classification drives precise user-facing messages: *"LEETCODE_SESSION expired on YYYY-MM-DD"* vs *"LeetCode rejected the csrftoken"* vs *"LeetCode is rate-limiting"*.

**Why send both a cookie AND an `x-csrftoken` header?** LeetCode uses Django's standard CSRF defense. The cookie alone is forgeable by any malicious site (browsers auto-attach cookies based on destination, not origin). The header has to be set explicitly by JavaScript that ran on `leetcode.com` and could read the `csrftoken` cookie — same-origin policy prevents cross-domain JavaScript from doing that. The server checks both match. We replicate what LeetCode's own JS does.

### commit.py — AI commit messages

Uses the Anthropic Python SDK:

1. Reads `git diff --staged` and `git status --short`.
2. Sends to Claude with a system prompt enforcing Conventional Commits format with emoji prefixes.
3. Interactive confirmation: `y` (accept), `n` (abort), `e` (edit in-place).

**The spinner.** A threaded braille spinner runs while waiting for the API response. A `threading.Event` signals it to stop cleanly when the response arrives.

**In-place editing.** The `e` option uses `readline.set_startup_hook()` to pre-fill the input line with the generated message. Special handling for macOS's `libedit`, which uses different keybinding syntax than GNU readline.

**Diff truncation.** The diff is truncated to 8000 characters before sending. Prevents token-limit issues on large commits while keeping enough context for a meaningful message.

**Decision:** `claude-haiku-4-5` with `max_tokens=128` and prompt caching (`cache_control: ephemeral`) optimizes for speed and cost — commit messages are short and the system prompt is reused across calls in the same session. The model is configurable via the `kestrelcp.commitModel` setting.

---

## 7. Security decisions

### Shell injection prevention

Every user-controlled value that reaches the terminal goes through `shellQuote()`:

- Problem URLs from `showInputBox()`
- Platform names from `showQuickPick()` (technically safe since they come from a fixed list, but quoted anyway for defense in depth)
- File path segments from `path.relative()`
- Extension install path (could contain spaces)

### Secrets in SecretStorage, not settings

All sensitive credentials — the Anthropic API key and the LeetCode session cookies — live in VS Code's [`SecretStorage`](https://code.visualstudio.com/api/references/vscode-api#SecretStorage) API, never in `settings.json`. `SecretStorage` is backed by the OS keychain (macOS Keychain / Windows Credential Manager / Secret Service on Linux).

The rationale:

1. `settings.json` is plain text on disk.
2. Settings Sync would propagate secrets to other machines and to MS servers.
3. A secret in `settings.json` ends up in `git diff` if the user ever commits their settings.

Users manage secrets through `KestrelCP: Set ...` commands that call `showInputBox({ password: true })` and store the value via `context.secrets.store()`. **There is no separate Clear command** — submitting an empty value to the Set command deletes the secret. This pattern keeps the palette uncluttered while still giving full lifecycle control.

Secrets are pushed to the bundled Python scripts at terminal-creation time via the `env` option on `vscode.window.createTerminal`. They are never logged or echoed. The cached terminal in `runner.ts` is recreated whenever the env hash changes, so a freshly-set secret takes effect on the very next command.

### Anthropic key migration (one-time)

Earlier versions of KestrelCP stored the Anthropic key in the `kestrelcp.anthropicApiKey` setting. On activation, `migrateAnthropicKey()` checks for a legacy value, copies it into SecretStorage if present, and shows a one-time notification telling the user to delete the old line from `settings.json`. The setting itself is no longer declared in `contributes.configuration`, so VS Code will mark a lingering entry as "unknown setting" — the notification's "Open settings.json" button takes the user straight there.

### Python script safety

The Python scripts use `subprocess.run()` with **list arguments** (not shell strings):

```python
subprocess.run(["javac", "-d", out_dir, solution_java], ...)
```

This avoids shell injection entirely on the Python side — arguments go directly to the process without shell interpretation.

---

## 8. Design decisions & trade-offs

### Why Python scripts instead of pure TypeScript?

- `beautifulsoup4` is significantly more ergonomic than any Node HTML parser for scraping.
- The `anthropic` Python SDK handles auth, retries, and streaming out of the box.
- Python scripts can be tested and run independently of VS Code (e.g. the canary).
- The scripts are usable as standalone CLI tools outside the extension.

The downside: users need Python 3 + pip packages installed. The README documents this requirement.

### Why a terminal instead of Output Channel or Task?

VS Code offers several ways to run external commands:

- **Terminal** — full interactive shell, visible to the user.
- **Output Channel** — read-only log panel.
- **Task** — structured build/test execution with problem matchers.

KestrelCP uses a terminal because:

- `commit.py` requires **interactive input** (y/n/e prompt, message editing) — only terminals support this.
- Users want to **see** what's happening (compilation output, test results) in real time.
- A single reusable terminal keeps things tidy.

Trade-off: the terminal API is fire-and-forget with no programmatic access to command results.

### Why Java-only?

Deliberate scope constraint — the author uses Java for competitive programming. Supporting multiple languages would require language-specific compile/run commands, per-language templates, and more complex test runner logic.

### Why LeetCode uses a separate test runner

The stdin / stdout / `.in` / `.out` model that Kattis and Codeforces share fundamentally doesn't fit LeetCode. LeetCode problems take typed method arguments and return typed values; design problems (LRU Cache, Twitter) take a sequence of method calls. There's no general way to express them as "read stdin, print stdout."

An earlier KestrelCP design supported LeetCode by jamming each method parameter into a separate line of a `.in` file and parsing it manually inside `Solution.main`. It worked for ~50% of problems but forced per-problem parsing boilerplate and broke entirely on design / tree / linked-list problems.

The current design sidesteps this by **not running LeetCode code locally at all** — `test_leetcode.py` ships the user's source to LeetCode's own judge, which understands all problem types natively. This is *faster* than local execution (~1s vs ~1.5s for cold-JVM `javac` + `java`), eliminates ~500 lines of deserializer code, and works for 100% of public problems including design ones. Trade-off: working LeetCode session cookies + subject to LeetCode's rate limits.

### Why search uses REST, not GraphQL

LeetCode deprecated the `problemsetQuestionList` GraphQL field. Its V2 successor (`problemsetQuestionListV2`) walls the `searchKeyword` arg behind authentication. The REST `/api/problems/all/` endpoint still works anonymously and gives us the full catalog in one ~1 MB request — we cache it in memory and filter client-side rather than depend on a search field that requires login.

### Why `onStartupFinished` activation?

More targeted activation events (like `onView:kestrelcp.daily`) would delay loading until the sidebar is opened. But `onStartupFinished` was chosen because:

- The extension is lightweight (no heavy initialization).
- The sidebar content needs to be ready immediately.
- The file watcher and context-key updater need to be active from the start.

### Synchronous file system calls

The daily-challenge provider and several commands use synchronous `fs` calls (`existsSync`, `readdirSync`, `mkdirSync`). In a VS Code extension this is acceptable because:

- `getChildren()` is expected to return synchronously (or a `Thenable`, but sync is simpler).
- The operations are local filesystem reads on small directories.
- The Extension Host runs in a separate process from the UI, so it doesn't block the editor.

---

## 9. End-to-end flows

### User scaffolds a new problem

```
User: Cmd+Shift+P → "KestrelCP: New Problem"
     ↓
extension.ts: newProblem() → showQuickPick(platform) → showInputBox(url)
     ↓
shellQuote(platform) + shellQuote(url) → terminal command
     ↓
runner.ts: runInTerminal() → sends to KestrelCP terminal
     ↓
Terminal: python3 '/path/to/scripts/new.py' 'codeforces' 'https://...'
     ↓
new.py: derive_problem_name() → "645A"
     ↓
new.py: scaffold() → creates codeforces/645A/Solution.java, notes.md
     ↓
new.py: fetch_codeforces() → scrapes sample tests → writes 1.in, 1.out
     ↓
FileSystemWatcher detects Solution.java creation
     ↓
extension.ts: vscode.open → Solution.java opens in editor
     ↓
onDidChangeActiveTextEditor → updateActiveContext() sets kestrelcp.activeIsProblem
     ↓
editor/title menu shows ▶ Run Tests (and ☁️ Submit if leetcode/)
```

### User runs tests (Kattis / Codeforces)

```
User has Solution.java open → clicks ▶ in editor toolbar (or Cmd+Shift+P → Run Tests)
     ↓
extension.ts: runTestsForCurrent() → derive platform + problem from active editor's path
     ↓
terminal command: python3 '/path/to/scripts/test.py' 'codeforces' '645A'
     ↓
test.py: javac Solution.java → temp directory
     ↓
test.py: for each *.in file → java Solution < N.in → compare with N.out
     ↓
Terminal output: "Test 1: PASS", "Test 2: FAIL", etc.
```

### User runs tests (LeetCode)

```
User has leetcode/two-sum/Solution.java open → clicks ▶ in editor toolbar
     ↓
extension.ts: runTestsForCurrent() → platform="leetcode"
     ↓
Read LeetCode cookies from context.secrets (SecretStorage)
     ↓
terminal env: { LEETCODE_SESSION, LEETCODE_CSRF, ANTHROPIC_API_KEY? }
terminal command: python3 .../scripts/test_leetcode.py 'two-sum'
     ↓
test_leetcode.py: read 1.in, 2.in, 3.in → concatenate into data_input
     ↓
leetcode_auth.load_session_from_env() → decode JWT, check exp; fail fast if stale
     ↓
GraphQL questionId(slug) → "1"
     ↓
POST /problems/two-sum/interpret_solution/ → interpret_id
     ↓
Poll /submissions/detail/<id>/check/ every 500ms → state == "SUCCESS"
     ↓
Compare code_answer[i] vs expected_code_answer[i] for each case;
honor correct_answer / status_msg for multi-valid-answer problems
     ↓
Terminal output: per-case PASS/FAIL/(custom-no-verdict) + summary
```

### User submits to LeetCode

```
User has leetcode/two-sum/Solution.java open → clicks ☁️ in editor toolbar
     ↓
extension.ts: submitLeetcode() — checks cookies exist, else prompts to set them
     ↓
terminal command: python3 .../scripts/submit_leetcode.py 'two-sum'
     ↓
submit_leetcode.py: confirm prompt ("Submit? [y/N]")
     ↓
POST /problems/two-sum/submit/ → submission_id
     ↓
Poll /submissions/detail/<id>/check/ → verdict
     ↓
Terminal output:
  Verdict: Accepted  (2.3s)
  Submission: https://leetcode.com/submissions/detail/.../
    Runtime: 5 ms  (beats 87.4%)
    Memory:  41.2 MB  (beats 62.1%)
```

### User clicks today's daily challenge

```
On activation: extension.ts: loadDaily()
     ↓
POST https://leetcode.com/graphql/ (questionOfToday, anonymous)
     ↓
daily.ts: setState({ kind: "loaded", question, scaffolded: <check fs> })
     ↓
Sidebar shows: 🎯 Two Sum II   Medium · 42.1% AC
     ↓
User clicks the row
     ↓
extension.ts: openOrScaffoldDaily()
     ↓ (if leetcode/<slug>/Solution.java exists) → vscode.open → done
     ↓ (else)                                    → python3 new.py leetcode <url>
     ↓
new.py: scaffold(...) → leetcode/<slug>/Solution.java + samples
     ↓
FileSystemWatcher → opens Solution.java + re-runs loadDaily() → row icon flips to 📄
```

### User searches LeetCode

```
User: Cmd+Shift+P → "KestrelCP: Search LeetCode"
     ↓
extension.ts: searchLeetcode() → showInputBox("Search keyword")
     ↓
Node global fetch → GET https://leetcode.com/api/problems/all/ (no auth needed)
  ~1 MB JSON of ~4000 problems, cached in cachedAllProblems for the session
     ↓
extension.ts: client-side filter by case-insensitive title substring (limit 30)
     ↓
showQuickPick(results) with title, difficulty, ac-rate, 🔒 marker for premium
     ↓
User picks a problem → extension.ts dispatches to new.py with the URL
     ↓
new.py: fetch_leetcode(url) via GraphQL → scaffold
```

### User makes an AI commit

```
User stages files → Cmd+Shift+P → "KestrelCP: AI Commit"
     ↓
extension.ts: aiCommit() → terminal command: python3 '/path/to/scripts/commit.py'
     ↓
commit.py: git diff --staged → sends to Claude API
     ↓
Claude returns: "✨ feat(codeforces): solve 645A"
     ↓
Terminal: "Commit with this message? [Y/n/e]"
     ↓
User types 'y' → git commit -m "✨ feat(codeforces): solve 645A"
```

---

## 10. Manual test plan

Use this checklist after any code change to verify everything still works end-to-end.

1. **Launch the dev instance**
   - In the kestrelcp repo window, press **F5** (or **Run** → _Start Debugging_).
   - A new VS Code window titled **[Extension Development Host]** opens with the extension active.

2. **Open a test workspace**
   - **File → Open Folder…** → pick a fresh empty folder (e.g. `~/tmp/kestrelcp-test`). Don't reuse the kestrelcp repo itself — it'll get cluttered with `kattis/`, `codeforces/`, etc.

3. **Initialize and check the sidebar**
   - **Cmd+Shift+P** → **KestrelCP: Initialize Workspace**.
   - Click the cube icon in the activity bar. The **LeetCode Daily** sidebar should appear with one row showing today's LeetCode Daily Challenge (`🎯 <Title>   <Difficulty> · <AC>% AC`), or `Loading daily challenge...` then `🎯 ...` once the GraphQL fetch returns.
   - Try running **New Problem** _before_ Initialize Workspace (in a fresh folder) — should show an error: `KestrelCP: run "Initialize Workspace" first.`

4. **Test the playground**

   | Action                                                                        | Expected                                                                                                                         |
   | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
   | Cmd+P → open `Playground.java`                                                | The Playground template is visible. The editor toolbar (top-right) shows a ▶ button.                                             |
   | Click the ▶ button on the editor toolbar                                      | A `KestrelCP` terminal runs `( cd playground && javac *.java && java Playground )` and prints `Hello from KestrelCP playground.` |
   | Edit `Playground.java`, save, click ▶ again                                   | Recompiles and prints the new output                                                                                             |
   | Add a `playground/Helper.java` class, call it from `Playground.main`, click ▶ | Both compile; `java Playground` uses `Helper`                                                                                    |
   | Cmd+Shift+P → **KestrelCP: Run Playground**                                   | Same as the ▶ button                                                                                                             |
   | Open a non-Playground file (e.g. README.md)                                   | The ▶ Run Playground button disappears from the editor toolbar (no context key match)                                            |

5. **Test problem flows** (Kattis / Codeforces regression)
   - **KestrelCP: New Problem** → pick a platform, paste a URL → folder + sample tests scaffolded.
   - After scaffolding completes, `Solution.java` should auto-open in the editor (file-watcher path).
   - With `Solution.java` open, the editor toolbar shows a ▶ button (top-right). Click it → tests run.
   - **KestrelCP: Run Tests for Current Problem** in the command palette → same effect. The command should only appear in the palette when a `Solution.java` is active (gated by `kestrelcp.activeIsProblem`).
   - Switch from `Solution.java` to e.g. `notes.md` — the ▶ button on the editor toolbar disappears and **KestrelCP: Run Tests for Current Problem** disappears from the palette.
   - **Re-scaffold guard**: delete the problem's `Solution.java`, then try **New Problem** with the same URL — `new.py` exits with `Already exists: ...` because the directory is still there. To genuinely re-scaffold, delete the whole `<platform>/<problem>/` folder first.

6. **Test AI commit** (requires an Anthropic API key)
   - First time: Cmd+Shift+P → **KestrelCP: Set Anthropic API Key** → paste `sk-ant-…`. Notification: `Anthropic key stored securely.`
   - Stage some changes in Source Control.
   - **KestrelCP: AI Commit** → terminal proposes a Conventional Commit message; respond with `y` / `n` / `e`.
   - Clear via the same command + empty input → next AI Commit run falls back to the shell `ANTHROPIC_API_KEY` env var (set one if you want the fallback to work).
   - **Migration check** (only meaningful if you had `kestrelcp.anthropicApiKey` in settings.json before this upgrade): on first activation post-upgrade, a notification reads "KestrelCP moved your Anthropic API key from settings to encrypted SecretStorage. You can safely delete `kestrelcp.anthropicApiKey` from your settings.json." The "Open settings.json" button opens the file.

7. **Test LeetCode flows** (requires a LeetCode account)
   - **Search**: Cmd+Shift+P → **KestrelCP: Search LeetCode**. Type `two sum` → quick pick lists matches with difficulty + AC rate. Pick "Two Sum" → scaffolds `leetcode/two-sum/`. `Solution.java` should match LeetCode's editor stub (`class Solution { public int[] twoSum(int[] nums, int target) { ... } }`), not the BufferedReader template. `.in` files contain newline-separated params (e.g. `[2,7,11,15]\n9`).
   - **Premium gate**: search for a premium-only problem (🔒 marker) → picking it shows an error and does not scaffold.
   - **Daily Challenge**: in the **LeetCode Daily** sidebar, click today's challenge row. If you've not scaffolded it yet, it scaffolds and opens `Solution.java`. Click again → opens the existing file (the row's icon flips from 🎯 to 📄; tooltip changes from "Scaffold ..." to "Open existing ..."). Click the 🔄 button on the view title → re-fetches and resets the icon if needed.
   - **Cookie setup**: Cmd+Shift+P → **KestrelCP: Set LeetCode Cookies**. Paste a real `LEETCODE_SESSION` and `csrftoken` from your browser DevTools.
   - **Run tests (LeetCode)**: open `leetcode/two-sum/Solution.java`, implement `twoSum`, click the ▶ button on the editor toolbar. Terminal should show `Judge status: Accepted` and per-case PASS within ~1-2 seconds.
   - **Multi-valid answer**: write a correct two-sum that returns indices in the *other* order from LeetCode's canonical (e.g. iterate in reverse). Run tests — the per-case lines should still report PASS with `(judge accepted equivalent answer)` notes, not FAIL. Summary should be `3 passed, 0 failed`.
   - **Custom input (no verdict)**: add a `4.in` with a fresh input you made up, e.g. `[1,2,3,4]\n5`. Run tests — `Test 4` should print `(custom input — LeetCode has no reference; eyeball the output)` plus your code's output, and NOT be counted as failed.
   - **Submit**: click the ☁️ button on the editor toolbar (only visible for LeetCode `Solution.java` — switch to a Codeforces one and verify it's hidden). Confirm at the `[y/N]` prompt. Terminal should print the verdict + runtime / memory percentile + a link to the submission detail page.
   - **Auth failures** (precise error messages):
     - Run tests _without_ cookies set → terminal: `[auth] missing LeetCode cookies: LEETCODE_SESSION, LEETCODE_CSRF`.
     - Set the cookies to obvious garbage → run tests → should report `[auth] LeetCode rejected the LEETCODE_SESSION` _or_ `[auth] LeetCode rejected the csrftoken`.
     - Set a real `LEETCODE_SESSION` that has already expired (paste an old one) → terminal: `[auth] LEETCODE_SESSION expired on YYYY-MM-DD HH:MM` (caught locally without a network call).
   - **Clear cookies**: Cmd+Shift+P → **KestrelCP: Set LeetCode Cookies** → submit empty for both prompts. Notification should read `cleared LEETCODE_SESSION + csrftoken`. Subsequent runs should error with the "missing cookies" message again.
   - **Rate limit**: rapid-fire ▶ on a LeetCode problem (5+ times in a few seconds). After a few successful runs the terminal should print `[rate-limit] LeetCode is rate-limiting`. Wait 30s and try again — should succeed.

---

## 11. Scraper canary (CI)

The bundled scrapers (`new.py`) depend on Kattis / Codeforces HTML and LeetCode's GraphQL schema — these change without notice. The **Scraper Canary** workflow ([`.github/workflows/scraper-canary.yml`](.github/workflows/scraper-canary.yml)) runs weekly (Monday 06:00 UTC) and on-demand to catch breakage early.

It runs [`tests/canary.py`](tests/canary.py), which fetches one stable problem per platform and asserts:

- `1.in` exists and is non-empty. `1.out` may be empty for LeetCode (output scrape is best-effort and not load-bearing — the judge supplies expected outputs at test time).
- `1.in` has at least the expected number of non-empty lines (per-platform `min_input_lines` in the `CANARIES` list) — guards against silent collapse where multi-line input gets joined onto a single line (e.g. Codeforces `<br>` tags dropped by the parser).
- `Solution.java` exists and is non-empty (catches the case where LeetCode's `codeSnippets` field disappears from the GraphQL schema).

On failure, it opens or comments on a GitHub issue tagged `scraper-broken` with the failing platform and a link to the run logs. Three retries per platform absorb transient flakes.

The canary only exercises the **scrape** path — it does NOT test `test_leetcode.py` or `submit_leetcode.py` because those require working LeetCode session cookies that cannot live in CI. Those paths must be validated by the manual test plan above.

Run it locally before pushing scraper changes:

```bash
pip install requests beautifulsoup4
python3 tests/canary.py
```

---

## 12. Build, debug & package

### Compilation

```bash
npm install       # install TypeScript, VS Code type definitions
npm run compile   # tsc -p ./ → compiles src/*.ts → out/*.js
npm run watch     # tsc -w -p ./ → recompile on file changes
```

`tsconfig.json` configures:

- **`target: "ES2022"`** — modern JavaScript features (top-level await, etc.).
- **`module: "commonjs"`** — Node.js-style require/exports (VS Code extensions use CommonJS).
- **`strict: true`** — full TypeScript strictness.
- **`outDir: "out"`** — compiled JS goes to `out/`, keeping `src/` clean.
- **`sourceMap: true`** — enables stepping through TypeScript in the debugger.

### Debugging (F5)

Pressing F5 in the kestrelcp repo launches a new VS Code window (the "Extension Development Host") with the extension loaded from source. You can:

- Set breakpoints in TypeScript files.
- See `console.log()` output in the Debug Console.
- Hot-reload with **Cmd+R** in the dev window after recompiling.

### Packaging

```bash
npm run package   # vsce package → produces kestrelcp-X.Y.Z.vsix
```

`vsce` (Visual Studio Code Extension manager) bundles everything into a `.vsix` file — a ZIP archive containing `package.json`, `out/`, `scripts/`, `media/`, etc.

### What gets included in the .vsix

The `.vsix` includes everything in the repo except what's listed in `.vscodeignore` (if present) or `node_modules` by default. Notably:

- `out/` (compiled JS) — **included** (this is the extension code)
- `src/` (TypeScript source) — typically excluded (not needed at runtime)
- `scripts/` (Python) — **included** (needed at runtime)
- `media/` (icons) — **included**
- `node_modules/` — KestrelCP has zero runtime dependencies (only `devDependencies`), so nothing is bundled

---

## 13. Release process

Releases are driven by two chained workflows — no local tagging required.

1. Push your changes to `main`.
2. GitHub → **Actions** → **Bump version and tag** → **Run workflow**, branch `main`, pick `patch` / `minor` / `major`.
   - Bumps `version` in `package.json`, commits as `chore: release vX.Y.Z`, creates tag `vX.Y.Z`, pushes both.
3. The pushed tag triggers **Release VS Code Extension**, which builds `kestrelcp-X.Y.Z.vsix` and attaches it to a new GitHub release.

Pull `main` afterward to get the bump commit locally, then install the new build:

```bash
git pull --rebase --tags origin main
code --install-extension kestrelcp-X.Y.Z.vsix
```

### One-time PAT setup (required for chained triggering)

GitHub deliberately does **not** fire downstream workflows when an action uses the default `GITHUB_TOKEN` to push. Without a PAT, the bump workflow creates the tag but `release-extension.yml` never runs. Setup:

1. https://github.com/settings/personal-access-tokens → **Generate new token (fine-grained)**.
2. Set an expiration that fits your renewal cadence (e.g. 1 year).
3. **Repository access** → click **"Only select repositories"** → pick `DNT-Khoa/kestrelcp`.
   - ⚠️ **Don't pick "Public Repositories (read-only)"** — it hides the per-repo permission options entirely. The "Contents" setting in the next step only appears once a non-public-only scope is selected.
4. **Scroll past the "Account permissions" section** (Profile, SSH keys, etc.) to **"Repository permissions"** (which appears only after step 3).
5. Set **Contents** → **Read and write**. **Metadata** is auto-set to Read-only — leave it. Everything else: "No access".
6. **Generate token**, copy the `github_pat_…` value (shown once).
7. In the repo: **Settings → Secrets and variables → Actions → New repository secret** → name `RELEASE_PAT` → paste → save.

The bump workflow ([`.github/workflows/bump-version.yml`](.github/workflows/bump-version.yml)) checks out and pushes using `${{ secrets.RELEASE_PAT }}`, so the tag push counts as a "human" event and triggers the release workflow.

**Verifying it worked**: after a successful **Bump version and tag** run, the Actions tab should show **Release VS Code Extension** running automatically a few seconds after. If it doesn't, re-check the PAT — see Troubleshooting below.

### PAT troubleshooting

**`remote: Write access to repository not granted` (HTTP 403) during checkout** — the PAT is reaching the action but lacks write permission. Fix:

- Go back to https://github.com/settings/personal-access-tokens → click the token name.
- Confirm **Repository access** is "Only select repositories" (or "All repositories"), with `DNT-Khoa/kestrelcp` listed.
- Confirm **Repository permissions → Contents** is **Read and write** (not "Read-only", not "No access"). If you can't see a Contents option at all, your Repository access is still set to "Public Repositories (read-only)" — fix that first.
- Save. The token value stays the same, so the `RELEASE_PAT` secret doesn't need to be re-pasted.

**Bump succeeds but release workflow still doesn't fire** — verify the secret name is exactly `RELEASE_PAT` (case-sensitive) under Settings → Secrets and variables → Actions.

**Token expired** — the bump workflow will start failing checkout. Generate a new fine-grained PAT with the same scopes, paste into the existing `RELEASE_PAT` secret (overwrites the old value).

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

> **Distribution model**: KestrelCP is published to the [VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=khoa-doan.kestrelcp) and also ships `.vsix` builds on GitHub Releases. The release workflow handles both automatically — pushing a `vX.Y.Z` tag creates a GitHub Release and publishes to the Marketplace via the `VSCE_PAT` secret.
