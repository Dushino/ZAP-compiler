const vscode = require('vscode');
const fs = require('fs');
const path = require('path');

// ---- ZAP source analysis helpers ----

// Strip inline and block comments from a single line.
// Returns the code portion only.
function stripLineComment(raw) {
    let s = raw.replace(/\/\*.*?\*\//g, '');
    const sc = s.indexOf(';');
    if (sc !== -1) s = s.slice(0, sc);
    return s;
}

// ZAP keywords that cannot be type names in a variable declaration.
const ZAP_KEYWORDS = new Set([
    'proc', 'func', 'if', 'else', 'elseif', 'while', 'for', 'repeat',
    'switch', 'case', 'default', 'break', 'continue', 'return', 'end',
    'until', 'struct', 'enum', 'const', 'asm', 'byte', 'word', 'long',
    'and', 'or', 'not', 'true', 'false', 'nil'
]);

// Recursively read lines from a .zap file, following .include directives.
// visited prevents cycles.
function collectAllLines(text, dir, visited = new Set()) {
    const lines = text.split('\n');
    const result = [];
    for (const line of lines) {
        result.push(line);
        const m = line.match(/^\s*\.include\s+"([^"]+)"/i);
        if (m) {
            const inclPath = path.resolve(dir, m[1]);
            if (!visited.has(inclPath)) {
                visited.add(inclPath);
                try {
                    const inclText = fs.readFileSync(inclPath, 'utf8');
                    result.push(...collectAllLines(inclText, path.dirname(inclPath), visited));
                } catch (_) { /* file not found – skip */ }
            }
        }
    }
    return result;
}

// Parse all struct definitions.
// Returns Map<structName, Array<{name, type, comment}>>
function parseStructs(lines) {
    const structs = new Map();
    let current = null;
    let fields = [];
    for (const raw of lines) {
        const code = stripLineComment(raw).trim();
        if (current === null) {
            const m = code.match(/^struct\s+(\w+)/i);
            if (m) { current = m[1]; fields = []; }
        } else {
            if (/^end\b/i.test(code)) {
                structs.set(current, fields);
                current = null; fields = [];
            } else if (code.length > 0) {
                // Field line: TYPE fieldname [optional array/annotation]
                const fm = code.match(/^(\w+)\s+(\w+)/);
                if (fm) {
                    const commentMatch = raw.match(/;(.*)$/);
                    fields.push({
                        type: fm[1],
                        name: fm[2],
                        comment: commentMatch ? commentMatch[1].trim() : ''
                    });
                }
            }
        }
    }
    return structs;
}

// Parse all enum definitions.
// Returns Map<enumName, Array<{member, value?}>>
function parseEnums(lines) {
    const enums = new Map();
    let current = null;
    let members = [];
    let nextVal = 0;
    for (const raw of lines) {
        const code = stripLineComment(raw).trim();
        if (current === null) {
            const m = code.match(/^enum\s+(\w+)/i);
            if (m) { current = m[1]; members = []; nextVal = 0; }
        } else {
            if (/^end\b/i.test(code)) {
                enums.set(current, members);
                current = null; members = [];
            } else if (code.length > 0) {
                // Member: NAME [= value] [,]   value may be decimal or $HH hex
                const parts = code.replace(/,$/, '').split(',');
                for (const part of parts) {
                    const em = part.trim().match(/^(\w+)(?:\s*=\s*(\$?[0-9A-Fa-f]+))?/);
                    if (em) {
                        const rawVal = em[2];
                        const val = rawVal === undefined ? nextVal
                            : rawVal.startsWith('$') ? parseInt(rawVal.slice(1), 16)
                            : parseInt(rawVal, 10);
                        members.push({ member: em[1], value: val, rawValue: rawVal || String(nextVal) });
                        nextVal = val + 1;
                    }
                }
            }
        }
    }
    return enums;
}

