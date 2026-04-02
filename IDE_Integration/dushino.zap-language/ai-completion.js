// AI inline code completion for ZAP! language.
// Provides Copilot-style ghost text suggestions using Anthropic Claude or OpenAI APIs.
// No npm dependencies — uses Node.js built-in https module.

const vscode = require('vscode');
const https = require('https');
const http = require('http');

// ---- ZAP! language system prompt ----

const ZAP_SYSTEM_PROMPT = `You are a code completion engine for the ZAP! programming language.
ZAP! is a high-level language that compiles to 6502/65C02 assembly for Atari 8-bit computers.

Language syntax:
- Types: byte (8-bit), word (16-bit), long (32-bit). Pointers use ^ prefix on type: ^byte, ^word.
- Variables: "byte x = 0", "word count", "long total = 0", "byte arr[10]"
- Constants: "const byte MAX = 255", "const word SCREEN = $E000"
- Procedures: "proc name(byte param1, word param2) ... end"
- Functions: "func byte name(byte a, byte b) ... return value ... end"
- Control flow: if/elseif/else/end, while/end, for i = 0 to N/end, for i = N downto 0/end, for i = 0 to N step 2/end, repeat/until, switch/case/default/break/end
- Structs: "struct Name ... byte field ... end"
- Enums: "enum Name ... Member1, Member2 = 5 ... end"
- Comments: ; line comment, /* block comment */
- Built-ins: PEEK(addr), POKE(addr, val), LOW(val), HIGH(val), LOWW(val), HIGHW(val), SIZEOF(type)
- Operators: +, -, *, /, %, &, |, ^, <<, >>, ==, !=, <, >, <=, >=, &&, ||, !
- Assignment: =, +=, -=, *=, /=, %=, &=, |=, ^=, <<=, >>=
- Inline assembly: asm ... end
- Preprocessor: .define, .ifdef, .ifndef, .else, .endif, .include, .module
- Port variables: #PORT, #RD, #WR attributes
- Pointer dereference: ptr^, address-of: @var
- All identifiers are case-insensitive.
- Variables must be declared at the top of proc/func before any statements.
- The main entry point is "proc main() ... end".

RULES:
- Output ONLY the code that continues from the cursor position.
- Do NOT include markdown fences, explanations, or comments about what the code does.
- Do NOT repeat code that already exists before the cursor.
- Keep completions short (1-5 lines typically). Stop at a natural boundary.
- Use proper ZAP! syntax, not C/Python/etc.
- Be memory-conscious: prefer byte over word when values fit in 8 bits.
- Match the indentation style of the surrounding code.`;

// ---- API client functions ----

// Make an HTTPS (or HTTP) request and return the response body as a string.
function apiRequest(url, options, body, signal) {
    return new Promise((resolve, reject) => {
        if (signal && signal.aborted) {
            return reject(new Error('Aborted'));
        }

        const parsedUrl = new URL(url);
        const transport = parsedUrl.protocol === 'http:' ? http : https;

        const req = transport.request(parsedUrl, options, (res) => {
            let data = '';
            res.on('data', chunk => { data += chunk; });
            res.on('end', () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    resolve(data);
                } else {
                    reject(new Error(`API ${res.statusCode}: ${data.slice(0, 200)}`));
                }
            });
        });

        req.on('error', reject);

        if (signal) {
            signal.addEventListener('abort', () => {
                req.destroy();
                reject(new Error('Aborted'));
            }, { once: true });
        }

        req.write(body);
        req.end();
    });
}

// Call Anthropic Messages API. Returns the completion text.
async function callAnthropic(apiKey, model, endpoint, systemPrompt, userPrompt, maxTokens, signal) {
    const url = (endpoint || 'https://api.anthropic.com') + '/v1/messages';
    const payload = JSON.stringify({
        model: model,
        max_tokens: maxTokens,
        system: systemPrompt,
        messages: [{ role: 'user', content: userPrompt }]
    });

    const response = await apiRequest(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'x-api-key': apiKey,
            'anthropic-version': '2023-06-01'
        }
    }, payload, signal);

    const json = JSON.parse(response);
    if (json.content && json.content.length > 0) {
        return json.content[0].text || '';
    }
    return '';
}

