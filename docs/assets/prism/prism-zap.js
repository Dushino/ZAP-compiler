/**
 * Prism.js language definition for ZAP! — a high-level language that compiles
 * to 6502/65C02 assembly for Atari 8-bit systems.
 *
 * Derived from the VS Code TextMate grammar at
 *   IDE_Integration/dushino.zap-language/syntaxes/zap.tmLanguage.json
 *
 * ZAP! is case-insensitive for keywords and identifiers, so every pattern
 * below uses the /i flag.
 *
 * Usage: load after prism.js, then fenced code blocks tagged ```zap will be
 * highlighted automatically by Prism.highlightAll().
 */
(function (Prism) {
    Prism.languages.zap = {
        // Block comments — /* ... */ — must come before line comments because
        // a `;` inside `/* */` is part of the comment body.
        'comment': [
            {
                pattern: /\/\*[\s\S]*?\*\//,
                greedy: true
            },
            {
                // Line comment: ; to end of line
                pattern: /;.*/,
                greedy: true
            }
        ],

        // Double-quoted strings with backslash escapes
        'string': {
            pattern: /"(?:\\[\s\S]|[^"\\])*"/,
            greedy: true
        },

        // Preprocessor directives: .define, .ifdef, .include, .module, etc.
        'zap-preprocessor': {
            pattern: /\.(?:ifdef|ifndef|else|endif|define|undef|module|include|error|warning|info)\b/i,
            alias: 'keyword'
        },

        // Attribute modifiers: #PORT, #RD, #WR, #KEEP, #EXPORT, #NOEXPORT
        'zap-attribute': {
            pattern: /#(?:PORT|RD|WR|KEEP|EXPORT|NOEXPORT)\b/i,
            alias: 'important'
        },

        // Storage types — must come before generic keywords so they get their
        // own color.
        'zap-type': {
            pattern: /\b(?:byte|word|long)\b/i,
            alias: 'class-name'
        },

        // Storage modifiers
        'zap-storage': {
            pattern: /\b(?:const|static)\b/i,
            alias: 'keyword'
        },

        // Control-flow keywords and declarations
        'keyword': {
            pattern: /\b(?:if|else|elseif|switch|case|default|break|continue|while|repeat|until|for|to|step|proc|func|procx|funcx|end|asm|return|exit|struct|enum|peek|poke|low|high|loww|highw|sizeof)\b/i
        },

        // Boolean / null-like constants (ZAP! doesn't have true booleans, but
        // enum-like identifiers get highlighted elsewhere; this is mostly a
        // hook for future keywords).
        'boolean': {
            pattern: /\b(?:TRUE|FALSE|NULL)\b/i
        },

        // Hex: $FF or 0xFF
        // Binary: %0101 or 0b0101
        // Decimal: plain integer
        'number': [
            {
                pattern: /\$[0-9A-Fa-f]+\b/,
                alias: 'hex'
            },
            {
                pattern: /\b0x[0-9A-Fa-f]+\b/,
                alias: 'hex'
            },
            {
                pattern: /%[01]+\b/,
                alias: 'binary'
            },
            {
                pattern: /\b0b[01]+\b/,
                alias: 'binary'
            },
            {
                // Character literal 'c' — treat as a number-ish constant
                pattern: /'(?:\\.|[^'\\])'/,
                alias: 'char'
            },
            {
                pattern: /\b\d+\b/
            }
        ],

        // Function calls: identifier immediately followed by `(`
        'function': {
            pattern: /\b[A-Za-z_][A-Za-z0-9_]*(?=\s*\()/
        },

        // Address-of operator @identifier or @$address
        'zap-address': {
            pattern: /@(?:\$[0-9A-Fa-f]+|[A-Za-z_][A-Za-z0-9_]*)?/,
            alias: 'symbol'
        },

        // Operators — order matters, longer matches first
        'operator': /==|!=|<=|>=|&&|\|\||<<|>>|\+=|-=|\*=|\/=|%=|&=|\|=|\^=|<<=|>>=|[+\-*/%&|^~<>=!]/,

        // Punctuation
        'punctuation': /[{}[\];(),.:^]/
    };

    // Allow ```zap and ```ZAP to both work (Prism normalizes to lowercase but
    // add an explicit alias just in case).
    Prism.languages.ZAP = Prism.languages.zap;
})(Prism);
