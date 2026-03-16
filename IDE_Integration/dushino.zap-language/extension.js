const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

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

// Like collectAllLines but also records the source file path and original line number.
// Returns Array<{text: string, file: string, lineNum: number}>
function collectAllLinesWithSource(text, filePath, visited = new Set()) {
    const lines = text.split('\n');
    const result = [];
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        result.push({ text: line, file: filePath, lineNum: i });
        const m = line.match(/^\s*\.include\s+"([^"]+)"/i);
        if (m) {
            const inclPath = path.resolve(path.dirname(filePath), m[1]);
            if (!visited.has(inclPath)) {
                visited.add(inclPath);
                try {
                    const inclText = fs.readFileSync(inclPath, 'utf8');
                    result.push(...collectAllLinesWithSource(inclText, inclPath, visited));
                } catch (_) { /* file not found – skip */ }
            }
        }
    }
    return result;
}

// Find the column of the first word-boundary match for `word` in `text` (case-insensitive).
function wordCol(text, word) {
    const m = text.search(new RegExp(`\\b${word}\\b`, 'i'));
    return m >= 0 ? m : 0;
}

// Search linesWithSource for the declaration of a plain identifier.
// Returns vscode.Location or undefined.
function findDefinitionLocation(word, linesWithSource) {
    const wl = word.toLowerCase();
    for (const { text, file, lineNum } of linesWithSource) {
        const code = stripLineComment(text).trim();

        // proc name(
        const procM = code.match(/^proc\s+(\w+)\s*\(/i);
        if (procM && procM[1].toLowerCase() === wl)
            return new vscode.Location(vscode.Uri.file(file), new vscode.Position(lineNum, wordCol(text, word)));

        // func TYPE name(
        const funcM = code.match(/^func\s+\w+\s+(\w+)\s*\(/i);
        if (funcM && funcM[1].toLowerCase() === wl)
            return new vscode.Location(vscode.Uri.file(file), new vscode.Position(lineNum, wordCol(text, word)));

        // struct NAME
        const structM = code.match(/^struct\s+(\w+)/i);
        if (structM && structM[1].toLowerCase() === wl)
            return new vscode.Location(vscode.Uri.file(file), new vscode.Position(lineNum, wordCol(text, word)));

        // enum NAME
        const enumM = code.match(/^enum\s+(\w+)/i);
        if (enumM && enumM[1].toLowerCase() === wl)
            return new vscode.Location(vscode.Uri.file(file), new vscode.Position(lineNum, wordCol(text, word)));

        // const TYPE name
        const constM = code.match(/^const\s+\w+\^?\s+(\w+)/i);
        if (constM && constM[1].toLowerCase() === wl)
            return new vscode.Location(vscode.Uri.file(file), new vscode.Position(lineNum, wordCol(text, word)));

        // TYPE[^] [^]name (variable declaration — all primitive and struct types)
        const varM = code.match(/^(\w+)\^?\s+\^?(\w+)\s*(?:\[|=|@|$)/);
        if (varM && varM[2].toLowerCase() === wl && !ZAP_FLOW_KW.has(varM[1].toLowerCase()))
            return new vscode.Location(vscode.Uri.file(file), new vscode.Position(lineNum, wordCol(text, word)));
    }
    return undefined;
}

// Navigate to a specific field inside a struct definition.
// Returns vscode.Location or undefined.
function findStructFieldDefinition(linesWithSource, structName, fieldName) {
    let inStruct = false;
    const snl = structName.toLowerCase(), fnl = fieldName.toLowerCase();
    for (const { text, file, lineNum } of linesWithSource) {
        const code = stripLineComment(text).trim();
        if (!inStruct) {
            const m = code.match(/^struct\s+(\w+)/i);
            if (m && m[1].toLowerCase() === snl) inStruct = true;
        } else {
            if (/^end\b/i.test(code)) { inStruct = false; continue; }
            const fm = code.match(/^(\w+)\s+(\w+)/);
            if (fm && fm[2].toLowerCase() === fnl)
                return new vscode.Location(vscode.Uri.file(file), new vscode.Position(lineNum, wordCol(text, fieldName)));
        }
    }
    return undefined;
}

// Navigate to a specific member inside an enum definition.
// Returns vscode.Location or undefined.
function findEnumMemberDefinition(linesWithSource, enumName, memberName) {
    let inEnum = false;
    const enl = enumName.toLowerCase(), mnl = memberName.toLowerCase();
    for (const { text, file, lineNum } of linesWithSource) {
        const code = stripLineComment(text).trim();
        if (!inEnum) {
            const m = code.match(/^enum\s+(\w+)/i);
            if (m && m[1].toLowerCase() === enl) inEnum = true;
        } else {
            if (/^end\b/i.test(code)) { inEnum = false; continue; }
            for (const part of code.replace(/,$/, '').split(',')) {
                const em = part.trim().match(/^(\w+)/);
                if (em && em[1].toLowerCase() === mnl)
                    return new vscode.Location(vscode.Uri.file(file), new vscode.Position(lineNum, wordCol(text, memberName)));
            }
        }
    }
    return undefined;
}

// Search linesWithSource for all code occurrences of a pattern (comments stripped).
// pattern must have the 'g' flag. match.index is used as the column directly.
// Returns Array<vscode.Location>.
function searchAllOccurrences(pattern, linesWithSource) {
    const locations = [];
    for (const { text, file, lineNum } of linesWithSource) {
        const code = stripLineComment(text);
        pattern.lastIndex = 0;
        let match;
        while ((match = pattern.exec(code)) !== null) {
            locations.push(new vscode.Location(
                vscode.Uri.file(file),
                new vscode.Position(lineNum, match.index)
            ));
        }
    }
    return locations;
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

// Keywords that open a new nesting level (each needs a matching end/until).
const BLOCK_OPEN_RX  = /^(proc|func|if|while|for|repeat|switch|asm|struct|enum)\b/i;
// Keywords that close a nesting level.
const BLOCK_CLOSE_RX = /^(end|until)\b/i;

// Scan forward from startLine to find the line that closes the block opened at startLine.
// Returns the line index of the closing end/until, or the last line if not found.
function findBlockEnd(lines, startLine) {
    let depth = 1;
    for (let i = startLine + 1; i < lines.length; i++) {
        const code = stripLineComment(lines[i]).trim();
        if (BLOCK_OPEN_RX.test(code))  depth++;
        if (BLOCK_CLOSE_RX.test(code)) { depth--; if (depth === 0) return i; }
    }
    return lines.length - 1;
}

// Build a DocumentSymbol whose full range spans startLine..endLine and whose
// selection range is the name token on startLine.
function makeSymbol(name, detail, kind, lines, startLine, endLine) {
    const nameLine  = lines[startLine] ?? '';
    const nameStart = wordCol(nameLine, name);
    const selRange  = new vscode.Range(startLine, nameStart, startLine, nameStart + name.length);
    const fullRange = new vscode.Range(startLine, 0, endLine, (lines[endLine] ?? '').length);
    return new vscode.DocumentSymbol(name, detail, kind, fullRange, selRange);
}

// Parse the current document into a DocumentSymbol tree (current file only, not includes).
// Top-level: proc, func, struct, enum, const, global var.
// Children:  struct fields, enum members, proc/func params.
function buildDocumentSymbols(document) {
    const text  = document.getText();
    const lines = text.split('\n');
    const symbols = [];
    let i = 0;

    while (i < lines.length) {
        const raw  = lines[i];
        const code = stripLineComment(raw).trim();
        if (!code) { i++; continue; }

        // --- struct NAME ---
        const structM = code.match(/^struct\s+(\w+)/i);
        if (structM) {
            const endLine = findBlockEnd(lines, i);
            const sym = makeSymbol(structM[1], 'struct', vscode.SymbolKind.Class, lines, i, endLine);
            // Children: field declarations inside the struct body
            for (let j = i + 1; j < endLine; j++) {
                const fc = stripLineComment(lines[j]).trim();
                const fm = fc.match(/^(\w+)\s+(\w+)/);
                if (fm && !ZAP_FLOW_KW.has(fm[1].toLowerCase())) {
                    sym.children.push(makeSymbol(fm[2], fm[1], vscode.SymbolKind.Field, lines, j, j));
                }
            }
            symbols.push(sym); i = endLine + 1; continue;
        }

        // --- enum NAME ---
        const enumM = code.match(/^enum\s+(\w+)/i);
        if (enumM) {
            const endLine = findBlockEnd(lines, i);
            const sym = makeSymbol(enumM[1], 'enum', vscode.SymbolKind.Enum, lines, i, endLine);
            for (let j = i + 1; j < endLine; j++) {
                const ec = stripLineComment(lines[j]).trim();
                for (const part of ec.replace(/,$/, '').split(',')) {
                    const em = part.trim().match(/^(\w+)(?:\s*=\s*(\S+))?/);
                    if (em) sym.children.push(
                        makeSymbol(em[1], em[2] ? `= ${em[2]}` : '', vscode.SymbolKind.EnumMember, lines, j, j)
                    );
                }
            }
            symbols.push(sym); i = endLine + 1; continue;
        }

        // --- proc NAME(...) ---
        const procM = code.match(/^proc\s+(\w+)\s*\(([^)]*)\)/i);
        if (procM) {
            const endLine = findBlockEnd(lines, i);
            const params  = parseParams(procM[2]);
            const detail  = `(${params.map(formatParam).join(', ')})`;
            const sym = makeSymbol(procM[1], detail, vscode.SymbolKind.Function, lines, i, endLine);
            params.forEach(p => sym.children.push(
                makeSymbol(p.name, p.type, vscode.SymbolKind.TypeParameter, lines, i, i)
            ));
            symbols.push(sym); i = endLine + 1; continue;
        }

        // --- func RETTYPE NAME(...) ---
        const funcM = code.match(/^func\s+(\w+)\s+(\w+)\s*\(([^)]*)\)/i);
        if (funcM) {
            const endLine = findBlockEnd(lines, i);
            const params  = parseParams(funcM[3]);
            const detail  = `${funcM[1]} (${params.map(formatParam).join(', ')})`;
            const sym = makeSymbol(funcM[2], detail, vscode.SymbolKind.Function, lines, i, endLine);
            params.forEach(p => sym.children.push(
                makeSymbol(p.name, p.type, vscode.SymbolKind.TypeParameter, lines, i, i)
            ));
            symbols.push(sym); i = endLine + 1; continue;
        }

        // --- const TYPE NAME ---
        const constM = code.match(/^const\s+(\w+\^?)\s+(\w+)/i);
        if (constM) {
            symbols.push(makeSymbol(constM[2], `const ${constM[1]}`, vscode.SymbolKind.Constant, lines, i, i));
            i++; continue;
        }

        // --- global variable TYPE[^] NAME ---
        const varM = code.match(/^(\w+)(\^?)\s+(\w+)\s*(?:\[|=|@|$)/);
        if (varM && !ZAP_FLOW_KW.has(varM[1].toLowerCase()) && !ZAP_KEYWORDS.has(varM[3].toLowerCase())) {
            symbols.push(makeSymbol(varM[3], varM[1] + varM[2], vscode.SymbolKind.Variable, lines, i, i));
        }

        i++;
    }
    return symbols;
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

    // 5. Inline diagnostics — run zapc on save/open/change, show error squiggles.
    const diagCollection = vscode.languages.createDiagnosticCollection('zap');
    context.subscriptions.push(diagCollection);

    // Return the best available range for a given file/line/col.
    // Uses the open document's word-range API when the file is already loaded.
    function diagRange(line, col, fsPath) {
        const doc = vscode.workspace.textDocuments.find(d => d.uri.fsPath === fsPath);
        if (doc) {
            const wr = doc.getWordRangeAtPosition(new vscode.Position(line, col), /\w+/);
            if (wr) return wr;
        }
        return new vscode.Range(line, col, line, col + 1);
    }

    // Run the compiler, parse its output, and populate diagCollection.
    function runDiagnostics(document) {
        if (document.languageId !== 'zap') return;
        const filePath  = document.uri.fsPath;
        const compiler  = process.platform === 'win32' ? 'zapc.exe' : 'zapc';

        exec(`"${compiler}" "${filePath}"`, { timeout: 15000 }, (_err, stdout, stderr) => {
            const output  = (stdout || '') + '\n' + (stderr || '');
            const diagMap = new Map(); // absPath → Diagnostic[]

            // Match:  file.zap:line:col: error: message
            const rx = /^(.+\.zap):(\d+):(\d+):\s+(error|warning|info):\s+(.+)$/gim;
            let m;
            while ((m = rx.exec(output)) !== null) {
                const [, file, lineStr, colStr, sev, msg] = m;
                const line = Math.max(0, parseInt(lineStr, 10) - 1);
                const col  = Math.max(0, parseInt(colStr,  10) - 1);
                const absPath = path.isAbsolute(file)
                    ? file : path.resolve(path.dirname(filePath), file);

                const severity = sev.toLowerCase() === 'error'   ? vscode.DiagnosticSeverity.Error
                               : sev.toLowerCase() === 'warning' ? vscode.DiagnosticSeverity.Warning
                               : vscode.DiagnosticSeverity.Information;

                const diag = new vscode.Diagnostic(diagRange(line, col, absPath), msg, severity);
                diag.source = 'zapc';

                if (!diagMap.has(absPath)) diagMap.set(absPath, []);
                diagMap.get(absPath).push(diag);
            }

            // Replace all previous diagnostics for this compilation run.
            diagCollection.clear();
            for (const [absPath, diags] of diagMap)
                diagCollection.set(vscode.Uri.file(absPath), diags);

            // Explicitly mark the main file clean if no errors were found in it.
            if (!diagMap.has(filePath))
                diagCollection.set(document.uri, []);
        });
    }

    let debounceTimer = null;

    // On save — run immediately.
    context.subscriptions.push(
        vscode.workspace.onDidSaveTextDocument(doc => runDiagnostics(doc))
    );
    // On open — run immediately.
    context.subscriptions.push(
        vscode.workspace.onDidOpenTextDocument(doc => runDiagnostics(doc))
    );
    // On change — run after 1.5 s of inactivity (avoids running on every keystroke).
    context.subscriptions.push(
        vscode.workspace.onDidChangeTextDocument(e => {
            if (e.document.languageId !== 'zap') return;
            if (debounceTimer) clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => runDiagnostics(e.document), 1500);
        })
    );
    // Run on the currently active file right away.
    if (vscode.window.activeTextEditor?.document.languageId === 'zap')
        runDiagnostics(vscode.window.activeTextEditor.document);

    // 6. Task Provider (Ctrl+Shift+B / task list) — populates the Outline panel and breadcrumb navigation.
    //    Top-level: proc, func, struct, enum, const, global var.
    //    Children:  struct fields, enum members, proc/func parameters.
    context.subscriptions.push(
        vscode.languages.registerDocumentSymbolProvider('zap', {
            provideDocumentSymbols(document) {
                return buildDocumentSymbols(document);
            }
        })
    );

    // 8. Find All References provider (Shift+F12 / right-click → Find All References)
    //    Plain identifier → all word-boundary matches in code (comments excluded).
    //    Dot-member (cursor on "field" in "owner.field") → all ".field" accesses.
    context.subscriptions.push(
        vscode.languages.registerReferenceProvider('zap', {
            provideReferences(document, position, refContext) {
                const range = document.getWordRangeAtPosition(position, /\w+/);
                if (!range) return [];
                const word = document.getText(range);

                const lineText   = document.lineAt(position.line).text;
                const charBefore = range.start.character > 0 ? lineText[range.start.character - 1] : '';
                const linesWithSource = collectAllLinesWithSource(document.getText(), document.uri.fsPath);

                let pattern;
                if (charBefore === '.') {
                    // Member access: match "." followed by the word — column lands on the dot,
                    // so we offset each result by 1 to point at the member name.
                    pattern = new RegExp(`\\.\\s*(${word})\\b`, 'gi');
                    const raw = searchAllOccurrences(pattern, linesWithSource);
                    // Adjust column: skip past the dot (and any spaces) to the word itself.
                    return raw.map(loc => {
                        const lineText2 = linesWithSource.find(
                            l => l.file === loc.uri.fsPath && l.lineNum === loc.range.start.line
                        )?.text ?? '';
                        const adjusted = wordCol(lineText2, word);
                        return new vscode.Location(loc.uri, new vscode.Position(loc.range.start.line, adjusted));
                    });
                } else {
                    // Plain identifier: whole-word match anywhere in code lines.
                    pattern = new RegExp(`\\b${word}\\b`, 'gi');
                    const all = searchAllOccurrences(pattern, linesWithSource);
                    if (refContext.includeDeclaration) return all;
                    // Exclude the declaration line (first definition found).
                    const defLoc = findDefinitionLocation(word, linesWithSource);
                    if (!defLoc) return all;
                    return all.filter(loc =>
                        !(loc.uri.fsPath === defLoc.uri.fsPath &&
                          loc.range.start.line === defLoc.range.start.line)
                    );
                }
            }
        })
    );

    // 8. Go to Definition provider (F12 / Ctrl+Click)
    //    Plain identifier → its declaration line; "owner.member" → field/enum-member line.
    context.subscriptions.push(
        vscode.languages.registerDefinitionProvider('zap', {
            provideDefinition(document, position) {
                const range = document.getWordRangeAtPosition(position, /\w+/);
                if (!range) return undefined;
                const word = document.getText(range);

                const lineText    = document.lineAt(position.line).text;
                const charBefore  = range.start.character > 0 ? lineText[range.start.character - 1] : '';
                const linesWithSource = collectAllLinesWithSource(document.getText(), document.uri.fsPath);

                // Dot context: "owner.member" → navigate to field or enum member
                if (charBefore === '.') {
                    const ownerMatch = lineText.slice(0, range.start.character - 1).match(/(\w+)\s*$/);
                    if (ownerMatch) {
                        const owner   = ownerMatch[1];
                        const allLines = linesWithSource.map(l => l.text);
                        // Struct field?
                        const decl = parseVarDecls(allLines).get(owner);
                        if (decl) return findStructFieldDefinition(linesWithSource, decl.typeName, word);
                        // Enum member?
                        return findEnumMemberDefinition(linesWithSource, owner, word);
                    }
                    return undefined;
                }

                // Plain identifier → find its declaration
                return findDefinitionLocation(word, linesWithSource);
            }
        })
    );

    // 8. Signature help provider — shows parameter hints when typing inside a call
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
