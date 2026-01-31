const vscode = require('vscode');

function activate(context) {
    // 1. Registrace Task Provideru (pro Ctrl+Shift+B a seznam úkolů)
    context.subscriptions.push(
        vscode.tasks.registerTaskProvider('zap', {
            provideTasks: () => {
                const editor = vscode.window.activeTextEditor;
                if (!editor || editor.document.languageId !== 'zap') return [];

                const filePath = editor.document.uri.fsPath;
                const definition = { type: 'zap' };

                // Pole argumentů je nejbezpečnější pro Windows i Linux
                const execution = new vscode.ShellExecution('zapc', [filePath]);

                const task = new vscode.Task(
                    definition,
                    vscode.TaskScope.Workspace,
                    'Build ZAP project',
                    'zap',
                    execution,
                    '$zap-matcher'
                );

                task.group = vscode.TaskGroup.Build;
                return [task];
            },
            resolveTask: (task) => {
                // Tato část umožňuje VS Code znovu sestavit úkol, pokud je volán z tasks.json
                if (task.definition.type === 'zap') {
                    const definition = task.definition;
                    return new vscode.Task(
                        definition,
                        task.scope,
                        task.name,
                        task.source,
                        new vscode.ShellExecution('zapc', [vscode.window.activeTextEditor.document.uri.fsPath]),
                        '$zap-matcher'
                    );
                }
                return undefined;
            }
        })
    );

    // 2. Registrace příkazu pro vlastní klávesovou zkratku
    context.subscriptions.push(
        vscode.commands.registerCommand('zap.runBuild', async () => {
            const tasks = await vscode.tasks.fetchTasks({ type: 'zap' });
            if (tasks && tasks.length > 0) {
                // Spustíme první nalezený úkol typu zap
                vscode.tasks.executeTask(tasks[0]);
            } else {
                vscode.window.showWarningMessage('No ZAP build task found. Open a .zap file.');
            }
        })
    );
}

function deactivate() { }

module.exports = { activate, deactivate };
