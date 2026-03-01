# ZAP! Building Blocks — Gap Tracking Checklist
# Created: 2026-03-01
# Purpose: Track completeness/correctness of every ZAP language building block.
# Update status as gaps are investigated and resolved.
#
# Status values: [ ] open  [~] in progress  [x] resolved

## Known Gaps / Items to Verify

- [x] GAP-01: FOR loop terminator — `grammar.ebnf` says `next <ident>`; actual parser uses `end`; `KEYWORDS` does not contain `next`. Fix grammar.ebnf.

- [x] GAP-02: `port` as TYPEMOD keyword — grammar lists `port` as a type modifier but tokenizer `TYPEMOD` set only has `{"const", "static"}`. Ports use `#PORT #RD #WR` declaration modifiers. Fix grammar.ebnf.

- [x] GAP-03: Arrays of structs — verify completeness: field access (`arr[i].field`), multi-dim indexing, list-init, runtime copy (`dst = src`). Flagged open in `todo.md`.
  - Covered by test `146-struct-array` (all 4 variants pass).
  - Constant-index and variable-index field read/write: ✓
  - List-init with nested braces `{{1,2},{3,4}}`: ✓
  - For-loop iteration over struct array: ✓
  - Multi-dim `arr[i].array_field[j]` (const and var index): ✓
  - Runtime copy `dst = src` for struct arrays: NOT supported (compiler raises error; use a loop instead).

- [x] GAP-04: Arrays inside struct fields — verify: declaration, initialization, access (`s.arr[i]`), copy. Flagged open in `todo.md`.
  - Covered by test `147-struct-array-field` (all 4 variants pass).
  - Declaration `byte data[4]` / `word vals[3]` inside struct: ✓
  - List-init with nested braces `{{1,2,3,4}}` (outer = struct, inner = array field): ✓
  - Constant-index and variable-index access for byte and word array fields: ✓
  - For-loop over array field: ✓
  - Struct copy (`dst = src`) correctly copies array field contents: ✓

- [x] GAP-05: Expression evaluation consistency — verify that the same expression produces identical code when used in: assignment RHS, proc/func call arg, if/while condition, for bounds, switch expr, return expr. Flagged open in `todo.md`.
  - Covered by test `148-expr-context` (all 4 variants pass).
  - Expressions `val+5` and `val*2-2` (both = 12, val=7) verified in all contexts: ✓
  - Assignment RHS, if condition, while condition, for upper bound,
    for start+end bounds, func call arg, return expr, switch expr: all correct.

- [x] GAP-06: Uninitialized variable behavior — verify error or defined behavior for all types (byte, word, long, pointer, array, struct) when declared without an initializer in all contexts (global, local, static). Flagged open in `todo.md`.
  - **Local scalars (byte/word/long/pointer)**: REJECTED at sema — `sema_proc.py` / `sema_func.py` definite-assignment analysis raises "Use of uninitialized variable". Covered by fail tests `uninit-byte-local`, `uninit-word-local`, `uninit-long-local`, `uninit-pointer-local`.
  - **Static local**: REJECTED — "STATIC variable must have an initializer" (`sema.py`).
  - **Local arrays**: Allowed (sema skips array base in definite-assignment check). Zero on first call (BSS).
  - **Local structs**: Allowed (sema always considers structs initialized). Zero on first call (BSS).
  - **Global (all types)**: Allowed. `.res N` in BSS — linker zeroes at program startup.
  - All verified by pass test `149-uninit-vars` (12 checks, all 4 variants pass).

- [x] GAP-07: SWITCH with no `default` clause — verify compiles and runs correctly (falls through to end with no match). No negative test exists.
  - Covered by pass test `150-switch-no-default` (all 4 variants pass).
  - Verified: byte/word/long switch with no default; matching case runs; non-matching skips entire body and continues; stacked cases (no match → skip); fall-through without default (no match → cnt=0).
  - `ZAP_LANGUAGE_REFERENCE.md` already stated `default` is optional; added no-default example.
  - Additional: switch variable mutation behavior (pass test `151-switch-var-mutation`):
    - Dispatch table is evaluated **once** before any case body runs (fast path reads variable address directly).
    - Modifying switch var inside case 1 with `break` → case 2 NOT executed (dispatch already chose case 1).
    - Modifying switch var inside case 1 without `break` → case 2 IS reached by fall-through (sequential code, not re-dispatch).
    - Modified value is retained after switch ends.
    - Documented in `ZAP_LANGUAGE_REFERENCE.md` under Key Feature 6 and new examples.

