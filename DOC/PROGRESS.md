# ZAP! Compiler — Progress & Status

**Current version**: 0.2.0
**Test suite**: 159 pass-tests · 105 fail-tests · all passing

---

## Completed Features

### Language

| Feature | Status |
|---|---|
| `byte`, `word`, `long` scalar types | Done |
| Pointer types (`byte^`, `word^`) and dereference (`ptr^`) | Done |
| Address-of operator (`@var`) | Done |
| `const` variables and arrays | Done |
| `static` local variables (initialized once at program start) | Done |
| `port` modifier for hardware-mapped variables | Done |
| `#RD` / `#WR` modifiers for read/write-only ports | Done |
| `#KEEP` — prevent dead-stripping | Done |
| `#NOEXPORT` / `#EXPORT` — module visibility control | Done |
| One-dimensional arrays with explicit or inferred size | Done |
| Multi-dimensional arrays (2D, 3D, …) | Done |
| Array `ListInit` initializer `{v0, v1, …}` | Done |
| Array `StringInit` initializer `"string"` | Done |
| Large array initialization (> 255 bytes) via `COPY_BYTES16` | Done |
| Array-to-array copy (`dst = src`) for BYTE, WORD, LONG, and multi-dim arrays | Done |
| Structs with field offsets, nested structs | Done |
| Struct `#port` / field `#rd` / `#wr` modifiers | Done |
| Struct copy: const → var, var → var, function-return → var | Done |
| Enum declarations with `EnumName.Member` qualified access | Done |
| `proc` declarations with default parameters | Done |
| `func` declarations with return types and default parameters | Done |
| Function return type validation (scalar, pointer, struct) | Done |
| Arithmetic operators: `+` `-` `*` `/` `%` | Done |
| Bitwise operators: `&` `\|` `^` `~` | Done |
| Shift operators: `<<` `>>` | Done |
| Comparison operators: `==` `!=` `<` `<=` `>` `>=` | Done |
| Logical operators: `&&` `\|\|` `!` | Done |
| Compound assignment: `+=` `-=` `*=` `/=` `%=` `&=` `\|=` `^=` `<<=` `>>=` | Done |
| `if / else / end` | Done |
| `while / end` | Done |
| `for / to / step / end` | Done |
| `repeat / until` | Done |
| `switch / case / default / end` | Done |
| `break` | Done |
| Inline `asm … end` blocks | Done |
| `low()` / `high()` / `loww()` / `highw()` / `sizeof()` built-in functions | Done |
| `continue` | Done |
| `elseif` | Done |
| String literals with escape sequences (`\n`, `\t`, `\r`, `\"`, `\'`, `\\`) | Done |
| Character literals | Done |
| Integer literals: decimal, hex (`$`), binary (`%`) | Done |
| Fixed-address variables (`@address`) | Done |

### Preprocessor

| Feature | Status |
|---|---|
| `.define NAME value` | Done |
| `.ifdef` / `.ifndef` / `.else` / `.endif` | Done |
| `.include "file"` | Done |
| `.incbin "file"` | Done |
| `.error "msg"` / `.warning "msg"` / `.info "msg"` | Done |
| `-D NAME` command-line defines | Done |
| `-I path` include search path | Done |
| CPU symbols (`_6502` / `_65C02`) auto-defined based on target | Done |
| `-SEGZ/-SEGB/-SEGC` configurable segment names | Done |

### Code Generation & Optimization

| Feature | Status |
|---|---|
| RPN-based expression evaluator (default) | Done |
| Fast-path BYTE arithmetic (3–9 instr instead of 15+) | Done |
| Fast-path WORD arithmetic | Done |
| In-place shift optimization (`var = var << N`) | Done |
| In-place bitwise optimization (`var = var & imm`) | Done |
| IF condition optimization (direct `BEQ`/`BNE`) | Done |
| Peephole optimizer (`-O1`) | Done |
| Dead code elimination within proc/func bodies | Done |
| Unused proc/func/global pruning | Done |
| Zero page priority allocation for hot locals | Done |
| Liveness-based variable slot sharing (reduces BSS/ZP usage) | Done |
| Jump threading | Done |
| Unused label removal | Done |
| `COPY_BYTES` (≤ 255 bytes) and `COPY_BYTES16` (> 255 bytes) runtime routines | Done |
| Math runtime routines: `MUL8`, `MUL16`, `DIV8`, `DIV16`, `DIV32`, `LSHIFT32`, `RSHIFT32` | Done |
| 65C02 vs NMOS 6502 code paths (target-specific instruction selection) | Done |
| Source-level debug comments in generated assembly | Done |