// Call OpenAI Chat Completions API. Returns the completion text.
async function callOpenAI(apiKey, model, endpoint, systemPrompt, userPrompt, maxTokens, signal) {
    const url = (endpoint || 'https://api.openai.com') + '/v1/chat/completions';
    const payload = JSON.stringify({
        model: model,
        max_tokens: maxTokens,
        temperature: 0.2,
        messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: userPrompt }
        ]
    });

    const response = await apiRequest(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiKey}`
        }
    }, payload, signal);

    const json = JSON.parse(response);
    if (json.choices && json.choices.length > 0) {
        return json.choices[0].message.content || '';
    }
    return '';
}

// ---- Context builder ----

// Build a prompt from the document content surrounding the cursor.
// Returns { userPrompt } with code before/after cursor clearly delimited.
function buildPrompt(document, position) {
    const totalLines = document.lineCount;
    const cursorLine = position.line;
    const cursorCol = position.character;

    // Gather lines before cursor (up to 100 lines of context)
    const startLine = Math.max(0, cursorLine - 100);
    const linesBefore = [];
    for (let i = startLine; i < cursorLine; i++) {
        linesBefore.push(document.lineAt(i).text);
    }
    // Add the partial current line up to cursor
    const currentLineText = document.lineAt(cursorLine).text;
    const beforeCursor = currentLineText.slice(0, cursorCol);
    linesBefore.push(beforeCursor);

    // Gather lines after cursor (up to 30 lines)
    const afterCursor = currentLineText.slice(cursorCol);
    const linesAfter = [];
    if (afterCursor.length > 0) {
        linesAfter.push(afterCursor);
    }
    const endLine = Math.min(totalLines, cursorLine + 31);
    for (let i = cursorLine + 1; i < endLine; i++) {
        linesAfter.push(document.lineAt(i).text);
    }

    const codeBefore = linesBefore.join('\n');
    const codeAfter = linesAfter.join('\n');

    let userPrompt = `Complete the ZAP! code at the cursor position marked with <CURSOR>.

${codeBefore}<CURSOR>${codeAfter.length > 0 ? '\n\n; --- code after cursor ---\n' + codeAfter : ''}

