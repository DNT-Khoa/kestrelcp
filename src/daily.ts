import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";

interface DailyQuestion {
  date: string;
  link: string;
  title: string;
  titleSlug: string;
  difficulty: string;
  acRate: number;
}

type State =
  | { kind: "loading" }
  | { kind: "loaded"; question: DailyQuestion; scaffolded: boolean }
  | { kind: "error"; message: string }
  | { kind: "none" };

export class DailyChallengeProvider
  implements vscode.TreeDataProvider<DailyItem>
{
  private _onDidChange = new vscode.EventEmitter<DailyItem | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChange.event;

  private state: State = { kind: "loading" };

  setState(state: State): void {
    this.state = state;
    this._onDidChange.fire();
  }

  getState(): State {
    return this.state;
  }

  getTreeItem(element: DailyItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: DailyItem): DailyItem[] {
    if (element) return [];

    switch (this.state.kind) {
      case "loading":
        return [
          new DailyItem(
            "Loading daily challenge...",
            new vscode.ThemeIcon("loading~spin"),
            "loading",
          ),
        ];
      case "error": {
        const item = new DailyItem(
          this.state.message,
          new vscode.ThemeIcon("error"),
          "error",
        );
        item.tooltip = "Click to retry";
        item.command = {
          command: "kestrelcp.refreshDaily",
          title: "Retry",
        };
        return [item];
      }
      case "none":
        return [
          new DailyItem(
            "No daily challenge available",
            new vscode.ThemeIcon("info"),
            "empty",
          ),
        ];
      case "loaded": {
        const { question, scaffolded } = this.state;
        const item = new DailyItem(
          question.title,
          new vscode.ThemeIcon(scaffolded ? "file-code" : "target"),
          "daily",
        );
        item.description = `${question.difficulty} · ${question.acRate.toFixed(1)}% AC`;
        item.tooltip = scaffolded
          ? `Open existing ${question.title}`
          : `Scaffold ${question.title}`;
        item.command = {
          command: "kestrelcp.openOrScaffoldDaily",
          title: scaffolded ? "Open" : "Scaffold",
        };
        return [item];
      }
    }
  }
}

class DailyItem extends vscode.TreeItem {
  constructor(
    label: string,
    icon: vscode.ThemeIcon,
    public override contextValue: string,
  ) {
    super(label, vscode.TreeItemCollapsibleState.None);
    this.iconPath = icon;
  }
}

export async function fetchDailyChallenge(): Promise<DailyQuestion | null> {
  const body = {
    operationName: "questionOfToday",
    variables: {},
    query: `query questionOfToday {
      activeDailyCodingChallengeQuestion {
        date
        link
        question {
          title
          titleSlug
          difficulty
          acRate
        }
      }
    }`,
  };
  const r = await fetch("https://leetcode.com/graphql/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    throw new Error(`HTTP ${r.status}`);
  }
  const j: any = await r.json();
  const node = j?.data?.activeDailyCodingChallengeQuestion;
  if (!node?.question) return null;
  return {
    date: node.date,
    link: node.link,
    title: node.question.title,
    titleSlug: node.question.titleSlug,
    difficulty: node.question.difficulty,
    acRate: node.question.acRate,
  };
}

export function isDailyScaffolded(
  workspaceRoot: string,
  slug: string,
): boolean {
  return fs.existsSync(
    path.join(workspaceRoot, "leetcode", slug, "Solution.java"),
  );
}
