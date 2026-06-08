import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import * as child_process from "child_process";
import {
  DailyChallengeProvider,
  fetchDailyChallenge,
  isDailyScaffolded,
} from "./daily";
import { runInTerminal } from "./runner";

let extensionRoot: string;
let extensionContext: vscode.ExtensionContext;

const LEETCODE_SESSION_KEY = "kestrelcp.leetcodeSession";
const LEETCODE_CSRF_KEY = "kestrelcp.leetcodeCsrf";
const ANTHROPIC_KEY = "kestrelcp.anthropicApiKey";

export function activate(context: vscode.ExtensionContext) {
  extensionRoot = context.extensionPath;
  extensionContext = context;

  const daily = new DailyChallengeProvider();
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

  context.subscriptions.push(
    vscode.commands.registerCommand("kestrelcp.init", () => initWorkspace()),
    vscode.commands.registerCommand("kestrelcp.newProblem", () => newProblem()),
    vscode.commands.registerCommand("kestrelcp.runTestsForCurrent", () =>
      runTestsForCurrent(),
    ),
    vscode.commands.registerCommand("kestrelcp.aiCommit", () => aiCommit()),
    vscode.commands.registerCommand("kestrelcp.runPlayground", () =>
      runPlayground(),
    ),
    vscode.commands.registerCommand("kestrelcp.searchLeetcode", () =>
      searchLeetcode(),
    ),
    vscode.commands.registerCommand("kestrelcp.submitLeetcode", () =>
      submitLeetcode(),
    ),
    vscode.commands.registerCommand("kestrelcp.setLeetcodeCookies", () =>
      setLeetcodeCookies(),
    ),
    vscode.commands.registerCommand("kestrelcp.setAnthropicKey", () =>
      setAnthropicKey(),
    ),
    vscode.commands.registerCommand("kestrelcp.refreshDaily", () =>
      loadDaily(daily),
    ),
    vscode.commands.registerCommand("kestrelcp.openOrScaffoldDaily", () =>
      openOrScaffoldDaily(daily),
    ),
  );

  const dailyView = vscode.window.createTreeView("kestrelcp.daily", {
    treeDataProvider: daily,
  });
  context.subscriptions.push(dailyView);

  checkPython3();
  migrateAnthropicKey();
  loadDaily(daily);

  updateActiveContext();
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(() => updateActiveContext()),
  );

  if (root) {
    const watcher = vscode.workspace.createFileSystemWatcher(
      "**/{kattis,codeforces,leetcode}/*/Solution.java",
    );

    let debounceTimer: ReturnType<typeof setTimeout> | undefined;
    const onCreate = (uri: vscode.Uri) => {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        vscode.commands.executeCommand("vscode.open", uri);
        if (daily.getState().kind === "loaded") {
          loadDaily(daily);
        }
      }, 300);
    };

    watcher.onDidCreate(onCreate);
    context.subscriptions.push(watcher);
  }
}

export function deactivate() {}

function workspaceRoot(): string | undefined {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) {
    vscode.window.showErrorMessage("KestrelCP: open a folder first.");
  }
  return root;
}

function requireInit(): string | undefined {
  const root = workspaceRoot();
  if (!root) return undefined;
  const initialized = platforms().some((p) =>
    fs.existsSync(path.join(root, p)),
  );
  if (!initialized) {
    vscode.window.showErrorMessage(
      'KestrelCP: run "Initialize Workspace" first.',
    );
    return undefined;
  }
  return root;
}

function platforms(): string[] {
  return ["codeforces", "kattis", "leetcode"];
}

function updateActiveContext() {
  const editor = vscode.window.activeTextEditor;
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  let isProblem = false;
  let isLeetcode = false;
  let isPlayground = false;
  if (editor && root) {
    const rel = path.relative(root, editor.document.uri.fsPath).split(path.sep);
    const filename = path.basename(editor.document.uri.fsPath);
    if (
      filename === "Solution.java" &&
      rel.length >= 3 &&
      platforms().includes(rel[0])
    ) {
      isProblem = true;
      if (rel[0] === "leetcode") isLeetcode = true;
    }
    if (filename === "Playground.java" && rel[0] === "playground") {
      isPlayground = true;
    }
  }
  vscode.commands.executeCommand(
    "setContext",
    "kestrelcp.activeIsProblem",
    isProblem,
  );
  vscode.commands.executeCommand(
    "setContext",
    "kestrelcp.activeIsLeetcode",
    isLeetcode,
  );
  vscode.commands.executeCommand(
    "setContext",
    "kestrelcp.activeIsPlayground",
    isPlayground,
  );
}

