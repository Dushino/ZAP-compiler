# Progress Tracker

---

## Refactor: sym_size() unification (2026-03-10)

### What was done

Extracted two identical `sym_size()` closures from `share_locals_liveness` and
`prioritize_locals_to_zp` into a single module-level `_sym_size(sym)` in
`compiler_pipeline.py`.  The second copy was also missing the `is_pointer` guard
(functionally equivalent since pointer `.type.width` == 2 either way, but the
unified version is explicit).  Removed both nested functions (−18 lines),
updated 3 call sites.

**Tests**: all 229 tests pass. No regressions.

---

## Refactor: simple_byte_operand() unification (2026-03-10)

### What was done

Extracted the duplicate `simple_byte_operand()` closure that existed in two
CodeGen methods into a single `CodeGen._simple_byte_operand(rhs, is_16bit)`
method in `codegen_expr.py`.

**Problem**: `_gen_relational` and `_emit_relational_branch_impl` each defined an
identical local closure to return a CMP-ready operand for a trivial byte RHS.
The two copies had a subtle divergence: `_gen_relational` used
`self._sym_operand(sym, low_byte=True)` (returns `#_SYMNAME` for const scalars),
while `_emit_relational_branch_impl` used `sym.asm_name()` (always memory — missing
the const-immediate optimization).

**Fix**:
- Added `CodeGen._simple_byte_operand(self, rhs, is_16bit)` after `_sym_operand`.
- Removed both local closures (−40 lines of duplicate code).
- Updated 3 call sites to `self._simple_byte_operand(…, is_16bit)`.
- Side-effect improvement: `_emit_relational_branch_impl` now emits immediate mode
  for const BYTE right-hand operands (previously always memory mode).

**Tests**: all 229 tests pass. No regressions.

---

## Refactor: cleanup_labels() unification (2026-03-10)

### What was done

- **Deleted** the weaker duplicate `cleanup_labels()` from `jump_threading.py`
  (21 lines removed).  It only tracked 5 branch mnemonics, had no `keep_always`
  runtime-label guard, and no data-label detection.  It was also dead code —
  never imported or called anywhere.
- **Rewrote** `jump_threading.py` with a module docstring explaining the pass,
  each transformation rule, and how to call it from the pipeline.
- **Rewrote** `label_cleanup.py` with a module docstring explaining the two-pass
  algorithm, what `keep_always` covers, and how to call it from the pipeline.
  Extended `keep_always` to include `LSHIFT32`, `RSHIFT32`, `COPY_BYTES`,
  `COPY_BYTES16` (already in the codegen but not guarded).
- **Wired both passes into the pipeline** (`compiler_pipeline.py`) after the
  optional peephole optimizer and before `_format_assembly`:
  ```
  cg.code = jump_threading(cg.code)
  cg.code = cleanup_labels(cg.code)
  cg.code = _format_assembly(cg.code, …)
  ```
  Previously both modules were dead code (never called).  Now the pipeline
  matches the architecture documented in `DOC/ARCHITECTURE.md`.

**Tests**: all 229 tests (157 pass + 72 fail) pass. No regressions.

---

## Refactor: sema_proc / sema_func shared helpers (2026-03-10)

### What was done

Introduced `sema_shared.py` — a new module that centralises the semantic
analysis helpers duplicated between `ProcAnalyzer` (sema_proc.py) and
`FuncAnalyzer` (sema_func.py).

**Problem**: Both analyzer classes contained near-identical implementations of
~11 helpers and the large `validate_stmt_exprs` body validator, resulting in
~600 lines of duplicated logic. Bug fixes in one copy were at risk of not being
applied to the other.

**Solution**:
- New file `sema_shared.py` (~310 lines) with all shared module-level functions:
  - `map_debug_line` / `attach_source_text` — debug line mapping and error annotation
  - `map_stmt_info` — source-location lookup for a statement node
  - `is_considered_initialized` — pure predicate for "safe to read without assignment"
  - `get_base_ident` — extract root identifier from an LHS expression chain
  - `check_uninitialized` — walk an expression and raise on first uninit local read
  - `mark_initialized_from_lhs` — record assignment target as initialized
  - `check_port_write` — raise on write to a read-only port variable
  - `build_local_symtab` — create SymbolTable and register all parameters
  - `build_init_set` — build the initial "known-initialized" upper-case name set
  - `validate_body_exprs` — unified statement-list type-checker with init tracking
