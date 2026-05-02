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
    vscode.commands.registerCommand('sheikah.refreshProblems',    () => provider.refresh()),
  );

  if (vscode.workspace.workspaceFolders?.[0]) {
    const watcher = vscode.workspace.createFileSystemWatcher('**/Solution.java');
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
  vscode.window.showInformationMessage(
    copied > 0
      ? `Sheikah initialized (${copied} script(s) copied).`
      : 'Sheikah already initialized.',
  );
  provider.refresh();
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
  const root = workspaceRoot();
  if (!root) return;
  if (!(await ensureInitialized(root))) return;

  let platform: string | undefined;
  let problem: string | undefined;

  if (item?.contextValue === 'problem') {
    platform = item.platform;
    problem = item.problem;
  } else {
    platform = await vscode.window.showQuickPick(platforms(), { placeHolder: 'Platform' });
    if (!platform) return;
    const platformDir = path.join(root, platform);
    if (!fs.existsSync(platformDir)) {
      vscode.window.showErrorMessage(`No "${platform}" folder in workspace.`);
      return;
    }
    const choices = fs.readdirSync(platformDir)
      .filter(d => fs.statSync(path.join(platformDir, d)).isDirectory())
      .sort();
    problem = await vscode.window.showQuickPick(choices, { placeHolder: 'Problem' });
    if (!problem) return;
  }

  await runInTerminal(`./test.py ${platform} ${problem}`);
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