function shellQuote(s: string): string {
  return "'" + s.replace(/'/g, "'\\''") + "'";
}

function bundledScript(name: string): string {
  return `python3 ${shellQuote(path.join(extensionRoot, "scripts", name))}`;
}

function checkPython3(): void {
  const child = child_process.spawn("python3", ["--version"], {
    stdio: "ignore",
    shell: false,
  });
  child.on("error", () => warnNoPython());
  child.on("exit", (code) => {
    if (code !== 0) warnNoPython();
  });
}

function warnNoPython(): void {
  vscode.window.showErrorMessage(
    "KestrelCP: `python3` not found on PATH. Install Python 3.10+ and ensure `python3 --version` works from your shell, otherwise the bundled scripts (new.py / test.py / test_leetcode.py / submit_leetcode.py / commit.py) cannot run.",
  );
}

async function leetcodeEnv(): Promise<Record<string, string>> {
  const env: Record<string, string> = {};
  const session = await extensionContext.secrets.get(LEETCODE_SESSION_KEY);
  const csrf = await extensionContext.secrets.get(LEETCODE_CSRF_KEY);
  if (session) env["LEETCODE_SESSION"] = session;
  if (csrf) env["LEETCODE_CSRF"] = csrf;
  return env;
}

async function fullEnv(
  extra: Record<string, string> = {},
): Promise<Record<string, string>> {
  const env: Record<string, string> = { ...extra };
  const apiKey = await extensionContext.secrets.get(ANTHROPIC_KEY);
  if (apiKey) env["ANTHROPIC_API_KEY"] = apiKey;
  return env;
}

async function migrateAnthropicKey() {
  const existing = await extensionContext.secrets.get(ANTHROPIC_KEY);
  if (existing) return;
  const legacy = vscode.workspace
    .getConfiguration("kestrelcp")
    .get<string>("anthropicApiKey");
  if (!legacy || !legacy.trim()) return;
  await extensionContext.secrets.store(ANTHROPIC_KEY, legacy.trim());
  vscode.window
    .showInformationMessage(
      "KestrelCP moved your Anthropic API key from settings to encrypted SecretStorage. " +
        "You can safely delete `kestrelcp.anthropicApiKey` from your settings.json.",
      "Open settings.json",
    )
    .then((choice) => {
      if (choice === "Open settings.json") {
        vscode.commands.executeCommand("workbench.action.openSettingsJson");
      }
    });
}

const PLAYGROUND_TEMPLATE = `public class Playground {
    public static void main(String[] args) {
        System.out.println("Hello from KestrelCP playground.");
    }
}
`;

function ensurePlayground(root: string) {
  const dir = path.join(root, "playground");
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, "Playground.java");
  if (!fs.existsSync(file)) fs.writeFileSync(file, PLAYGROUND_TEMPLATE);
}

async function initWorkspace() {
  const root = workspaceRoot();
  if (!root) return;

  for (const p of platforms()) {
    const dir = path.join(root, p);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  }
  ensurePlayground(root);

  vscode.window.showInformationMessage("KestrelCP workspace ready.");
}

async function runPlayground() {
  const root = requireInit();
  if (!root) return;
  ensurePlayground(root);
  await runInTerminal(
    "( cd playground && javac *.java && java Playground )",
    await fullEnv(),
  );
}

async function newProblem() {
  const root = requireInit();
  if (!root) return;

  const platform = await vscode.window.showQuickPick(platforms(), {
    placeHolder: "Platform",
  });
  if (!platform) return;

  const url = await vscode.window.showInputBox({
    prompt: "Problem URL",
    placeHolder:
      platform === "leetcode"
        ? "https://leetcode.com/problems/two-sum/"
        : platform === "codeforces"
          ? "https://codeforces.com/problemset/problem/1/A"
          : "https://open.kattis.com/problems/oddecho",
    validateInput: (v) =>
      v.startsWith("http://") || v.startsWith("https://")
        ? undefined
        : "Please enter a full URL",
  });
  if (!url) return;

  await runInTerminal(
    `${bundledScript("new.py")} ${shellQuote(platform)} ${shellQuote(url)}`,
    await fullEnv(),
  );
}

function activeProblem(root: string): { platform: string; problem: string } | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return undefined;
  const rel = path.relative(root, editor.document.uri.fsPath).split(path.sep);
  if (rel.length < 3 || !platforms().includes(rel[0])) return undefined;
  if (path.basename(editor.document.uri.fsPath) !== "Solution.java") return undefined;
  return { platform: rel[0], problem: rel[1] };
}

