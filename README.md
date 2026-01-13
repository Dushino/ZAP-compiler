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
# Compile an Zap! program
python compiler.py program.zap -o program.s

# Assemble the output (using ca65)
ca65 -t atari program.s -o program.o
ld65 -t atari program.o -o program.xex
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
