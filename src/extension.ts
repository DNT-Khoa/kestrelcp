import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import { ProblemsTreeProvider, Item } from "./tree";
import { runInTerminal } from "./runner";

let extensionRoot: string;

export function activate(context: vscode.ExtensionContext) {
  extensionRoot = context.extensionPath;

  const provider = new ProblemsTreeProvider(platforms);
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

  // Track known problems to detect newly added ones
  const knownProblems = new Set<string>(
    context.workspaceState.get<string[]>("knownProblems", []),
  );
  let initialized = context.workspaceState.get<boolean>(
    "problemTrackingInit",
    false,
  );

  function scanProblems(): Set<string> {
    const result = new Set<string>();
    if (!root) return result;
    for (const p of platforms()) {
      const dir = path.join(root, p);
      if (!fs.existsSync(dir)) continue;
      try {
        for (const d of fs.readdirSync(dir)) {
          const problemDir = path.join(dir, d);
          if (
            fs.statSync(problemDir).isDirectory() &&
            fs.existsSync(path.join(problemDir, "Solution.java"))
          ) {
            result.add(`${p}/${d}`);
          }
        }
      } catch {}
    }
    return result;
  }

  function syncProblems(): string[] {
    const current = scanProblems();
    const justAdded: string[] = [];
    if (!initialized) {
      for (const p of current) knownProblems.add(p);
      initialized = true;
      context.workspaceState.update("problemTrackingInit", true);
    } else {
      for (const p of current) {
        if (!knownProblems.has(p)) {
          knownProblems.add(p);
          justAdded.push(p);
        }
      }
    }
    for (const p of [...knownProblems]) {
      if (!current.has(p)) {
        knownProblems.delete(p);
      }
    }
    context.workspaceState.update("knownProblems", [...knownProblems]);
    return justAdded;
  }

  syncProblems();

  context.subscriptions.push(
    vscode.commands.registerCommand("kestrelcp.init", () =>
      initWorkspace(provider),
    ),
    vscode.commands.registerCommand("kestrelcp.newProblem", () =>
      newProblem(provider),
    ),
    vscode.commands.registerCommand("kestrelcp.runTests", (item?: Item) =>
      runTests(item),
    ),
    vscode.commands.registerCommand("kestrelcp.runTestsForCurrent", () =>
      runTestsForCurrent(),
    ),
    vscode.commands.registerCommand("kestrelcp.aiCommit", () => aiCommit()),
    vscode.commands.registerCommand("kestrelcp.runPlayground", () =>
      runPlayground(),
    ),
    vscode.commands.registerCommand("kestrelcp.refetchAllTests", () =>
      refetchAllTests(),
    ),
    vscode.commands.registerCommand("kestrelcp.refreshProblems", () =>
      provider.refresh(),
    ),
  );

  const treeView = vscode.window.createTreeView("kestrelcp.problems", {
    treeDataProvider: provider,
  });
  context.subscriptions.push(treeView);

  function revealActiveProblem() {
    if (!root || !treeView.visible) return;
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    const rel = path.relative(root, editor.document.uri.fsPath).split(path.sep);
    if (rel.length < 3 || !platforms().includes(rel[0])) return;
    const [platform, problem] = rel;
    const item = new Item(
      problem,
      vscode.TreeItemCollapsibleState.None,
      "problem",
      platform,
      problem,
    );
    treeView.reveal(item, { focus: false, select: true });
  }

  treeView.onDidChangeVisibility((e) => {
    if (e.visible) revealActiveProblem();
  });
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(() => {
      if (treeView.visible) revealActiveProblem();
    }),
  );

  if (root) {
    const watcher =
      vscode.workspace.createFileSystemWatcher("**/*.{java,in,out}");
    const dirWatcher = vscode.workspace.createFileSystemWatcher("**/*/");

    let debounceTimer: ReturnType<typeof setTimeout> | undefined;
    const debouncedSync = () => {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        const added = syncProblems();
        provider.refresh();
        if (added.length > 0) {
          const key = added[added.length - 1];
          const [platform, problem] = key.split("/");
          const item = new Item(
            problem,
            vscode.TreeItemCollapsibleState.None,
            "problem",
            platform,
            problem,
          );
          const sol = path.join(root, platform, problem, "Solution.java");
          setTimeout(() => {
            if (treeView.visible) {
              treeView.reveal(item, { focus: false, select: true });
            }
            vscode.commands.executeCommand(
              "vscode.open",
              vscode.Uri.file(sol),
            );
          }, 200);
        }
      }, 500);
    };

    watcher.onDidCreate(debouncedSync);
    watcher.onDidDelete(debouncedSync);
    dirWatcher.onDidCreate(debouncedSync);
    dirWatcher.onDidDelete(debouncedSync);
    context.subscriptions.push(watcher, dirWatcher);
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
  return ["kattis", "codeforces", "leetcode"];
}

