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
| codegen_expr.py | Code generator (~13,000 lines); RPN, peephole opts |
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
- tests/pass/ — 176 positive tests (numbered 001–210, with some gaps)
- tests/fail/ — 139 negative tests (error detection)
- Each positive test: 4 variants (65C02, 65C02+O1, 6502, 6502+O1)
- Verification: ZAP → ca65 → ld65 → 6502 simulator → memory dump vs .ref file
- generated_tests/ — ~50 Python unit tests for focused feature testing
- `.ref` files must have exactly ONE trailing newline (two newlines → OUTPUT_MISMATCH)
- Fail tests: `.ref` is documentation-only (runner checks exit code, not output)
- Tests 209-210: use fixed absolute address 0x4200 for dump (stable across optimization variants)

## VS Code profile gotcha — check profile before debugging syntax highlighting
- If `#asm`/keywords look wrong, verify the user is on their personal VS Code profile (not default)
- Opening a different folder can silently switch to the default profile which uses a different colour scheme

## label_cleanup bug fix (2026-06-07): module proc/func labels were dropped
- `label_cleanup.py` now only removes `__ZAP_*` internal labels; all other labels kept unconditionally
- Root cause: old pass removed any unreferenced label; `.word _NMI_HANDLER` vector refs were invisible to it
- All 176 pass tests still pass

## `#asm` proc/func infrastructure fix (2026-06-06)
- `#asm` now works on both `proc` AND `func` declarations
- Compiler emits param name equates (`_NAME$PARAM = slot`) BEFORE the raw body so assembly can reference them
- `sema_func.py`: suppressed "FUNC must have RETURN" check when `pure_asm=True`
- `codegen_expr.py`: `_emit_pure_asm_body()` helper shared by both gen_proc and gen_func
- `zap-ca65.injection.json`: second injection pattern for `proc/func #asm` body highlighting in VS Code
- Tests 209 (proc params) and 210 (func) added; use fixed address 0x4200 for stable cross-variant output

## LONG Datatype Gap Fixes + Subscript Speed-Up (2026-03-16)
- **Phase 1** (`_gen_subscript`): element_size=2 + constant base label: uses `ASL A / TAX / LDA #$00 / ROL A / TAY / CLC / TXA / ADC #<lbl / STA TMP0 / TYA / ADC #>lbl / STA TMP0+1` — eliminates TMP3 memory ops, saves ~10 cycles per subscript.
- **Phase 2a** (`_gen_subscript` struct field element_width ~L8357): Added `elif field_info.base_type == "LONG": element_width = 4` — was falling through to `else → nested_struct.size or 2`.
- **Phase 2b** (`gen_vars_block` ZP allocation ~L6685): Added `elif sym.type.base == "LONG": element_size = 4` — was allocating 1 byte per LONG element.
- **Phase 2c** (`_gen_multidim_subscript` ~L7997): Added `element_width == 4` LONG load/store branches using `(TMP0),Y` → MATH0 pattern.
- **Phase 3** (RPNNode `width == 2` audit): No changes needed — all `== 2` checks are preceded by `> 2` guards; LONG always hits `is_32 = left_width > 2 or right_width > 2` path first.

## OPT-7/OPT-8 correctness fixes (2026-03-16)
- **OPT-8 indexed addressing** — don't track `known_a_mem` for operands ending in `,X` or `,Y` (index register changes between uses, operand string alone is not sufficient to prove same address)
- **OPT-8 loop iteration** — reset `known_a_mem = None` on conditional branches (`BNE`/`BEQ`/`BMI`/`BPL`/`BVC`/`BVS`/`BCS`/`BCC`); `known_a` (immediate) is kept since A register value is unchanged by the branch
- **OPT-7 carry flag safety** — enhanced forward scan after `CMP #$00` candidate elimination: when encountering a conditional branch (`BNE`/`BEQ`/etc.), follow the branch target label and scan first 5 instructions for carry-users (`BCS`/`BCC`); stop scan at target if carry-setter or control-flow found
- **Pylance fix**: `self._line_mapped: bool = False` added to `CompileError.__init__` in `errors.py`; attribute now recognized on all subclasses (`SemanticError`, etc.)
- **Test results**: 166 pass / 125 fail — all OK

