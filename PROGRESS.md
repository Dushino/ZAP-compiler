# Progress Tracker

## What was done
- Initialized tracking documents (`task.md` and `PROGRESS.md`).
- Reviewed project root directory and `README.md`.
- Read and summarized the overall compiler architecture (`compiler.py`, `compiler_pipeline.py`).
- Read and summarized type representation (`ast_nodes.py`, `sema_types.py`, `symbols.py`).
- Read and summarized operator processing (`sema_expr.py`).
- Read and summarized code generation (`codegen_expr.py`).
- Produced the final summary artifact.
- Found all usages of enums mapped to variables, fields, and return types in the codebase.
- Re-architected Enum `FieldAccess` handling: Enum members are now successfully mapped to expressions and evaluated identically to `CONST` declarations via `constsubst.py`.
- Verified Enums reliably support arithmetic, logical, and relational operators with correctly propagated optimizations and constant folding without entering the RPN virtual stack.
- Wrote full evaluation scripts under `generated_tests/test_enum_const.zap`.
- Ported comprehensive Enum operation tests into the official suite format at `tests/pass/134-enum-ops/134-enum-ops.zap`. This test strictly verifies every arithmetic, bitwise, relational, and logical operator across both `byte` and `word` base Enum types, asserting correct memory layout directly under the `65C02` and `6502` virtual simulator environments.
- Created `DOC/ARCHITECTURE.md` to summarize the compiler architecture out of the previous initial investigation.
- Updated `DOC/ZAP_LANGUAGE_REFERENCE.md` to explicitly list arithmetic, relational, bitwise and logical operations supported on Enum objects.
- Analyzed the codebase and generated a new fresh architecture summary artifact (`architecture_summary.md`).
- Investigated mathematical and logical expression evaluation across ALL combinations of datatypes (BYTE, WORD, LONG, pointers, arrays, enums) and operators (+, -, *, /, %, ~, !, @). Identified gaps such as pointer-distance subtractions acting invalid, and `VALUE - PTR` being permitted. Presented findings in the `expression_matrix.md` artifact table.
- Implemented C-style pointer math constraints in `sema_expr.py`. 
    - Operations `PTR + INT` / `INT + PTR` and `PTR - INT` are permitted.
    - Operation `PTR - PTR` computes element-wise offset correctly.
    - Added valid boundary blocking for operations like `PTR + PTR`, multiplying pointers, etc.
- Intercepted allowed pointer arithmetic in code generation before passing expressions down to the RPN evaluation stack (`codegen_expr.py:ast_to_rpn`).
    - Successfully inject `MUL sizeof(T)` AST-to-RPN instructions for pointer incrementing natively.
    - Successfully inject `DIV sizeof(T)` AST-to-RPN instructions for calculating the difference element-count.
- Added comprehensive unit tests asserting all the above operations (and their relation checking variants / `for` loop constraints) at `tests/pass/136-pointer-math.zap`.
- Fixed a bug in `codegen_expr.py` where `for` loops conditionally lost pointer dimensionality and implicitly cleared the pointer MSB extending from an 8-bit native width.
- Fixed an issue in `sema_expr.py` where pointer relational type checking was overly permissive, unexpectedly passing failing generic integration tests (`013` and `026`).
- Documented all C-style strict pointer arithmetic constraints and allowed relational comparisons inside `DOC/ZAP_LANGUAGE_REFERENCE.md` and `DOC/ADVANCED_TOPICS.md`.
- Implemented fixes for 32-bit `LONG` truncation bugs across control flow expressions (`codegen_expr.py`).
    - **FOR Loops**: Dynamic bounds and steps natively allocate 4-byte temporary variables (instead of assuming 1-byte) when tracking 32-bit fields, maintaining data precision during high-range iterations.
    - **Truthiness Evaluation**: Branches (`IF`, `WHILE`, `REPEAT`) parsing a 32-bit condition expression safely bitwise-OR collapse (`ORA`) all four individual bytes into the central Accumulator before branching, supporting full-range truth checks without incorrectly evaluating high-byte truth values as 0. 
    - **SWITCH / CASE Statements**: Dynamically sized temporary variable allocations. Native byte comparison generated statically across literal cases and dynamic variable cases up to 32-bits via multi-byte sequence checks instead of 16-bit truncations.
