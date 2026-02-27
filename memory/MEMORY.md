# ZAP Compiler — Memory

## Project identity
- ZAP! is a high-level language that compiles to 6502/65C02 assembly using ca65/ld65
- Primary targets: Atari 8-bit, also Apple II, C64, NES
- Written in Python 3.10+; version 0.2.0
- CLI entry point: `compiler.py`

## Key source files
| File | Role |
|---|---|
| tokenizer.py | Lexer → Token list |
| token_types.py | Token type constants |
| parser.py | Recursive-descent parser → AST |
| ast_nodes.py | All AST node dataclasses |
| symbols.py | SymbolTable, ScopedSymbolTable, ProcTable, FuncTable, StructRegistry |
| sema.py | Struct/Enum/Declaration semantic analysis |
| sema_types.py | ExprKind (VALUE/LVALUE/ADDR) + ExprType |
| sema_expr.py | Expression type checker |
| sema_func.py | Function body analysis |
| sema_proc.py | Procedure body analysis |
| compiler_pipeline.py | Main orchestrator (2019 lines); DCE, liveness, variable sharing |
| codegen_expr.py | Code generator (12,662 lines); RPN, peephole opts |
| constfold.py | Constant folding pass |
| constsubst.py | Replaces const/enum refs with literals |
| dce.py | Dead code elimination |
| jump_threading.py | Jump chain simplification |
| label_cleanup.py | Strips unused labels from output asm |
| preprocessor.py | .ifdef/.define conditional compilation |
| module_system.py | Multi-file module loading & merging |
| errors.py | CompileError/SemanticError/SyntaxError/TokenizerError |
| identifier.py | Legacy Identifier dataclass (mostly superseded) |

## Compilation pipeline (in order)
1. preprocessor.py — conditional compilation (.ifdef/.define)
2. tokenizer.py — lexing
3. parser.py — AST construction (two-pass: struct names collected first)
4. module_system.py — include resolution, module merging, export collection
5. sema.py — struct/enum layout, declaration validation → symbol tables
6. sema_expr.py (via sema_func/proc) — expression type checking
7. sema_func.py / sema_proc.py — body analysis, initialization tracking
8. compiler_pipeline.py — prune unused, liveness analysis, variable slot sharing
9. codegen_expr.py — AST → 6502 assembly (RPN-based)
10. peephole pass inside codegen_expr.py
11. jump_threading.py / label_cleanup.py — post-process assembly text

## Type system (three phases)
- **AST phase**: `TypeNode(base, is_pointer)` — syntactic only
- **Semantic phase**: `SemType(base, is_pointer, struct_info)` — with struct metadata
- **Expression phase**: `ExprType = SemType + ExprKind`
  - VALUE: r-value (literals, temporaries)
  - LVALUE: assignable memory location
  - ADDR: address/pointer of something

## Operator processing
- Type promotion: BYTE → WORD → LONG when operand widths differ
- Pointer arithmetic (C-style): PTR+INT, INT+PTR, PTR-INT allowed; PTR-PTR → WORD (element count); PTR+PTR forbidden
- Enum members → CONST nodes via constsubst.py before code gen
- Relational operators always return BYTE
- Logical ops (&&, ||, !) always return BYTE
- Bitwise ops preserve operand type

## Code generation strategy (codegen_expr.py)
- Converts AST expressions to RPN (Reverse Polish Notation) first
- RPN evaluated using: A register (8-bit), X:A (16-bit), MATH0/MATH1/MATH_STACK zero-page
- 32-bit (LONG): uses 4-byte temporaries, bitwise-OR collapse for truthiness
- Power-of-2 optimizations for multiply/divide
- Peephole: 50+ micro-optimizations (redundant loads, tail calls, dead stores)
- Zero-page prioritization: hot scalar locals placed in ZP
- Variable slot sharing: liveness-based, interference graph + greedy coloring

## Language primitives
- Types: byte (8-bit), word (16-bit), long (32-bit), struct, enum, pointers (^)
- Modifiers: const, static, port, #KEEP, #NOEXPORT, #EXPORT, #RD, #WR
- Fixed-address placement: `byte x @$4000`
- Control flow: if/elseif/else/end, while/end, repeat/until, for/next, switch/case/default/end
- Inline asm: ASM...END blocks
- Segments: .segment "name"

## Test suite
- tests/pass/ — 125 positive tests (numbered 001–136)
- tests/fail/ — 60 negative tests (error detection)
- Each positive test: 4 variants (65C02, 65C02+O1, 6502, 6502+O1)
- Verification: ZAP → ca65 → ld65 → 6502 simulator → memory dump vs .ref file
- generated_tests/ — ~50 Python unit tests for focused feature testing

## Code generation optimisations
- **32-bit direct compare** (`codegen_expr.py:11831`): fast path in `_emit_relational_branch_impl` compares LONG/WORD/BYTE simple identifiers and IntLiterals byte-by-byte directly; saves 14–16 instructions vs old MATH0/MATH1 spill path. Falls back to MATH0/MATH1 for complex expressions.
- **SWITCH direct compare** (`codegen_expr.py:11192`): when switch expression is a simple scalar identifier, compare bytes directly from source variable — no temp copy or BSS allocation; saves 2/4/8 LDA/STA instructions for BYTE/WORD/LONG.
- **Dead JMP + proxy elimination** (`codegen_expr.py:11808`): `_emit_relational_branch` wrapper simplified to a single delegation call; removed always-dead `JMP lbl_true` and unnecessary `REL_FALSE_PROXY` indirection — saves 3 instructions per relational branch in all control-flow contexts.
- **Redundant LDA elimination in LONG constant stores** (`codegen_expr.py:5167` gen_init, ~9544 gen_assign): both paths now use a `last_a: int | None` tracking loop over 4 bytes; `LDA #$XX` is skipped if A already holds that value. STZ (65C02) resets `last_a=None` since it doesn't affect A. Saves up to 3 LDA instructions per LONG constant (worst case: all bytes equal, e.g. `long x = 0` on 6502).

## Known fixed bugs
- `codegen_expr.py` (was ~5168): `val & 0xFFFF` mask before LONG init was removed — it truncated bytes 2-3 for values > 65535
- `compiler_pipeline.py:_predeclare_for_loop_temps`: `declare_temp` now takes `type_base: str` (was `is_word: bool`); end/step temps declared as LONG when loop var or bound is LONG; `RepeatUntilStmt` added to `scan_stmts` recursion
- Pylance/pyright (2026-02-27): 36 errors in `codegen_expr.py` + 1 in `ast_nodes.py` fixed. Key: RPNNode.value type widened to include `Expr`; `UnOp.NEG` added to enum; dead stub methods deleted; nested function `op` annotation removed; `stx_operand` initialized; missing vars added to dead `gen_vars`.

## User preferences
- No changes unless explicitly asked
- Update PROGRESS.md after each significant change
- Update documentation in DOC folder when needed
- Any fix mus be applicable for all datatypes, and operators and all possible use cases according to grammar
- After any change always check for pylance errors and repair them