- `validate_body_exprs` accepts two optional callbacks for routine-specific logic:
  - `on_call_stmt(stmt, initialized)` — proc supplies argument uninit validation;
    func passes None
  - `on_return_stmt(stmt, initialized)` — proc supplies basic expression check;
    func passes None (top-level returns validated separately for full type checking)
- `_map_debug_line` and `_attach_source_text` in both Analyzer classes are now
  one-line delegations to `sema_shared`.
- All per-statement nested helper functions (`_map_stmt_info`, `_is_considered_initialized`,
  `_check_uninitialized`, `_mark_initialized_from_lhs`, `_get_base_ident`) removed
  from both analyzer methods.

**Files changed**:
- `sema_shared.py` — new, ~310 lines
- `sema_proc.py` — reduced from ~737 to ~210 lines (−527 lines)
- `sema_func.py` — reduced from ~565 to ~215 lines (−350 lines)
- Net: ~570 lines removed, ~310 added → **−260 lines overall**

**Tests**: all 229 tests (157 pass + 72 fail) pass. No regressions.

---

## Refactor: unified AST walker (2026-03-10)

### What was done

Introduced `ast_walker.py` — a new module that centralises all recursive AST
traversal logic for the compiler pipeline.

**Problem**: `compiler_pipeline.py` contained 11 near-identical functions
across 4 families, each re-implementing the same recursive dispatch over the
same AST node types (BinaryExpr, UnaryExpr, IfStmt, ForStmt, SwitchStmt, …).
Adding a new AST node type previously required updating all 11 functions.

**Solution**:
- New file `ast_walker.py` with three generic walkers:
  - `walk_expr(expr, *, on_identifier, on_call_expr)`
  - `walk_stmt(stmt, *, on_call_stmt, on_identifier, on_call_expr)`
  - `walk_initializer(init, *, on_identifier, on_call_expr)`
- Each walker accepts optional callbacks for semantically-interesting nodes
  (Identifier, CallExpr, CallStmt); structural recursion is handled once.
- The 11 functions in `compiler_pipeline.py` are now thin wrappers that define
  the relevant callbacks and delegate traversal to `ast_walker`.
- Added `_BUILTIN_CALLS` module-level constant (previously inlined as a literal
  set in three places: `{"LOW", "HIGH", "SIZEOF", "LOWW", "HIGHW"}`).
- Added `_make_global_callbacks()` helper to share the Identifier and CallExpr
  callback closures across the three Family-1 wrappers.

**Files changed**:
- `ast_walker.py` — new, ~170 lines (traversal logic + docstrings)
- `compiler_pipeline.py` — removed ~490 lines of duplicated traversal, added
  ~100 lines of thin wrappers and helpers; net ~−390 lines

**Tests**: all 229 tests (157 pass + 72 fail) pass. No regressions.

---

## Slot allocator: interference graph precision fixes (2026-03-10)

### What was done

Fixed two bugs in `compiler_pipeline.py:share_locals_liveness()` that caused excessive false interference edges in the graph coloring, leading to over-allocation of memory slots for local variables and parameters.

**Bug 1 — `sym_size()` checked `is_struct` before `is_pointer`** (line 1072):
- For pointer-to-struct types (e.g. `FILE^`), `sym_size()` was returning `struct_info.size` instead of `type.width` (pointer size)
- Fix: added `if sym.type.is_pointer: return sym.type.width` before the `is_struct` check

**Bug 2 — `call_live_across` incorrectly included call arguments** (line 776):
- In `_liveness_block()`, for `AssignStmt` with a call in the RHS (e.g. `rv = CIO(filename, 0, mode)`), the argument variables (`filename`, `mode`, etc.) were added to `call_live_across` via `uses_rhs`
- Arguments are consumed at the call point — they are NOT live inside the callee — so this created false interference between caller argument variables and all callee locals
- Fix: changed `update(live | uses_rhs | uses_lhs)` to `update(live | uses_lhs)` — argument variables dropped, LHS addressing variables retained

**Bug 3 — same issue in `_liveness_inits()`** (line 1035):
- Initializer argument variables were included in `call_live_across` via `uses`
- Fix: changed `update(live | uses)` to `update(live)`

### Impact on test_stdio.zap