## Recent additions (2026-03-10)
- **Shift-add index multiply** (`_gen_index_multiply(n)`): replaces repeated-addition loops for array index scaling. Power-of-2 → pure shifts; ≤3 set bits (e.g. 3,5,6,10,12) → shift-add; fallback repeated-add. Used in `_gen_subscript`, pointer arithmetic, `@array[index]`, RPN MUL evaluator. Tests: `pass/164`, `pass/165`.
- **Compile-time constant array index folding** (`_try_eval_const`): when index is a const expression, offset computed at compile time — emits `LDA #<offset` directly. Covers `_gen_subscript` (both paths), `_gen_multidim_subscript` (per-index), `@array[index]`. Test: `pass/171`.
- **Shift-add for BYTE × small constant** (RPN evaluator): `a * 3/5/6/10/12` uses `_gen_index_multiply` instead of `JSR MUL8`. Test: `pass/172`.
- **String literal high-byte fix**: `\x80`–`\xFF` in string literals now works in all contexts (was crashing with `UnicodeEncodeError` as function args). New helpers: `_str_to_bytes()` (inline path) and `_str_to_asm_directive()` (data section, readable mixed format: `"ASCII", $9B, $00`). Tokenizer rejects raw non-ASCII with proper line/col error. Tests: `pass/173`, `fail/string-raw-nonascii`.
- **Peephole rules** (2026-03-10): generalized dead `LDX #0` elimination; `LDX <mem>; [non-X]; TXA → [non-X]; LDA <mem>` rule.
- **OPT-3: Wide-window LDA #imm elimination** (`_eliminate_redundant_imm_lda`): second-pass after main peephole loop; tracks `known_a: int | None`; removes `LDA #imm` when A already holds that value across any number of A-safe instructions. Resets on control-flow, labels, and any A-modifying instruction.
- **OPT-4: Register transfer instead of immediate reload** (`_replace_imm_load_with_transfer`): third-pass; tracks `known_a/known_x/known_y: int | None`; replaces `LDA #imm` with `TXA/TYA`, `LDX #imm` with `TAX`, `LDY #imm` with `TAY` when source register already holds same value. X↔Y not optimized (no TXY/TYX on 6502/65C02 — those are 65C816). Saves 1 byte per replacement.
- **OPT-5: Transfer+store → direct store** (`_replace_transfer_sta_with_direct_store`): fourth-pass; forward: `TYA;STA*`→`STY*`, `TXA;STA*`→`STX*` (removes transfer, requires A dead after block and no bad addressing modes); reverse: `TAX;STX*`→`STA*`, `TAY;STY*`→`STA*` (always safe, A unchanged). Saves 1 instruction per group. Addressing: STY valid on zp/zp,X/abs; STX valid on zp/zp,Y/abs (no ,Y for STY, no ,X for STX, no indirect).
- **Generated label fix**: `NOCARRY_*` labels used `id(expr)` suffix (long pointer value); replaced all 7 sites with `new_label()` for short sequential numbers.
- **`SymbolTable.lookup()` fix**: raises `SemanticError("Undefined variable '...'")` instead of leaking `KeyError`. `ScopedSymbolTable` catches `SemanticError` (not `KeyError`). `constsubst.py` catches `SemanticError` and returns expr unchanged for unknown identifiers.
- **`two_bytes` arg ordering fix** (`_emit_call_args` reorder_regs path): X loaded AFTER A evaluation; A evaluation (e.g. pointer field access) clobbers X, so X must be loaded last.
- **Liveness `call_live_across` fix** (`compiler_pipeline.py`): `CallStmt` now includes argument vars (`uses`) in `call_live_across`; `AssignStmt` includes `uses_rhs`. Without this, call-argument variables that had no other uses were not marked as interfering with callee locals → slot aliasing corruption.
- **Atari CIO `ICAX1` convention**: Atari OS CIO at `$E456` checks `ICAX1` as open mode for EVERY command, not just OPEN. CIO function must only write `ICAX1/ICAX2/ICAX3` when command=OPEN; all other commands must leave them unchanged or the OS returns `$87` (RDONLY).

