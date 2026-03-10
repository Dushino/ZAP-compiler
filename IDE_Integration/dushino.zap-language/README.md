# Zap Language Support for VS Code

This extension provides syntax highlighting for the Zap programming language.

## Features

- **Syntax Highlighting** for Zap source files (.zap)
- **Comment Support** - Semicolon-based line comments, multiline C-style comments
- **Bracket Matching** - Auto-closing and matching for (), [], {}, /* */
- **Code Folding** - Fold PROC/FUNC, Control flow commands, ASM, STRUCT and multiline comment blocks

## Supported Syntax

### Keywords
- Control flow: `IF`, `ELSE`, `ELSEIF`, `WHILE`, `FOR`, `TO`, `STEP`, `REPEAT`, `UNTIL`, `SWITCH`, `CASE`, `DEFAULT`, `RETURN`, `BREAK`, `CONTINUE`, `END`
- Declarations: `PROC`, `FUNC`, `STRUCT`, `ENUM`, `END`
- Inline assembler: `ASM`, `END` (embedded ca65 highlighting between ASM / END)

### Data Types
- `BYTE`, `WORD`, `LONG`
- `CONST`, `STATIC` type modifiers
- `low()`, `high()`, `loww()`, `highw()`, `sizeof()` built-in functions

### Declaration Modifiers
- `#PORT`, `#RD`, `#WR` - For hardware port definitions
- `#KEEP`, `#NOEXPORT`, `#EXPORT` - For symbol visibility and dead code elimination control

### Preprocessor Directives
- `.module`, `.include`
- `.define`, `.undef`
- `.ifdef`, `.ifndef`, `.else`, `.endif`
- `.error`, `.warning`, `.info`

### Operators
- Assignment: `=`
- Arithmetic/bitwise: `+`, `-`, `*`, `/`, `%`, `&`, `|`, `^`, `~`, `<<`, `>>`
- Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`
- Logical: `&&`, `||`, `!`
- Address-of: `@`
- Member access: `.`
- Indexing: `[`, `]`

### Literals
- Decimal numbers: `123`, `0`
- Hexadecimal numbers: `$FF`, `$1234`
- Binary numbers: `%1010`, `%11001100`
- Strings: `"Hello, World!"`
- ASCII values: `'a'`


## Documentation

For complete documentation, please visit the repository:

- [Getting Started Guide](https://github.com/Dushino/ZAP-compiler/blob/main/DOC/GETTING_STARTED.md)
- [Language Reference Manual](https://github.com/Dushino/ZAP-compiler/blob/main/DOC/ZAP_LANGUAGE_REFERENCE.md)
- [Advanced Topics](https://github.com/Dushino/ZAP-compiler/blob/main/DOC/ADVANCED_TOPICS.md)

## Installation

See the main tutorial in the repository for installation instructions: https://github.com/Dushino/ZAP-compiler

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

This extension is part of the Zap Compiler project. Contributions welcome! Repo: https://github.com/Dushino/ZAP-compiler

## License

GPL v.3
