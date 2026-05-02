import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export class ProblemsTreeProvider implements vscode.TreeDataProvider<Item> {
  private _onDidChange = new vscode.EventEmitter<Item | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChange.event;

  refresh(): void {
    this._onDidChange.fire();
  }

  getTreeItem(element: Item): vscode.TreeItem {
    return element;
  }

  getChildren(element?: Item): Item[] {
    const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!root) return [];

    const platforms = vscode.workspace.getConfiguration('sheikah').get<string[]>('platforms')
      ?? ['kattis', 'codeforces', 'leetcode'];

    if (!element) {
      return platforms
        .filter(p => fs.existsSync(path.join(root, p)))
        .map(p => new Item(p, vscode.TreeItemCollapsibleState.Collapsed, 'platform', p));
    }

    if (element.contextValue === 'platform') {
      const dir = path.join(root, element.platform);
      if (!fs.existsSync(dir)) return [];
      return fs.readdirSync(dir)
        .filter(d => {
          try {
            return fs.statSync(path.join(dir, d)).isDirectory();
          } catch {
            return false;
          }
        })
        .sort()
        .map(d => {
          const item = new Item(d, vscode.TreeItemCollapsibleState.None, 'problem', element.platform, d);
          const sol = path.join(dir, d, 'Solution.java');
          if (fs.existsSync(sol)) {
            item.command = {
              command: 'vscode.open',
              title: 'Open Solution',
              arguments: [vscode.Uri.file(sol)],
            };
          }
          return item;
        });
    }

    return [];
  }
}

export class Item extends vscode.TreeItem {
  constructor(
    label: string,
    state: vscode.TreeItemCollapsibleState,
    public override contextValue: 'platform' | 'problem',
    public platform: string,
    public problem?: string,
  ) {
    super(label, state);
    this.iconPath = contextValue === 'platform'
      ? new vscode.ThemeIcon('folder')
      : new vscode.ThemeIcon('file-code');
  }
}