function shellQuote(s: string): string {
  return "'" + s.replace(/'/g, "'\\''") + "'";
}

function bundledScript(name: string): string {
  const pythonPath =
    vscode.workspace.getConfiguration("kestrelcp").get<string>("pythonPath") ||
    "python3";
  return `${shellQuote(pythonPath)} ${shellQuote(path.join(extensionRoot, "scripts", name))}`;
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

async function initWorkspace(provider: ProblemsTreeProvider) {
  const root = workspaceRoot();
  if (!root) return;

  for (const p of platforms()) {
    const dir = path.join(root, p);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  }
  ensurePlayground(root);

  vscode.window.showInformationMessage("KestrelCP workspace ready.");
  provider.refresh();
}

async function runPlayground() {
  const root = requireInit();
  if (!root) return;
  ensurePlayground(root);
  await runInTerminal("( cd playground && javac *.java && java Playground )");
}

async function newProblem(provider: ProblemsTreeProvider) {
  const root = requireInit();
  if (!root) return;

  const platform = await vscode.window.showQuickPick(platforms(), {
    placeHolder: "Platform",
  });
  if (!platform) return;

  const url = await vscode.window.showInputBox({
    prompt: "Problem URL",
    placeHolder: "https://leetcode.com/problems/two-sum/",
    validateInput: (v) =>
      v.startsWith("http://") || v.startsWith("https://")
        ? undefined
        : "Please enter a full URL",
  });
  if (!url) return;

  await runInTerminal(
    `${bundledScript("new.py")} ${shellQuote(platform)} ${shellQuote(url)}`,
  );
}

async function runTests(item?: Item) {
  if (item?.contextValue !== "problem") return;
  const root = requireInit();
  if (!root) return;
  await runInTerminal(
    `${bundledScript("test.py")} ${shellQuote(item.platform)} ${shellQuote(item.problem!)}`,
  );
}

async function refetchAllTests() {
  const root = requireInit();
  if (!root) return;

  const counts: Record<string, number> = {};
  let total = 0;
  for (const p of platforms()) {
    const dir = path.join(root, p);
    if (!fs.existsSync(dir)) continue;
    const probs = fs.readdirSync(dir).filter((d) => {
      try {
        return fs.statSync(path.join(dir, d)).isDirectory();
      } catch {
        return false;
      }
    });
    if (probs.length > 0) {
      counts[p] = probs.length;
      total += probs.length;
    }
  }

  if (total === 0) {
    vscode.window.showInformationMessage("KestrelCP: no problems to refetch.");
    return;
  }

  const summary = Object.entries(counts)
    .map(([p, n]) => `${p}: ${n}`)
    .join(", ");
  const choice = await vscode.window.showWarningMessage(
    `Re-fetch sample tests for ${total} problem(s) (${summary})? ` +
      `This hits each platform once per problem and overwrites *.in / *.out files. ` +
      `Solution.java and notes.md are preserved.`,
    { modal: true },
    "Refetch all",
  );
  if (choice !== "Refetch all") return;

  const platformList = Object.keys(counts)
    .map((p) => shellQuote(p))
    .join(" ");
  const newPyCmd = bundledScript("new.py");
  const cmd = [
    `for p in ${platformList}; do`,
    `for d in "$p"/*/; do`,
    `[ -d "$d" ] || continue;`,
    `${newPyCmd} --refetch "$p" "$(basename "$d")" || echo "  (failed: $p/$(basename "$d"))";`,
    `done; done; echo; echo "KestrelCP: refetch complete."`,
  ].join(" ");

  await runInTerminal(cmd);
}

async function runTestsForCurrent() {
  const editor = vscode.window.activeTextEditor;
  const root = requireInit();
  if (!root) return;
  if (!editor) {
    vscode.window.showErrorMessage("No active editor.");
    return;
  }
  const rel = path.relative(root, editor.document.uri.fsPath).split(path.sep);
  if (rel.length < 3 || !platforms().includes(rel[0])) {
    vscode.window.showErrorMessage(
      "Active file is not inside <platform>/<problem>/.",
    );
    return;
  }
  await runInTerminal(
    `${bundledScript("test.py")} ${shellQuote(rel[0])} ${shellQuote(rel[1])}`,
  );
}

async function aiCommit() {
  const root = requireInit();
  if (!root) return;
  await runInTerminal(bundledScript("commit.py"));
}
