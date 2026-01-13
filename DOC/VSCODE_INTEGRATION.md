# VS Code Integration Tutorial for Zap Language

This tutorial explains how to add syntax highlighting for Zap (.zap files) in Visual Studio Code.

## Overview

VS Code uses TextMate grammars for syntax highlighting. This tutorial covers:
1. Installing the Zap syntax highlighting extension
2. Understanding the extension structure
3. Customizing the syntax highlighting
4. Creating your own modifications

## Quick Installation

### Method 1: Install from Directory (Recommended for Development)

1. **Copy the extension folder:**
   ```bash
   cp -r vscode-zap-syntax ~/.vscode/extensions/
   ```

2. **Reload VS Code:**
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS)
   - Type "Reload Window" and press Enter
   - Or restart VS Code

3. **Test the extension:**
   - Open any `.zap` file
   - Syntax highlighting should now be active

### Method 2: Create Symbolic Link (Best for Active Development)

If you're actively developing the Zap compiler and want syntax changes to update automatically:

```bash
# Create a symbolic link instead of copying
ln -s /path/to/ZAP-compiler/vscode-zap-syntax ~/.vscode/extensions/zap-language
```

Then reload VS Code as above.

## Extension File Structure

The extension is located in the `vscode-zap-syntax/` directory:

```
vscode-zap-syntax/
├── package.json                    # Extension manifest
├── language-configuration.json      # Language features (brackets, comments)
├── syntaxes/
│   └── zap.tmLanguage.json         # Syntax highlighting rules
├── README.md                        # Extension documentation
└── .vscodeignore                   # Files to exclude when packaging
```

## Understanding the Files

### 1. package.json

This is the extension manifest that tells VS Code about your extension:

```json
{
  "name": "zap-language",
  "displayName": "Zap Language Support",
  "contributes": {
    "languages": [{
      "id": "zap",
      "extensions": [".zap"],
      "configuration": "./language-configuration.json"
    }],
    "grammars": [{
      "language": "zap",
      "scopeName": "source.zap",
      "path": "./syntaxes/zap.tmLanguage.json"
    }]
  }
}
```

**Key fields:**
- `name`: Internal identifier for the extension
- `displayName`: Name shown in VS Code UI
- `languages`: Registers the `.zap` file extension
- `grammars`: Points to the TextMate grammar file

### 2. language-configuration.json

Defines language-specific editor behavior:

```json
{
  "comments": {
    "lineComment": ";"
  },
  "brackets": [
    ["{", "}"],
    ["[", "]"],
    ["(", ")"]
  ],
  "autoClosingPairs": [
    { "open": "(", "close": ")" },
    { "open": "\"", "close": "\"" }
  ]
}
```

**Features enabled:**
- `;` for line comments (Ctrl+/ will insert `;`)
- Bracket matching and auto-closing
- Quote auto-closing

### 3. syntaxes/zap.tmLanguage.json

The TextMate grammar that defines syntax highlighting patterns using regular expressions:

```json
{
  "scopeName": "source.zap",
  "patterns": [
    { "include": "#keywords" },
    { "include": "#comments" }
  ],
  "repository": {
    "keywords": {
      "patterns": [{
        "name": "keyword.control.zap",
        "match": "\\b(IF|THEN|ELSE|WHILE|DO|OD)\\b"
      }]
    }
  }
}
```

**Structure:**
- `patterns`: Top-level patterns to match
- `repository`: Named pattern groups for reuse
- `name`: Scope name that determines color (based on theme)
- `match`: Regular expression to identify tokens

## Customizing Syntax Highlighting

### Adding New Keywords

To add new keywords (e.g., `BREAK`):

1. Open `vscode-zap-syntax/syntaxes/zap.tmLanguage.json`

2. Find the `keywords` section in the `repository`:

```json
"keywords": {
  "patterns": [
    {
      "name": "keyword.control.zap",
      "match": "\\b(IF|THEN|ELSE|ELSEIF|FI|WHILE|DO|OD|FOR|TO|STEP|UNTIL|RETURN|EXIT|BREAK)\\b"
    }
  ]
}
```