## Code generation optimisations
- **32-bit direct compare** (`codegen_expr.py:11831`): fast path in `_emit_relational_branch_impl` compares LONG/WORD/BYTE simple identifiers and IntLiterals byte-by-byte directly; saves 14–16 instructions vs old MATH0/MATH1 spill path. Falls back to MATH0/MATH1 for complex expressions.
- **SWITCH direct compare** (`codegen_expr.py:11192`): when switch expression is a simple scalar identifier, compare bytes directly from source variable — no temp copy or BSS allocation; saves 2/4/8 LDA/STA instructions for BYTE/WORD/LONG.
- **Dead JMP + proxy elimination** (`codegen_expr.py:11808`): `_emit_relational_branch` wrapper simplified to a single delegation call; removed always-dead `JMP lbl_true` and unnecessary `REL_FALSE_PROXY` indirection — saves 3 instructions per relational branch in all control-flow contexts.
- **Grouped STA by value for multibyte constant stores** (`codegen_expr.py:5167` gen_init, ~9532 gen_assign, 1680 `_emit_store_word_const`): bytes grouped by value in first-occurrence order using `dict[int, list[int]]`. One `LDA #$XX` per unique byte value, all its `STA`s follow immediately. 65C02 zero group uses `STZ` (no LDA). Total LDA count = number of unique byte values — strictly optimal. Supersedes sequential `last_a` approach.

## Refactoring
- **`__ARRCPY` unified into `__COPY_BYTES`** (`codegen_expr.py`): deleted `_gen_arrcpy_routine()`, `arrcpy_needed` flag, `"ARRCPY"` name-map entry; converted both former callers (`_gen_string_copy` and `gen_local_var_init` StringInit BYTE path) to `copy_bytes_needed=True` + `LDX #count` + `JSR COPY_BYTES`. Unified convention: TMP0=src, TMP2=dst, X=count (0..255), clobbers A/X/Y only (TMP3 no longer consumed).

## Array copy / struct copy bugs fixed (2026-02-28)
- **`_gen_string_copy` (array var→var copy)**: was BYTE-only, used deprecated `array_len` (0 for multi-dim), truncated count with 8-bit LDX. Fixed: use `get_total_array_size()`, 2-way split (>255→COPY_BYTES16, else COPY_BYTES).
- **`gen_assign()` array dispatch**: condition used `lhs_t.sem_type.is_pointer` which is ALWAYS True for bare array identifiers (sema returns is_pointer=True for ADDR kind). Fixed: use `lhs_sym.type.is_struct` instead (the symbol's own type).
- **`_gen_const_struct_copy` and struct-from-function return**: 8-bit LDX overflow for structs >255 bytes. Fixed: 2-way split (>255→COPY_BYTES16, else COPY_BYTES).
- **var→var struct copy (Group C)**: no handler existed; fell to scalar codegen. Added explicit COPY_BYTES/COPY_BYTES16 path.
- **struct-array assignment (Group D)**: was silently generating wrong code. Added `_raise_error` guard.
- **RETBUF (struct-returning func return buffer)**: symbols added to global_symtab BEFORE `prune_unused()`, which then removed them. Fixed: move RETBUF generation to AFTER `prune_unused()` in `compiler_pipeline.py`.
- **Bare array identifier ExprType**: `sema_expr.py:50-61` — for `sym.is_array`, always returns `is_pointer=True` in ExprType (correct for ADDR kind). All array copy code must check `sym.type.is_struct` (Symbol's own type), NOT `lhs_t.sem_type.is_struct`.

## Struct pointer fields + word-field init fix (2026-03-13)
- Pointer fields (`byte^`, `word^`, `long^`, struct pointers) are **fully supported** in struct definitions
- `DOC/ZAP_LANGUAGE_REFERENCE.md` updated: pointer types added to field list; "Pointer Fields" subsection added
- Regression test: `tests/pass/177-struct-pointer-fields` — `Target { byte val1; word wval; byte val2 }` verifies the word-field init fix; all 4 variants pass
- **Bug fixed (symbols.py)**: `StructFieldInfo.width` property compared lowercase but `base_type` is stored uppercase → returned 0 for all primitive fields; fixed with `.upper()` normalisation
- **Bug fixed (codegen_expr.py)**: struct `ListInit` codegen used `sym.type.base == "WORD"` (always False for struct types) → WORD/pointer fields only stored low byte; replaced with `_build_struct_init_layout(fields)` helper that uses actual `(offset, width)` per field; const path emits `LDA #byte / STA dest+offset` per byte (user-requested pattern); removes spurious `LDX #$00` for byte fields

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
