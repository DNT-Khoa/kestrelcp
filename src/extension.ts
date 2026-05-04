import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import { ProblemsTreeProvider, Item } from "./tree";
import { runInTerminal } from "./runner";

let extensionRoot: string;

export function activate(context: vscode.ExtensionContext) {
  extensionRoot = context.extensionPath;

  const provider = new ProblemsTreeProvider(platforms);
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider("sheikah.problems", provider),
    vscode.commands.registerCommand("sheikah.init", () =>
      initWorkspace(provider),
    ),
    vscode.commands.registerCommand("sheikah.newProblem", () =>
      newProblem(provider),
    ),
    vscode.commands.registerCommand("sheikah.runTests", (item?: Item) =>
      runTests(item),
    ),
    vscode.commands.registerCommand("sheikah.runTestsForCurrent", () =>
      runTestsForCurrent(),
    ),
    vscode.commands.registerCommand("sheikah.aiCommit", () => aiCommit()),
    vscode.commands.registerCommand("sheikah.runPlayground", () =>
      runPlayground(),
    ),
    vscode.commands.registerCommand("sheikah.refetchAllTests", () =>
      refetchAllTests(),
    ),
    vscode.commands.registerCommand("sheikah.refreshProblems", () =>
      provider.refresh(),
    ),
  );

  if (vscode.workspace.workspaceFolders?.[0]) {
    const watcher =
      vscode.workspace.createFileSystemWatcher("**/*.{java,in,out}");
    watcher.onDidCreate(() => provider.refresh());
    watcher.onDidDelete(() => provider.refresh());
    context.subscriptions.push(watcher);
  }
}

export function deactivate() {}

function workspaceRoot(): string | undefined {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) {
    vscode.window.showErrorMessage("Sheikah: open a folder first.");
  }
  return root;
}

function platforms(): string[] {
  return (
    vscode.workspace.getConfiguration("sheikah").get<string[]>("platforms") ?? [
      "kattis",
      "codeforces",
      "leetcode",
    ]
  );
}

function shellQuote(s: string): string {
  return "'" + s.replace(/'/g, "'\\''") + "'";
}

function bundledScript(name: string): string {
  const pythonPath =
    vscode.workspace.getConfiguration("sheikah").get<string>("pythonPath") ||
    "python3";
  return `${shellQuote(pythonPath)} ${shellQuote(path.join(extensionRoot, "scripts", name))}`;
}

const PLAYGROUND_TEMPLATE = `public class Playground {
    public static void main(String[] args) {
        System.out.println("Hello from Sheikah playground.");
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

  vscode.window.showInformationMessage("Sheikah workspace ready.");
  provider.refresh();
}

async function runPlayground() {
  const root = workspaceRoot();
  if (!root) return;
  ensurePlayground(root);
  await runInTerminal("( cd playground && javac *.java && java Playground )");
}

async function newProblem(provider: ProblemsTreeProvider) {
  const root = workspaceRoot();
  if (!root) return;

  const platform = await vscode.window.showQuickPick(platforms(), {
    placeHolder: "Platform",
  });
  if (!platform) return;

  const slugOrUrl = await vscode.window.showInputBox({
    prompt: "Problem URL or slug",
    placeHolder: "https://leetcode.com/problems/two-sum/   or   oddecho",
  });
  if (!slugOrUrl) return;

  await runInTerminal(
    `${bundledScript("new.py")} ${shellQuote(platform)} ${shellQuote(slugOrUrl)}`,
  );
}

async function runTests(item?: Item) {
  if (item?.contextValue !== "problem") return;
  const root = workspaceRoot();
  if (!root) return;
  await runInTerminal(
    `${bundledScript("test.py")} ${shellQuote(item.platform)} ${shellQuote(item.problem!)}`,
  );
}

async function refetchAllTests() {
  const root = workspaceRoot();
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
    vscode.window.showInformationMessage("Sheikah: no problems to refetch.");
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
    `done; done; echo; echo "Sheikah: refetch complete."`,
  ].join(" ");

  await runInTerminal(cmd);
}

async function runTestsForCurrent() {
  const editor = vscode.window.activeTextEditor;
  const root = workspaceRoot();
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
  const root = workspaceRoot();
  if (!root) return;
  await runInTerminal(bundledScript("commit.py"));
}
