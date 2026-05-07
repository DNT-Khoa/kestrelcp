# KestrelCP — Architecture & Design Guide

A comprehensive walkthrough of how this VS Code extension is built, aimed at someone who has never developed a VS Code extension before. Covers every file, every design decision, and how all the pieces connect.

---

## Table of Contents

1. [What Is a VS Code Extension?](#1-what-is-a-vs-code-extension)
2. [Project Structure](#2-project-structure)
3. [The Extension Manifest — package.json](#3-the-extension-manifest--packagejson)
4. [TypeScript Source — src/](#4-typescript-source--src)
   - [extension.ts — Entry Point & Commands](#extensionts--entry-point--commands)
   - [tree.ts — Sidebar Tree View](#treets--sidebar-tree-view)
   - [runner.ts — Terminal Management](#runnerts--terminal-management)
5. [Python Scripts — scripts/](#5-python-scripts--scripts)
   - [new.py — Problem Scaffolding & Scraping](#newpy--problem-scaffolding--scraping)
   - [test.py — Test Runner](#testpy--test-runner)
   - [commit.py — AI Commit Messages](#commitpy--ai-commit-messages)
6. [Testing — tests/](#6-testing--tests)
7. [Security Decisions](#7-security-decisions)
8. [Design Decisions & Trade-offs](#8-design-decisions--trade-offs)
9. [How It All Fits Together — End-to-End Flows](#9-how-it-all-fits-together--end-to-end-flows)
10. [Build, Debug, & Package](#10-build-debug--package)

---

## 1. What Is a VS Code Extension?

A VS Code extension is a Node.js package that VS Code loads into its process. At its core, you need:

- **`package.json`** — the _manifest_. Declares everything the extension contributes to VS Code: commands, views, settings, menus, activation triggers, and metadata. VS Code reads this file _before_ running any of your code to know what your extension provides.
- **An entry point** (typically `out/extension.js`) — a JavaScript/TypeScript module that exports an `activate()` function. VS Code calls this when your extension needs to start up.
- **`tsconfig.json`** — TypeScript configuration. Extensions are almost always written in TypeScript and compiled to JavaScript.

The extension runs in VS Code's **Extension Host** process — a separate Node.js process that VS Code manages. Your code has access to the full VS Code API (`vscode` module) but runs isolated from the editor's UI thread.

---

## 2. Project Structure

```
kestrelcp/
├── package.json          ← Extension manifest — THE most important file
├── tsconfig.json         ← TypeScript compiler config
├── src/
│   ├── extension.ts      ← Activation, command registration, orchestration
│   ├── tree.ts           ← Sidebar tree data provider
│   └── runner.ts         ← Shared terminal helper
├── scripts/
│   ├── new.py            ← Problem scaffolding + web scraping
│   ├── test.py           ← Compile & run Java solutions against test cases
│   └── commit.py         ← AI-generated git commit messages via Claude
├── tests/
│   └── canary.py         ← CI smoke test for scrapers
├── media/
│   ├── icon.svg          ← Source artwork (Rubik's cube)
│   ├── icon-sidebar.svg  ← Activity bar icon (24×24 monochrome)
│   └── icon.png          ← 256×256 marketplace icon
├── DEVELOPMENT.md        ← Internal dev docs
└── README.md             ← User-facing docs
```

**Why two languages?** The TypeScript code handles VS Code integration (commands, UI, settings). The Python scripts handle the heavy lifting (web scraping, process management, AI calls). This split exists because:

- Web scraping libraries (`requests`, `beautifulsoup4`) are mature and battle-tested in Python.
- The `anthropic` Python SDK is first-class.
- Competitive programmers commonly have Python installed already.

The scripts ship inside the `.vsix` package and run from the extension's install directory — they are never copied into user workspaces.

---

## 3. The Extension Manifest — package.json

This is the most important file in any VS Code extension. VS Code reads it to understand what the extension does _before_ executing any code.

### Metadata

```json
{
  "name": "kestrelcp",
  "displayName": "KestrelCP",
  "version": "0.5.0",
  "publisher": "khoa-doan",
  "main": "./out/extension.js",
  "engines": { "vscode": "^1.85.0" }
}
```

- **`name`** — The npm-style package name (lowercase, no spaces). Combined with `publisher` to form the extension ID: `khoa-doan.kestrelcp`.
- **`main`** — Points to the compiled JavaScript entry point. TypeScript compiles `src/extension.ts` → `out/extension.js`.
- **`engines.vscode`** — The minimum VS Code version required. `^1.85.0` means 1.85.0 or newer. This controls which VS Code APIs you can use.

### Activation Events

```json
"activationEvents": ["onStartupFinished"]
```

VS Code is lazy — it doesn't load your extension until it's needed. **Activation events** declare _when_ to load it. Options include:

- `onCommand:kestrelcp.init` — activate only when a specific command is invoked.
- `onView:kestrelcp.problems` — activate when the sidebar view becomes visible.
- `onStartupFinished` — activate after VS Code finishes starting up.

**Decision:** KestrelCP uses `onStartupFinished` because the sidebar tree view needs to be populated immediately — the user expects to see their problems listed as soon as they open VS Code. Using a more targeted event like `onView:` would also work, but `onStartupFinished` is simpler and the extension is lightweight enough that the startup cost is negligible.

### Commands

```json
"contributes": {
  "commands": [
    {
      "command": "kestrelcp.init",
      "title": "KestrelCP: Initialize Workspace"
    },
    {
      "command": "kestrelcp.newProblem",
      "title": "KestrelCP: New Problem",
      "icon": "$(add)"
    },
    ...
  ]
}
```

Each command has:

- **`command`** — a unique string ID. Convention: `extensionName.commandName`.
- **`title`** — what the user sees in the Command Palette (Cmd+Shift+P).
- **`icon`** — optional. Uses VS Code's built-in [Codicon](https://microsoft.github.io/vscode-codicons/) icon set via `$(iconName)` syntax.

Declaring a command here _only registers it in the UI_. The actual handler is registered in `extension.ts` using `vscode.commands.registerCommand()`.

### Views (Sidebar)

```json
"viewsContainers": {
  "activitybar": [{
    "id": "kestrelcp",
    "title": "KestrelCP",
    "icon": "media/icon-sidebar.svg"
  }]
},
"views": {
  "kestrelcp": [{
    "id": "kestrelcp.problems",
    "name": "Problems"
  }]
}
```

This creates:

1. A **view container** — the cube icon in the activity bar (the vertical icon strip on the far left/right of VS Code).
2. A **view** inside that container — the "Problems" panel. Its content is populated by a `TreeDataProvider` registered in code.

**Decision:** Using the activity bar (not the Explorer sidebar) gives KestrelCP its own dedicated space. Competitive programmers will have many problems listed; mixing them into the Explorer would be noisy.

### Menus

```json
"menus": {
  "commandPalette": [
    { "command": "kestrelcp.runTests", "when": "false" }
  ],
  "view/title": [
    { "command": "kestrelcp.newProblem", "when": "view == kestrelcp.problems", "group": "navigation@1" },
    { "command": "kestrelcp.refreshProblems", "when": "view == kestrelcp.problems", "group": "navigation@2" }
  ],
  "view/item/context": [
    { "command": "kestrelcp.runTests", "when": "view == kestrelcp.problems && viewItem == problem", "group": "inline" },
    { "command": "kestrelcp.runPlayground", "when": "view == kestrelcp.problems && viewItem == playground", "group": "inline" }
  ]
}
```

Menus control _where_ commands appear and _when_ they're visible:

- **`commandPalette`** — `"when": "false"` hides `kestrelcp.runTests` from the Command Palette entirely. It only makes sense as a contextual action on a specific problem in the tree, not as a global command.
- **`view/title`** — buttons in the header of the Problems view (the `+` and refresh icons).
- **`view/item/context`** with `"group": "inline"` — action buttons that appear inline when hovering a tree item. The `when` clause uses `viewItem` to match the tree item's `contextValue` (set in `tree.ts`), so the ▶ play button only appears on problems, and the playground play button only on the Playground item.
- **`@1`, `@2`** — ordering suffixes within a menu group.

### Configuration (Settings)

```json
"configuration": {
  "title": "KestrelCP",
  "properties": {
    "kestrelcp.pythonPath": {
      "type": "string",
      "default": "python3",
      "description": "Python 3 interpreter used to run new.py / test.py / commit.py."
    },
    "kestrelcp.anthropicApiKey": {
      "type": "string",
      "default": "",
      "description": "Anthropic API key for AI commit messages."
    }
  }
}
```

These appear in VS Code's Settings UI under "KestrelCP". Code reads them via `vscode.workspace.getConfiguration('kestrelcp').get<T>('key')`.

**Decision:** The `anthropicApiKey` setting has an empty default. When empty, the extension passes no extra env var, and `commit.py` falls back to reading `ANTHROPIC_API_KEY` from the user's shell environment. This gives two options: settings UI for convenience, or env var for security (settings are stored in plain-text JSON on disk).

---

## 4. TypeScript Source — src/

### extension.ts — Entry Point & Commands

This is the brain of the extension. It exports two functions that VS Code calls:

```typescript
export function activate(context: vscode.ExtensionContext) { ... }
export function deactivate() {}
```

**`activate()`** is called once when the extension starts. **`deactivate()`** is called when the extension is unloaded (VS Code closing, extension disabled) — KestrelCP has nothing to clean up, so it's empty.

#### The ExtensionContext

```typescript
extensionRoot = context.extensionPath;
```

`context.extensionPath` gives the absolute path to where the extension is installed on disk (e.g., `~/.vscode/extensions/khoa-doan.kestrelcp-0.5.0/`). This is how the extension locates the bundled Python scripts.

`context.subscriptions` is a disposal array — anything pushed into it gets automatically cleaned up when the extension deactivates. This prevents resource leaks.

#### Command Registration

```typescript
context.subscriptions.push(
  vscode.commands.registerCommand('kestrelcp.init', () => initWorkspace(provider)),
  vscode.commands.registerCommand('kestrelcp.runTests', (item?: Item) => runTests(item)),
  ...
);
```

Each `registerCommand` call connects a command ID (from `package.json`) to a TypeScript handler function. Note that `kestrelcp.runTests` receives an `item` parameter — when triggered from a tree view context menu, VS Code passes the clicked tree item as the first argument.

#### FileSystemWatcher

```typescript
const watcher = vscode.workspace.createFileSystemWatcher("**/*.{java,in,out}");
const dirWatcher = vscode.workspace.createFileSystemWatcher("**/*/");
```

Two watchers monitor the workspace:

- **File watcher** (`**/*.{java,in,out}`) — detects individual file creates/deletes (Solution.java, test files). On create, it calls `syncProblems()` to detect newly added problems and triggers auto-reveal + auto-open. On delete, it refreshes the tree.
- **Directory watcher** (`**/*/`) — detects folder creates/deletes (e.g. entire problem folder removed via Finder or `rm -rf`). This ensures the tree stays in sync even when directories are removed in bulk, since `createFileSystemWatcher` may not fire individual file events for bulk directory deletions.

**Decision:** Watching for file events is more reliable than using `setTimeout` to guess when the scaffolding script finishes. The terminal command runs asynchronously and there's no API to detect when it completes — the watcher reacts to the actual file creation event instead.

#### New-Problem Tracking & Auto-Reveal

Newly added problems are automatically focused in the tree and their `Solution.java` opened in the editor. The implementation uses `workspaceState` to track which problems have been seen before:

1. **`workspaceState` persistence** — a `knownProblems` set is stored in `context.workspaceState`. A `problemTrackingInit` flag ensures the first activation seeds all existing problems as "known" so they don't trigger auto-open. Only directories containing `Solution.java` are counted — this ensures that deleting and re-adding a problem correctly treats it as new.

2. **`syncProblems()`** — scans `<platform>/<problem>/` directories (requiring `Solution.java` to exist), compares against `knownProblems`, and returns newly added keys. Also cleans up deleted problems. Called on activation and on file watcher events.

3. **Auto-reveal + auto-open** — when the file watcher detects a newly created problem, the watcher callback constructs an `Item` and calls `treeView.reveal(item, { focus: true, select: true })` to expand the platform node and highlight the problem, then opens `Solution.java` in the editor. A short `setTimeout` lets the tree finish refreshing first.

This requires two things from `tree.ts`:

- **`getParent()`** — implemented on `ProblemsTreeProvider` so `reveal()` can walk up the tree hierarchy.
- **Stable `id`** — set on each `Item` (e.g. `"kattis/oddecho"`) so `reveal()` can match items across tree refreshes.

#### Active Editor Auto-Follow

The tree view automatically highlights the problem matching the current editor's file:

- **`onDidChangeVisibility`** — when the user clicks the KestrelCP activity bar icon (tree becomes visible), `revealActiveProblem()` checks the active editor's file path, determines its `<platform>/<problem>` from the relative path, and calls `treeView.reveal()` to scroll to and select that problem.
- **`onDidChangeActiveTextEditor`** — when the user switches editor tabs while the tree is already visible, the tree follows along and highlights the corresponding problem.

Both use `{ focus: false, select: true }` to highlight without stealing keyboard focus from the editor.

#### Shell Quoting (Security)

```typescript
function shellQuote(s: string): string {
  return "'" + s.replace(/'/g, "'\\''") + "'";
}
```

All values interpolated into terminal commands go through `shellQuote()`, which wraps the string in POSIX single quotes and escapes any embedded single quotes. This prevents shell injection — without it, a problem URL like `` `whoami` `` or `$(rm -rf .)` pasted into the input box would be executed as a shell command.

The quoting follows the standard POSIX technique: end the current single-quoted string (`'`), insert an escaped literal single quote (`\'`), then start a new single-quoted string (`'`). For example, `it's` becomes `'it'\''s'`.

```typescript
function bundledScript(name: string): string {
  const pythonPath =
    vscode.workspace.getConfiguration("kestrelcp").get<string>("pythonPath") ||
    "python3";
  return `${shellQuote(pythonPath)} ${shellQuote(path.join(extensionRoot, "scripts", name))}`;
}
```

Even the Python interpreter path and script path are quoted — the extension install path could contain spaces (e.g., `/Users/John Smith/.vscode/extensions/...`).

#### Key Command Implementations

**`initWorkspace`** — Creates platform directories and the playground scaffold. This is the only command (besides `refreshProblems`) that does not go through `requireInit()`, since it _is_ the initialization step. Uses synchronous `fs` calls (`mkdirSync`, `writeFileSync`) which is acceptable here because the operation is fast (creating a few empty directories) and runs in the Extension Host process, not the UI thread.

**`newProblem`** — First calls `requireInit()`, which checks that at least one platform directory exists (i.e. the workspace has been initialized). If not, shows an error message asking the user to run "Initialize Workspace" first. Then uses VS Code's built-in UI primitives:

- `showQuickPick()` — dropdown selection for platform
- `showInputBox()` — text input for URL (validated to require a full URL)

Then dispatches to the Python script via the terminal. The FileSystemWatcher handles the tree refresh.

**Note:** All commands except `initWorkspace` and `refreshProblems` use `requireInit()` to ensure the workspace is initialized before proceeding.

**`runTests`** — Receives a tree `Item` (the clicked problem), extracts `platform` and `problem` from it, and runs `test.py` in the terminal.

**`runTestsForCurrent`** — Determines the platform and problem from the _active editor's file path_ using `path.relative()`. If the file is at `<workspace>/codeforces/645A/Solution.java`, the relative path splits into `['codeforces', '645A', 'Solution.java']` — index 0 is the platform, index 1 is the problem.

**`refetchAllTests`** — The most complex command. It:

1. Scans the workspace to count problems per platform.
2. Shows a confirmation modal (`showWarningMessage` with `{ modal: true }`) listing counts.
3. Constructs a shell `for` loop that iterates over every platform and problem directory, calling `new.py --refetch` for each.

The loop is a single terminal command because the terminal API is fire-and-forget — there's no way to run commands sequentially or get exit codes back.

**`aiCommit`** — Simply dispatches `commit.py` to the terminal. The script itself handles all interaction (prompts, editing).

### tree.ts — Sidebar Tree View

Implements VS Code's `TreeDataProvider<Item>` interface, which requires two methods:

```typescript
getTreeItem(element: Item): vscode.TreeItem  // How to display an item
getChildren(element?: Item): Item[]          // What items exist (and their children)
```

#### How Tree Views Work

VS Code calls `getChildren(undefined)` to get root-level items. When the user expands a collapsible item, VS Code calls `getChildren(thatItem)` to get its children. This is lazy — children are only loaded when expanded.

#### The Tree Structure

```
Playground          ← contextValue: "playground", collapsible: None, icon: beaker
kattis              ← contextValue: "platform", collapsible: Collapsed, icon: folder
  oddecho           ← contextValue: "problem", collapsible: None, no icon
  helloworld        ← contextValue: "problem", collapsible: None, no icon
codeforces          ← contextValue: "platform", collapsible: Collapsed, icon: folder
  645A              ← contextValue: "problem", collapsible: None, no icon
leetcode            ← contextValue: "platform", collapsible: Collapsed, icon: folder
  two-sum           ← contextValue: "problem", collapsible: None, no icon
```

**Root level** (`element` is undefined):

- Checks if `playground/Playground.java` exists → adds a Playground item.
- Iterates over configured platforms → adds a folder item for each that exists on disk.

**Platform level** (`element.contextValue === 'platform'`):

- Reads the platform directory, filters for subdirectories, sorts them alphabetically.
- Each subdirectory becomes a problem item. If it contains `Solution.java`, clicking it opens that file.

#### The `contextValue` Property

```typescript
public override contextValue: 'platform' | 'problem' | 'playground'
```

This is the key that connects tree items to menu visibility. In `package.json`:

```json
"when": "viewItem == problem"
```

This `when` clause checks the clicked item's `contextValue`. That's how the ▶ button only appears on problems, not on platform folders.

#### Refresh Mechanism

```typescript
private _onDidChange = new vscode.EventEmitter<Item | undefined | void>();
readonly onDidChangeTreeData = this._onDidChange.event;

refresh(): void {
  this._onDidChange.fire();
}
```

VS Code's tree view listens to the `onDidChangeTreeData` event. When `refresh()` fires it (with no argument = refresh everything), VS Code re-calls `getChildren()` from the root. This is the standard pattern for refreshable tree views.

**Note:** The tree is registered using `vscode.window.createTreeView()` (not `registerTreeDataProvider`) because the returned `TreeView` object exposes `reveal()`, which is needed for auto-scrolling to newly added problems.

#### Dependency Injection

```typescript
constructor(getPlatforms: () => string[]) {
  this._getPlatforms = getPlatforms;
}
```

The tree provider receives a `getPlatforms` callback instead of owning the platform list directly. This keeps `tree.ts` decoupled from the source of the list — if the list ever becomes configurable again, only `extension.ts` needs to change.

### runner.ts — Terminal Management

```typescript
let cachedTerminal: vscode.Terminal | undefined;
let cachedApiKey: string | undefined;

export async function runInTerminal(cmd: string): Promise<void> { ... }
```

VS Code's Terminal API lets you create terminals and send text to them. The key constraint: **it's fire-and-forget**. You can send a command, but you cannot:

- Wait for it to finish
- Read its output
- Get its exit code

This is why all the "heavy" logic (compilation, test comparison, scraping) lives in the Python scripts — they handle their own output and exit codes.

#### Terminal Caching

```typescript
if (!cachedTerminal || cachedTerminal.exitStatus !== undefined || apiKey !== cachedApiKey) {
  cachedTerminal?.dispose();
  ...
  cachedTerminal = vscode.window.createTerminal({ name: "KestrelCP", cwd: root, env });
}
```

Creating a terminal is expensive (spawns a shell process), so the extension reuses a single "KestrelCP" terminal. It creates a new one only when:

1. No terminal exists yet
2. The previous terminal was closed (`exitStatus !== undefined`)
3. The Anthropic API key setting changed — because `env` is baked in at terminal creation time, a setting change requires recreating the terminal

#### Environment Variables

```typescript
const env: Record<string, string> = {};
if (apiKey) env["ANTHROPIC_API_KEY"] = apiKey;
```

The `env` option in `createTerminal` adds environment variables to the terminal's shell process. This is how the API key gets from VS Code settings to the Python script.

---

## 5. Python Scripts — scripts/

### new.py — Problem Scaffolding & Scraping

The largest script (~390 lines). Handles two main flows:

**Scaffolding** (`scaffold()`):

1. Creates `<platform>/<problem>/` directory
2. Writes `Solution.java` from a template
3. Writes `notes.md` with a link to the problem URL
4. If a URL is provided, fetches sample test cases and writes `1.in`/`1.out`, `2.in`/`2.out`, etc.

**Refetching** (`refetch_samples()`):

1. Reads the problem URL from `notes.md` (regex: `[Problem](https://...)`)
2. Re-scrapes sample tests from the URL
3. Deletes all existing `*.in`/`*.out` files
4. Writes fresh ones

#### Platform-Specific Scrapers

Each platform has a different HTML/API structure:

- **Kattis** — standard HTML scraping. Samples are in `table.sample > pre` elements.
- **Codeforces** — HTML scraping. Samples are in `div.input pre` and `div.output pre`.
- **LeetCode** — uses LeetCode's GraphQL API (not HTML scraping). The `exampleTestcases` field provides inputs; outputs are parsed from `<pre>` blocks in the rendered `content` HTML. The script also reads `metaData` to know how many parameters per test case (needed to group multi-line inputs correctly).

**Decision:** HTML scraping is inherently fragile — if the site changes its markup, the scraper breaks. This is why the canary CI test exists (see section 6). The scrapers use `requests` with browser-like headers to avoid being blocked.

#### URL Derivation

```python
def derive_problem_name(platform: str, url: str) -> str:
```

The script extracts a folder-safe problem name from the URL:

- Kattis/LeetCode: `/problems/oddecho` → `oddecho`
- Codeforces: `/problemset/problem/645/A` → `645A`

#### Argument Parsing

The script supports two modes via `argparse`:

- `./new.py <platform> <url>` — scaffold mode (default)
- `./new.py --refetch <platform> <problem>` — refetch mode

The `--refetch` flag switches the behavior entirely: instead of creating new directories, it re-scrapes an existing problem. The `argcomplete` integration (optional) provides tab completion in shells that support it.

### test.py — Test Runner

A straightforward compile-and-compare script:

1. **Compile**: `javac -d <tmpdir> Solution.java` — compiles to a temp directory so `.class` files don't litter the problem folder.
2. **Run each test**: For every `*.in` file, runs `java -cp <tmpdir> Solution < N.in` and captures stdout.
3. **Compare**: If `N.out` exists and is non-empty, normalizes both (strip trailing whitespace, remove blank lines) and compares. Reports PASS/FAIL/TIMEOUT/RUNTIME ERROR.

**Decision:** Using `tempfile.TemporaryDirectory()` as a context manager ensures the compiled `.class` files are always cleaned up, even on errors. The 5-second timeout prevents infinite loops from hanging the test runner.

#### Output Normalization

```python
def normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
```

Competitive programming judges are lenient about trailing whitespace and blank lines. This normalizer matches that behavior — your solution won't fail just because it prints an extra newline.

### commit.py — AI Commit Messages

Uses the Anthropic Python SDK to generate git commit messages:

1. **Reads staged diff**: `git diff --staged` and `git status --short`
2. **Sends to Claude**: With a system prompt enforcing Conventional Commits format with emoji prefixes
3. **Interactive confirmation**: User types `y` (accept), `n` (abort), or `e` (edit in-place)

#### The Spinner

```python
def _spin(stop: threading.Event) -> None:
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    ...
```

A threaded braille spinner runs while waiting for the Claude API response. The `stop` event signals it to terminate cleanly.

#### In-Place Editing

The `e` option uses `readline.set_startup_hook()` to pre-fill the input line with the generated message, so the user can edit it rather than retyping from scratch. There's special handling for macOS's `libedit` (which uses different keybinding syntax than GNU readline).

#### Diff Truncation

```python
f"Diff:\n{diff[:8000]}"
```

The diff is truncated to 8000 characters before sending to the API. This prevents token limit issues on large commits while keeping enough context for a meaningful message.

**Decision:** Using `claude-opus-4-7` with `max_tokens=128` and prompt caching (`cache_control: ephemeral`) optimizes for speed and cost — commit messages are short, and the system prompt is reused across calls within the same session.

---

## 6. Testing — tests/

### canary.py — Scraper Smoke Tests

The canary is not a unit test — it's an **integration test that hits live websites**. It exists because the scrapers depend on external HTML/API structures that change without notice.

For each platform, it:

1. Scaffolds a known-stable problem in a temp directory
2. Verifies `1.in` and `1.out` exist and are non-empty
3. Checks that `1.in` has at least N non-empty lines (catches the "silent collapse" failure mode where multi-line input gets joined onto one line)

Features:

- **3 retries per platform** with 10s sleep — absorbs transient network flakes
- **Temp directory cleanup** via `try/finally` with `shutil.rmtree()`
- **GitHub Actions integration** — on failure, writes structured output to `$GITHUB_OUTPUT` for downstream workflow steps (opening/commenting on issues)

---

## 7. Security Decisions

### Shell Injection Prevention

Every user-controlled value that reaches the terminal goes through `shellQuote()`:

- Problem URLs from `showInputBox()`
- Platform names from `showQuickPick()` (technically safe since these come from a fixed list, but quoted anyway for defense in depth)
- File path segments from `path.relative()`
- Python interpreter path from settings
- Extension install path (could contain spaces)

### API Key Handling

The `anthropicApiKey` setting is stored in VS Code's settings (plain-text JSON). The README recommends using the shell environment variable as an alternative for users who prefer not to store secrets in settings. The key is passed to the terminal via the `env` option on terminal creation — it's never logged or echoed.

### Python Script Safety

The Python scripts use `subprocess.run()` with **list arguments** (not shell strings):

```python
subprocess.run(["javac", "-d", out_dir, solution_java], ...)
```

This avoids shell injection entirely on the Python side — arguments are passed directly to the process without shell interpretation.

---

## 8. Design Decisions & Trade-offs

### Why Python Scripts Instead of Pure TypeScript?

The extension could theoretically do everything in TypeScript using Node.js HTTP libraries and child processes. But:

- `beautifulsoup4` is significantly more ergonomic than any Node HTML parser for scraping
- The `anthropic` Python SDK handles auth, retries, and streaming out of the box
- Python scripts can be tested and run independently of VS Code (e.g., the canary)
- The scripts are also usable as standalone CLI tools outside the extension

The downside: users need Python 3 + pip packages installed. The README documents this requirement.

### Why a Terminal Instead of Output Channel or Task?

VS Code offers several ways to run external commands:

- **Terminal** — full interactive shell, visible to the user
- **Output Channel** — read-only log panel
- **Task** — structured build/test execution with problem matchers

KestrelCP uses a terminal because:

- `commit.py` requires **interactive input** (y/n/e prompt, message editing) — only terminals support this
- Users want to **see** what's happening (compilation output, test results) in real time
- A single reusable terminal keeps things tidy

The trade-off: the terminal API is fire-and-forget with no programmatic access to command results.

### Why Java-Only?

The extension currently only supports Java solutions (`Solution.java`). This is a deliberate scope constraint — the author uses Java for competitive programming. Supporting multiple languages would require:

- Language-specific compilation commands
- Language-specific run commands
- Template files per language
- More complex test runner logic

### Why `onStartupFinished` Activation?

More targeted activation events (like `onView:kestrelcp.problems`) would delay loading until the sidebar is opened. But `onStartupFinished` was chosen because:

- The extension is lightweight (no heavy initialization)
- The sidebar content needs to be ready immediately
- The file watcher needs to be active from the start

### Synchronous File System Calls

The tree provider and several commands use synchronous `fs` calls (`existsSync`, `readdirSync`, `mkdirSync`). In a VS Code extension, this is acceptable because:

- `getChildren()` is expected to return synchronously (or a `Thenable`, but sync is simpler)
- The operations are local filesystem reads on small directories
- The Extension Host runs in a separate process from the UI, so it doesn't block the editor

---

## 9. How It All Fits Together — End-to-End Flows

### Flow: User Scaffolds a New Problem

```
User clicks + → showQuickPick("Platform") → showInputBox("URL")
     ↓
extension.ts: newProblem()
     ↓
shellQuote(platform) + shellQuote(url) → terminal command
     ↓
runner.ts: runInTerminal() → sends to KestrelCP terminal
     ↓
Terminal runs: python3 '/path/to/scripts/new.py' 'codeforces' 'https://...'
     ↓
new.py: derive_problem_name() → "645A"
     ↓
new.py: scaffold() → creates codeforces/645A/Solution.java, notes.md
     ↓
new.py: fetch_codeforces() → scrapes sample tests → writes 1.in, 1.out
     ↓
FileSystemWatcher detects Solution.java creation
     ↓
extension.ts: syncProblems() → detects new problem
     ↓
tree.ts: refresh() → getChildren() re-reads filesystem → sidebar updates
     ↓
treeView.reveal() → auto-expands platform node, focuses new problem
     ↓
vscode.open → Solution.java opens in editor
```

### Flow: User Runs Tests

```
User hovers problem → clicks ▶
     ↓
extension.ts: runTests(item) → item.platform="codeforces", item.problem="645A"
     ↓
terminal command: python3 '/path/to/scripts/test.py' 'codeforces' '645A'
     ↓
test.py: javac Solution.java → temp directory
     ↓
test.py: for each *.in file → java Solution < N.in → compare with N.out
     ↓
Terminal output: "Test 1: PASS", "Test 2: FAIL", etc.
```

### Flow: User Makes an AI Commit

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

## 10. Build, Debug, & Package

### Compilation

```bash
npm install       # Install TypeScript, VS Code type definitions
npm run compile   # tsc -p ./ → compiles src/*.ts → out/*.js
npm run watch     # tsc -w -p ./ → recompile on file changes
```

`tsconfig.json` configures:

- **`target: "ES2022"`** — modern JavaScript features (top-level await, etc.)
- **`module: "commonjs"`** — Node.js-style require/exports (VS Code extensions use CommonJS)
- **`strict: true`** — full TypeScript strictness (null checks, implicit any errors, etc.)
- **`outDir: "out"`** — compiled JS goes to `out/`, keeping `src/` clean
- **`sourceMap: true`** — enables stepping through TypeScript in the debugger

### Debugging (F5)

Pressing F5 in the kestrelcp repo launches a new VS Code window (the "Extension Development Host") with the extension loaded from source. You can:

- Set breakpoints in TypeScript files
- See `console.log()` output in the Debug Console
- Hot-reload with Cmd+R in the dev window after recompiling

### Packaging

```bash
npm run package   # vsce package → produces kestrelcp-X.Y.Z.vsix
```

`vsce` (Visual Studio Code Extension manager) bundles everything into a `.vsix` file — a ZIP archive containing `package.json`, `out/`, `scripts/`, `media/`, etc. This is what gets distributed.

### What Gets Included in the .vsix

The `.vsix` includes everything in the repo except what's listed in `.vscodeignore` (if present) or `node_modules` by default. Notably:

- `out/` (compiled JS) — **included** (this is the extension code)
- `src/` (TypeScript source) — typically excluded (not needed at runtime)
- `scripts/` (Python) — **included** (needed at runtime)
- `media/` (icons) — **included**
- `node_modules/` — KestrelCP has zero runtime dependencies (only `devDependencies`), so nothing is bundled
