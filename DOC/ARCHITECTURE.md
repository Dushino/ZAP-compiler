# ZAP! Compiler Architecture

ZAP! is a structured, statically-typed language that compiles to 6502/65C02 assembly for the ca65/ld65 toolchain. The compiler is written in Python and produces `.s` files ready for assembly with ca65.

---

## Compilation Pipeline

The pipeline is implemented in `compiler.py` (entry point) and `compiler_pipeline.py` (orchestration). Each stage is listed in execution order.

```
Source file (.zap)
     │
     ▼
1. Preprocessor        preprocessor.py     .define, .ifdef/.ifndef/.else/.endif,
                                           .include, .incbin, .error/.warning/.info
     │
     ▼
2. Module System       module_system.py    Resolves .module / .include dependencies,
                                           merges multi-file programs into one AST
     │
     ▼
3. Parser              parser.py           Recursive-descent; produces AST (ast_nodes.py)
     │
     ▼
4. Semantic Analysis
   ├── EnumAnalyzer     sema.py             Registers enum members as compile-time consts
   ├── StructAnalyzer   sema.py             Calculates struct sizes and field offsets
   ├── DeclarationAnalyzer sema.py          Resolves global variable/const/array/port declarations
   ├── ProcAnalyzer     sema_proc.py        Registers and type-checks procedure bodies
   ├── FuncAnalyzer     sema_func.py        Registers and type-checks function bodies
   └── ExprTypeChecker  sema_expr.py        Validates all expressions; handles promotion and casts
     │
     ▼
5. Constant Folding     constfold.py        Folds constant expressions at compile time
   & Substitution       constsubst.py       Substitutes const/enum references → IntLiteral nodes
     │
     ▼
6. Dead Code            dce.py              Removes unreachable statements within procedure bodies
   Elimination          compiler_pipeline.py prune_unused() removes unused procs, funcs, and globals
     │
     ▼
7. Code Generation      codegen_expr.py     Translates annotated AST to 6502/65C02 assembly
     │
     ▼
8. Post-processing
   ├── Jump Threading   jump_threading.py   Eliminates redundant branch/jump chains
   ├── Label Cleanup    label_cleanup.py    Removes unreferenced labels
   └── Peephole Opt.    codegen_expr.py     Pattern-based assembly optimization (-O1 flag)
     │
     ▼
Output assembly (.s)    ca65 format
```

---

## Source Files

| File | Lines | Role |
|---|---|---|
| `compiler.py` | ~150 | CLI entry point; parses flags, invokes pipeline |
| `compiler_pipeline.py` | ~2000 | Full pipeline orchestration; `compile_program()` |
| `preprocessor.py` | ~400 | Macro/include preprocessor |
| `module_system.py` | ~600 | Multi-file module resolution |
| `tokenizer.py` | ~700 | Lexer; produces token stream |
| `token_types.py` | ~80 | Token type constants |
| `parser.py` | ~1800 | Recursive-descent parser → AST |
| `ast_nodes.py` | ~600 | AST dataclass definitions |
| `sema.py` | ~860 | Declaration, struct, and enum analysis |
| `sema_expr.py` | ~900 | Expression type checker |
| `sema_proc.py` | ~600 | Procedure body analysis |
| `sema_func.py` | ~500 | Function body analysis |
| `sema_types.py` | ~50 | `ExprType` / `ExprKind` definitions |
| `symbols.py` | ~310 | Symbol tables, `SemType`, `StructInfo`, `ProcSymbol` |
| `constfold.py` | ~200 | Constant expression folding |
| `constsubst.py` | ~150 | Const/enum → literal substitution |
| `dce.py` | ~200 | Dead code elimination |
| `jump_threading.py` | ~150 | Jump chain threading |
| `label_cleanup.py` | ~100 | Unused label removal |
| `codegen_expr.py` | ~12930 | Code generation + peephole optimizer |
| `errors.py` | ~100 | `SemanticError` with file/line/col context |
| `identifier.py` | ~50 | Identifier validation helpers |
| `version.py` | 1 | Version string (`0.2.0`) |

---

## Type System

Types exist in two forms:

