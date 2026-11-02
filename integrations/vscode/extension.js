// @ts-check
// cufflink for VS Code: the selection, read aloud by cufflink.
//
// Everything audible happens in cufflink -- the pill, pause, stop, speed and
// voice all stay on its own keys. This only decides what text to hand over.

const vscode = require("vscode");
const ports = require("./ports");

const INSTALL = "https://cufflink.reddy.world/#install";

/** @param {vscode.ExtensionContext} context */
function activate(context) {
  context.subscriptions.push(vscode.commands.registerTextEditorCommand("cufflink.read", read));
}

/** @param {vscode.TextEditor} editor */
async function read(editor) {
  const text = selected(editor);
  if (!ports.spoken(text).trim()) {
    vscode.window.setStatusBarMessage("cufflink: nothing to read here", 3000);
    return;
  }
  try {
    await ports.say(text, { from: vscode.workspace.name });
  } catch (err) {
    if (err instanceof ports.NotRunning) {
      const choice = await vscode.window.showErrorMessage(
        "cufflink isn't running. Start it, then try again.", "How to install");
      if (choice) vscode.env.openExternal(vscode.Uri.parse(INSTALL));
    } else {
      vscode.window.showErrorMessage(`cufflink: ${err instanceof Error ? err.message : err}`);
    }
  }
}

/**
 * What was selected, top to bottom, or the line the cursor is on.
 *
 * Several cursors give several selections in the order they were made, which
 * is not the order they are read in.
 * @param {vscode.TextEditor} editor
 */
function selected(editor) {
  const parts = editor.selections
    .filter((s) => !s.isEmpty)
    .sort((a, b) => a.start.compareTo(b.start))
    .map((s) => editor.document.getText(s));
  if (parts.length) return parts.join("\n");
  return editor.document.lineAt(editor.selection.active.line).text;
}

function deactivate() {}

module.exports = { activate, deactivate };