- [x] GAP-08: FOR loop — all data types, step variants, expression bounds, pointer loop var, deref end bound.
    - Verified: BYTE/WORD/LONG loop vars; step from literal >1, step from variable; bounds crossing BYTE/WORD boundaries; bounds from compound expressions; pointer as loop variable iterating over array; dereferenced pointer as end bound.
    - Pass test: `152-for-loop-types` (12 checks, expected result $0C). All 4 variants pass.
    - Compiler bug fixed: `_predeclare_for_loop_temps` in `compiler_pipeline.py` now mirrors codegen: FOR_END temp only when end is not an Identifier; FOR_STEP temp only when step is neither IntLiteral nor Identifier. Previously always created both → counter mismatch with codegen → wrong type for predeclared temps → slot aliasing conflicts and LONG=BYTE assignment bug.

- [x] GAP-09: Multi-dim array >= 256 bytes total — COPY_BYTES16 path. Covered by `141`, `142`, `143`. Verify for arrays-of-structs and word arrays at boundary sizes (255, 256, 257 bytes).
    - Verified: byte[255]=COPY_BYTES max, byte[257]=COPY_BYTES16; word[127]=254B COPY_BYTES, word[129]=258B COPY_BYTES16; Pair[127]=254B struct COPY_BYTES, Pair[128]=256B struct COPY_BYTES16 exact boundary, Pair[129]=258B struct COPY_BYTES16.
    - Pass test: `153-array-init-boundary` (14 checks, expected result $0E). All 4 variants pass.
    - LONG array index: any integer type accepted as subscript; only low bytes used for address calculation; no warning (by design). Documented in `DOC/ZAP_LANGUAGE_REFERENCE.md`.

- [ ] GAP-10: Struct-returning function + assignment to struct field chain — e.g. `s.field = myfunc().field`. Needs explicit test.

- [ ] GAP-11: REPEAT/UNTIL with BREAK and CONTINUE — partially tested in `117`. Verify break exits repeat, continue goes to until-condition, and nesting with for/while works correctly.

- [ ] GAP-12: CONTINUE inside SWITCH — should skip to next iteration of the *enclosing loop*, not affect the switch. No explicit test.

- [ ] GAP-13: Const struct passed directly as function argument `fn({1, 2})` — marked done in `todo.md`. Verify with a dedicated test if not already covered.

- [ ] GAP-14: PORT struct with all field access patterns — `#PORT` struct, `#RD`-only field read, `#WR`-only field write, mixed `#RD #WR`, field without modifier inheriting struct-level defaults. Some tests exist; verify completeness.

- [ ] GAP-15: `SIZEOF()` on pointer-to-struct vs the struct itself — e.g. `SIZEOF(MyStruct)` vs `SIZEOF(ptr_to_struct)`. Verify correct size returned in both cases.

- [ ] GAP-16: `LOW()` / `HIGH()` edge cases — verify on: struct field (`LOW(s.field)`), array element (`HIGH(arr[i])`), deref expression (`LOW(ptr^)`), long variable (should return low/high of full 4-byte value?). Codegen handles identifiers and IntLiteral; complex args use `gen_expr()` fallback.

- [ ] GAP-17: Auto short branches — JMP → BXX where branch target is within ±127 bytes. Not implemented. Open todo item; deferred.

---

## Documentation Bugs (fix in grammar.ebnf / DOC/)

- [x] DOC-01: `grammar.ebnf` FOR loop: replace `"next" IDENT` with `"end"`.
- [x] DOC-02: `grammar.ebnf` type_modifier: remove `"port"` from the production (ports use `#PORT` declmod).
- [ ] DOC-03: `grammar.ebnf` NOTES: add two-char character literal form `'a''b'` → WORD.
- [ ] DOC-04: `grammar.ebnf` NOTES: add block comment syntax `/* ... */`.
- [ ] DOC-05: `grammar.ebnf`: add `LOW`, `HIGH`, `SIZEOF` to primary expression as built-in calls.

---

## Building Block Coverage Matrix
(Quick reference — mark [x] when a dedicated test or code path is confirmed working)