### AST Level — `TypeNode` (`ast_nodes.py`)
Syntactic type as written in source: base name string + `is_pointer` flag. Examples: `byte`, `word^`, `MyStruct`.

### Semantic Level — `SemType` (`symbols.py`)
```python
@dataclass(frozen=True)
class SemType:
    base: str           # "BYTE", "WORD", "LONG", or struct name
    is_pointer: bool    # True if ^ (pointer-to)
    is_struct: bool     # True if base is a struct name
    struct_info: Optional[StructInfo]   # metadata if is_struct
```
Width rules: pointer → 2, BYTE → 1, WORD → 2, LONG → 4, struct → `struct_info.size`.

### Expression Level — `ExprType` (`sema_types.py`)
Wraps `SemType` with an `ExprKind` tag:
- `VALUE` — r-value (literal, temp result, function return)
- `LVALUE` — assignable memory location (variable, array element, struct field)
- `ADDR` — 16-bit address of something (result of `@` operator)

---

## Symbol Tables

| Structure | Key |
|---|---|
| `SymbolTable` | Global and per-procedure variable/const/array symbols |
| `ProcTable` | Procedure signatures (name, param count, owner file, exported flag) |
| `FuncTable` | Function signatures (name, return type, param count) |
| `StructRegistry` | Struct definitions (name → `StructInfo` with field offsets and sizes) |

All lookups are case-insensitive. Local variables shadow globals; `ScopedSymbolTable` chains local + global lookups.

---

## Operator Processing

Handled in `sema_expr.py` by `ExprTypeChecker`:

- **Promotion**: `promote(a, b)` → LONG if either is LONG; WORD if either is WORD/pointer; otherwise BYTE.
- **Pointer arithmetic**: Only `pointer + value` and `pointer - value` are allowed; result is same pointer type.
- **Struct restrictions**: Structs cannot appear in arithmetic or bitwise expressions; only assignment and address-of are valid.
- **Compound assignment** (`+=`, `-=`, etc.): Desugared at parse time in `parser.py:parse_assign()` to `lhs = lhs op rhs`. No sema/codegen changes needed.
- **Array subscript chains**: Intermediate subscripts yield `ADDR`; final subscript yields `LVALUE`.
- **Port access checks**: `#RD`-only variables cannot appear in write contexts; `#WR`-only variables cannot appear in read contexts.

---

## Code Generation

All code generation is in `codegen_expr.py` via the `CodeGen` class (~12,930 lines).

### Registers and Zero Page
```
A           8-bit accumulator; primary arithmetic register
X           High byte of 16-bit values (X:A pair)
Y           Loop counter / indirect addressing offset

Zero page (compiler-reserved):
  MATH0       4 bytes — primary math operand / result (LONG-capable)
  MATH1       4 bytes — secondary math operand
  MATH_STACK  32 bytes — spill stack for nested expressions
  TMP0–TMP15  2 bytes each — temporary pointers and intermediate values
```

### RPN Expression Evaluation

Expressions are compiled via a Reverse Polish Notation (RPN) evaluator:
1. `ast_to_rpn()` walks the expression AST and produces a flat postfix list of `RPNNode` objects.
2. `rpn_eval_to_code()` processes the list left-to-right, tracking the current value in A/X and spilling to `MATH0`/`MATH1`/`MATH_STACK` when needed.
3. For complex sub-expressions the result is stacked; the final value is returned in A (8-bit) or X:A (16-bit/pointer).

This approach reduces code size by ~22% compared to naive recursive code generation.

### Fast Paths

Before entering the general RPN path, `gen_expr()` checks for many special cases that produce shorter code:

| Pattern | Output |
|---|---|
| `byte_var = byte_var + imm` | `INC`/`DEC` or `LDA; ADC #imm; STA` (3 instr) |
| `word_var = word_var + imm` | `CLC; LDA; ADC #lo; STA; LDA; ADC #hi; STA` |
| `var = var << N` (byte, N=1) | `ASL addr` (1 instr) |
| `var = var << N` (word) | N × `ASL addr; ROL addr+1` |
| `var = var & imm` | `LDA; AND #imm; STA` per byte |
| `if byte_var == imm` | `LDA; CMP #imm; BEQ/BNE` (no temp) |

