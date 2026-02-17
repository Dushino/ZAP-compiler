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

                const compiler = process.platform === 'win32' ? 'zapc.exe' : 'zapc';
                const execution = new vscode.ShellExecution(compiler, [filePath]);

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
                    const compiler = process.platform === 'win32' ? 'zapc.exe' : 'zapc';
                    return new vscode.Task(
                        definition,
                        task.scope,
                        task.name,
                        task.source,
                        new vscode.ShellExecution(compiler, [vscode.window.activeTextEditor.document.uri.fsPath]),
                        '$zap-matcher'
                    );
                }
                return undefined;
            }
        })
    );

    // Helper to get executable name based on OS
    const getZapCompiler = () => {
        return process.platform === 'win32' ? 'zapc.exe' : 'zapc';
    };

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

    // 3. Register Quick Compile command (Ctrl+Shift+Z)
    context.subscriptions.push(
        vscode.commands.registerCommand('zap.compile', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor || editor.document.languageId !== 'zap') {
                vscode.window.showInformationMessage('Open a .zap file to compile.');
                return;
            }

            const filePath = editor.document.uri.fsPath;
            const compiler = getZapCompiler();

            // Create a dedicated terminal or reuse existing
            let terminal = vscode.window.terminals.find(t => t.name === 'ZAP Compiler');
            if (!terminal) {
                terminal = vscode.window.createTerminal('ZAP Compiler');
            }

            terminal.show(true);
            // Quote path to handle spaces
            terminal.sendText(`${compiler} "${filePath}"`);
        })
    );

    // Folding provider for CASE/DEFAULT -> BREAK fallthrough blocks.
    context.subscriptions.push(
        vscode.languages.registerFoldingRangeProvider('zap', {
            provideFoldingRanges(document) {
                const ranges = [];
                const stack = [];
                let currentStart = null;
                let inBlockComment = false;

                const startRegex = /^(proc|func|if|else|elseif|switch|while|repeat|for|asm|struct|enum|\.ifdef|\.ifndef|\.else)\b/;
                const endRegex = /^(return|end|until|else|elseif|\.endif|\.else)\b/;

                for (let line = 0; line < document.lineCount; line++) {
                    let text = document.lineAt(line).text;

                    if (inBlockComment) {
                        const endIndex = text.indexOf('*/');
                        if (endIndex === -1) {
                            continue;
                        }
                        inBlockComment = false;
                        text = text.slice(endIndex + 2);
                    }

                    const blockStartIndex = text.indexOf('/*');
                    if (blockStartIndex !== -1) {
                        const blockEndIndex = text.indexOf('*/', blockStartIndex + 2);
                        if (blockEndIndex === -1) {
                            inBlockComment = true;
                            text = text.slice(0, blockStartIndex);
                        } else {
                            text = text.slice(0, blockStartIndex) + text.slice(blockEndIndex + 2);
                        }
                    }

                    const lineCommentIndex = text.indexOf(';');
                    if (lineCommentIndex !== -1) {
                        text = text.slice(0, lineCommentIndex);
                    }

                    const trimmed = text.trimStart();
                    if (trimmed.length === 0) continue;

                    const lower = trimmed.toLowerCase();
                    const isCase = lower.startsWith('case ') || lower === 'case';
                    const isDefault = lower.startsWith('default ') || lower === 'default';
                    const isBreak = lower.startsWith('break ') || lower === 'break';

                    if ((isCase || isDefault) && currentStart === null) {
                        currentStart = line;
                        continue;
                    }

                    if (isBreak && currentStart !== null) {
                        if (line > currentStart) {
                            ranges.push(new vscode.FoldingRange(currentStart, line));
                        }
                        currentStart = null;
                    }

                    if (endRegex.test(lower)) {
                        if (stack.length > 0) {
                            const startLine = stack.pop();
                            if (line > startLine) {
                                ranges.push(new vscode.FoldingRange(startLine, line));
                            }
                        }
                    }

                    if (startRegex.test(lower)) {
                        stack.push(line);
                    }
                }

                return ranges;
            }
        })
    );
}

function deactivate() { }

module.exports = { activate, deactivate };
