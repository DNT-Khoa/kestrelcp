import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";

export class ProblemsTreeProvider implements vscode.TreeDataProvider<Item> {
  private _onDidChange = new vscode.EventEmitter<Item | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChange.event;
  private _getPlatforms: () => string[];

  constructor(getPlatforms: () => string[]) {
    this._getPlatforms = getPlatforms;
  }

  refresh(): void {
    this._onDidChange.fire();
  }

  getTreeItem(element: Item): vscode.TreeItem {
    return element;
  }

  getChildren(element?: Item): Item[] {
    const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!root) return [];

    const platforms = this._getPlatforms();

    if (!element) {
      const items: Item[] = [];

      const playgroundFile = path.join(root, "playground", "Playground.java");
      if (fs.existsSync(playgroundFile)) {
        const pg = new Item(
          "Playground",
          vscode.TreeItemCollapsibleState.None,
          "playground",
          "playground",
        );
        pg.command = {
          command: "vscode.open",
          title: "Open Playground",
          arguments: [vscode.Uri.file(playgroundFile)],
        };
        items.push(pg);
      }

      for (const p of platforms) {
        if (fs.existsSync(path.join(root, p))) {
          items.push(
            new Item(
              p,
              vscode.TreeItemCollapsibleState.Collapsed,
              "platform",
              p,
            ),
          );
        }
      }

      return items;
    }

    if (element.contextValue === "platform") {
      const dir = path.join(root, element.platform);
      if (!fs.existsSync(dir)) return [];
      return fs
        .readdirSync(dir)
        .filter((d) => {
          try {
            return fs.statSync(path.join(dir, d)).isDirectory();
          } catch {
            return false;
          }
        })
        .sort()
        .map((d) => {
          const item = new Item(
            d,
            vscode.TreeItemCollapsibleState.None,
            "problem",
            element.platform,
            d,
          );
          const sol = path.join(dir, d, "Solution.java");
          if (fs.existsSync(sol)) {
            item.command = {
              command: "vscode.open",
              title: "Open Solution",
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
    public override contextValue: "platform" | "problem" | "playground",
    public platform: string,
    public problem?: string,
  ) {
    super(label, state);
    this.iconPath =
      contextValue === "platform"
        ? new vscode.ThemeIcon("folder")
        : contextValue === "playground"
          ? new vscode.ThemeIcon("beaker")
          : new vscode.ThemeIcon("file-code");
  }
}