| Metric | Before | After |
|--------|--------|-------|
| User variable slots (count) | 26 | 17 |
| User variable slots (bytes, ZP) | 36 | 22 |
| User variable slots (bytes, BSS) | 6 | 4 |
| **Total user slot bytes** | **42** | **26** |
| Theoretical minimum | — | 20 bytes |

Notable improvements: FOPEN.FILENAME + FWRITE.BUFFER + MEMCPY.PTR1 + MEMSET.PTR collapsed into one 2-byte slot. Five byte-class variables now share slot 5, five more share slot 6.

**Tests**: all 229 tests (157 pass + 72 fail) still pass. No regressions.

---

## Math slot conditional allocation (2026-03-10)

### What was done

Extended the TMP-slot conditional-emission pattern to cover `MATH_STACK`, `MATH0`, and `MATH1`. Previously these three slots were **always** emitted in ZP regardless of whether the program used WORD/LONG arithmetic. Now they are only allocated when actually referenced in the generated code.

**Changes in `codegen_expr.py`**:
- `_detect_temp_usage()`: added `MATH_STACK`, `MATH0`, `MATH1` to the code scan set, and added flag-based prediction `if math_routines_needed: add MATH0+MATH1` (needed because math library routines are emitted by `gen_file_footer()` *after* the scan runs)
- `emit_memory_map()` (both `gen_vars_block` and `gen_vars` copies): added `if internal_name not in temps_in_use: continue` guard for MATH slots, mirroring the existing TMP guard
- Slot-sizing loop: extended single TMP condition to cover all system temps uniformly

**Changes in `compiler_pipeline.py`**:
- Fixed wrong sizes in `system_temps` list: `MATH_STACK` 8 → 32, `MATH1` 2 → 4 (the interference graph now uses the correct size classes)

### Impact on test_stdio.zap (BYTE-only program, no WORD/LONG arithmetic)

| Metric | Before | After |
|--------|--------|-------|
| MATH_STACK (ZP) | 32 bytes | 0 (removed) |
| MATH0 (ZP) | 4 bytes | 0 (removed) |
| MATH1 (ZP) | 4 bytes | 0 (removed) |
| **Total MATH bytes saved** | **40 bytes** | — |
| Total ZP (proc/func + TMP + MATH) | ~74 bytes | 32 bytes |

Programs that use WORD/LONG arithmetic are unaffected — MATH slots are still emitted when needed.

**Side effect**: `200-ops-byte.ref` updated (ZP layout shifted 32 bytes due to MATH_STACK removal; program output at `0x9C40` unchanged).

**Tests**: all 229 tests (157 pass + 72 fail) pass. No regressions.

---

## GAP-22: NULL pointer checks — WORD/pointer comparison (2026-03-04)

### What was done

Fixed type checking in `sema_expr.py` to allow comparing a pointer with a WORD value (in addition to literal 0 already working).

**Root cause**: The comparison check (`_is_zero_literal`) only accepted `IntLiteral(0)`. Using `const word NULL = $0000` and then `if ptr == NULL` failed at sema because `NULL` is still an `Identifier` at sema time (constant substitution runs later in the pipeline).

**Fix** in `sema_expr.py` (BinaryExpr comparison section):
- Old rule: pointer vs non-pointer allowed only if non-pointer side is `IntLiteral` with value 0
- New rule: also allow if non-pointer side has base="WORD" (and is not a struct or pointer itself)

**Preserved behavior**: `x == "string"` (BYTE value vs string pointer) still fails with "Invalid pointer comparison" because `x` is BYTE, not WORD — the test `026-equality-error` is unaffected.

**Allowed patterns**:
- `ptr == NULL` — `const word NULL = $0000` compared to pointer ✓
- `ptr != NULL` — negated ✓
- `NULL == ptr` — reversed (WORD on left, pointer on right) ✓
- `ptr == word_var` — any WORD variable ✓
- `ptr == 0` — literal zero (existing, BYTE literal) ✓
- `ptr = NULL` — assignment already worked, no change needed ✓

**Test**: `tests/pass/165-null-ptr/` — 4 checks (non-null check, reversed null check, post-assignment null check, literal-zero null check), result=$0F, all 4 variants pass.

---

## GAP-20: LONG struct field read/write codegen (2026-03-03)

### What was done

Implemented full LONG (32-bit) struct field read/write support in `codegen_expr.py`.