### Module System

| Feature | Status |
|---|---|
| `.module` file compilation | Done |
| Exported / unexported symbols per module | Done |
| Module constructor pattern (`#KEEP #NOEXPORT`) | Done |
| Struct and enum propagation across module boundaries | Done |
| Circular dependency detection | Done |

### Tooling

| Feature | Status |
|---|---|
| Error messages with `file:line:col: error: message` format | Done |
| VS Code extension (syntax highlighting, build task) | Done |
| `ca65` / `ld65` toolchain integration | Done |
| Test suite with 4 variants per test (65C02, 65C02+O1, 6502, 6502+O1) | Done |

---

## Test Suite

Tests live in `tests/pass/` (must compile and run correctly) and `tests/fail/` (must be rejected by the compiler).

**Running all tests:**
```bash
make tests
```

**Running a single test:**
```bash
make test pass/144-array-copy
```

Each pass-test directory contains:
- `.zap` — source code
- `.json` — simulator config: `{"max_cycles": N, "dump_memory": ["0xADDR-0xADDR"]}`
- `.ref` — expected memory dump (one line per 8 bytes, e.g. `9C40: 03 00 00 00 …`)

---

## Known Bugs Fixed

| Bug | Fix |
|---|---|
| Arrays with ≥ 256 bytes used 8-bit copy count → infinite loop at program start | Added `COPY_BYTES16` routine and 3-way size split in array initialization |
| `ADC #0A` emitted instead of `ADC #$0A` (ca65 rejects bare decimal) | Added `$` prefix in all hex emit paths |
| Empty array inferred from `arr[] = {}` silently produced `.res 0` | `sema.py` now raises error for zero-length `ListInit` |
| Peephole incorrectly eliminated `LDX` when intervening instruction modified the tracked address | Added `_modifies_memory_operand()` check before elimination |
| `_gen_string_copy()` (array var→var copy) was BYTE-only and used deprecated `array_len` field → multi-dim arrays silently copied 0 bytes | Fixed: use `get_total_array_size()`; 2-way COPY_BYTES / COPY_BYTES16 split |
| Array copy condition in `gen_assign()` checked `lhs_t.sem_type.is_pointer`, which is always `True` for bare array identifiers → WORD and LONG array copies fell through to scalar codegen | Fixed: check `lhs_sym.type.is_struct` on the `Symbol` object instead |
| var→var struct copy had no handler → fell through to scalar codegen, producing wrong code | Added explicit COPY_BYTES/COPY_BYTES16 dispatch path in `gen_assign()` |
| `_gen_const_struct_copy()` and struct-from-function-return used 8-bit `LDX #size` → overflow for structs > 255 bytes | Fixed: 2-way COPY_BYTES / COPY_BYTES16 split based on struct size |
| Struct-returning function return buffers (`__RETBUF_FUNCNAME`) were added to `global_symtab` before `prune_unused()`, which then removed them as unreferenced | Fixed: generate RETBUF symbols after `prune_unused()` in `compiler_pipeline.py` |
| Function return type not validated against declared type — struct returned as byte, wrong struct type, or missing return expression not caught | Added comprehensive return type checking in `sema_func.py`; pointers treated as WORD-compatible |

---

## Open Items

| Item | Priority |
|---|---|
| Add GitHub Linguist entry for ZAP! syntax highlighting on GitHub | Low |
| VS Code: "Build: ZAP: Compile current file" command palette hotkey review | Low |
| Auto short-branch generation (replace `JMP` with `BRA`/`Bxx` where range allows) | Medium |
| Unify cosmetics in generated code (mixed `#$00` vs `#0`, extra blank lines) | Low |
| Const struct literals with word/long fields store values as bytes — field widths not respected | Medium |
| Tutorial examples and expanded language reference | Low |