Continue from <CURSOR>. Output only the completion code.`;

    return userPrompt;
}

// ---- Check if cursor is inside a comment or string ----

// Simple heuristic: check if cursor position is inside a comment or string literal.
function isInsideCommentOrString(document, position) {
    const lineText = document.lineAt(position.line).text;
    const col = position.character;
    const prefix = lineText.slice(0, col);

    // Inside line comment (after ;)
    const semi = prefix.indexOf(';');
    if (semi !== -1) {
        // Check it's not inside a string
        const beforeSemi = prefix.slice(0, semi);
        const quoteCount = (beforeSemi.match(/"/g) || []).length;
        if (quoteCount % 2 === 0) return true;
    }

    // Inside string (odd number of unescaped quotes before cursor)
    const quoteCount = (prefix.match(/"/g) || []).length;
    if (quoteCount % 2 !== 0) return true;

    // Inside block comment: scan backwards for /* without matching */
    const fullText = document.getText(new vscode.Range(
        Math.max(0, position.line - 50), 0,
        position.line, col
    ));
    const lastOpen = fullText.lastIndexOf('/*');
    const lastClose = fullText.lastIndexOf('*/');
    if (lastOpen !== -1 && lastOpen > lastClose) return true;

    return false;
}

// ---- Main registration ----

// Register the AI inline completion provider and related commands.
// Called from extension.js activate().
function registerAICompletion(context) {
    // Debounce state
    let debounceTimer = null;
    let abortController = null;

    // Status bar item
    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 50);
    statusBar.command = 'zap.aiToggle';
    context.subscriptions.push(statusBar);

    // Update status bar text based on current settings.
    function updateStatusBar(loading) {
        const config = vscode.workspace.getConfiguration('zap.ai');
        const enabled = config.get('enabled', false);
        if (!enabled) {
            statusBar.text = '$(circle-slash) ZAP AI: Off';
            statusBar.tooltip = 'Click to enable AI completions';
            statusBar.show();
            return;
        }
        const apiKey = config.get('apiKey', '');
        if (!apiKey) {
            statusBar.text = '$(warning) ZAP AI: No Key';
            statusBar.tooltip = 'Set zap.ai.apiKey in settings';
            statusBar.show();
            return;
        }
        if (loading) {
            statusBar.text = '$(sync~spin) ZAP AI';
            statusBar.tooltip = 'Requesting completion...';
        } else {
            statusBar.text = '$(sparkle) ZAP AI: On';
            statusBar.tooltip = 'AI completions active. Click to disable.';
        }
        statusBar.show();
    }

    // Show status bar only when a .zap file is active.
    function onActiveEditorChanged(editor) {
        if (editor && editor.document.languageId === 'zap') {
            updateStatusBar(false);
        } else {
            statusBar.hide();
        }
    }

    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(onActiveEditorChanged)
    );
    onActiveEditorChanged(vscode.window.activeTextEditor);

    // Update status bar when config changes.
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration(e => {
            if (e.affectsConfiguration('zap.ai')) {
                onActiveEditorChanged(vscode.window.activeTextEditor);
            }
        })
    );

    // Toggle command
    context.subscriptions.push(
        vscode.commands.registerCommand('zap.aiToggle', async () => {
            const config = vscode.workspace.getConfiguration('zap.ai');
            const current = config.get('enabled', false);
            await config.update('enabled', !current, vscode.ConfigurationTarget.Global);
            updateStatusBar(false);
        })
    );

    // Inline completion provider
    const provider = vscode.languages.registerInlineCompletionItemProvider('zap', {
        async provideInlineCompletionItems(document, position, completionContext, token) {
            const config = vscode.workspace.getConfiguration('zap.ai');
            if (!config.get('enabled', false)) return [];

            const apiKey = config.get('apiKey', '');
            if (!apiKey) return [];

            // Skip inside comments or strings
            if (isInsideCommentOrString(document, position)) return [];

            // Skip if line is empty and we're at position 0 (likely just pressing enter)
            const lineText = document.lineAt(position.line).text;
            if (lineText.trim().length === 0 && position.character === 0) return [];

            // Cancel previous in-flight request
            if (abortController) {
                abortController.abort();
                abortController = null;
            }

            // Debounce
            const debounceMs = config.get('debounceMs', 500);
            await new Promise((resolve) => {
                if (debounceTimer) clearTimeout(debounceTimer);
                debounceTimer = setTimeout(resolve, debounceMs);
            });

            // Check if cancelled during debounce
            if (token.isCancellationRequested) return [];

            const provider = config.get('provider', 'anthropic');
            const model = config.get('model', 'claude-sonnet-4-6-20250514');
            const endpoint = config.get('endpoint', '');
            const maxTokens = config.get('maxTokens', 256);

            abortController = new AbortController();
            const signal = abortController.signal;

            // Wire VS Code cancellation to our AbortController
            token.onCancellationRequested(() => {
                if (abortController) abortController.abort();
            });

            updateStatusBar(true);

            try {
                const userPrompt = buildPrompt(document, position);
                let completionText = '';

                if (provider === 'anthropic') {
                    completionText = await callAnthropic(
                        apiKey, model, endpoint,
                        ZAP_SYSTEM_PROMPT, userPrompt, maxTokens, signal
                    );
                } else {
                    completionText = await callOpenAI(
                        apiKey, model, endpoint,
                        ZAP_SYSTEM_PROMPT, userPrompt, maxTokens, signal
                    );
                }

                updateStatusBar(false);

                if (!completionText || completionText.trim().length === 0) return [];

                // Strip markdown fences if the model wraps output
                completionText = completionText
                    .replace(/^```(?:zap)?\s*\n?/i, '')
                    .replace(/\n?```\s*$/i, '');

                // Create inline completion at cursor position
                const item = new vscode.InlineCompletionItem(
                    completionText,
                    new vscode.Range(position, position)
                );

                return [item];
            } catch (err) {
                updateStatusBar(false);
                // Silent failure — no popup. Log for debugging.
                if (err.message !== 'Aborted') {
                    console.warn('[ZAP AI]', err.message);
                }
                return [];
            }
        }
    });

    context.subscriptions.push(provider);
}

module.exports = { registerAICompletion };