3. Add `BREAK` to the list (don't forget the `\\b` word boundaries)

4. Reload VS Code to see changes

### Adding New Data Types

To add a new data type:

```json
"storage-types": {
  "patterns": [
    {
      "name": "storage.type.zap",
      "match": "\\b(BYTE|WORD|CARD|INT|POINTER|ARRAY|NEWTYPE)\\b"
    }
  ]
}
```

### Adding Preprocessor Directives

The preprocessor directives are handled separately:

```json
"preprocessor": {
  "patterns": [
    {
      "name": "keyword.control.preprocessor.zap",
      "match": "\\.(ifdef|ifndef|else|endif|define|undef|module|include|segment)\\b"
    }
  ]
}
```

## Color Customization

The colors are determined by your VS Code theme and the scope names. The main scopes used:

| Scope Name | Typical Color | Used For |
|------------|---------------|----------|
| `keyword.control` | Purple/Pink | Control flow keywords |
| `storage.type` | Blue | Data types |
| `storage.modifier` | Blue/Cyan | CONST modifier |
| `comment.line` | Green/Gray | Comments |
| `string.quoted` | Red/Orange | String literals |
| `constant.numeric` | Green/Orange | Numbers |
| `keyword.operator` | White/Gray | Operators |
| `entity.name.function` | Yellow | Function names |
| `keyword.control.preprocessor` | Purple | Preprocessor directives |

### Override Colors in VS Code Settings

You can override colors for specific scopes in your VS Code settings:

1. Open Settings (JSON): `Ctrl+Shift+P` → "Preferences: Open Settings (JSON)"

2. Add `editor.tokenColorCustomizations`:

```json
{
  "editor.tokenColorCustomizations": {
    "textMateRules": [
      {
        "scope": "keyword.control.zap",
        "settings": {
          "foreground": "#FF00FF",
          "fontStyle": "bold"
        }
      },
      {
        "scope": "storage.type.zap",
        "settings": {
          "foreground": "#00FFFF"
        }
      }
    ]
  }
}
```

## Testing Your Changes

After modifying any files in the extension:

1. **Save all changes**

2. **Reload VS Code:**
   - `Ctrl+Shift+P` → "Developer: Reload Window"
   - Or press `Ctrl+R`

3. **Test with a sample file:**
   ```zap
   ; Test file
   PROC TestProc()
     BYTE x
     CONST WORD max = $FFFF
     
     .ifdef DEBUG
       x = 0
     .endif
     
     WHILE x < 10 DO
       x = x + 1
     OD
     
     RETURN
   END
   ```

4. **Inspect tokens** (for debugging):
   - `Ctrl+Shift+P` → "Developer: Inspect Editor Tokens and Scopes"
   - Click on any token to see its scope

## Advanced: Regular Expression Tips

TextMate grammars use Oniguruma regular expressions:

- `\\b` - Word boundary
- `(?i)` - Case insensitive
- `(?=...)` - Positive lookahead
- `(?!...)` - Negative lookahead
- `[A-Za-z_]` - Character class
- `\\s*` - Zero or more whitespace
- `.*?` - Non-greedy match

### Common Patterns

**Match function calls:**
```json
{
  "name": "entity.name.function.zap",
  "match": "\\b([A-Za-z_][A-Za-z0-9_]*)\\s*(?=\\()"
}
```

**Match preprocessor with argument:**
```json
{
  "name": "keyword.control.preprocessor.zap",
  "match": "^\\s*\\.(ifdef|ifndef)\\s+([A-Z_]+)",
  "captures": {
    "1": { "name": "keyword.control.preprocessor.zap" },
    "2": { "name": "entity.name.constant.zap" }
  }
}
```

## Publishing Your Extension (Optional)

To share your extension with others:

1. **Install vsce** (VS Code Extension Manager):
   ```bash
   npm install -g @vscode/vsce
   ```

2. **Package the extension:**
   ```bash
   cd vscode-zap-syntax
   vsce package
   ```
   
   This creates a `.vsix` file.

3. **Install the .vsix file:**
   ```bash
   code --install-extension zap-language-1.0.0.vsix
   ```

4. **Or publish to VS Code Marketplace:**
   - Create a publisher account at https://marketplace.visualstudio.com/
   - Follow the publishing guide: https://code.visualstudio.com/api/working-with-extensions/publishing-extension

## Troubleshooting

### Extension Not Loading

1. Check that files are in `~/.vscode/extensions/vscode-zap-syntax/`
2. Verify `package.json` is valid JSON (use a JSON validator)
3. Check VS Code's developer console: `Help` → `Toggle Developer Tools`

### Syntax Highlighting Not Working

1. Verify file extension is `.zap`
2. Check language mode in bottom-right corner of VS Code
3. Manually set language: Click language mode → "Configure File Association" → "Zap"

### Colors Not Showing

1. Try a different color theme
2. Check if scope names are correct using "Inspect Editor Tokens"
3. Some themes don't define colors for all scopes

### Changes Not Appearing

1. Make sure you reloaded the window after changes
2. If using a copy (not symlink), copy files again
3. Clear VS Code cache: Delete `~/.vscode/extensions/vscode-zap-syntax` and reinstall

## Resources

- [VS Code Language Extensions Guide](https://code.visualstudio.com/api/language-extensions/syntax-highlight-guide)
- [TextMate Grammar Documentation](https://macromates.com/manual/en/language_grammars)
- [VS Code Extension API](https://code.visualstudio.com/api)
- [Oniguruma Regular Expressions](https://github.com/kkos/oniguruma/blob/master/doc/RE)

## Summary

You now have:
- ✅ Syntax highlighting for `.zap` files
- ✅ Comment toggling with `Ctrl+/`
- ✅ Auto-closing brackets and quotes
- ✅ Function name highlighting
- ✅ Preprocessor directive support
- ✅ Knowledge to customize and extend the syntax

Happy coding in Zap! ⚡