**Load paths (L1-L6)** in `_gen_field_access`:
- L1: `ptr^.field` (is_deref=True) via 4-byte (TMP0),Y indirect load into MATH0
- L2: `ident.field` (Identifier base) via 4-byte direct load into MATH0
- L3: `arr[i].field` (SubscriptExpr base) via 4-byte (TMP0),Y indirect load into MATH0
- L4: nested `obj.f1.f2` (FieldAccess→Identifier) via 4-byte direct load
- L5: nested `arr[i].f1.f2` (FieldAccess→SubscriptExpr) via 4-byte indirect load
- L6: `myfunc().field` (CallExpr base) via 4-byte direct load from return buffer

**Store paths (S1-S7)** in `_gen_field_access` + `gen_assign`:
- S1: fast path in `gen_assign` — direct Identifier.field LONG store from MATH0 (returns early)
- S2: staging fix — skip TMP2 staging for LONG (MATH0 already has value)
- S3-S7: mirror of L1-L5 store directions (MATH0 → field via direct or indirect addressing)

**Additional bugs found and fixed**:
- **LONG store MATH0 overwrite**: In non-is_deref branch, SubscriptExpr and nested FieldAccess load sections were emitting LONG loads (clobbering MATH0) even during store operations. Fixed with `field_width == 4 and load_only` guard.
- **DerefExpr case missing**: `FieldAccess(is_deref=False, object=DerefExpr)` reached the error else-branch. Added `elif isinstance(expr.object, DerefExpr)` in both load and store sections.
- **LONG argument passing**: `_emit_call_args` used `STA asm; STX asm+1` for all non-1-byte args, truncating LONG to 2 bytes. Added `if width == 4:` case copying all 4 MATH0 bytes to parameter slot.

**Test**: `tests/pass/164-struct-long-field/` — 6 checks, all 4 variants (65C02, 65C02 -O1, 6502, 6502 -O1) pass with result=$06.

### What remains
- GAP-22, GAP-23, GAP-24, GAP-25 (see building_blocks.md).

---

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

---

## Optimisation: Eliminate redundant LDA in LONG constant assignment — gen_assign + gen_init (2026-02-27)

### What was done

Applied `last_a` tracking to avoid emitting duplicate `LDA #$XX` instructions when multiple
consecutive bytes of a LONG constant share the same value.

**gen_assign** (`codegen_expr.py` LONG branch of IntLiteral assign):
Replaced 4 independent `if zero → STZ / else → LDA + STA` blocks with a `for _bi in range(4)`
loop that tracks `last_a: int | None`. If `A` already holds the required byte value, the `LDA`
is omitted.

**gen_init** (`codegen_expr.py:5167` — declaration initialisation path):
Applied the identical loop pattern to the LONG initialiser block in `gen_init()`, which previously
used the same independent-block approach.

**Before** (`long my_long = 65536`, 6502 target — bytes 0x00, 0x00, 0x01, 0x00):
```asm
LDA #$00 / STA _MAIN_MY_LONG       ; byte 0
LDA #$00 / STA _MAIN_MY_LONG+1    ; byte 1 — redundant LDA
LDA #$01 / STA _MAIN_MY_LONG+2    ; byte 2
LDA #$00 / STA _MAIN_MY_LONG+3    ; byte 3 — redundant LDA
```

**After**:
```asm
LDA #$00
STA _MAIN_MY_LONG
STA _MAIN_MY_LONG+1               ; A still $00 — no reload
LDA #$01
STA _MAIN_MY_LONG+2
LDA #$00
STA _MAIN_MY_LONG+3
```

Savings depend on byte pattern; up to 3 `LDA` instructions saved per LONG constant (when all 4
bytes are equal, e.g. `long x = 0` on 6502 saves 3 loads).

On 65C02 zero bytes still use `STZ` (which does not modify A, so `last_a` is reset to `None`).

### Verification
- `make tests`: 124/124 pass-tests pass, 60/60 fail-tests correctly rejected — 0 regressions.
- `pyright codegen_expr.py`: 0 errors, 0 warnings.

---

## Optimisation: Group STAs by value for multibyte constant stores (2026-02-27)

### What was done