- Modified memory slot generation in `codegen_expr.py` to allow CA65 to successfully link `.res` shared aliased `LONG` memory overlaps.

## What remains
- None.

---

## Documentation update: LONG type coverage (2026-02-27)

Audited all user-facing documentation for correctness and completeness regarding the `long` (32-bit) type. Applied fixes across 5 files.

### Changes

**`DOC/grammar.ebnf`**:
- Added `"long"` to `base_type` production — was silently missing, making the grammar technically wrong.
- Updated header comment to record the change.
- Added a `LONG Type` section in the `NOTES` block documenting FOR bounds, SWITCH case, and truthiness rules.
- Updated the CONST note to include `long` in the list of supported types.

**`DOC/ZAP_LANGUAGE_REFERENCE.md`**:
- **SWITCH/CASE**: Corrected false claim "byte or word" → "byte, word, or long".
- **Zero/Non-Zero Evaluation**: Added sub-section explaining 32-bit truthiness: all 4 bytes are OR-ed; a value like `65536` correctly evaluates as True even though its low byte is 0. Added code examples for IF, WHILE, and REPEAT-UNTIL with `long` conditions.
- **FOR loop**: Added a `long` bounds example (start/end above word range) and a note that the compiler automatically allocates 4-byte temporaries for `long` bounds.
- **Comparison operators**: Added a leading sentence stating that all comparisons work on `byte`, `word`, and `long`.
- **Bitwise operators**: Added that operators work on all three integer types with result width matching the widest operand; added a `long` bitwise example.

**`DOC/GETTING_STARTED.md`**:
- Added `long` row to the Variable Types table with range and purpose.
- Added a `long` initialisation example to the code snippet.

**`DOC/README.md`**:
- Added a line to Language Support listing all three integer types: `byte`, `word`, `long`.

## Known issues
- None.

---

## Optimisation: direct 32-bit comparison without MATH0/MATH1 (2026-02-27)

### What was done

Added a **fast path** inside `_emit_relational_branch_impl` (`codegen_expr.py`) for 32-bit (LONG)
comparisons where both operands are simple scalar identifiers or the right operand is a compile-time
`IntLiteral`. Instead of spilling both operands through the MATH0/MATH1 zero-page registers first,
the four bytes are compared directly:

**Before** (`my_long < end_val`, LONG vs LONG):
```asm
; 8 LDA/STA to load end_val → MATH1
LDA _MAIN_END_VAL   → STA __MATH1  …  (×4 bytes)
; 8 LDA/STA to load my_long → MATH0
LDA _MAIN_MY_LONG   → STA __MATH0  …  (×4 bytes)
; 8 LDA/CMP comparing MATH0 vs MATH1
LDA __MATH0+3 → CMP __MATH1+3 → BNE decide  …
```

**After**:
```asm
LDA _MAIN_MY_LONG+3 / CMP _MAIN_END_VAL+3 / BNE decide
LDA _MAIN_MY_LONG+2 / CMP _MAIN_END_VAL+2 / BNE decide
LDA _MAIN_MY_LONG+1 / CMP _MAIN_END_VAL+1 / BNE decide
LDA _MAIN_MY_LONG   / CMP _MAIN_END_VAL
decide: BCC …
```

**Savings per comparison**: 14–16 instructions for LONG vs LONG; 8–12 for mixed widths.

**Cases covered by the new fast path**:

| Left operand | Right operand | Notes |
|---|---|---|
| LONG identifier | LONG identifier | Most common (FOR loop bound check) |
| LONG identifier | WORD identifier | Right bytes 3,2 = `#$00` |
| LONG identifier | BYTE identifier | Right bytes 3,2,1 = `#$00` |
| LONG identifier | IntLiteral | Right bytes from compile-time constant |
| WORD identifier | LONG identifier | Left bytes 3,2 loaded as `#$00` |
| BYTE identifier | LONG identifier | Left bytes 3,2,1 loaded as `#$00` |

