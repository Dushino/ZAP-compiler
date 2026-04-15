The author of this software stands in solidarity with 🇺🇦 Ukraine. We believe in a world where international borders are respected and human rights are upheld. We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


# ZAP Language Support for VS Code

Full-featured language support for the [ZAP programming language](https://github.com/Dushino/ZAP-compiler) — a modern high-level language targeting 6502/65C02 processors (Atari 8-bit, C64, NES, Apple II).

---

## Features

### Syntax Highlighting
Full colorization of keywords, types, literals, operators, preprocessor directives, and inline ca65 assembly blocks (`asm ... end`).

### Code Folding
Collapse `proc`, `func`, `if`, `while`, `for`, `repeat`, `switch`, `struct`, `enum`, `asm` blocks and `case`/`default`/`break` sections.

### IntelliSense — Struct Member Completions
Type `fd.` on a `FILE`-typed variable and get a popup listing all fields with types and comments.

```zap
FILE fd
fd.          ; → fd : byte, error : ERRNO, eof : BOOL
```

### IntelliSense — Enum Member Completions
Type `ICAX1_Mode.` to see all enum members with their values.

```zap
ICAX1_Mode.  ; → Read = 4, Write = 8, Append = 9, ...
```

### IntelliSense — Identifier Completions
Typing any identifier prefix shows all declared symbols from the current file and all `.include`d files: variables, constants, procedures, functions, struct types, and enum types — each with its full signature.

### Hover Information
Hover over any identifier to see:
- **Variables** — type name; if struct-typed, the full field list
- **Procedures/Functions** — complete signature with all parameters and default values
- **Struct types** — all fields with types and comments
- **Enum types** — all members with values
- **`owner.field`** — type of that specific field
- **`EnumName.Member`** — value of that enum member

### Signature Help
While typing a call, a tooltip appears showing the full signature with the current parameter highlighted. Updates live as you type `,` to move to the next argument.

```zap
rv = fopen(      ; shows: proc fopen(byte^ fd, byte^ name, byte mode)
                 ;                   ^^^^^^^^^  highlighted
```

### Go to Definition — F12
- **F12 on a proc/func name** → jumps to its declaration (follows `.include` chains)
- **F12 on a variable** → jumps to its declaration line
- **F12 on `fd.error`** (cursor on `error`) → jumps to the `error` field inside `struct FILE`
- **F12 on `ICAX1_Mode.Write`** (cursor on `Write`) → jumps to `Write = 8` in the enum
- **Ctrl+Click** works the same way

### Find All References — Shift+F12
- **Shift+F12 on a name** → lists every use across the current file and all included files
- **Shift+F12 on `fd.error`** (cursor on `error`) → lists every `.error` member access
- Right-click → **Find All References** works the same way

### Document Symbols / Outline
The **Outline** panel (View → Open View → Outline) shows the full symbol tree of the current file:

```
▼ FILE                struct
    fd                  byte
    error               ERRNO
    eof                 BOOL
▼ ICAX1_Mode          enum
    Read                = 4
    Write               = 8
▼ fopen               byte^ fd, byte^ name, byte mode
    fd
    name
    mode
```

The breadcrumb bar at the top of the editor also uses this — it shows which proc/func/struct you are currently inside.

### Inline Compiler Diagnostics
The compiler runs automatically and error squiggles appear in the editor:

- **On save** — runs immediately
- **While typing** — runs 1.5 s after you stop typing
- **On file open** — runs once
- Errors in **included files** get squiggles in their own file too
- Hover over a squiggle to read the full error message

> **Requires** `zapc` to be in your `PATH`.

### Code Snippets
Type a prefix and press **Tab** to expand:

| Prefix | Expands to |
|--------|-----------|
| `proc` | Procedure skeleton with tab stops |
| `func` | Function skeleton with return type and value |
| `struct` | Struct with one field |
| `enum` | Enum with two members |
| `if` | `if … end` |
| `ife` | `if … else … end` |
| `ifee` | `if … elseif … else … end` |
| `while` | `while … end` |
| `for` | `for i = 0 to N … end` |
| `ford` | `for … downto … end` |
| `fors` | `for … to … step … end` |
| `repeat` | `repeat … until condition` |
| `switch` | `switch` with `case` and `default` |
| `case` | Single `case … break` block |
| `asm` | Inline assembly block |
| `byte` / `word` / `long` | Variable with optional initializer |
| `bytearr` / `wordarr` | Array declarations |
| `constb` / `constw` / `consts` | Constant declarations |
| `.module` / `.include` / `.define` | Preprocessor directives |
| `.ifdef` / `.ifndef` | Conditional compilation blocks |

### AI Inline Code Completions

Optional Copilot-style ghost text powered by Anthropic Claude or OpenAI — tailored for ZAP! syntax and 6502 conventions.

1. Set `zap.ai.enabled` to `true` in VS Code settings
2. Set `zap.ai.apiKey` to your Anthropic or OpenAI API key
3. Optionally choose `zap.ai.provider` (`anthropic` or `openai`) and `zap.ai.model`

As you type, gray suggestions appear after a short delay. Press **Tab** to accept, **Esc** to dismiss. The status bar shows current AI state. Click it to toggle on/off.

Also works with local models via Ollama (set `zap.ai.endpoint` to `http://localhost:11434` and provider to `openai`).

> AI completions are optional and disabled by default. See [IDE Integration Guide](https://github.com/Dushino/ZAP-compiler/blob/main/docs/IDE_INTEGRATION.md) for full setup.

### Build Integration
| Shortcut | Action |
|----------|--------|
| **Ctrl+Shift+Z** | Quick compile current file (output in ZAP Compiler terminal) |
| **Ctrl+Alt+Z** | Run `zap: Build ZAP project` task |
| **Ctrl+Shift+B** | VS Code build task picker |

---

## Case Insensitivity

ZAP is a case-insensitive language. All IntelliSense features work regardless of identifier capitalization — `FILE`, `file`, and `File` are all recognized as the same symbol.

---

## Cross-File Support

All IntelliSense features follow `.include` directives recursively. Symbols defined in any included library are fully available in every file that includes it.

---

## Supported Syntax

### Keywords
Control flow: `IF`, `ELSE`, `ELSEIF`, `WHILE`, `FOR`, `TO`, `DOWNTO`, `STEP`, `REPEAT`, `UNTIL`, `SWITCH`, `CASE`, `DEFAULT`, `RETURN`, `BREAK`, `CONTINUE`, `END`

Declarations: `PROC`, `FUNC`, `STRUCT`, `ENUM`, `CONST`

Inline assembler: `ASM … END` (embedded ca65 syntax highlighting)

### Data Types
`BYTE`, `WORD`, `LONG`, pointer types with `^`

### Declaration Modifiers
`#PORT`, `#RD`, `#WR` — hardware port definitions
`#KEEP`, `#NOEXPORT`, `#EXPORT` — symbol visibility

### Preprocessor
`.module`, `.include`, `.define`, `.undef`, `.ifdef`, `.ifndef`, `.else`, `.endif`, `.error`, `.warning`, `.info`

### Built-in Functions & Commands
`low()`, `high()`, `loww()`, `highw()`, `sizeof()`, `peek()`, `poke()`

---

## Documentation

- [Getting Started Guide](https://github.com/Dushino/ZAP-compiler/blob/main/docs/GETTING_STARTED.md)
- [IDE Integration Guide](https://github.com/Dushino/ZAP-compiler/blob/main/docs/IDE_INTEGRATION.md)
- [Language Reference](https://github.com/Dushino/ZAP-compiler/blob/main/docs/ZAP_LANGUAGE_REFERENCE.md)
- [Standard Library](https://github.com/Dushino/ZAP-compiler/blob/main/docs/STDLIB.md)

---

## Installation

See the [Getting Started Guide](https://github.com/Dushino/ZAP-compiler/blob/main/docs/GETTING_STARTED.md) for full installation instructions, or run the install script in the `IDE_Integration/` folder of the repository.

---

## License

GPL v3 — part of the [ZAP Compiler](https://github.com/Dushino/ZAP-compiler) project.