async function runTestsForCurrent() {
  const root = requireInit();
  if (!root) return;
  const active = activeProblem(root);
  if (!active) {
    vscode.window.showErrorMessage(
      "KestrelCP: open a Solution.java inside <platform>/<problem>/ first.",
    );
    return;
  }
  if (active.platform === "leetcode") {
    await runInTerminal(
      `${bundledScript("test_leetcode.py")} ${shellQuote(active.problem)}`,
      await fullEnv(await leetcodeEnv()),
    );
  } else {
    await runInTerminal(
      `${bundledScript("test.py")} ${shellQuote(active.platform)} ${shellQuote(active.problem)}`,
      await fullEnv(),
    );
  }
}

async function aiCommit() {
  const root = requireInit();
  if (!root) return;
  const model =
    vscode.workspace
      .getConfiguration("kestrelcp")
      .get<string>("commitModel") || "claude-haiku-4-5";
  await runInTerminal(
    `${bundledScript("commit.py")} ${shellQuote(model)}`,
    await fullEnv(),
  );
}

async function submitLeetcode() {
  const root = requireInit();
  if (!root) return;
  const active = activeProblem(root);
  if (!active || active.platform !== "leetcode") {
    vscode.window.showErrorMessage(
      "KestrelCP: open a LeetCode Solution.java first.",
    );
    return;
  }

  const env = await leetcodeEnv();
  if (!env["LEETCODE_SESSION"] || !env["LEETCODE_CSRF"]) {
    const choice = await vscode.window.showWarningMessage(
      "LeetCode cookies not set. Run 'KestrelCP: Set LeetCode Cookies' first.",
      "Set cookies now",
    );
    if (choice === "Set cookies now") {
      await setLeetcodeCookies();
    }
    return;
  }

  await runInTerminal(
    `${bundledScript("submit_leetcode.py")} ${shellQuote(active.problem)}`,
    await fullEnv(env),
  );
}

async function setLeetcodeCookies() {
  const session = await vscode.window.showInputBox({
    prompt:
      "Paste LEETCODE_SESSION (DevTools > Application > Cookies > leetcode.com). Submit empty to clear.",
    password: true,
    ignoreFocusOut: true,
  });
  if (session === undefined) return;

  const csrf = await vscode.window.showInputBox({
    prompt: "Paste csrftoken (same DevTools panel). Submit empty to clear.",
    password: true,
    ignoreFocusOut: true,
  });
  if (csrf === undefined) return;

  const cleared: string[] = [];
  const stored: string[] = [];

  if (session.trim() === "") {
    await extensionContext.secrets.delete(LEETCODE_SESSION_KEY);
    cleared.push("LEETCODE_SESSION");
  } else {
    await extensionContext.secrets.store(LEETCODE_SESSION_KEY, session.trim());
    stored.push("LEETCODE_SESSION");
  }
  if (csrf.trim() === "") {
    await extensionContext.secrets.delete(LEETCODE_CSRF_KEY);
    cleared.push("csrftoken");
  } else {
    await extensionContext.secrets.store(LEETCODE_CSRF_KEY, csrf.trim());
    stored.push("csrftoken");
  }

  const parts: string[] = [];
  if (stored.length) parts.push(`stored ${stored.join(" + ")}`);
  if (cleared.length) parts.push(`cleared ${cleared.join(" + ")}`);
  vscode.window.showInformationMessage(`KestrelCP: ${parts.join("; ")}.`);
}

async function setAnthropicKey() {
  const key = await vscode.window.showInputBox({
    prompt: "Paste Anthropic API key (sk-ant-...). Submit empty to clear.",
    password: true,
    ignoreFocusOut: true,
  });
  if (key === undefined) return;

  if (key.trim() === "") {
    await extensionContext.secrets.delete(ANTHROPIC_KEY);
    vscode.window.showInformationMessage("KestrelCP: Anthropic key cleared.");
  } else {
    await extensionContext.secrets.store(ANTHROPIC_KEY, key.trim());
    vscode.window.showInformationMessage(
      "KestrelCP: Anthropic key stored securely.",
    );
  }
}

interface LeetcodeSearchResult {
  title: string;
  titleSlug: string;
  difficulty: string;
  acRate: number;
  paidOnly: boolean;
}

let cachedAllProblems: LeetcodeSearchResult[] | undefined;