### Math Runtime Routines

Complex operations are delegated to generated subroutines appended to the output:

| Routine | Operation |
|---|---|
| `MUL8` | 8-bit unsigned multiply |
| `MUL16` | 16-bit unsigned multiply |
| `DIV8` | 8-bit unsigned divide/modulo |
| `DIV16` | 16-bit unsigned divide/modulo |
| `DIV32` | 32-bit divide |
| `LSHIFT32` / `RSHIFT32` | 32-bit shifts by ≥5 |
| `COPY_BYTES` | Byte copy; X = count (1–255), TMP0=src, TMP2=dst |
| `COPY_BYTES16` | Byte copy; TMP4/TMP4+1 = 16-bit count, for arrays > 255 bytes |

### Array Initialization

Arrays with `ListInit` or `StringInit` initializers are stored as ROM data and copied to BSS RAM at program start. Copy strategy:

| Array size (bytes) | Strategy |
|---|---|
| ≤ 8 | Inline indexed loop (`LDA rom_label+n; STA ram_label+n`) |
| 9 – 255 | `COPY_BYTES` subroutine (8-bit count in X) |
| ≥ 256 | `COPY_BYTES16` subroutine (16-bit count in TMP4/TMP4+1) |

### Parameter Passing

Procedures and functions pass arguments via dedicated global variables (`_PROCNAME_PARAM`). Up to two byte-wide parameters may be passed through A and X registers when the optimizer detects no intervening usage (fast-path calling convention). Return values are passed in A (byte) or X:A (word/pointer); struct return values use a caller-allocated global buffer.

---

## Peephole Optimizer (-O1)

The peephole optimizer runs over the generated assembly string before output. It applies a sliding window of pattern-replacement rules:

- **Redundant load elimination**: `STA addr; LDA addr` → removes `LDA` if `addr` not modified between store and load.
- **Dead store elimination**: `STA` immediately overwritten without any intervening read.
- **Jump threading**: `JMP label1; label1: JMP label2` → `JMP label2`.
- **Branch shortening**: `BXX tmp; JMP target` → `BXX_INVERSE target` where branch range allows.
- **INC/DEC pairs**: `INC addr; DEC addr` → eliminated.
- **Redundant LDA #0**: Multiple consecutive `STA` of zero share a single `LDA #$00`.
- **IF condition optimization**: `CMP; BNE tmp; BEQ then` → `CMP; BEQ then`.

---

## Module System

`.module` files export their symbols and procedures for use by including files. The module system:
- Resolves circular dependencies via a visited-set.
- Filters exported symbols based on `#NOEXPORT` / `#EXPORT` attributes.
- Ensures module constructors (`proc X() #KEEP #NOEXPORT`) are always included even if not directly called.
- Propagates struct and enum definitions across module boundaries.

---

## Zero Page Allocation

After semantic analysis, the compiler computes a priority score for each local variable based on loop-nesting depth and access frequency (`zp_priority`). The highest-priority variables are placed in zero page (faster 2-byte addressing) up to the available ZP budget. All other locals use absolute 3-byte addressing.

---

## Enum and Const Architecture

Enums are parsed as `EnumDecl` nodes. `EnumAnalyzer` registers each member as a compile-time `const` symbol. Before code generation, `constsubst.py` replaces all `Identifier` and `FieldAccess` references to consts and enum members with `IntLiteral` nodes. This ensures all constant-valued sub-expressions are visible to `constfold.py` for compile-time evaluation, and that code generation never needs to load const values from memory.

---

## Error Reporting

All errors are reported as `SemanticError` (defined in `errors.py`) with:
- Filename, line, and column (mapped back through preprocessor includes)
- Original source text snippet
- Format: `filename:line:col: error: message`

---

## Supported Targets

| Flag | CPU | Notes |
|---|---|---|
| *(default)* | 65C02 | Enables `STZ`, `PHX`/`PLX`/`PHY`/`PLY`, `BRA`, indirect-indexed improvements |
| `-6502` | NMOS 6502 | Disables 65C02-only instructions; uses `LDA #0; STA addr` instead of `STZ` |
| `-O1` | either | Enables peephole optimizer |
