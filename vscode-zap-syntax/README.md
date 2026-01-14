# Zap Language Support for VS Code

This extension provides syntax highlighting and custom file icons for the Zap programming language.

## Features

- **Syntax Highlighting** for Zap source files (.zap)
- **Custom File Icon** - Microchip-themed "Z" icon in modern blue colors
- **Comment Support** - Semicolon-based line comments
- **Bracket Matching** - Auto-closing and matching for (), [], {}
- **Code Folding** - Fold PROC/FUNC blocks

## Supported Syntax

### Keywords
- Control flow: `IF`, `THEN`, `ELSE`, `ELSEIF`, `FI`, `WHILE`, `DO`, `OD`, `FOR`, `TO`, `STEP`, `UNTIL`, `RETURN`, `EXIT`
- Declarations: `PROC`, `FUNC`, `END`

### Data Types
- `BYTE`, `WORD`, `CARD`, `INT`, `POINTER`, `ARRAY`
- `CONST` modifier

### Preprocessor Directives
- `.ifdef`, `.ifndef`, `.else`, `.endif`
- `.define`, `.undef`
- `.module`, `.include`
- `.segment`

### Operators
- Arithmetic: `+`, `-`, `*`, `/`, `MOD`, `&`, `|`, `^`, `<<`, `>>`
- Comparison: `=`, `#`, `<`, `>`, `<=`, `>=`, `<>`, `AND`, `OR`, `NOT`

### Literals
- Decimal numbers: `123`, `0`
- Hexadecimal numbers: `$FF`, `$1234`
- Strings: `"Hello, World!"`

## Installation

Linux
1. Copy the `vscode-zap-syntax` folder to `~/.vscode/extensions/`
2. Restart VS Code

Windows
1. run install_vscode_extension.bat
2. Restart VS Code


## File Icon

The extension includes a custom SVG icon


## Example

```zap
; Hello World program

PROC Main()
  BYTE x
  CONST BYTE max = 100
  
  .ifdef DEBUG
    ; Debug code
    x = 0
  .endif
  
  WHILE x < max
    x = x + 1
  END
  
END
```

## Contributing

This extension is part of the Zap Compiler project. Contributions welcome!

## License

GPL v.3
