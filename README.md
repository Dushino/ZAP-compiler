# ⚡ Zap Compiler

**A modern, optimizing compiler for the Zap! programming language**

Zap compiles Zap! source code into optimized 6502 assembly for Atari 8-bit computers and other 6502-based systems.

## Features

### Advanced Optimizations
- 🔥 **Constant Folding** - Compile-time evaluation of constant expressions
- 🎯 **Algebraic Simplification** - Eliminates neutral elements (x+0, x*1, etc.)
- 🧹 **Dead Code Elimination** - Removes unreachable code
- ⚡ **Peephole Optimization** - Pattern-based code improvements
- 📊 **Register Allocation** - Efficient use of 6502 registers

### Language Support
- Syntax is heavily inspired by Action! and C programming languages
- Module system with `.module` and `.include` directives
- Multi-file compilation
- Inline assembly support
- 65C02 instruction set support

### Developer Experience
- Detailed error messages with line numbers
- Source-level debugging comments in generated assembly
- Optimized code generation for both speed and size

## Quick Start

```bash
# Compile a Zap! program
python compiler.py program.zap -o program.s

# Assemble the output (using ca65)
ca65 -t atari program.s -o program.o
ld65 -t atari program.o -o program.xex
```

## Command Line Options

```bash
python compiler.py [OPTIONS] <source.zap>
```

### Available Options

#### `-o <output.s>`
Specifies the output assembly file. If not provided, the generated assembly code is printed to stdout.

**Example:**
```bash
python compiler.py program.zap -o program.s
```

#### `--6502`
Targets the NMOS 6502 instruction set instead of the default WDC 65C02. Use this option when compiling for:
- Original Atari 8-bit computers (Atari 400/800/XL/XE)
- Apple II
- Commodore 64
- NES/Famicom
- Other systems with NMOS 6502 CPUs

**Example:**
```bash
python compiler.py program.zap --6502 -o program.s
```

**Note:** The WDC 65C02 (default) includes additional instructions and addressing modes not available on the NMOS 6502.

#### `--peepholes`
Enables peephole optimizations. These are pattern-based optimizations that improve the generated code by:
- Eliminating redundant load/store sequences
- Optimizing branch patterns
- Reducing instruction count
- Improving code size and performance

**Example:**
```bash
python compiler.py program.zap --peepholes -o program.s
```

**Recommended:** Enable this option for production builds to generate more efficient code.

#### `-D <SYMBOL>`
Defines a preprocessor symbol that can be checked with `.ifdef` directives. Multiple `-D` options can be specified. Symbol names are automatically converted to uppercase.

**Example:**
```bash
python compiler.py program.zap -D DEBUG -D PLATFORM_ATARI -o program.s
```

**Usage in source code:**
```zap
.ifdef DEBUG
  ; Debug-only code
  BYTE debug_flag
.endif

.ifdef PLATFORM_ATARI
  ; Atari-specific code
.else
  ; Other platform code
.endif
```

This allows conditional compilation for different platforms, debug/release builds, or feature toggles.

### Combining Options

All options can be combined as needed:

```bash
# Production build for 6502 with optimizations
python compiler.py game.zap --6502 --peepholes -o game.s

# Debug build with symbols defined
python compiler.py app.zap -D DEBUG -D VERBOSE -o app_debug.s

# WDC 65C02 with peepholes and platform symbol
python compiler.py program.zap --peepholes -D SBC_PLATFORM -o program.s
```

### Usage Examples

```bash
# Basic compilation to stdout
python compiler.py hello.zap

# Compile to file
python compiler.py hello.zap -o hello.s

# Compile for Atari with optimizations
python compiler.py game.zap --6502 --peepholes -o game.s

# Conditional compilation for different platforms
python compiler.py app.zap -D ATARI --6502 -o app_atari.s
python compiler.py app.zap -D SBC --peepholes -o app_sbc.s

# Debug build with verbose output
python compiler.py app.zap -D DEBUG -D VERBOSE -o app_debug.s
```

## Example

**Input (program.zap):**
```zap
PROC main()
  BYTE x, y
  CONST BYTE factor = 5
  
  y = 10
  x = y * factor + 0    ; Optimized at compile time!
RETURN
```

**Generated Assembly:**
```asm
; Optimized: y * 5 + 0 → y * 5 → computed as 50
LDA #50
STA _MAIN_X
```

## Project Structure

- `compiler.py` - Main compiler entry point
- `parser.py` - Recursive descent parser
- `lexer.py` / `tokenizer.py` - Lexical analysis
- `codegen_expr.py` - 6502 code generation
- `constfold.py` - Constant folding optimization
- `dce.py` - Dead code elimination
- `sema*.py` - Semantic analysis

## Requirements

- Python 3.10+
- ca65/ld65 (cc65 toolchain) for assembling

## Why "Zap"?

**Zap** captures the speed and energy of this compiler - it quickly eliminates inefficiencies and generates tight, optimized code for classic hardware. Plus, it's got that retro computing vibe! ⚡

## License

GPL v.3

## Contributing

Contributions welcome! This compiler is actively developed and improving.

---

*Bringing modern compiler optimizations to classic 8-bit computing* 🎮
