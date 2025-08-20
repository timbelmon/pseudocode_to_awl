const vscode = require('vscode');
const cp = require('child_process');
const path = require('path');

function activate(context) {
    const disposable = vscode.workspace.onDidChangeTextDocument(event => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || event.document !== editor.document) {
            return;
        }
        for (const change of event.contentChanges) {
            if (change.text === '\n') {
                const line = change.range.start.line;
                const lineText = event.document.lineAt(line).text.trim();
                if (!lineText) {
                    continue;
                }
                const script = path.join(context.extensionPath, '..', 'transpile.py');
                try {
                    const res = cp.spawnSync('python3', [script, lineText], { encoding: 'utf8' });
                    if (res.status === 0 && res.stdout) {
                        editor.edit(edit => {
                            const start = new vscode.Position(line, 0);
                            const end = new vscode.Position(line, event.document.lineAt(line).text.length);
                            edit.replace(new vscode.Range(start, end), res.stdout.trim());
                        });
                    }
                } catch (err) {
                    console.error(err);
                }
            }
        }
    });
    context.subscriptions.push(disposable);
}

function deactivate() {}

module.exports = {
    activate,
    deactivate
};
