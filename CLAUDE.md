# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Git Rules — STRICT
- NEVER run `git push` under any circumstances
- NEVER run `git push --force`
- NEVER run `git revert`
- NEVER modify remote tracking branches
- Local commits are allowed
- Always ask for explicit user approval before any git operation

When you see `git push` in the user's prompt, STOP and ask for clarification. Do NOT interpret "push" as a command to push code. Treat "push" as a keyword that requires explicit confirmation. If you are unsure about any git operation, refuse to perform it.

---

## Common Commands

```bash
# Compile a single source file (65c02, no optimisation)
python3 compiler.py source.zap -o out.s

# Compile for 6502 with peephole optimisation
python3 compiler.py -6502 -O1 source.zap -o out.s

# Run all tests (pass + fail)
make tests

# Run only one test directory
make test tests/pass/245-math

# Clean all generated artefacts
make clean

# View the latest test report
cat tests/tests_report.txt
```

Compiler flags: `-6502` (target 6502 vs default 65c02), `-O1` (peephole optimisation), `-D SYMBOL` (preprocessor define), `-I dir` (include path), `-o file.s` (output), `--module` (module mode), `-cfg ld65.cfg` (linker config for ZP start), `-ZPSTART addr`.

---

## Test System

### Structure
```
tests/
  pass/NNN-name/     ← should compile and produce correct output
  fail/NNN-name/     ← should be rejected by the compiler
```

Each **pass** test has:
- `*.zap` — source
- `*.ref` — expected simulator memory dump (e.g. `0200: 28 00 00 00`)
- `*.json` — simulator config (`max_cycles`, `dump_memory` address ranges)

Each **fail** test has:
- `*.zap` — source that must be rejected
- `*.err` — expected error message prefix (must match exactly, including line/column)
- `*.flags` — extra compiler flags (optional)

### Four variants per test
Every test is compiled four ways; all four must pass:

| Variant suffix | Flags |
|---|---|
| `_default` | *(none — 65c02, no opt)* |
| `_6502` | `-6502` |
| `_O1` | `-O1` |
| `_6502_-O1` | `-6502 -O1` |

The runner: compile → assemble (ca65) → link (ld65, `cfg/my_atari.cfg`) → simulate (6502_simulator) → compare output against `.ref`. For fail tests it verifies the compiler rejects the file and the error message matches `.err`.

### Rules for new tests
- New regression tests go in `tests/pass/` or `tests/fail/` in their own numbered subdirectory.
- All existing pass tests must still pass; all fail tests must still fail with the exact error message, line, and column.
- After changing a pass test, update its `.ref` to match the new simulator output.
- Temporary/development files go in `generated_tests/`, not in the project root.

---

## Compiler Architecture

A traditional multi-phase pipeline in Python, targeting ca65 assembly for 6502/65c02. Entry point: `compiler.py`; orchestration: `compiler_pipeline.py → compile_program()`.

### Pipeline

```
Source text
  │
  ├─ tokenizer.py       Lexical analysis → token stream
  ├─ preprocessor.py    .define / .ifdef / .endif
  ├─ parser.py          Recursive-descent → frozen-dataclass AST
  ├─ module_system.py   .include resolution, merged Program AST
  │
  ├─ sema.py            Declarations, structs, enums (DeclarationAnalyzer)
  ├─ sema_proc.py       Procedure parameters + local validation
  ├─ sema_func.py       Function return-type enforcement
  ├─ sema_expr.py       ExprTypeChecker — computes BYTE/WORD/LONG for every expr
  │
  ├─ constsubst.py      Replace const references with literals
  ├─ constfold.py       Fold compile-time arithmetic
  │
  ├─ codegen_expr.py    Code generation (~18 k lines — see below)
  │
  ├─ jump_threading.py  } -O1 only: post-process generated assembly
  ├─ dce.py             }
  └─ label_cleanup.py   }
```

### codegen_expr.py internals

This is the largest and most complex file. Key concepts:

- **Result registers**: byte → `A`; word/pointer → `A` (low) + `X` (high); 32-bit → `MATH0`…`MATH0+3`.
- **MATH scratch**: `MATH0`/`MATH1` are 4-byte zeropage slots used by all 32-bit routines. `MATH_STACK` saves/restores them during nested expressions.
- **`assign_target_type`** (CodeGen field): carries the LHS type into expression codegen. When it is `LONG`, the RPN evaluator sets `_long_target_widen=True` and uses 32-bit routines even for BYTE/WORD operands — *except* BYTE-result expressions, which keep 8-bit wrap-around semantics.
- **`force_word_result`**: forces 16-bit evaluation (preserves carry to bit 15) without widening to 32 bits.
- **`_is_rpn_safe(expr)`**: `True` when all leaves are `Identifier` or `IntLiteral`. RPN-safe expressions use `rpn_eval_to_code`; others use `_gen_binary`.
- **`_collect_add_sub_chain` / `_gen_add_sub_chain_rpn`**: optimise 3+ element ADD/SUB chains — *guarded* by `_is_long_assign` so LONG context is not bypassed.
- **`_emit_call_args`**: marshals arguments into callee parameter slots. For LONG params with WORD-result BinaryExpr, sets `assign_target_type = LONG` (RPN-safe expressions) or uses `_gen_math_binop(long_target=True)` (non-RPN-safe). BYTE-result expressions use `force_word_result` to preserve 8-bit wrap.
- **`_gen_math_binop(long_target=)`**: 32-bit math stack path for MUL/DIV/MOD and LONG arithmetic. When `long_target=True` all bytes of MATH0 are preserved.

### Key data structures
- `ast_nodes.py` — frozen dataclasses for every AST node.
- `symbols.py` — `SymbolTable`, `Symbol`, `SemType` (base `BYTE`/`WORD`/`LONG`/struct/enum + `is_pointer`, `is_array`, `is_const`).
- `sema_types.py` — `ExprKind` (VALUE vs ADDR) + `ExprType` (SemType + kind).
- `errors.py` — `CompileError`; `print_error()` formats source-location-aware messages.

---

## Design Rules

- **Prefer generic, unified code paths.** If logic already exists (e.g. TMP-variable allocation, MATH_STACK push/pop), reuse it rather than duplicating it. Duplicate code paths mean bugs get fixed in one place but not another.
- **Consolidate duplicates.** When you find two copies of equivalent logic, unify them.

---

## After Every Change

| What changed | What to update |
|---|---|
| Compiler source (`*.py`) | `PROGRESS.md` |
| Grammar / new language feature | `docs/` cross-check + `PROGRESS.md` |
| Grammar / implementation / docs | `IDE_Integration/` cross-check |
| Grammar / implementation / docs | `examples/` cross-check |
| Every function/method added | Short one-line comment before the `def` |
| Memory-worthy insight | `memory/MEMORY.md` |
| New language feature | New regression tests in `tests/pass/` AND `tests/fail/` |

---

## Code Generation Rules

- `ASM…END` blocks must **never** be optimised by peephole passes. Labels, instructions, and directives inside ASM blocks are user-controlled and must be emitted verbatim.
- Only `__ZAP_*`-prefixed labels are compiler-generated internal labels. All other labels must be preserved by optimisation passes.

## Compact mode

When using compact, focus on test output and code changes.
