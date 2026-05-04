import * as vscode from "vscode";

let cachedTerminal: vscode.Terminal | undefined;
let cachedApiKey: string | undefined;

export async function runInTerminal(cmd: string): Promise<void> {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) return;

  const apiKey =
    vscode.workspace
      .getConfiguration("sheikah")
      .get<string>("anthropicApiKey") || "";

  if (
    !cachedTerminal ||
    cachedTerminal.exitStatus !== undefined ||
    apiKey !== cachedApiKey
  ) {
    cachedTerminal?.dispose();
    cachedApiKey = apiKey;
    const env: Record<string, string> = {};
    if (apiKey) env["ANTHROPIC_API_KEY"] = apiKey;

    cachedTerminal = vscode.window.createTerminal({
      name: "Sheikah",
      cwd: root,
      env,
    });
  }
  cachedTerminal.show();
  cachedTerminal.sendText(cmd);
}
