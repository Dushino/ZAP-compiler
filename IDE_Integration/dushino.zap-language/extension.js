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
// Includes primitive types (byte/word/long) so parseVarDecls only captures struct-typed vars.
const ZAP_KEYWORDS = new Set([
    'proc', 'func', 'if', 'else', 'elseif', 'while', 'for', 'repeat',
    'switch', 'case', 'default', 'break', 'continue', 'return', 'end',
    'until', 'struct', 'enum', 'const', 'asm', 'byte', 'word', 'long',
    'and', 'or', 'not', 'true', 'false', 'nil'
]);

// Flow/control keywords that cannot be a type name — does NOT include byte/word/long
// so that primitive-typed variable declarations are captured in parseAllSymbols.
const ZAP_FLOW_KW = new Set([
    'proc', 'func', 'if', 'else', 'elseif', 'while', 'for', 'repeat',
    'switch', 'case', 'default', 'break', 'continue', 'return', 'end',
    'until', 'struct', 'enum', 'const', 'asm', 'and', 'or', 'not', 'true', 'false', 'nil'
]);

// Case-insensitive Map: normalizes all string keys to lowercase automatically.
// Allows lookups and storage to work regardless of identifier casing in ZAP source.
class CIMap extends Map {
    set(k, v) { return super.set(typeof k === 'string' ? k.toLowerCase() : k, v); }
    get(k)    { return super.get(typeof k === 'string' ? k.toLowerCase() : k); }
    has(k)    { return super.has(typeof k === 'string' ? k.toLowerCase() : k); }
}

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
    const structs = new CIMap();
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
    const enums = new CIMap();
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
    const vars = new CIMap();
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

// Parse parameter list string into [{type, name, defaultVal?}]
// Handles both "byte^ name" and "byte ^name" pointer styles, plus "word n = 0" defaults.
function parseParams(paramStr) {
    if (!paramStr.trim()) return [];
    return paramStr.split(',').map(p => {
        // type[^] [^]name [= defaultVal]
        const pm = p.trim().match(/^(\w+)(\^?)\s+(\^?)(\w+)(?:\s*=\s*(\S+))?/);
        if (!pm) return null;
        const type = pm[1] + (pm[2] || pm[3] ? '^' : '');
        return { type, name: pm[4], defaultVal: pm[5] };
    }).filter(Boolean);
}

// Format a single parameter for display: "byte^ str" or "word adr = 0"
function formatParam(p) {
    return p.defaultVal ? `${p.type} ${p.name} = ${p.defaultVal}` : `${p.type} ${p.name}`;
}

// Build a snippet insert string for a call: name(${1:p1}, ${2:p2}) or name() if no params.
function buildCallSnippet(name, params) {
    if (!params || params.length === 0) return `${name}()`;
    const args = params.map((p, i) => `\${${i + 1}:${p.name}}`).join(', ');
    return `${name}(${args})`;
}

