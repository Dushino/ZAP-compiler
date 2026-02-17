# ZAP Language Summary

This document summarizes the key features and syntax of the ZAP programming language, based on the `DOC` folder and compiler implementation.

## Overview
ZAP is a high-level language that compiles to 6502 assembly (specifically for Atari 8-bit systems). It balances high-level constructs (structs, loops) with low-level control (pointers, hardware registers).

## Documentation

For complete documentation, please visit the repository:

- [Getting Started Guide](https://github.com/Dushino/ZAP-compiler/blob/main/DOC/GETTING_STARTED.md)
- [Language Reference Manual](https://github.com/Dushino/ZAP-compiler/blob/main/DOC/ZAP_LANGUAGE_REFERENCE.md)
- [Advanced Topics](https://github.com/Dushino/ZAP-compiler/blob/main/DOC/ADVANCED_TOPICS.md)

## Installation

See the main tutorial in the repository for installation instructions: https://github.com/Dushino/ZAP-compiler


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
