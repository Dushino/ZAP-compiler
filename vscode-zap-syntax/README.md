# Zap Language Support for VS Code

This VS Code extension provides syntax highlighting, file icons, and language support for the Zap programming language targeting 6502-based systems.

## Features

- **Syntax Highlighting** for Zap source files (.zap) with customized color scheme
- **Custom File Icon** - Microchip-themed "Z" icon in modern blue colors
- **Language Configuration** - Comment support, bracket matching, auto-closing pairs
- **Code Folding** - Fold PROC/FUNC blocks for better code organization
- **Keybindings Support** - Ready for custom keybindings and commands
- **Multi-line Comment Support** - Recognizes line comments with semicolon (;)

## Supported Syntax

### Keywords
**Control Flow:**
- `IF`, `THEN`, `ELSE`, `ELSEIF`, `FI`
- `WHILE`, `DO`, `OD`
- `FOR`, `TO`, `STEP`, `UNTIL`
- `RETURN`, `EXIT`, `BREAK`, `CONTINUE`

**Declarations:**
- `PROC` - Procedure declaration
- `FUNC` - Function declaration
- `END` - End of proc/func block

**Type Modifiers:**
- `CONST` - Constant declaration
- `STATIC` - Static variables
- `INLINE` - Inline procedures/functions

### Data Types
- `BYTE` - 8-bit unsigned integer (0-255)
- `WORD` - 16-bit unsigned integer (0-65535)
- `BYTE ^` - Memory pointer to BYTE
- `WORD ^` - Memory pointer to WORD
- `ARRAY` - Array type with brackets
- `STRING` - String type

### Preprocessor Directives
- `.ifdef` / `.ifndef` - Conditional compilation
- `.else` / `.endif` - Conditional blocks
- `.define` / `.undef` - Symbol definitions
- `.module` / `.include` - Module system
- `.segment` - Code segments

### Operators
**Arithmetic:**
- `+` (addition), `-` (subtraction)
- `*` (multiplication), `/` (division)
- `MOD` (modulo), `&` (bitwise AND)
- `|` (bitwise OR), `^` (bitwise XOR)
- `<<` (left shift), `>>` (right shift)

**Comparison:**
- `=` (equal), `#` or `<>` (not equal)
- `<` (less), `>` (greater)
- `<=` (less or equal), `>=` (greater or equal)
- `AND` (logical AND), `OR` (logical OR)
- `NOT` (logical NOT)

### Literals
- **Decimal Numbers:** `123`, `0`, `1000`
- **Hexadecimal Numbers:** `$FF`, `$1234`, `$0A`
- **Binary Numbers:** `%11010101`
- **Strings:** `"Hello"`, `"World!"`
- **Character Literals:** `'A'`, `'Z'`

## Installation

### Linux/Unix/macOS
1. Clone or copy the `vscode-zap-syntax` folder to `~/.vscode/extensions/`
2. Folder should be named as: `~/.vscode/extensions/zap-syntax-vscode`
3. Restart VS Code

### Windows

**Option 1: Manual Installation**
1. Copy `vscode-zap-syntax` folder to `%APPDATA%\Code\User\extensions\`
2. Restart VS Code

**Option 2: Automated Installation**
```batch
install_vscode_extension.bat
```

**Option 3: PowerShell Installation**
```powershell
.\install_vscode_extension.ps1
```

## File Icon

The extension includes a custom SVG icon (Microchip-themed "Z") that appears in:
- File explorer for `.zap` files
- File tabs in the editor
- Quick open file list

## Example

```zap
; Zap! program example
; Demonstrates various language features

PROC main()
  BYTE counter, result
  WORD value
  
  .ifdef DEBUG
    ; Debug code only in debug builds
    value = 0
  .endif
  
  ; Simple loop
  counter = 0
  WHILE counter < 10
    result = counter * 2
    counter = counter + 1
  END
  
  RETURN
END

FUNC add(a, b)
  RETURN a + b
END
```

## Extension Files

- `package.json` - Extension manifest with activation events and commands
- `language-configuration.json` - Language-specific settings (comments, brackets, etc.)
- `syntaxes/zap.tmLanguage.json` - TextMate grammar for syntax highlighting
- `icons/` - Custom file and product icons

## Contributing

This extension is part of the Zap Compiler project. Contributions welcome!

## License

GPL v3

## Related Projects

- **ZAP Compiler** - Main compiler project (https://github.com/Dushino/ZAP-compiler)
- **6502 Simulator** - Runtime environment for testing compiled code