Replaced the sequential `last_a` tracking loop with a **grouping-by-value** approach in all three
multibyte constant-store sites. Instead of emitting bytes in offset order 0→1→2→3 (which only
saves a reload when identical values are _consecutive_), bytes are now grouped by value in
first-occurrence order. Each unique byte value gets one `LDA`, followed immediately by all `STA`s
that need that value.

**Sites changed:**
| Site | Location |
|---|---|
| `gen_init` LONG | `codegen_expr.py:5167` |
| `gen_assign` LONG | `codegen_expr.py:~9532` |
| `_emit_store_word_const` WORD | `codegen_expr.py:1680` |

**Algorithm:** build `dict[int, list[int]]` (Python insertion-ordered) mapping each unique byte
value to the list of byte offsets that hold it. Then for each group: on 65C02 emit `STZ` for
the zero group (if any), otherwise emit `LDA #$XX` + one `STA` per offset in the group.

**Before** (`long end_val = 65540` = `$00010004`, 6502):
```asm
LDA #$04 / STA +0
LDA #$00 / STA +1
LDA #$01 / STA +2
LDA #$00 / STA +3   ← redundant LDA ($00 already loaded for +1)
```

**After** (6502):
```asm
LDA #$04 / STA +0
LDA #$00 / STA +1 / STA +3   ← both $00 bytes grouped
LDA #$01 / STA +2
```

**After** (65C02):
```asm
LDA #$04 / STA +0
STZ +1 / STZ +3               ← zero group uses STZ (no LDA)
LDA #$01 / STA +2
```

Savings (6502): one `LDA` per byte value that appears more than once.
Worst case (all 4 bytes unique): no change. Best case (all equal, e.g. `long x = 0`): 3 `LDA`s
eliminated (1 LDA + 4 STA instead of 4 LDA + 4 STA). Total `LDA` count is now always exactly
equal to the number of unique byte values — strictly optimal.

This supersedes the previous `last_a` approach which only saved consecutive repeats.

### Verification
- `make tests`: 124/124 pass-tests pass, 60/60 fail-tests correctly rejected — 0 regressions.
- `pyright codegen_expr.py`: 0 errors, 0 warnings.

---

## Refactor: Unify __ARRCPY into __COPY_BYTES (2026-02-27)

### What was done

Eliminated the duplicate `__ARRCPY` runtime routine and all supporting infrastructure,
routing its two former callers to the existing `__COPY_BYTES` routine instead.

**Root cause:** Both routines performed identical forward byte copies (TMP0 → TMP2),
differing only in how the count was passed: `__ARRCPY` took count in A (saved to TMP3),
while `__COPY_BYTES` took count in X (count-down, no TMP3). With 8 call sites vs 2,
adopting the `__COPY_BYTES` calling convention for all callers is the minimal change.

**Changes in `codegen_expr.py`:**
| What | Where |
|---|---|
| Removed `arrcpy_needed` flag | `__init__` (line ~56) |
| Removed `"ARRCPY"` from runtime name-map | `_build_internal_name_map()` (line ~1516) |
| Removed `_gen_arrcpy_routine()` call | `gen_file_footer()` (line ~3107) |
| Deleted `_gen_arrcpy_routine()` | lines 3138–3178 (~40 lines deleted) |
| Converted `_gen_string_copy()` A1 | flag: `arrcpy_needed` → `copy_bytes_needed`; `LDA #count` → `LDX #count`; `JSR ARRCPY` → `JSR COPY_BYTES` |
| Converted `gen_local_var_init()` A2 | same three changes |
| Simplified `_detect_temp_usage()` | removed `or self.arrcpy_needed` |

**`DOC/ADVANCED_TOPICS.md`:** Removed `__ARRCPY` entry; updated `__COPY_BYTES` description
to include the calling convention (`TMP0=src, TMP2=dst, X=count`).

**Net effect:** ~50 lines removed from codegen_expr.py. The two formerly-ARRCPY callers now
emit `LDX #count / JSR __COPY_BYTES` instead of `LDA #count / JSR __ARRCPY`. Binary output
is functionally identical (same bytes copied); one opcode byte differs per call site
(`A2` LDX vs `A9` LDA) but is irrelevant to program semantics.

### Verification
- `pyright codegen_expr.py`: 0 errors, 0 warnings.
- `make tests`: 125/125 pass-tests pass, 60/60 fail-tests correctly rejected — 0 regressions.

---

## Cleanup: Remove `.segment` directive remnants (2026-02-27)

