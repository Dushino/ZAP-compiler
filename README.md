# ZAP! — A High-Level Language for 6502 / Atari 8-bit

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.9.4-orange.svg)](version.py)
[![Tests](https://github.com/Dushino/ZAP-compiler/actions/workflows/test.yml/badge.svg)](https://github.com/Dushino/ZAP-compiler/actions/workflows/test.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

The author of this software stands in solidarity with 🇺🇦 Ukraine. 
We believe in a world where international borders are respected and human rights are upheld. 
We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.

---

**ZAP!** is a modern high-level language that compiles to **6502 / 65C02 assembly**, targeting **Atari 8-bit** computers. It combines high-level constructs (structs, enums, functions, loops) with low-level control (pointers, hardware registers, inline assembly) and produces tight, optimized 6502 code.

In benchmark comparisons, ZAP! generates code that runs **~44% faster than Action!** on the Atari 8-bit platform — see [benchmarks/BENCHMARKS.md](benchmarks/BENCHMARKS.md).

## Quickstart

### Hello, World!

Save this as `hello.zap`:

```zap
.include "lib/atari/atari_stdio.zap"

proc main()
    puts("Hello, ZAP!")
end
```

Compile, assemble, and link:

```bash
zapc --cpu 6502 -O1 -I lib hello.zap -o hello.s
ca65 hello.s -o hello.o
ld65 -C cfg/my_atari.cfg hello.o -o hello.xex
```

The resulting `hello.xex` runs on any Atari 8-bit emulator (Altirra, Atari800) or real hardware.

## Installation

### Option 1: Pre-built binary

Download the latest `zapc` executable from the [Releases page](https://github.com/Dushino/ZAP-compiler/releases) and place it somewhere in your `PATH`.

### Option 2: Build from source

You need Python 3.x and PyInstaller:

```bash
pip install pyinstaller
git clone https://github.com/Dushino/ZAP-compiler.git
cd ZAP-compiler

# Linux/macOS
./make_dist.sh

# Windows
make_dist.bat
```

This produces `dist/zapc` (or `dist/zapc.exe`). The script also copies it to `$ZAPC_INSTALL_DIR` (default: `~/local/bin`).

### Required: cc65 toolchain

ZAP! generates `.s` files that are assembled and linked using the [cc65 toolchain](https://cc65.github.io/) (`ca65` and `ld65`).

```bash
# Ubuntu/Debian
sudo apt-get install cc65

# macOS
brew install cc65
```

Windows users: download from https://cc65.github.io/

## Documentation

For complete documentation, see the [`DOC/`](DOC/) folder:

- [Getting Started Guide](DOC/GETTING_STARTED.md) — beginner tutorial
- [Language Reference Manual](DOC/ZAP_LANGUAGE_REFERENCE.md) — complete language spec
- [Advanced Topics](DOC/ADVANCED_TOPICS.md) — pointers, inline assembly, optimization
- [Standard Library](DOC/STDLIB.md) — built-in functions and modules
- [Error Messages](DOC/ERROR_MESSAGES.md) — compiler error catalog
- [Known Limitations](DOC/KNOWN_LIMITATIONS.md) — current limitations
- [Architecture](DOC/ARCHITECTURE.md) — how the compiler works internally

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request — it explains how to file good bug reports, what tests to add, and which docs to update.

See also:

- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## License

ZAP! is released under the [GNU General Public License v3.0](LICENSE).


## Core Syntax

### Program Structure
- **Global Scope:** Variables, constants, procedures, functions, structs, enums.
- **Entry Point:** `proc main()` is required.
- **Case Sensitivity:** Case-insensitive for identifiers (internally uppercased), but sensitive for strings/chars.

### Types
- `byte`: 8-bit unsigned (0-255).
- `word`: 16-bit unsigned (0-65535).
- `struct`: User-defined composite types.
- `enum`: Compile-time named integer constants (default `byte`, can be `word`).
- `^`: Pointers (e.g., `byte ^ptr`, `struct Point ^p`).
- `[]`: Arrays (e.g., `byte arr[10]`).

### Modifiers
- `const`: Compile-time constants (cannot be changed).
- `static`: Local variables that persist between calls.
- `port`: Hardware register mapping (requires `@ address`).
  - `#PORT`: Base modifier.
  - `#RD`, `#WR`: Read/Write access control.

### Declarations
```zap
byte x = 10              ; Global with init
byte y @$D000            ; Global at fixed address
const word MAX = 1000    ; Constant
struct Point
    byte x
    byte y
end
Point p = {10, 20}       ; Struct init
```

### Control Flow
- **If:** `if ... elseif ... else ... end`
- **While:** `while ... end`
- **Repeat:** `repeat ... until ...`
- **For:** `for i = 0 to 10 step 1 ... next i`
- **Switch:** `switch ... case ... default ... end`
- **Break/Continue:** Supported in loops.

### Procedures & Functions
- **Procedure:** `proc name(params) ... end` (no return value).
- **Function:** `func type name(params) ... return val ... end` (returns value).
- **Parameters:** Passed by value.
- **Modifiers:** `#KEEP` (prevent DCE), `#NOEXPORT`, `#EXPORT`.

### Pointers & Memory
- **Address-of:** `@var` returns the address (word).
- **Dereference:** `ptr^` accesses the value.
- **Field Access:** `obj.field` or `ptr^.field`.

### Arrays
- **Declaration:** `byte arr[10]` or `byte arr[] = {1, 2}`.
- **Access:** `arr[i]`.
- **Strings:** Just byte arrays. `byte s[] = "Hello"`.

### Bitwise Operators
- `&` (AND), `|` (OR), `^` (XOR), `~` (NOT), `<<`, `>>`.

### Inline Assembly
```zap
asm
    LDA #0
    STA $D020
end
```

## Compiler Features
- **Uninitialized Variable Detection:** Enforced definite assignment for locals.
- **Dead Code Elimination (DCE):** Removes unused procedures/globals (unless `#KEEP`).
- **Module System:** `.module` / `.include`.
- **Optimizations:** Constant folding, zero-page optimization (implied).

## Implementation details (from Python code)
- **Tokenizer:** Handles hex (`$FF`, `0xFF`), binary (`%01`, `0b01`), and escape sequences in strings.
- **Parser:** Recursive descent. `ASTNode` hierarchy mirrors the language structure.
- **Semantics:** Strong type checking (implied by `sema*.py` presence).