// Parse ALL named symbols from lines for bare-identifier completion.
// Returns array of {kind, name, type?, retType?, params?}
// Handles: proc, func, const, variables of any type (byte/word/long/struct), struct names, enum names.
function parseAllSymbols(lines) {
    const seen = new CIMap(); // name → symbol (last definition wins, dedup across includes)
    let inStructOrEnum = false;

    for (const raw of lines) {
        const code = stripLineComment(raw).trim();
        if (!code) continue;

        // Struct/enum body — capture the type name, skip internal field lines
        if (/^struct\b/i.test(code)) {
            const sm = code.match(/^struct\s+(\w+)/i);
            if (sm) seen.set(sm[1], { kind: 'struct', name: sm[1] });
            inStructOrEnum = true; continue;
        }
        if (/^enum\b/i.test(code)) {
            const em = code.match(/^enum\s+(\w+)/i);
            if (em) seen.set(em[1], { kind: 'enum', name: em[1] });
            inStructOrEnum = true; continue;
        }
        if (inStructOrEnum) {
            if (/^end\b/i.test(code)) inStructOrEnum = false;
            continue;
        }

        // proc name(params)
        const procM = code.match(/^proc\s+(\w+)\s*\(([^)]*)\)/i);
        if (procM) {
            seen.set(procM[1], { kind: 'proc', name: procM[1], params: parseParams(procM[2]) });
            continue;
        }

        // func rettype name(params)
        const funcM = code.match(/^func\s+(\w+)\s+(\w+)\s*\(([^)]*)\)/i);
        if (funcM) {
            seen.set(funcM[2], { kind: 'func', name: funcM[2], retType: funcM[1], params: parseParams(funcM[3]) });
            continue;
        }

        // const TYPE name [= value | [...]]
        const constM = code.match(/^const\s+(\w+\^?)\s+(\w+)/i);
        if (constM) {
            seen.set(constM[2], { kind: 'const', name: constM[2], type: constM[1] });
            continue;
        }

        // TYPE[^] name  (variable of any type, including byte/word/long)
        const varM = code.match(/^(\w+)(\^?)\s+(\w+)\s*(?:\[|=|@|$)/);
        if (varM) {
            const type = varM[1], name = varM[3];
            if (!ZAP_FLOW_KW.has(type.toLowerCase()) && !ZAP_KEYWORDS.has(name.toLowerCase())) {
                if (!seen.has(name)) seen.set(name, { kind: 'var', name, type: type + varM[2] });
            }
        }
    }
    return [...seen.values()];
}

