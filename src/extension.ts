import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { ProblemsTreeProvider, Item } from './tree';
import { runInTerminal } from './runner';

let extensionRoot: string;

export function activate(context: vscode.ExtensionContext) {
  extensionRoot = context.extensionPath;

  const provider = new ProblemsTreeProvider();
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('sheikah.problems', provider),
    vscode.commands.registerCommand('sheikah.init',               () => initWorkspace(provider)),
    vscode.commands.registerCommand('sheikah.newProblem',         () => newProblem(provider)),
    vscode.commands.registerCommand('sheikah.runTests',           (item?: Item) => runTests(item)),
    vscode.commands.registerCommand('sheikah.runTestsForCurrent', () => runTestsForCurrent()),
    vscode.commands.registerCommand('sheikah.aiCommit',           () => aiCommit()),
    vscode.commands.registerCommand('sheikah.runPlayground',      () => runPlayground()),
    vscode.commands.registerCommand('sheikah.refetchAllTests',    () => refetchAllTests()),
    vscode.commands.registerCommand('sheikah.refreshProblems',    () => provider.refresh()),
  );

  if (vscode.workspace.workspaceFolders?.[0]) {
    const watcher = vscode.workspace.createFileSystemWatcher('**/{Solution,Playground}.java');
    watcher.onDidCreate(() => provider.refresh());
    watcher.onDidDelete(() => provider.refresh());
    context.subscriptions.push(watcher);
  }
}

export function deactivate() {}

function workspaceRoot(): string | undefined {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) {
    vscode.window.showErrorMessage('Sheikah: open a folder first.');
  }
  return root;
}

function platforms(): string[] {
  return vscode.workspace.getConfiguration('sheikah').get<string[]>('platforms')
    ?? ['kattis', 'codeforces', 'leetcode'];
}

function scriptsExist(root: string): boolean {
  return ['new.py', 'test.py', 'commit.py'].every(f => fs.existsSync(path.join(root, f)));
}

async function ensureInitialized(root: string): Promise<boolean> {
  if (scriptsExist(root)) return true;
  const choice = await vscode.window.showInformationMessage(
    'Sheikah scripts are not in this folder. Initialize now?',
    'Initialize', 'Cancel',
  );
  if (choice !== 'Initialize') return false;
  await copyScripts(root);
  return true;
}

async function copyScripts(root: string): Promise<number> {
  const scriptsDir = path.join(extensionRoot, 'scripts');
  const targets = ['new.py', 'test.py', 'commit.py'];
  let copied = 0;
  for (const f of targets) {
    const dst = path.join(root, f);
    if (fs.existsSync(dst)) continue;
    fs.copyFileSync(path.join(scriptsDir, f), dst);
    fs.chmodSync(dst, 0o755);
    copied++;
  }
  return copied;
}

async function initWorkspace(provider: ProblemsTreeProvider) {
  const root = workspaceRoot();
  if (!root) return;
  const copied = await copyScripts(root);
  for (const p of platforms()) {
    const dir = path.join(root, p);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  }
  ensurePlayground(root);
  vscode.window.showInformationMessage(
    copied > 0
      ? `Sheikah initialized (${copied} script(s) copied).`
      : 'Sheikah already initialized.',
  );
  provider.refresh();
}

const PLAYGROUND_TEMPLATE = `public class Playground {
    public static void main(String[] args) {
        System.out.println("Hello from Sheikah playground.");
    }
}
`;

function ensurePlayground(root: string) {
  const dir = path.join(root, 'playground');
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, 'Playground.java');
  if (!fs.existsSync(file)) fs.writeFileSync(file, PLAYGROUND_TEMPLATE);
}

async function runPlayground() {
  const root = workspaceRoot();
  if (!root) return;
  ensurePlayground(root);
  await runInTerminal('( cd playground && javac *.java && java Playground )');
}

async function newProblem(provider: ProblemsTreeProvider) {
  const root = workspaceRoot();
  if (!root) return;
  if (!(await ensureInitialized(root))) return;

  const platform = await vscode.window.showQuickPick(platforms(), { placeHolder: 'Platform' });
  if (!platform) return;

  const slugOrUrl = await vscode.window.showInputBox({
    prompt: 'Problem URL or slug',
    placeHolder: 'https://leetcode.com/problems/two-sum/   or   oddecho',
  });
  if (!slugOrUrl) return;

  await runInTerminal(`./new.py ${platform} "${slugOrUrl.replace(/"/g, '\\"')}"`);
  setTimeout(() => provider.refresh(), 1500);
}

async function runTests(item?: Item) {
  if (item?.contextValue !== 'problem') return;
  const root = workspaceRoot();
  if (!root) return;
  if (!(await ensureInitialized(root))) return;
  await runInTerminal(`./test.py ${item.platform} ${item.problem}`);
}

async function refetchAllTests() {
  const root = workspaceRoot();
  if (!root) return;
  if (!(await ensureInitialized(root))) return;

  const counts: Record<string, number> = {};
  let total = 0;
  for (const p of platforms()) {
    const dir = path.join(root, p);
    if (!fs.existsSync(dir)) continue;
    const probs = fs.readdirSync(dir)
      .filter(d => {
        try { return fs.statSync(path.join(dir, d)).isDirectory(); }
        catch { return false; }
      });
    if (probs.length > 0) {
      counts[p] = probs.length;
      total += probs.length;
    }
  }

  if (total === 0) {
    vscode.window.showInformationMessage('Sheikah: no problems to refetch.');
    return;
  }

  const summary = Object.entries(counts).map(([p, n]) => `${p}: ${n}`).join(', ');
  const choice = await vscode.window.showWarningMessage(
    `Re-fetch sample tests for ${total} problem(s) (${summary})? `
      + `This hits each platform once per problem and overwrites *.in / *.out files. `
      + `Solution.java and notes.md are preserved.`,
    { modal: true },
    'Refetch all',
  );
  if (choice !== 'Refetch all') return;

  const platformList = Object.keys(counts).map(p => `'${p}'`).join(' ');
  const cmd = [
    `for p in ${platformList}; do`,
    `for d in "$p"/*/; do`,
    `[ -d "$d" ] || continue;`,
    `./new.py --refetch "$p" "$(basename "$d")" || echo "  (failed: $p/$(basename "$d"))";`,
    `done; done; echo; echo "Sheikah: refetch complete."`,
  ].join(' ');

  await runInTerminal(cmd);
}

async function runTestsForCurrent() {
  const editor = vscode.window.activeTextEditor;
  const root = workspaceRoot();
  if (!root) return;
  if (!editor) {
    vscode.window.showErrorMessage('No active editor.');
    return;
  }
  const rel = path.relative(root, editor.document.uri.fsPath).split(path.sep);
  if (rel.length < 3 || !platforms().includes(rel[0])) {
    vscode.window.showErrorMessage('Active file is not inside <platform>/<problem>/.');
    return;
  }
  await runInTerminal(`./test.py ${rel[0]} ${rel[1]}`);
}

async function aiCommit() {
  const root = workspaceRoot();
  if (!root) return;
  if (!(await ensureInitialized(root))) return;
  await runInTerminal(`./commit.py`);
}