All six comparison operators (EQ, NE, LT, LE, GT, GE) are handled. The existing MATH0/MATH1
fallback path is retained unchanged for complex (non-trivial) expressions.

Also tightened the pyright guard for the MATH0/MATH1 fallback: replaced the `bool` flag
`right_is_simple_identifier` with a direct `isinstance(cond.right, Identifier)` check so pyright
can narrow the type (eliminated 2 latent errors introduced by the new isinstance checks above).

### What remains
- None.

### Verification
- `make tests`: 124/124 pass-tests pass, 60/60 fail-tests correctly rejected — 0 regressions.
- `pyright codegen_expr.py`: 0 errors, 0 warnings.

---

## Optimisation: eliminate dead JMP and proxy label in relational branches (2026-02-27)

### What was done

Simplified `_emit_relational_branch` (`codegen_expr.py:11808`). The old implementation created
a `REL_FALSE_PROXY` label and emitted three extra instructions per comparison:

```asm
; Old pattern (3 extra instructions, 1 always dead):
BCC lbl_true
JMP REL_FALSE_PROXY      ; to false
JMP lbl_true             ; ← DEAD — impl always ends with explicit JMP
REL_FALSE_PROXY:
JMP lbl_false
```

Root cause: `_emit_relational_branch_impl` always ends with an explicit `JMP lbl_false` (all six
operator paths return after emitting an unconditional JMP), so the fall-through `JMP lbl_true`
added by the wrapper was never reached. And since `lbl_false` is already accessed via `JMP` in the
impl (full 16-bit range), the proxy label forwarding was also redundant.

Fix: the wrapper now simply delegates:
```python
def _emit_relational_branch(self, …):
    self._emit_relational_branch_impl(cond, lbl_true=lbl_true, lbl_false=lbl_false)
```

**Result for the FOR loop bound check** (`my_long < end_val`):
```asm
; Before:
__ZAP_CMP32_DECIDE_11:
    BCC __ZAP_while_body_9
    JMP __ZAP_REL_FALSE_PROXY_10   ; indirect
    JMP __ZAP_while_body_9         ; dead
__ZAP_REL_FALSE_PROXY_10:
    JMP __ZAP_endwhile_8

; After:
__ZAP_CMP32_DECIDE_10:
    BCC __ZAP_while_body_9
    JMP __ZAP_endwhile_8
```

3 instructions eliminated per relational branch. Applies to all comparison operators in all
control-flow contexts (IF, WHILE, REPEAT-UNTIL, FOR).

### What remains
- None.

### Verification
- `make tests`: 124/124 pass-tests pass, 60/60 fail-tests correctly rejected — 0 regressions.
- `pyright codegen_expr.py`: 0 errors, 0 warnings.

---

## Optimisation: SWITCH direct compare without temp copy (2026-02-27)

### What was done

In the SWITCH statement codegen (`codegen_expr.py:11185`), when the switch expression is a simple
scalar identifier (not array, not port, not volatile, no fixed address), the value is now compared
directly from the source variable — no temporary copy needed.

**Before** (`switch switch_val` where `switch_val` is a LONG):
```asm
; 8 LDA/STA to copy switch_val → temp
LDA _MAIN_SWITCH_VAL   → STA _MAIN___ZAP_SWITCH_VAL_16   (×4 bytes)
; comparisons read from the temp
LDA _MAIN___ZAP_SWITCH_VAL_16+3 / CMP #$00 / BNE next
LDA _MAIN___ZAP_SWITCH_VAL_16+2 / CMP #$01 / BNE next …
```

**After**:
```asm
; no copy — read directly from the switch variable
LDA _MAIN_SWITCH_VAL+3 / CMP #$00 / BNE next
LDA _MAIN_SWITCH_VAL+2 / CMP #$01 / BNE next …
```

Savings: 8 LDA/STA instructions for LONG switch expressions (4 for WORD, 2 for BYTE), plus the
elimination of the temp variable's BSS allocation.