### What was done

The `.segment` directive was already removed from the ZAP language (only valid inside `asm...end`
blocks). However, dead code and documentation references remained.

**`ast_nodes.py`**: Removed `SegmentDirective` dataclass entirely.

**`parser.py`**:
- Removed `SegmentDirective` from `from ast_nodes import …`
- Removed `SegmentDirective |` from `parse_stmt()` return type annotation

**`compiler_pipeline.py`**:
- Merged duplicate `from ast_nodes import …` lines (removed redundant line 1)
- Removed `SegmentDirective` from the import
- Removed dead `isinstance(p, SegmentDirective)` handler in the main code-gen loop

**`codegen_expr.py`**:
- Removed `SegmentDirective` from the local import inside `gen_stmt()`
- Removed dead `isinstance(stmt, SegmentDirective)` handler

**`module_system.py`**: Updated stale comment to remove `SegmentDirective` mention.

**`DOC/grammar.ebnf`**:
- Removed `| segment_directive` from `top_level` production
- Removed `| segment_directive` from `statement` production
- Removed `segment_directive ::= ".segment" STRING ;` rule definition
- Updated notes to reflect that `.segment` is only valid inside `asm...end` blocks

**`generated_tests/debug_parse_prog_inst.py`**: Removed dead `.SEGMENT` parsing branches
that would have crashed (class no longer exists).

### Verification
- `pyright` (all modified files): 0 errors, 0 warnings.
- `make tests`: 125/125 pass-tests pass, 60/60 fail-tests correctly rejected — 0 regressions.

---

## Feature: Compound assignment operators (2026-02-27)

### What was done

Added 10 compound assignment operators as pure **parse-time syntax sugar**. `lhs op= rhs`
desugars to `lhs = lhs op rhs` inside `parse_assign()` before semantic analysis, so all
existing type-checking and optimisations apply automatically.

**Operators:** `+=  -=  *=  /=  %=  &=  |=  ^=  <<=  >>=`

**Files changed:**

| File | Change |
|---|---|
| `token_types.py` | Added `TOK_COMPOUNDASSIGN = "COMPOUNDASSIGN"` |
| `tokenizer.py` | Added `COMPOUND_ASSIGN_TWO` / `COMPOUND_ASSIGN_THREE` dicts; recognition inserted before the two-char ops check (three-char `<<=`/`>>=` checked first) |
| `parser.py` | `parse_assign()` desugars `TOK_COMPOUNDASSIGN` → `AssignStmt(lhs, BinaryExpr(lhs, op, rhs))` |
| `DOC/grammar.ebnf` | Added `compound_op` production; updated `assignment` rule |
| `DOC/ZAP_LANGUAGE_REFERENCE.md` | Added "Compound Assignment Operators" section |
| `tests/pass/140-compound-assign/` | New 20-check test covering all 10 operators on BYTE/WORD/LONG scalars, array subscript, and pointer lvalue |

**Bug fixed during test development:**

`codegen_expr.py` O1 peephole optimizer at line ~2282: the redundant-LDX elimination pass
checked for arithmetic ops clobbering `A` only (`if load_op == "LDA"`), but neglected the
case where a memory-modifying instruction like `ROL __TMP0+1` modified the tracked memory
address between a `STX __TMP0+1` and a subsequent `LDX __TMP0+1`. Added a call to the
existing `_modifies_memory_operand()` helper to invalidate the elimination in that case.
This manifested as `w <<= 1` (16-bit left shift) storing the wrong high byte under `-O1`.

### Verification
- `pyright token_types.py tokenizer.py parser.py codegen_expr.py`: 0 errors, 0 warnings.
- `make tests`: 126/126 pass-tests pass, 60/60 fail-tests correctly rejected — 0 regressions.

---

## Optimisation: In-place shift codegen for BYTE/WORD/LONG (2026-02-28)

### What was done

Added a new handler in `gen_assign()` (`codegen_expr.py` ~line 9721) that detects
`var = var << N` / `var = var >> N` (constant-count compound shifts on a simple identifier
lvalue) and emits read-modify-write memory instructions directly, avoiding the previous
copy-through-TMP0/MATH0 path.

Also fixed the existing `BinOp.MUL`/`BinOp.DIV` power-of-2 WORD handler to use the same
direct-memory approach (previously went through `_gen_lshift(True, "A", N)` → TMP0).