// Walk the line prefix backwards to find the enclosing function call context.
// Returns { funcName, activeParam } where activeParam is the 0-based index of
// the parameter the cursor is currently inside, or null if not inside a call.
function getFunctionCallContext(linePrefix) {
    let depth = 0;
    for (let i = linePrefix.length - 1; i >= 0; i--) {
        const c = linePrefix[i];
        if (c === ')') { depth++; continue; }
        if (c === '(' ) {
            if (depth > 0) { depth--; continue; }
            // This is the opening paren of the enclosing call.
            // Count commas at depth 0 between here and the cursor.
            let activeParam = 0, d = 0;
            for (const ch of linePrefix.slice(i + 1)) {
                if      (ch === '(') d++;
                else if (ch === ')') d--;
                else if (ch === ',' && d === 0) activeParam++;
            }
            // Extract function name immediately before the paren.
            const nameMatch = linePrefix.slice(0, i).trimEnd().match(/(\w+)\s*$/);
            if (nameMatch) return { funcName: nameMatch[1], activeParam };
            return null;
        }
    }
    return null;
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

    // 6. Completion provider — bare-identifier completions (vars, consts, procs, funcs, structs, enums)
    //    Triggered by normal typing; skipped when cursor is in a dot-access context.
    context.subscriptions.push(
        vscode.languages.registerCompletionItemProvider(
            'zap',
            {
                provideCompletionItems(document, position) {
                    const linePrefix = document.lineAt(position).text.slice(0, position.character);

                    // Skip — dot provider handles "identifier." contexts
                    if (/\.\s*\w*$/.test(linePrefix)) return undefined;

                    const docDir  = path.dirname(document.uri.fsPath);
                    const allLines = collectAllLines(document.getText(), docDir);
                    const symbols  = parseAllSymbols(allLines);

                    return symbols.map(sym => {
                        switch (sym.kind) {
                            case 'var': {
                                const item = new vscode.CompletionItem(sym.name, vscode.CompletionItemKind.Variable);
                                item.detail = `${sym.type} ${sym.name}`;
                                return item;
                            }
                            case 'const': {
                                const item = new vscode.CompletionItem(sym.name, vscode.CompletionItemKind.Constant);
                                item.detail = `const ${sym.type} ${sym.name}`;
                                return item;
                            }
                            case 'proc': {
                                const item = new vscode.CompletionItem(sym.name, vscode.CompletionItemKind.Function);
                                const paramStr = sym.params.map(formatParam).join(', ');
                                item.detail = `proc ${sym.name}(${paramStr})`;
                                item.insertText = new vscode.SnippetString(buildCallSnippet(sym.name, sym.params));
                                return item;
                            }
                            case 'func': {
                                const item = new vscode.CompletionItem(sym.name, vscode.CompletionItemKind.Function);
                                const paramStr = sym.params.map(formatParam).join(', ');
                                item.detail = `func ${sym.retType} ${sym.name}(${paramStr})`;
                                item.insertText = new vscode.SnippetString(buildCallSnippet(sym.name, sym.params));
                                return item;
                            }
                            case 'struct': {
                                const item = new vscode.CompletionItem(sym.name, vscode.CompletionItemKind.Class);
                                item.detail = `struct ${sym.name}`;
                                return item;
                            }
                            case 'enum': {
                                const item = new vscode.CompletionItem(sym.name, vscode.CompletionItemKind.Enum);
                                item.detail = `enum ${sym.name}`;
                                return item;
                            }
                            default:
                                return null;
                        }
                    }).filter(Boolean);
                }
            }
            // No trigger character — VS Code calls this during normal word typing
        )
    );

    // 7. Signature help provider — shows parameter hints when typing inside a call
    //    Triggered by '(' and ',' — highlights the active parameter as cursor moves.
    context.subscriptions.push(
        vscode.languages.registerSignatureHelpProvider(
            'zap',
            {
                provideSignatureHelp(document, position) {
                    const linePrefix = document.lineAt(position).text.slice(0, position.character);
                    const ctx = getFunctionCallContext(linePrefix);
                    if (!ctx) return undefined;

                    const docDir  = path.dirname(document.uri.fsPath);
                    const allLines = collectAllLines(document.getText(), docDir);
                    const symbols  = parseAllSymbols(allLines);
                    const sym = symbols.find(s => s.name.toLowerCase() === ctx.funcName.toLowerCase());
                    if (!sym || (sym.kind !== 'proc' && sym.kind !== 'func')) return undefined;

                    const paramStr = sym.params.map(formatParam).join(', ');
                    const label = sym.kind === 'func'
                        ? `func ${sym.retType} ${sym.name}(${paramStr})`
                        : `proc ${sym.name}(${paramStr})`;

                    const sigInfo = new vscode.SignatureInformation(label);

                    // Each ParameterInformation spans the exact substring in label so VS Code
                    // can bold/highlight it. We locate each param's text inside label.
                    let searchFrom = label.indexOf('(') + 1;
                    sigInfo.parameters = sym.params.map(p => {
                        const pLabel = formatParam(p);
                        const start  = label.indexOf(pLabel, searchFrom);
                        searchFrom   = start + pLabel.length;
                        return new vscode.ParameterInformation([start, searchFrom]);
                    });

                    const sigHelp = new vscode.SignatureHelp();
                    sigHelp.signatures    = [sigInfo];
                    sigHelp.activeSignature = 0;
                    sigHelp.activeParameter = Math.min(ctx.activeParam, Math.max(0, sym.params.length - 1));
                    return sigHelp;
                }
            },
            '(', ','  // trigger characters
        )
    );

    // 8. Hover provider — show type/signature/struct-fields/enum-members on hover
    context.subscriptions.push(
        vscode.languages.registerHoverProvider('zap', {
            provideHover(document, position) {
                const range = document.getWordRangeAtPosition(position, /[\w]+/);
                if (!range) return undefined;
                const word = document.getText(range);

                // Check if this word is immediately preceded by a dot  → hover on a member
                const beforeRange = new vscode.Position(position.line, range.start.character - 1);
                const charBefore  = range.start.character > 0
                    ? document.getText(new vscode.Range(beforeRange, range.start))
                    : '';

                const docDir   = path.dirname(document.uri.fsPath);
                const allLines = collectAllLines(document.getText(), docDir);

                // --- Hovering over "field" in "varname.field" ---
                if (charBefore === '.') {
                    // Find the owner identifier: text before the dot on the same line
                    const lineText  = document.lineAt(position.line).text;
                    const ownerMatch = lineText.slice(0, range.start.character - 1).match(/(\w+)\s*$/);
                    if (ownerMatch) {
                        const owner = ownerMatch[1];

                        // Struct field hover
                        const vars    = parseVarDecls(allLines);
                        const decl    = vars.get(owner);
                        if (decl) {
                            const structs = parseStructs(allLines);
                            const fields  = structs.get(decl.typeName) || [];
                            const field   = fields.find(f => f.name.toLowerCase() === word.toLowerCase());
                            if (field) {
                                const md = new vscode.MarkdownString();
                                md.appendCodeblock(`${decl.typeName}.${field.name} : ${field.type}`, 'zap');
                                if (field.comment) md.appendMarkdown(`*${field.comment}*`);
                                return new vscode.Hover(md, range);
                            }
                        }

                        // Enum member hover
                        const allEnums = parseEnums(allLines);
                        const members  = allEnums.get(owner);
                        if (members) {
                            const em = members.find(m => m.member.toLowerCase() === word.toLowerCase());
                            if (em) {
                                const md = new vscode.MarkdownString();
                                md.appendCodeblock(`${owner}.${em.member} = ${em.rawValue}`, 'zap');
                                md.appendMarkdown(`Member of enum \`${owner}\``);
                                return new vscode.Hover(md, range);
                            }
                        }
                    }
                    return undefined;
                }

                // --- Hovering over a bare identifier ---
                const symbols = parseAllSymbols(allLines);
                const sym = symbols.find(s => s.name.toLowerCase() === word.toLowerCase());

                if (sym) {
                    const md = new vscode.MarkdownString();
                    switch (sym.kind) {
                        case 'var':
                            md.appendCodeblock(`${sym.type} ${sym.name}`, 'zap');
                            // If it's a struct type, also show its fields
                            if (sym.type) {
                                const structs = parseStructs(allLines);
                                const fields  = structs.get(sym.type.replace('^', ''));
                                if (fields && fields.length > 0) {
                                    md.appendMarkdown('\n\n**Fields:**\n');
                                    fields.forEach(f => {
                                        const c = f.comment ? ` — ${f.comment}` : '';
                                        md.appendMarkdown(`- \`${f.type} ${f.name}\`${c}\n`);
                                    });
                                }
                            }
                            break;
                        case 'const':
                            md.appendCodeblock(`const ${sym.type} ${sym.name}`, 'zap');
                            break;
                        case 'proc': {
                            const paramStr = sym.params.map(formatParam).join(', ');
                            md.appendCodeblock(`proc ${sym.name}(${paramStr})`, 'zap');
                            break;
                        }
                        case 'func': {
                            const paramStr = sym.params.map(formatParam).join(', ');
                            md.appendCodeblock(`func ${sym.retType} ${sym.name}(${paramStr})`, 'zap');
                            break;
                        }
                        case 'struct': {
                            const structs = parseStructs(allLines);
                            const fields  = structs.get(sym.name) || [];
                            md.appendCodeblock(`struct ${sym.name}`, 'zap');
                            if (fields.length > 0) {
                                md.appendMarkdown('\n\n**Fields:**\n');
                                fields.forEach(f => {
                                    const c = f.comment ? ` — ${f.comment}` : '';
                                    md.appendMarkdown(`- \`${f.type} ${f.name}\`${c}\n`);
                                });
                            }
                            break;
                        }
                        case 'enum': {
                            const allEnums = parseEnums(allLines);
                            const members  = allEnums.get(sym.name) || [];
                            md.appendCodeblock(`enum ${sym.name}`, 'zap');
                            if (members.length > 0) {
                                md.appendMarkdown('\n\n**Members:**\n');
                                members.forEach(em => {
                                    md.appendMarkdown(`- \`${em.member}\` = ${em.rawValue}\n`);
                                });
                            }
                            break;
                        }
                        default:
                            return undefined;
                    }
                    return new vscode.Hover(md, range);
                }

                return undefined;
            }
        })
    );
}

function deactivate() { }

module.exports = { activate, deactivate };
