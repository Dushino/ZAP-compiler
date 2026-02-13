# Zap Language Support for VS Code

This extension provides syntax highlighting for the Zap programming language.

## Features

- **Syntax Highlighting** for Zap source files (.zap)
- **Comment Support** - Semicolon-based line comments, multiline C-style comments
- **Bracket Matching** - Auto-closing and matching for (), [], /* */
- **Code Folding** - Fold PROC/FUNC and multiline comment blocks

## Supported Syntax

### Keywords
- Control flow: `IF`, `ELSE`, `ELSEIF`, `ENDIF`, `WHILE`, `FOR`, `TO`, `STEP`, `RETURN`, `EXIT`
- Declarations: `PROC`, `FUNC`, `END`
- Inline assembler: `ASM`, `END` supporting ca65 syntax highlighting
- Embedded ca65 assembler syntax highlighting between ASM / END


### Data Types
- `BYTE`, `WORD`, `STRUCT`
- `CONST`, `STATIC` modifiers

### Preprocessor Directives
- `.ifdef`, `.ifndef`, `.else`, `.endif`
- `.define`, `.undef`
- `.module`, `.include`

### Operators
- Arithmetic: `+`, `-`, `*`, `/`, `%`, `&`, `|`, `^`, `<<`, `>>`
- Comparison: `=`, `!=`, `<`, `>`, `<=`, `>=`, `<>`

### Literals
- Decimal numbers: `123`, `0`
- Hexadecimal numbers: `$FF`, `$1234`
- Binary numbers: `%1010`, `%11001100`
- Strings: `"Hello, World!"`
- ASCII values: `'a'`


## Installation

See the main tutorial in the repository for installation instructions.

## Example

```zap
; Hello World program

.define DEBUG

PROC Main()
  BYTE x = 1
  CONST BYTE max = 100
  
  .ifdef DEBUG
    ; Debug code
    x = 0
  .endif
  
  WHILE x < max
    x = x + 1
    IF x > 5
        BREAK
    END
  END
  
END
```

## Contributing

This extension is part of the Zap Compiler project. Contributions welcome!

## License

GPL v.3
