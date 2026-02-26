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
- Check for user confirmation on the final state of the repository.

## Known issues
- None.