// Parse all variable declarations.
// Returns Map<varName, {typeName, isPointer}>
// Handles: TYPE varname, TYPE^ varname, TYPE varname[n], TYPE varname = ...
function parseVarDecls(lines) {
    const vars = new Map();
    for (const raw of lines) {
        const code = stripLineComment(raw).trim();
        // Match: TYPE[^] varname  (optional pointer caret)
        const m = code.match(/^(\w+)(\^?)\s+(\w+)\s*(?:\[|=|$|;)/);
        if (!m) continue;
        const type = m[1];
        const isPointer = m[2] === '^';
        const name = m[3];
        if (ZAP_KEYWORDS.has(type.toLowerCase())) continue;
        if (ZAP_KEYWORDS.has(name.toLowerCase())) continue;
        vars.set(name, { typeName: type, isPointer });
    }
    return vars;
}

// Parse all proc/func signatures.
// Returns Map<name, {kind:'proc'|'func', retType:string|null, params:[{type,name}]}>
function parseProcsAndFuncs(lines) {
    const subs = new Map();
    for (const raw of lines) {
        const code = stripLineComment(raw).trim();
        // func rettype name(params) or proc name(params)
        const funcM = code.match(/^func\s+(\w+)\s+(\w+)\s*\(([^)]*)\)/i);
        if (funcM) {
            subs.set(funcM[2], { kind: 'func', retType: funcM[1], params: parseParams(funcM[3]) });
            continue;
        }
        const procM = code.match(/^proc\s+(\w+)\s*\(([^)]*)\)/i);
        if (procM) {
            subs.set(procM[1], { kind: 'proc', retType: null, params: parseParams(procM[2]) });
        }
    }
    return subs;
}

// Parse parameter list string "byte a, word b" into [{type, name}]
function parseParams(paramStr) {
    if (!paramStr.trim()) return [];
    return paramStr.split(',').map(p => {
        const pm = p.trim().match(/^(\w+\^?)\s+(\w+)/);
        return pm ? { type: pm[1], name: pm[2] } : null;
    }).filter(Boolean);
}

// ---- VS Code Extension ----