Applies to:
- All three data types (BYTE, WORD, LONG)
- Both literal case values (`case 65536:`) and variable case values (`case some_const:`)

The fallback path (temp copy via `_declare_temp` + `gen_assign`) is retained for complex
switch expressions that cannot be read directly.

### What remains
- None.

### Verification
- `make tests`: 124/124 pass-tests pass, 60/60 fail-tests correctly rejected — 0 regressions.
- `pyright codegen_expr.py`: 0 errors, 0 warnings.

---

## Fix: LONG type bugs in control-flow (2026-02-27)

Root cause investigation and repair of two bugs affecting the LONG (32-bit) type.

### What was done

**Bug 1 — `codegen_expr.py:5168`**: Removed the `val & 0xFFFF` mask that was applied before emitting 4-byte LONG initialisers. The mask silently zeroed bytes 2–3 for any constant > 65535. The downstream byte-by-byte emit already masks correctly per-byte; the 16-bit mask was simply wrong for LONG. One line deleted.

**Bug 2 — `compiler_pipeline.py:_predeclare_for_loop_temps`**:
- Changed `declare_temp(... is_word: bool)` signature to `declare_temp(... type_base: str)` so it can create LONG-typed symbols.
- Updated `end_is_word` / `step_is_word` callers to compute `max(var_width, expr_width)` and select `"LONG"` / `"WORD"` / `"BYTE"` accordingly — mirroring the logic already present in `codegen_expr.py`'s `_gen_for_const_step` and `_gen_for_general`.
- Added `RepeatUntilStmt` recursion to `scan_stmts` so FOR loops nested inside REPEAT-UNTIL bodies are also predeclared correctly.

**Test 138**: Created missing `.ref` and `.json` files. All 4 variants (65C02, 65C02+O1, 6502, 6502+O1) now produce `result = 4` as expected. Regression tests 133-long, 134-enum-ops, 136-pointer-math all still pass.

---

## Pylance/Pyright error fixes (2026-02-27)

Fixed all 36 pyright errors in `codegen_expr.py` and 1 in `ast_nodes.py`. No test regressions.

### Changes made

**`codegen_expr.py`**:
- `RPNNode.__init__` value parameter widened from `BinOp | UnOp | str | int | None` to `BinOp | UnOp | str | int | Expr | None` — `SubscriptExpr`, `FieldAccess`, `DerefExpr`, `CallExpr`, and generic `Expr` nodes are all stored there.
- Removed `BinOp` type annotation from `op` parameter of nested function `get_math_routine_for_op` (pyright could not resolve it in nested-function scope).
- Added `stx_operand: str = ""` initialiser before the STX-search loop to prevent "possibly unbound" pyright report when `stx_found` is `False`.
- Deleted dead stub `gen_vars_block` (3038-3045) — was overridden by the full implementation at line 4388.
- Deleted dead stub `gen_vars` (4250-4254) — was overridden by the implementation at line 4736.
- Added missing variable definitions to dead `gen_vars` method (4736+): `temp_sizes`, `shared_slots_zp`, `shared_slots_bss`, `pointer_scalars`, `pointer_arrays`, `byte_vars`.

**`ast_nodes.py`**:
- Added `NEG = "-"` to `UnOp` enum — `codegen_expr.py` referenced `UnOp.NEG` in two code-generation paths for unary negation; without the enum member pyright reported `reportAttributeAccessIssue`.

### Result
`pyright codegen_expr.py` reports **0 errors, 0 warnings**. All 124 pass tests and 60 fail tests still pass.

---

## Codebase Architecture Review (2026-02-27)

Read the entire codebase, all documentation, and test suite to produce the architectural summary below. No changes were made to any source files.

### Summary of findings
- Full compiler pipeline reviewed: tokenizer → parser → sema → codegen → peephole
- Type system reviewed across all phases (AST TypeNode → SemType → ExprType)
- Operator processing and code generation strategy documented
- Test suite: 125 passing tests, 60 negative tests, 4 compilation variants each