**BYTE N=1:**
```
; before:  LDA _B; ASL; STA _B  (3 instructions)
; after:   ASL _B                (1 instruction)
```
BYTE N>1: unchanged (accumulator path `LDA; N×ASL; STA` is still optimal because A holds
the result and enables O1 comparison-LDA elimination).

**WORD `<<= N` / `>>= N`:**
```
; before:  LDA; LDX; STA TMP0; STX TMP0+1; N×(ASL TMP0; ROL TMP0+1); LDA; LDX; STA; STX  (12+ instr)
; after:   N × (ASL addr; ROL addr+1)   e.g. 2 instructions for N=1
```

**LONG `<<= N` / `>>= N`, N ≤ 4:**
```
; before:  MATH1 setup (5 instr) + MATH0 load (8) + JSR + writeback (8) = 23 instructions
; after:   N × (ASL addr; ROL addr+1; ROL addr+2; ROL addr+3) = 4 instructions for N=1
```

**LONG `<<= N` / `>>= N`, N ≥ 5:** MATH0 load + JSR + writeback = 17 instructions
(saves the 5-instruction MATH1 setup that the old path required).

**MUL/DIV WORD fix** (`w *= 2`, `w /= 2`): same improvement as WORD shift.

### Instruction count reductions

| Operation | Before (default) | After |
|---|---|---|
| `b <<= 1` | 3 | 1 |
| `b >>= 1` | 3 | 1 |
| `w <<= 1` | 14 | 2 |
| `w >>= 1` | 14 | 2 |
| `w *= 2` | 14 | 2 |
| `l <<= 1` | 23 | 4 |
| `l >>= 1` | 23 | 4 |
| `l <<= 5` | 23 | 17 |

### Verification
- `pyright codegen_expr.py`: 0 errors, 0 warnings.
- `make tests`: 126/126 pass-tests pass, 60/60 fail-tests correctly rejected — 0 regressions.

---

## Optimisation: In-place bitwise AND/OR/XOR codegen (2026-02-28)

### What was done

Added a handler in `gen_assign()` for `BinOp.BAND`, `BinOp.BOR`, `BinOp.BXOR` (directly
after the LSHIFT/RSHIFT handler). Covers `var &= expr`, `var |= expr`, `var ^= expr` where
the lvalue is a simple identifier.

**Why this matters:** The old generic RPN path generated ~15 instructions for `w &= $00FF`
(load MATH0, load MATH1, apply BAND16, spill MATH0, store to var). The new handler emits
`LDA addr; AND/ORA/EOR #byte; STA addr` per byte — at most 3 instructions per byte.

**Smart constant handling:**
- Identity bytes are silently skipped: `AND #$FF`, `OR #$00`, `EOR #$00` leave the byte
  unchanged — no instructions emitted for that byte at all.
- AND #$00 clears the byte → emits `STZ addr` (65C02) or `LDA #$00; STA addr` (6502).

**Variable RHS** (`w &= other_word`): handled when RHS is a simple identifier (non-array,
non-port) — emits `LDA lhs_byte; AND/ORA/EOR rhs_byte; STA lhs_byte` per byte.

**Scope:** BYTE, WORD, and LONG for both constant and identifier RHS. Commutative property
is exploited: both `var op= expr` and `var = expr op var` forms are handled.

### Before vs after (`w &= $00FF` on 65C02)

**Before:** 15 instructions (LDA _W; LDX _W+1; AND #$FF; TAY; TXA; AND #$00; TAX; TYA;
STA MATH0; STX MATH0+1; LDA MATH0; LDX MATH0+1; STA _W; STX _W+1; …)

**After:**
```asm
STZ _MAIN_W+1   ; AND #$FF (identity) skipped; AND #$00 → STZ
```
1 instruction total.

**Other examples:**
| Expression | Before | After |
|---|---|---|
| `w &= $00FF` (65C02) | 15 instr | 1 instr |
| `w \|= $0300` | 15 instr | 3 instr |
| `w ^= $FFFF` | 15 instr | 6 instr |
| `l &= $FFFFFF00` (65C02) | ~23 instr | 4 instr |

### Verification
- `pyright codegen_expr.py`: 0 errors, 0 warnings.
- `make tests`: 126/126 pass-tests pass, 60/60 fail-tests correctly rejected — 0 regressions.