function activate(context) {

    // 1. Task Provider (Ctrl+Shift+B / task list)
    context.subscriptions.push(
        vscode.tasks.registerTaskProvider('zap', {
            provideTasks: () => {
                const editor = vscode.window.activeTextEditor;
                if (!editor || editor.document.languageId !== 'zap') return [];
                const filePath = editor.document.uri.fsPath;
                const compiler = process.platform === 'win32' ? 'zapc.exe' : 'zapc';
                const task = new vscode.Task(
                    { type: 'zap' },
                    vscode.TaskScope.Workspace,
                    'Build ZAP project',
                    'zap',
                    new vscode.ShellExecution(compiler, [filePath]),
                    '$zap-matcher'
                );
                task.group = vscode.TaskGroup.Build;
                return [task];
            },
            resolveTask: (task) => {
                if (task.definition.type === 'zap') {
                    const compiler = process.platform === 'win32' ? 'zapc.exe' : 'zapc';
                    return new vscode.Task(
                        task.definition, task.scope, task.name, task.source,
                        new vscode.ShellExecution(compiler, [vscode.window.activeTextEditor.document.uri.fsPath]),
                        '$zap-matcher'
                    );
                }
                return undefined;
            }
        })
    );

    // Helper to get compiler executable name
    const getZapCompiler = () => process.platform === 'win32' ? 'zapc.exe' : 'zapc';

    // 2. Run Build command
    context.subscriptions.push(
        vscode.commands.registerCommand('zap.runBuild', async () => {
            const tasks = await vscode.tasks.fetchTasks({ type: 'zap' });
            if (tasks && tasks.length > 0) {
                vscode.tasks.executeTask(tasks[0]);
            } else {
                vscode.window.showWarningMessage('No ZAP build task found. Open a .zap file.');
            }
        })
    );

    // 3. Quick Compile command (Ctrl+Shift+Z)
    context.subscriptions.push(
        vscode.commands.registerCommand('zap.compile', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor || editor.document.languageId !== 'zap') {
                vscode.window.showInformationMessage('Open a .zap file to compile.');
                return;
            }
            const filePath = editor.document.uri.fsPath;
            let terminal = vscode.window.terminals.find(t => t.name === 'ZAP Compiler');
            if (!terminal) terminal = vscode.window.createTerminal('ZAP Compiler');
            terminal.show(true);
            terminal.sendText(`${getZapCompiler()} "${filePath}"`);
        })
    );

    // 4. Folding provider (proc/func/if/switch/struct/enum/asm blocks + case/break)
    context.subscriptions.push(
        vscode.languages.registerFoldingRangeProvider('zap', {
            provideFoldingRanges(document) {
                const ranges = [];
                const stack = [];
                let currentStart = null;
                let inBlockComment = false;
                const startRx = /^(proc|func|if|else|elseif|switch|while|repeat|for|asm|struct|enum|\.ifdef|\.ifndef|\.else)\b/;
                const endRx   = /^(return|end|until|else|elseif|\.endif|\.else)\b/;

                for (let i = 0; i < document.lineCount; i++) {
                    let text = document.lineAt(i).text;
                    if (inBlockComment) {
                        const ei = text.indexOf('*/');
                        if (ei === -1) continue;
                        inBlockComment = false;
                        text = text.slice(ei + 2);
                    }
                    const bsi = text.indexOf('/*');
                    if (bsi !== -1) {
                        const bei = text.indexOf('*/', bsi + 2);
                        if (bei === -1) { inBlockComment = true; text = text.slice(0, bsi); }
                        else { text = text.slice(0, bsi) + text.slice(bei + 2); }
                    }
                    const sci = text.indexOf(';');
                    if (sci !== -1) text = text.slice(0, sci);
                    const trimmed = text.trimStart();
                    if (!trimmed) continue;
                    const lower = trimmed.toLowerCase();

                    const isCase    = lower.startsWith('case ')    || lower === 'case';
                    const isDefault = lower.startsWith('default ') || lower === 'default';
                    const isBreak   = lower.startsWith('break ')   || lower === 'break';

                    if ((isCase || isDefault) && currentStart === null) { currentStart = i; continue; }
                    if (isBreak && currentStart !== null) {
                        if (i > currentStart) ranges.push(new vscode.FoldingRange(currentStart, i));
                        currentStart = null;
                    }
                    if (endRx.test(lower) && stack.length > 0) {
                        const s = stack.pop();
                        if (i > s) ranges.push(new vscode.FoldingRange(s, i));
                    }
                    if (startRx.test(lower)) stack.push(i);
                }
                return ranges;
            }
        })
    );

    // 5. Completion provider — struct member + enum member completions (triggered by ".")
    //    "fd."          → fields of the struct type declared for variable "fd"
    //    "ICAX1_Mode."  → members of enum ICAX1_Mode (enum name used directly)
    context.subscriptions.push(
        vscode.languages.registerCompletionItemProvider(
            'zap',
            {
                provideCompletionItems(document, position) {
                    const linePrefix = document.lineAt(position).text.slice(0, position.character);

                    // Must end with "identifier."
                    const m = linePrefix.match(/(\w+)\s*\.$/);
                    if (!m) return undefined;
                    const name = m[1];

                    const docDir = path.dirname(document.uri.fsPath);
                    const allLines = collectAllLines(document.getText(), docDir);

                    // --- Struct member completion: variable name → struct type → fields ---
                    const vars = parseVarDecls(allLines);
                    const decl = vars.get(name);
                    if (decl) {
                        const structs = parseStructs(allLines);
                        const fields  = structs.get(decl.typeName);
                        if (fields && fields.length > 0) {
                            return fields.map(f => {
                                const item = new vscode.CompletionItem(f.name, vscode.CompletionItemKind.Field);
                                item.detail = `${decl.typeName}.${f.name} : ${f.type}`;
                                item.documentation = new vscode.MarkdownString(
                                    f.comment ? `*${f.comment}*` : `Field of \`${decl.typeName}\``
                                );
                                return item;
                            });
                        }
                    }

                    // --- Enum member completion: enum type name used directly ---
                    const allEnums = parseEnums(allLines);
                    const members  = allEnums.get(name);
                    if (members && members.length > 0) {
                        return members.map(em => {
                            const item = new vscode.CompletionItem(em.member, vscode.CompletionItemKind.EnumMember);
                            item.detail = `${name}.${em.member} = ${em.rawValue}`;
                            item.documentation = new vscode.MarkdownString(`Member of enum \`${name}\``);
                            return item;
                        });
                    }

                    return undefined;
                }
            },
            '.'  // trigger character
        )
    );
}

function deactivate() { }

module.exports = { activate, deactivate };