### Literals
- [x] Decimal integer
- [x] Hex $xx / 0xXX
- [x] Binary %... / 0b...
- [x] Character literal 'x'
- [ ] Two-char word literal 'a''b' — no dedicated test found
- [x] String literal "..."
- [x] String escapes \n \t \r \0 \\ \" etc.
- [ ] String escape \xHH — verify
- [ ] String escape \OOO (octal) — verify
- [ ] String escape \bBBBBBBBB (binary) — verify

### Types & Declarations
- [x] byte / word / long scalar
- [x] pointer types (byte^ etc.)
- [x] const modifier
- [x] static modifier
- [x] port (#PORT #RD #WR)
- [x] @address specifier
- [x] 1D array with explicit size
- [x] 1D array with inferred size []
- [x] 2D array
- [x] 3D array
- [x] struct definition
- [x] enum definition (byte base)
- [x] enum definition (word base)
- [x] multiple declarators on one line (e.g. `byte a, b, c`)

### Initializers
- [x] scalar expr init
- [x] string init (byte[] only)
- [x] list init {e, e, e}
- [x] nested list init {{...},{...}}
- [x] trailing comma in list
- [x] large array init (> 255 bytes, COPY_BYTES16)
- [ ] struct list init with nested struct field

### Expressions & Operators
- [x] All arithmetic operators + - * / %
- [x] All comparison operators == != < > <= >=
- [x] All bitwise operators & | ^ ~ << >>
- [x] Logical operators && || !
- [x] Address-of @
- [x] Pointer dereference ^
- [x] Array subscript []
- [x] Struct field access .
- [x] Deref + field ^.
- [x] Function call in expression
- [x] Struct literal in expression {…}
- [x] Compound assignment all 10 operators
- [x] Operator precedence
- [x] Type promotion BYTE→WORD→LONG
- [x] Pointer arithmetic ptr+int, ptr-int, ptr-ptr
- [x] LOW() HIGH() on simple identifier
- [x] SIZEOF() on struct name
- [ ] LOW() HIGH() on complex expression
- [ ] SIZEOF() on struct instance (not name)
- [ ] Two-char char literal 'a''b'

### Statements
- [x] assignment
- [x] compound assignment
- [x] procedure call
- [x] if / elseif / else / end
- [x] while / end
- [x] repeat / until
- [x] for / end (byte var)
- [x] for / end (word var)
- [x] for / end (long var)
- [x] for with step
- [x] switch / case / default / end
- [ ] switch with no default
- [x] break (in while)
- [x] break (in for)
- [ ] break (in repeat)
- [ ] break (in switch)
- [x] continue (in for)
- [x] continue (in while)
- [ ] continue (in repeat)
- [ ] continue (inside switch — should affect enclosing loop)
- [x] return (in proc, no expr)
- [x] return (in func, with expr)
- [x] asm...end inline assembly
- [x] .error .warning .info directives

### Procedures & Functions
- [x] proc with no params
- [x] proc with params
- [x] proc with default params
- [x] func returning byte
- [x] func returning word
- [x] func returning long
- [x] func returning pointer
- [x] func returning struct
- [x] array param (type name[])
- [x] const param
- [ ] skipped default arg in call proc(1,,3)
- [x] #KEEP #NOEXPORT #EXPORT on proc/func

### Structs
- [x] struct scalar fields
- [x] struct pointer fields
- [x] struct array fields
- [x] struct with @address on field
- [x] struct with #PORT #RD #WR
- [x] const struct
- [x] struct assignment (copy)
- [x] struct-returning function
- [x] array of structs — init (list-init), access (const+var index, multi-dim); copy via loop only (dst=src not supported)
- [x] struct with array field — init (nested braces), access (const+var index, byte+word), copy

### Enums
- [x] enum byte (auto-increment)
- [x] enum word
- [x] enum with explicit values
- [x] qualified access EnumName.Member
- [x] unqualified access MEMBER
- [x] enum used in arithmetic
- [x] enum used in comparison
- [x] enum used in switch/case

### Module System
- [x] .module declaration
- [x] .include
- [x] symbol export/noexport
- [x] module constructors (#KEEP #NOEXPORT proc)
- [x] struct/enum propagation across modules

### Preprocessor
- [x] .define
- [x] .ifdef / .ifndef / .else / .endif
- [x] .include / .incbin
- [x] .error / .warning / .info
- [ ] .undef — verify behavior