async function fetchAllLeetcodeProblems(): Promise<LeetcodeSearchResult[]> {
  if (cachedAllProblems) return cachedAllProblems;
  // /api/problems/all/ is the REST catalog endpoint — works anonymously and
  // returns ~4000 problems in one ~1 MB JSON blob. The GraphQL
  // problemsetQuestionList field was deprecated; its V2 successor walls
  // searchKeyword behind auth, so client-side filter over this REST list
  // is the simplest no-auth path.
  const r = await fetch("https://leetcode.com/api/problems/all/", {
    headers: { "User-Agent": "kestrelcp/1.0" },
  });
  if (!r.ok) {
    throw new Error(`LeetCode catalog failed: HTTP ${r.status}`);
  }
  const j: any = await r.json();
  const levels = ["", "Easy", "Medium", "Hard"];
  cachedAllProblems = ((j?.stat_status_pairs as any[]) || []).map((entry) => {
    const stat = entry?.stat || {};
    const total = stat.total_submitted || 0;
    return {
      title: stat.question__title || "",
      titleSlug: stat.question__title_slug || "",
      difficulty: levels[entry?.difficulty?.level || 0] || "?",
      acRate: total > 0 ? (stat.total_acs / total) * 100 : 0,
      paidOnly: !!entry?.paid_only,
    };
  });
  return cachedAllProblems;
}

async function fetchLeetcodeQuestions(
  searchKeywords: string,
): Promise<LeetcodeSearchResult[]> {
  const all = await fetchAllLeetcodeProblems();
  const needle = searchKeywords.toLowerCase().trim();
  if (!needle) return all.slice(0, 30);
  return all
    .filter((q) => q.title.toLowerCase().includes(needle))
    .slice(0, 30);
}

async function searchLeetcode() {
  const root = requireInit();
  if (!root) return;

  const query = await vscode.window.showInputBox({
    prompt: "Search LeetCode problems by title or keyword",
    placeHolder: "two sum",
  });
  if (!query) return;

  const questions = await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Searching LeetCode...",
    },
    async () => {
      try {
        return await fetchLeetcodeQuestions(query);
      } catch (e: any) {
        vscode.window.showErrorMessage(`KestrelCP: ${e.message}`);
        return [];
      }
    },
  );

  if (questions.length === 0) {
    vscode.window.showInformationMessage(
      "KestrelCP: no LeetCode problems match that query.",
    );
    return;
  }

  const picks = questions.map((q) => ({
    label: `${q.title}${q.paidOnly ? " 🔒" : ""}`,
    description: `${q.difficulty} · ${q.acRate.toFixed(1)}% AC`,
    detail: `https://leetcode.com/problems/${q.titleSlug}/`,
    question: q,
  }));

  const picked = await vscode.window.showQuickPick(picks, {
    placeHolder: "Pick a problem to scaffold",
    matchOnDescription: true,
    matchOnDetail: true,
  });
  if (!picked) return;

  if (picked.question.paidOnly) {
    vscode.window.showErrorMessage(
      "KestrelCP: this is a premium-only LeetCode problem and cannot be scaffolded without a paid subscription.",
    );
    return;
  }

  await runInTerminal(
    `${bundledScript("new.py")} leetcode ${shellQuote(picked.detail)}`,
    await fullEnv(),
  );
}

async function loadDaily(provider: DailyChallengeProvider) {
  provider.setState({ kind: "loading" });
  try {
    const question = await fetchDailyChallenge();
    if (!question) {
      provider.setState({ kind: "none" });
      return;
    }
    const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    const scaffolded = root
      ? isDailyScaffolded(root, question.titleSlug)
      : false;
    provider.setState({ kind: "loaded", question, scaffolded });
  } catch (e: any) {
    provider.setState({
      kind: "error",
      message: `Could not load daily challenge: ${e.message || e}`,
    });
  }
}

async function openOrScaffoldDaily(provider: DailyChallengeProvider) {
  const state = provider.getState();
  if (state.kind !== "loaded") return;
  const root = requireInit();
  if (!root) return;
  const { question } = state;
  const solutionPath = path.join(
    root,
    "leetcode",
    question.titleSlug,
    "Solution.java",
  );
  if (fs.existsSync(solutionPath)) {
    await vscode.commands.executeCommand(
      "vscode.open",
      vscode.Uri.file(solutionPath),
    );
    return;
  }
  const url = `https://leetcode.com${question.link}`;
  await runInTerminal(
    `${bundledScript("new.py")} leetcode ${shellQuote(url)}`,
    await fullEnv(),
  );
}
