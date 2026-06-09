# Progress Tracker

The author of this software stands in solidarity with 🇺🇦 Ukraine. 
We believe in a world where international borders are respected and human rights are upheld. 
We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


---

## Add GLOBAL_START label before globals initialization (2026-06-09)

### Change
Added `GLOBAL_START:` label immediately after `.segment "CODE"` and before the globals
initialization block, so the reset vector can jump directly to the program entry point.

Generated output:
```
.segment "CODE"
GLOBAL_START:
; Globals initialization
; Call MAIN
    JSR _MAIN
    JMP *
```

### Files
- **`codegen_expr.py`** (`gen_globals_header`) — one-line addition: `self.emit("GLOBAL_START:")`

### Tests
All 177 pass tests compile without error.

---

## Fix: #port struct field reads dead-store eliminated (2026-06-07)

### Problem
`_elim_dead_stores` (AST-level pass) correctly skips elimination when the LHS is a PORT
variable, but did NOT check whether the RHS reads from a port variable or port struct field.

In code like:
```
tmp = ACIA.STATUS
tmp = ACIA.CONTROL
tmp = ACIA.COMMAND
tmp = ACIA.DATA
```
The first three reads were eliminated as "dead stores" because `tmp` is immediately overwritten.
However, reading a hardware port has observable side effects (clearing flags, advancing FIFOs)
that must not be suppressed.

### Root Cause
`_lhs_is_port` guarded writes to port LHS, but there was no equivalent guard for RHS port reads.
`sema.py` already propagates `is_port=True` from a `#port` struct definition to any variable of
that struct type, so the information was available — it just wasn't being checked for the RHS.

### Changes
- **`codegen_expr.py`** — Added `_expr_reads_port(expr)` helper (~30 lines) that recursively
  walks an expression tree and returns True if any node reads from a PORT variable or PORT struct
  field (via `Identifier`, `FieldAccess`, `BinaryExpr`, `UnaryExpr`, `SubscriptExpr`,
  `DerefExpr`, `CallExpr`).
- **`codegen_expr.py`** (`_elim_dead_stores`) — Added `not self._expr_reads_port(stmt.rhs)`
  guard so dead-store elimination never suppresses a port read.

### Tests
- **211-port-struct-no-dead-store**: declares a 4-field `#port` struct, reads all 4 fields
  consecutively into `tmp` (the exact bug pattern), then accumulates them independently into
  a sum. Checks that `result = $0A` ($01+$02+$03+$04). All 8 LDA instructions appear in the
  generated assembly with no "dead store eliminated" comments for the port reads.
- All 177 pass tests compile without error.

---

## Fix: module proc/func labels missing when `label_cleanup` drops them (2026-06-07)

### Problem
Procedures (and functions) defined in an included module (e.g. `vectors.zap`) were compiled
correctly by `gen_proc`, which emits their entry-point label (e.g. `_NMI_HANDLER:`). However,
the standalone `cleanup_labels` pass in `label_cleanup.py` subsequently removed those labels
because they were not the target of any JSR/JMP instruction in the generated code — interrupt
handlers are referenced only via `.word _NMI_HANDLER` in a vector table, which the old pass
did not recognise as a reference.

### Root Cause
`label_cleanup.cleanup_labels` was removing any label not reachable via JMP/JSR/Bxx or a
`#<`/`#>` immediate. This violated the stated design rule (CLAUDE.md): *"Only `__ZAP_*`
prefixed labels are compiler-generated internal labels. All other labels must be preserved by
optimization passes."* The internal `_remove_unreferenced_labels` in `codegen_expr.py` already
implemented this rule correctly (only removes `__ZAP_*`); `label_cleanup.py` did not.

### Changes
- **`label_cleanup.py`** — Rewrote `cleanup_labels` to only remove `__ZAP_*` prefixed labels
  that are unreferenced. All other labels (user proc/func entries, ASM-block labels, math
  routines, variable declarations) are kept unconditionally. ASM blocks are skipped entirely.

### Tests
- All 176 pass tests still compile without error.
- Manual verification: `vectors.zap` module procs now emit `_VECTORS:`, `_NMI_HANDLER:`,
  `_IRQ_HANDLER:`, `_RESET_HANDLER:` labels in the output.

---

## `#asm` on `proc`/`func`: emit equates before body; extend to `func` (2026-06-06)

### Problem
`proc #asm` previously had an early return that fired BEFORE parameter name equates and local
variable equates were emitted. Raw assembly in the body could not reference `_PROCNAME$PARAM`
symbols. Also, `#asm` was not supported on `func` declarations at all.

### Changes
- **`ast_nodes.py`** — Added `pure_asm: bool` and `asm_body: str` fields to `FuncDecl`
- **`parser.py`** (`parse_func`) — Added `#ASM` DECLMOD handling; consumes `TOK_ASM_BLOCK` and
  returns early with `pure_asm=True`, matching the existing `parse_proc` behaviour
- **`sema_func.py`** — Suppressed "FUNC must have RETURN" check for `pure_asm` funcs
- **`codegen_expr.py`** (`gen_proc`) — Moved pure_asm body emission to AFTER param equates and
  local equates; extracted reusable `_emit_pure_asm_body()` helper
- **`codegen_expr.py`** (`gen_func`) — Added pure_asm conditional (after equates, no RTS)
- **`compiler_pipeline.py`** — Threads `pure_asm`/`asm_body` through `FuncDecl` DCE rebuild
- **`module_system.py`** — Extended `func #asm` body-skip logic alongside existing `proc #asm`

### Tests
- **209-pure-asm-proc-params**: `proc my_poke(byte val) #asm` — verifies param equate generated
  and assembly can reference `_MY_POKE$VAL`; stores to fixed address 0x4200, ref: `4200: 42`
- **210-pure-asm-func**: `func byte add_bytes(byte a, byte b) #asm` — verifies func #asm works
  end-to-end; adds 3+4 in assembly, result stored to `result @ $4200`, ref: `4200: 07`
- All 176 pass + 139 fail tests pass.

### VS Code / IDE
- **`zap.tmLanguage.json`** — Added `proc-asm-block` as the first repository entry and first
  include in the top-level patterns array. `begin` matches any `proc`/`func` declaration line
  that contains `#asm`; `beginCaptures` applies `#keywords`, `#attributes`, `#storage-types`,
  and `#numbers` sub-patterns to the header so `proc`/`func`/`byte`/`word`/`#asm`/`#noexport`
  all remain correctly coloured; body lines get `source.ca65` embedding; `end` closes the block.
  Putting it in the base grammar (not injection) avoids injection-priority issues where the base
  grammar's `keywords` rule would win at position 0 before the injection `begin` could match.
- **`zap-ca65.injection.json`** — Kept for inline `asm...end` blocks only (unchanged behaviour).
- **`zap-language-0.9.4.vsix`** — Rebuilt with `vsce package --no-dependencies`

---

## KNOWN_LIMITATIONS: "No Struct Arithmetic" rephrased for clarity (2026-04-23)

- Expanded the one-line note into a short narrative section with rationale, an
  explicit list of blocked operators, an example contrasting what is and isn't
  allowed (scalar fields and struct pointers still work), and a workaround.
- Behavior of the compiler is unchanged; pure documentation clarification.
- Cross-check: [docs/ERROR_MESSAGES.md](docs/ERROR_MESSAGES.md) and
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) already consistent — no changes
  needed there.

---

## GitHub Pages site with ZAP! syntax highlighting (2026-04-15)

### Phase 1 — Restructure
- Renamed `DOC/` → `docs/` (via `git mv`, preserves history)
- Updated references in: `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/feature_request.md`, `IDE_Integration/dushino.zap-language/README.md`, `lib/README.md`, `CLAUDE.md`
- Historical log entries in `PROGRESS.md` and `memory/MEMORY.md` intentionally left as-is

### Phase 2 — Jekyll scaffold
- `docs/_config.yml` — `just-the-docs` remote theme, kramdown with highlighter disabled (so Prism handles all highlighting), search enabled, "Edit on GitHub" link
- `docs/index.md` — landing page adapted from README with quickstart and nav buttons
- `docs/Gemfile` — pins `github-pages` gem so local preview matches GitHub's build
- Front matter added to all 8 doc files with `nav_order` for sidebar ordering
- `docs/PROGRESS.md` (stale 176-line duplicate from old `DOC/`) excluded from Jekyll build via `_config.yml` — flagged for removal separately

### Phase 3 — Prism.js integration
- `docs/_includes/head_custom.html` — loads Prism 1.29.0 from cdnjs with SRI hashes, imports bash/python/json/yaml/makefile/batch built-in languages, loads custom ZAP! language, triggers `highlightAll()` on DOMContentLoaded
- Style tweaks for code blocks (border-radius, font, color accents for ZAP!-specific tokens)

### Phase 4 — Custom ZAP! language for Prism
- `docs/assets/prism/prism-zap.js` — ~100 lines of JavaScript
- Ports all patterns from `IDE_Integration/dushino.zap-language/syntaxes/zap.tmLanguage.json`
- Covers: comments (block + line), strings with escapes, preprocessor directives, attribute modifiers, types (`byte`/`word`/`long`), storage (`const`/`static`), control-flow keywords, numbers (hex/binary/decimal/char literal), function calls, `@` address operator, operators, punctuation
- Case-insensitive patterns (ZAP! is case-insensitive for identifiers)

### Phase 6 — README polish
- Added "Docs" badge linking to `dushino.github.io/ZAP-compiler/`
- Added "Browse online" callout above the doc file list

### Next (user action)
- Push changes to GitHub
- Repo Settings → Pages → Source: Deploy from a branch → `main` / `/docs` → Save
- Wait ~1 min for first build, then visit the Pages URL to verify

### Flagged for approval (destructive)
- `docs/PROGRESS.md` — stale 176-line duplicate of the root `PROGRESS.md`. Should be deleted with `git rm docs/PROGRESS.md` once confirmed it's not referenced anywhere important.

---

## Public release preparation (2026-04-14)

### Project files added
- `CONTRIBUTING.md` — bug report / feature request / PR rules
- `CODE_OF_CONDUCT.md` — short, project-specific community standards
- `SECURITY.md` — vulnerability reporting policy and scope
- `CHANGELOG.md` — Keep a Changelog format, populated from project history

### .github/ infrastructure
- Issue templates: `bug_report.md`, `feature_request.md`, `config.yml` (links blank issues to Discussions)
- Pull request template with test/docs checklist
- CI workflow `.github/workflows/test.yml`: runs `make tests` on Ubuntu with cc65, plus Python compileall lint

### Personal path cleanup
- `make_dist.bat` / `make_dist.sh` now use `ZAPC_INSTALL_DIR` env var (default `~/local/bin` / `%USERPROFILE%\local\bin`)
- `work/go.bat` / `benchmarks/go.bat` now use `ALTIRRA` env var
- `.gitignore` extended: `.venv/`, `venv/`, `*.spec`, `generated_tests/*.s`, `work/*.s`, `benchmarks/*.s`, `Internal_DOC/`

### Version sync
- IDE extension `package.json` version aligned to compiler `0.9.4` (was `1.0.0`)

### README rewrite
- Added badges (license, version, CI, PRs welcome)
- Added Quickstart with Hello World example
- Added direct install instructions (binary + source build)
- Linked CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CHANGELOG
- Linked all DOC/ files

### Documentation
- Added "Building the Compiler from Source" section to `DOC/GETTING_STARTED.md`
- Documents `make_dist.sh` / `make_dist.bat` scripts and PyInstaller requirement
- Fixed stray unclosed code block in "Setting Up ZAP!" section

### Flagged for user approval (destructive ops)
- 226 already-tracked generated `.s` files in `generated_tests/`, `work/`, `benchmarks/` contain personal paths in source comments — need `git rm --cached` to untrack
- `_backup/amber/` contains 3 unused icon backup files — candidate for removal
- `Internal_DOC/` (todo.md, building_blocks.md, prompts.md) tracked but now gitignored — needs `git rm --cached -r` to untrack

---

## Standard library redesign: ERRNO, CIO, print functions (2026-04-02)

### ERRNO enum — Atari CIO status codes
- Replaced POSIX-based ERRNO enum (76 entries) with native Atari CIO status byte values (28 entries)
- `ERRNO.OK = 0` (API level), `ERRNO.SUCCESS = 1` (raw CIO), errors at $80-$FF
- All atari_stdio.zap references updated to new names (e.g., `EBADF` -> `NOT_OPEN`, `ENODEV` -> `NONEXISTENT_DEV`)

### CIO function redesign
- Removed special-case return semantics for single-byte GetChr (was returning char in A, now always returns status)
- Status read from Y register (`sty _CIO_RV`) instead of `IOCB[ch].ICSTA` (ICSTA was unreliable)
- Bit 7 check for success/error: `(rv & $80) == 0` -> `ERRNO.OK` (CIO returns various success codes like $01, $03)
- `cio_char` module-level byte stores accumulator value after CIO call

### File I/O fixes
- `fgetc`: uses `@cio_char` as 1-byte buffer (accumulator unreliable on EOF); returns char for both OK and EOF status
- `fputc`: implemented — stores char in `cio_char`, passes `@cio_char` with len=1 to CIO PutChr
- `fputs`: implemented — passes string pointer and `strlen(str)` to CIO PutChr
- EOF only checked on read operations (fread, fgetc), not writes — matches POSIX semantics
- `checkeof` removed from `fwrite`

### BCD decimal print engine (shared)
- Unified `printb`/`printw`/`printl` via shared 6502 BCD double-dabble algorithm (`SED` mode)
- `print_convert()`: 32-iteration ASM loop converts 32-bit binary to 10 packed BCD digits (~960 cycles fixed)
- `print_decimal()`: shared output with leading-zero suppression and right-alignment
- `printb(byte, lzero, ralign)`: 3-digit decimal (rewritten from repeated-subtraction)
- `printw(word, lzero, ralign)`: 5-digit decimal (new)
- `printl(long, lzero, ralign)`: 10-digit decimal (new)
- `putxw(word)`: 4-digit hex via `HIGH()`/`LOW()` + `putx()` (new)

### Documentation
- STDLIB.md: ERRNO table, File I/O section, CIO internals, KEY enum, print functions all updated
- atari_stdio.zap: header comments updated

### New tests
- **pass/207-print-decimal**: printb/printw/printl/putxw with all argument combinations
- **fail/printb-word-arg**: printb rejects word argument
- **fail/printw-long-arg**: printw rejects long argument
- **fail/putxw-long-arg**: putxw rejects long argument

**Files changed**: errno.zap, atari_stdio.zap, STDLIB.md

---

## Argument width validation for proc/func calls (2026-04-02)

### Compile-time type width checking:
- Passing a wider type to a narrower parameter is now a compile-time error (WORD->BYTE, LONG->BYTE, LONG->WORD)
- **Exception**: constant expressions that fit in the parameter width are allowed (e.g., `foo(42)` for BYTE param)
- Error messages suggest correct narrowing functions: `LOW()`, `HIGH()`, `LOWW()`, `HIGHW()`
- Validation shared via `validate_call_arg_widths()` in sema_shared.py
- `ProcSymbol` and `FuncSymbol` now store `param_types: list[SemType]` for per-parameter type info
- All 3 call sites covered: proc body calls, func body calls, function-as-expression calls

### New tests:
- **pass/206-arg-width-valid**: All valid combinations (same type, narrower-to-wider, constants that fit, LOW/HIGH/LOWW/HIGHW narrowing, pointer-to-pointer)
- **fail/145-arg-word-to-byte**: WORD var to BYTE param
- **fail/146-arg-long-to-byte**: LONG var to BYTE param
- **fail/147-arg-long-to-word**: LONG var to WORD param
- **fail/148-arg-const-overflow-byte**: Constant 256 to BYTE param

**Files changed**: symbols.py, sema_shared.py, sema_proc.py, sema_func.py, sema_expr.py, compiler_pipeline.py

---

## PEEK/POKE type validation (2026-04-02)

### Type checking added:
- **PEEK(address)**: address must be BYTE or WORD; LONG rejected with hint to use LOWW()/HIGHW()
- **POKE(address, value)**: address must be BYTE or WORD (same rule); value must be BYTE — WORD rejected with LOW()/HIGH() hint, LONG rejected with LOW()/HIGH()/LOWW()/HIGHW() hint
- Validation shared via `validate_poke_types()` in sema_shared.py (called from both sema_proc.py and sema_func.py)

### New tests:
- **pass/205-peek-poke**: PEEK/POKE with byte addr, word addr, literal addr, expression addr, LOWW/HIGHW of long addr; POKE with byte value, LOW/HIGH of word, LOW/HIGH of LOWW/HIGHW of long
- **fail/141-peek-long-addr**: PEEK with raw LONG address
- **fail/142-poke-long-addr**: POKE with raw LONG address
- **fail/143-poke-word-value**: POKE with raw WORD value
- **fail/144-poke-long-value**: POKE with raw LONG value

**Files changed**: sema_expr.py, sema_shared.py, sema_proc.py, sema_func.py, sema.py (import cleanup)

---

## Peephole optimization session (2026-03-26)

**Benchmark**: Sieve of Eratosthenes, ZAP! **0.830s** vs Action! 1.52s (PAL, SDMCTL=0, -6502 -O1)
**ZAP! is 45.4% faster than Action!** — down from 1.88s at start of optimization work.
**Broke the 1-second barrier (0.992s), then reached 0.830s with LSR Step 3!**

### Optimizations implemented:
- **OPT-D**: Dead low-byte CMP when const_lo==0 in word-vs-constant comparisons
- **OPT-B/A**: TMP2 round-trip elimination for constant byte array stores
- **OPT-C**: Inline ADD16/SUB16 with constant (skip JSR overhead)
- **OPT-F**: 65C02 `STA (zp)` without LDY#$00 (with Y-safety fix for word stores)
- **OPT-G**: Direct hi-byte load for word Identifier index (skip LDX/TXA)
- **MATH0 round-trip peephole**: Eliminate STA/LDA MATH0 across BCC/INC/label gaps
- **Branch threading**: Bxx label → Bxx far_target when label is JMP trampoline
- **Unreferenced label removal**: Clean __ZAP_* labels after threading (respects ASM blocks)
- **Branch inversion fix**: BCC body / JMP end / body: → BCS end (label-aware)
- **Loop strength reduction Step 1**: Running pointer in TMP0 for `arr[loop_var]` in simple for loops
- **Loop strength reduction Step 2**: Dedicated TMP2 pointer for `arr[loop_var]` reads in complex for loops (if/while in body)
- **Loop strength reduction Step 3**: While-loop pointer walking — eliminates loop variable entirely, replaces `while k <= N; arr[k] = val; k += stride` with pointer comparison + indirect store + pointer add
- **Loop-invariant hoisting**: LDY#$00, LDA#const moved before loop when body doesn't modify them
- **Generalized inline add/sub**: Skip MATH0 store when left operand already in A/X
- **Shift scratch optimization**: Power-of-2 shift uses MATH0 directly when followed by inline add
- **Dead register elimination**: LDX addr / STX addr → remove STX; dead LDX across BCC/INC/label

### Benchmark journey:
| Point | Time | vs Action! |
|-------|------|-----------|
| Start (no optimizations) | 1.88s | 24% slower |
| After peephole opts | 1.158s | 24% faster |
| After LSR Step 1 (init loop) | 1.108s | 27% faster |
| After branch fixes + hoisting | 1.052s | 30.8% faster |
| After LSR Step 2 (main loop) | **0.992s** | 34.7% faster |
| After LSR Step 3 (inner loop) | **0.830s** | **45.4% faster** |

### Code quality improvements:
- Eliminated global mutable state in dce.py (stmt_src passed as parameter)
- Narrowed exception catches in compiler.py (was `except Exception`)
- Modernized type hints across 12 files (Optional→X|None, List→list, etc.)
- Added module docstrings to 6 files
- Translated all Czech comments to English
- Fixed 9 Pylance type errors across 4 files
- grammar.ebnf: added preprocessor/diagnostic/incbin rules
- New DOC/ERROR_MESSAGES.md error message guide
- Removed redundant DOC/README.md (keep root only)
- Updated CLAUDE.md with ASM block optimization rule

**Files changed**: codegen_expr.py (peephole passes, LSR, inline add/sub, branch threading), dce.py, compiler_pipeline.py, compiler.py, errors.py, symbols.py, sema_func.py, sema_expr.py, + 12 files (type hints)
**Tests**: 170 pass, 125 fail (expected), full `make tests` verified

---

## Fix word-vs-constant comparison codegen and word-index array subscript (2026-03-25)

**Problem 1 — CMP instead of CPX**: In `_gen_conditional_branch()`, the word-identifier-vs-constant fast path for LT/GT/GE used `CMP` after `LDX high_byte`, comparing the accumulator (stale value) instead of X register against the high-byte constant.

**Problem 2 — Missing BNE in LT**: After `BCC lbl_true` (high < const_hi), the code fell through to low-byte comparison even when high > const_hi. Example: `$0300 < $02FF` would incorrectly evaluate to true.

**Problem 3 — LE compared low byte first**: Starting with the low byte ignores the significance of the high byte. `$0200 <= $01FF` would be true because `$00 < $FF`.

**Problem 4 — GT/GE completely broken**: GT used `BCS lbl_true / BNE lbl_true` which covers all cases (always true). GE had similar unreachable-branch issues.

**Problem 5 — LDX #$00 clobbered word index**: In `_gen_subscript()`, for byte-element arrays (`element_width == 1`) with a word index, the code zeroed X (`LDX #$00`) after `gen_expr(index)` loaded the 16-bit index into A/X. This discarded the high byte, making array access wrong for indices >= 256.

**Fix**: Rewrote all four relational operators (LT/LE/GT/GE) in the word-vs-constant path to match the correct algorithms already present in the A/X-preloaded path (lines 15607-15665). For the subscript bug, added a type check: only zero X when the index is BYTE-typed.

**Fix (phase 2)**: Comprehensive word-index support across all codegen paths:

1. **Dead code elimination in RPN power-of-2 multiply**: `rpn_eval_to_code()` unconditionally stored operands to MATH0/MATH1 before detecting power-of-2 optimization. Added early detection (`_skip_math_for_inline_mul`) to skip dead MATH0/MATH1 stores. Saves 4 instructions per `i * 2` pattern.

2. **`_gen_index_multiply()` upgraded with `word_index` parameter**: New `_gen_index_multiply_word()` handles 16-bit A/X index pairs. All paths (power-of-2, shift-add, fallback) use TMP3/TMP3+1 for 16-bit shift/accumulate.

3. **`_gen_subscript()` element_width==2 fast path guarded**: The `ASL A` fast path (byte index only) now checks index type. Word indices fall through to the general path which calls `_gen_index_multiply(word_index=True)`.

4. **`gen_assign()` element_width==2 inline path unified**: Replaced inline `ASL A / LDX #$00` with `_gen_index_multiply(2, word_index=...)` call, sharing logic with the read path.

5. **All `_gen_index_multiply` callers audited**: Added `word_index=True` for multi-dim stride (line 8368), pointer arithmetic `_gen_add`/`_gen_sub`, and address-of array element. X-indexed store path (`STA arr,X`) now guards against arrays where max offset > 255.

**Files changed**: `codegen_expr.py` (`rpn_eval_to_code`, `_gen_index_multiply`, `_gen_index_multiply_word` (new), `_gen_subscript`, `gen_assign`, `_gen_add`, `_gen_sub`, `_gen_multidim_subscript`, addr-of handler)
**Tests**: 170 pass (new: 203-word-compare-const, 204-word-index-array), 125 fail (expected) — no regressions

---

## Sieve peephole optimizations (2026-03-25)

Targeted optimizations identified by analyzing the Sieve of Eratosthenes generated assembly. Benchmark: ZAP! 1.88s vs Action! 1.52s on PAL Atari 800 (before these opts).

**OPT-D — Dead low-byte comparison when const_lo==0**: For word-vs-constant comparisons where the constant's low byte is $00 (e.g., `i < 8192` where 8192=$2000), the low-byte `CMP #$00 / BCC` is dead code. Eliminated for LT, LE, GT, GE. Saves 4 instructions per loop iteration for aligned constants. Applied in `_gen_conditional_branch()`.

**OPT-B/A — TMP2 round-trip elimination for constant array stores**: When storing a constant to an array element (`flags[i] = 0`), the compiler saved the constant to TMP2, computed the address, then reloaded from TMP2. Now computes the address first and stores the constant directly. Saves 4-6 instructions per store. Added early-return path in `gen_assign()` Case 2 for `IntLiteral` RHS.

**OPT-C — Inline word add-constant**: `JSR __ADD16_AX` for adding a constant (e.g., `i*2+3`) replaced with inline `CLC/ADC #imm/STA/BCC/INC` (or full 16-bit path for hi != 0). Eliminates JSR/RTS overhead + MATH1 loading. Added `_inline_add_sub_const` flag in `rpn_eval_to_code()` with both ADD and SUB support.

**OPT-F — 65C02 indirect addressing peephole**: `LDY #$00 / STA (zp),Y` → `STA (zp)` on 65C02. New `_65c02_indirect_no_y()` pass in `peephole_optimize()`. Guarded by `self.is_65c02`. Saves 2 bytes + 2 cycles per occurrence. 6502 mode unchanged.

**OPT-G — Direct hi-byte load for word Identifier index**: When the index is a simple word Identifier and the array base is a const label, load the high byte directly with `LDA var+1` instead of `LDX var+1 / TXA`. Saves 2 instructions per array access. Applied in `_gen_subscript()` and `gen_assign()` Case 2a.

**65C02 peephole Y-safety fix (2026-03-26)**: The `_65c02_indirect_no_y` peephole removed `LDY #$00` before `STA/LDA (zp),Y` → `STA/LDA (zp)` but didn't check if subsequent instructions (INY for word high-byte stores) depended on Y=0. Fixed by scanning forward after replacement to check for Y reads before the next LDY reset. Tests 162, 167, 176, 177 were affected (O1 variant only).

**Code quality review (2026-03-26)**: Eliminated global mutable state in dce.py (stmt_src passed as parameter), narrowed broad exception catches in compiler.py, modernized type hints (Optional→X|None) across 12 files, added module docstrings to 6 files, translated all Czech comments to English, removed duplicate docstrings in errors.py.

**Files changed**: `codegen_expr.py` (`_gen_conditional_branch`, `gen_assign`, `rpn_eval_to_code`, `peephole_optimize`, `_65c02_indirect_no_y`), `dce.py`, `compiler_pipeline.py`, `compiler.py`, `errors.py`, + 12 files (type hint modernization)
**Tests**: 170 pass, 125 fail (expected) — full `make tests` verified including simulator

---

## BYTE-target narrowing: 16-bit → 8-bit for byte assignments (2026-03-24)

**Problem**: `byte rv += fwrite(...)` generated 16-bit arithmetic (`JSR __ADD16`, stack-save/restore of garbage high byte, TMP0 round-trip) because `fwrite` returns WORD and the type promotion picked ADD16 for BYTE+WORD. But only the low byte of the result is stored — the high byte is wasted.

**Insight**: For ADD, SUB, AND, OR, XOR, the low byte of the result depends only on the low bytes of the operands. When the assignment target is BYTE, we can safely narrow WORD operands to BYTE and use inline 8-bit arithmetic.

**Fix**: In `_gen_binary` (codegen_expr.py), when `assign_target_type.base == "BYTE"` and the operator is ADD/SUB/AND/OR/XOR, set `result_16_temp = False` to force 8-bit path. Guards: do not narrow pointer arithmetic or address expressions. Clear `assign_target_type` after the decision to prevent leakage into sub-expression evaluation (LHS pointer computation).

Also added matching narrowing in the RPN evaluator for when the RPN path is used.

**Before** (14 instructions): `LDA rv; PHA; TXA; PHA; ...; JSR __ADD16; STA rv`
**After** (7 instructions): `LDA rv; PHA; ...; STA __TMP0; PLA; CLC; ADC __TMP0; STA rv`

**Files changed**: `codegen_expr.py` (`_gen_binary`, `rpn_eval_to_code`)

**Fix for test 167**: The narrowing leaked into pointer sub-expressions via `assign_target_type` not being cleared in `_gen_field_access` before evaluating `gen_expr(expr.object.pointer)`. `(sptr + 1)^.x = 99` narrowed the `sptr + 1` pointer arithmetic to 8-bit, losing the pointer's high byte. Fixed by saving/clearing `assign_target_type` around pointer evaluations in `_gen_field_access`.

---

## OPT-14: TMP0 round-trip elimination for 16-bit add after call (2026-03-24)

**Pattern** (11 instructions):
```
STA __TMP0; STX __TMP0+1; PLA; TAX; PLA; STA __MATH0; STX __MATH0+1;
LDA __TMP0; STA __MATH1; LDA __TMP0+1; STA __MATH1+1
```

**Replacement** (6 instructions):
```
STA __MATH1; STX __MATH1+1; PLA; STA __MATH0+1; PLA; STA __MATH0
```

**Savings**: 5 instructions per occurrence. Eliminates the TMP0 save/restore round-trip when a function call result (A/X) feeds into a 16-bit addition with a stacked operand (e.g., `rv += fwrite(...)`).

**Files changed**: `codegen_expr.py` (`peephole_optimize`, OPT-14 rule)

---

## atari_stdio.zap file I/O bug fixes (2026-03-24)

**Problem**: Multiple bugs in the Atari CIO-based file I/O functions prevented correct file read/write operations. The test program `test_stdio.zap` wrote "Hello!" to a file, read it back, but `puts(buf)` showed only 'o' instead of "Hello" (a compiler slot-aliasing bug, fixed separately) and all file operations used wrong success checks.

**Bugs fixed**:
1. `fclose`, `fread`, `fwrite`: checked `rv != 1` for error, but `CIO()` remaps Atari OK (1) → 0, so success = 0. Changed to `rv != 0`. The success path was dead code before this fix.
2. `checkeof`: checked `errno == 1` to clear EOF, but callers pass CIO's remapped value (0 = OK). Changed to `errno == 0`. EOF flag could never be cleared.
3. `fread`, `fwrite`: `checkeof` was only called in the (dead) success path. Moved before the error check so EOF (status 136) is always recorded.
4. `fgetc`: returned `buffer` (always 0) instead of the character. Rewrote to read ICSTA directly for status and return the character from CIO's accumulator result.
5. Header comment block updated to mark fread, fgetc, rename, remove as IMPLEMENTED.

**Files changed**: `work/lib/atari/atari_stdio.zap`

---

## Slot liveness / argument evaluation order bug fix (2026-03-24)

**Problem**: When a function call like `fwrite(fd, buf, strlen(buf))` had a nested call in a later argument, the codegen stored earlier memory-parameter values to their shared `__LVSLOT` slots before evaluating later arguments. If the nested call (`strlen`) used the same `__LVSLOT` for its own parameter, it clobbered the previously stored value. This caused `fwrite` to receive a corrupted buffer address — the exact bug observed in `test_stdio.zap` where `puts(buf)` showed only 'o' instead of "Hello".

**Root cause**: Two-layer problem:
1. **Codegen** (`_emit_call_args`): stored parameter slot values left-to-right immediately, without protecting them from nested `gen_expr` calls in later arguments.
2. **Liveness analysis** (`share_locals_liveness`): did not create interference edges between a callee's earlier parameters and the locals/params of functions called during evaluation of later arguments ("sibling-call" pattern).

**Fix (Layer 1 — codegen)**: Added deferred-store mechanism in `_emit_call_args`. When any later argument expression contains a function call, earlier memory-parameter values are pushed to the 6502 hardware stack instead of stored directly to `__LVSLOT`. After all argument expressions are evaluated, the deferred values are popped and stored to their parameter slots. Compile-time constant (IntLiteral) arguments use a late-store optimization that avoids the stack entirely.

**Fix (Layer 2 — liveness)**: Added a new interference phase in `share_locals_liveness` that walks all call expressions and adds edges between a callee's params `p[0..j-1]` and all locals/params of functions called during evaluation of arg `j`. This prevents the slot allocator from assigning conflicting slots in the first place.

**Files changed**: `codegen_expr.py` (`_emit_call_args`), `compiler_pipeline.py` (`share_locals_liveness`).

**Tests**: 168 pass + 128 fail tests all green. Two new regression tests added:
- `tests/pass/201-nested-call-args` — pointer/word params with nested calls
- `tests/pass/202-deferred-param-store` — exact fwrite/strlen pattern with 3 memory params

---

## `-ZPSTART` CLI parameter for Zero Page budget control (2026-03-18)

**Problem**: The compiler hardcoded `ZEROPAGE_SIZE = 256` and a heuristic offset of 64 bytes for system use, but real linker configs (e.g., Atari 8-bit: `$82`–`$FF` = 126 bytes) have much less ZP available. This caused `ld65` overflow errors.

**Solution**: New `-ZPSTART <addr>` CLI flag sets the first usable ZP address. Budget = `256 - addr`. Supports decimal and hex (`0x82`). The compiler now also accounts for shared ZP slot sizes when computing the ZP budget, preventing over-allocation.

**Files changed**: `compiler.py`, `compiler_pipeline.py`, `codegen_expr.py`, `work/go.bat`, `DOC/README.md`, `DOC/ARCHITECTURE.md`, `DOC/KNOWN_LIMITATIONS.md`.

---

## Optimisation: 16-bit → 8-bit Narrowing (OPT-A/B/C/E) (2026-03-17)

**Goal**: Minimise 16-bit operations to 8-bit when the compiler can prove at compile time that values fit in a byte.

### PREREQ: Array bounds info at codegen time
- Computed `_max_byte_offset = array_size * element_width` from `sym.array_dims` / `sym.array_len` in `_gen_subscript()`.
- `_offset_fits_byte = True` when max offset ≤ 255.

### OPT-A: Array subscript carry elimination
**Where**: `_gen_subscript()` fast path (element_width==2, const base label).
**Before** (12 instr): `ASL A; TAX; LDA #$00; ROL A; TAY; CLC; TXA; ADC #<lbl; STA TMP0; TYA; ADC #>lbl; STA TMP0+1`
**After** (7 instr): `ASL A; CLC; ADC #<lbl; STA TMP0; LDA #>lbl; ADC #$00; STA TMP0+1`
**Savings**: 5 instr × 3 instances in test_stdio = 15 instructions.

### OPT-B: Shift-multiply carry elimination
**Where**: `_gen_index_multiply()` power-of-2 and shift-add paths.
**Before** (e.g. ×16): `STA TMP3; LDA #$00; (ASL TMP3; ROL A)×4; TAX; LDA TMP3` (12 instr)
**After**: `(ASL A)×4; LDX #$00` (5 instr)
**Savings**: 7 instr × 2 instances = 14 instructions.

### OPT-C: WORD == 0 / != 0 → ORA pattern
**Where**: RPN evaluator (16-bit comparison), `_gen_relational()`, `_emit_relational_branch_impl()`.
**Before**: `LDA MATH0; CMP MATH1; BNE ...; LDA MATH0+1; CMP MATH1+1; BNE ...`
**After**: `LDA MATH0; ORA MATH0+1; BNE/BEQ ...`
**Savings**: 2 instr per comparison, 2 instances in test_stdio.

### OPT-E: WORD array index carry elimination
**Where**: `gen_assign()` subscript store path (element_width==2).
**Before**: `ASL A; LDX #$00; BCC skip; INX; skip:` (5 instr)
**After**: `ASL A; LDX #$00` (2 instr)
**Savings**: 3 instr per occurrence.

**Test results:** 166 pass / 125 fail — all OK.

---

## Bugfix: Two Peephole Optimizer Safety Issues (2026-03-17)

### Bug 1: `_replace_transfer_sta_with_direct_store` — wrong A-liveness check
**Symptom**: `-6502 -O1` variant of test 164 (struct-array-pow2-index) produced wrong values. The peephole removed `TXA; STA addr` → `STX addr`, but A's value (set by TXA) was needed by a subsequent `ASL A` sequence.

**Root cause**: `A_LOAD_MNEMONICS` included `ASL`, `LSR`, `ROL`, `ROR`, `ADC`, `SBC`, `AND`, `ORA`, `EOR`. These all **read A first** (A = A op operand), so A is live before them — they are not dead-A points. Only `LDA`, `TXA`, `TYA`, `PLA` truly reload A from scratch.

**Fix** (`codegen_expr.py`): Removed all read-modify-write mnemonics from `A_LOAD_MNEMONICS`, keeping only `{"LDA", "TXA", "TYA", "PLA"}`.

### Bug 2: `_indirect_word_load_store` — aliased pointer/store corruption
**Symptom**: `-6502 -O1` variant of test 103 (array_of_pointers) produced wrong pointer dereferences. The peephole reordered stores to write `addr+1` before the second `LDA (ptr),Y`, but `addr` and `ptr` were aliased via equates (both = `__LVSLOT_1`).

**Root cause**: Writing `addr+1` corrupted the pointer before the second indirect load when the store destination and the pointer variable shared the same zero-page slot.

**Fix** (`codegen_expr.py`): Added equate-aware alias detection — builds a map of label equates from the assembly, resolves both the pointer base and store address through the equate chain, and skips the optimization when they resolve to the same base.

**Test results:** 166 pass / 125 fail — all OK.

---

## Bugfix: Em-dash Encoding in Error Messages (2026-03-17)

**Symptom**: `struct-too-large` fail test showed `[MSG_MISMATCH]` — the em-dash character (`—`, U+2014) in the error message was corrupted by Windows console encoding (byte `0x97` instead of UTF-8 `0xE2 0x80 0x94`).

**Fix** (`sema.py`): Replaced em-dash with ASCII dash (`-`) in the struct-too-large error message. Updated `.err` and `.ref` files to match.

---

## IDE: ASM/END Keyword Highlighting in VS Code (2026-03-17)

**Symptom**: `asm` and `end` keywords inside ASM blocks were not syntax-highlighted as ZAP keywords — the injection grammar took over the entire region without preserving keyword scoping.

**Fix** (`zap-ca65.injection.json`): Added `beginCaptures` and `endCaptures` to explicitly assign `keyword.control.zap` scope to the `asm` and `end` keywords within the injection pattern.

---

## Optimisation: Indirect WORD Load-Store — Eliminate TAX Round-Trip (2026-03-17)

**Pattern**: When loading a WORD value from `(ptr),Y` (high byte first, then low byte) and immediately storing to a variable, the `TAX` / `STX var+1` round-trip is unnecessary — the high byte can be stored directly from A.

**Before** (7 instructions):
```asm
LDA (__TMP0),Y   ; high byte
TAX              ; save in X (unnecessary)
DEY
LDA (__TMP0),Y   ; low byte
STA _CURPTR
STX _CURPTR+1    ; from X (unnecessary round-trip)
```

**After** (5 instructions):
```asm
LDA (__TMP0),Y   ; high byte
STA _CURPTR+1    ; store directly from A
DEY
LDA (__TMP0),Y   ; low byte
STA _CURPTR
```

**Fix** (`codegen_expr.py`): Added `_indirect_word_load_store()` peephole pass (5th pass). Detects `LDA (ptr),Y; TAX; DEY; LDA (ptr),Y; STA addr; STX addr+1` and replaces with direct store pattern.

**Test results:** 166 pass / 125 fail — all OK.

---

## Optimisation: Branch Inversion Now Runs Unconditionally (2026-03-17)

**Change**: Moved `_branch_inversion()` from `-O1`-only (inside `peephole_optimize()`) to always run in the pipeline (before jump threading and label cleanup). This is a safe, size-reducing pass — replaces `Bxx skip; JMP target; skip:` with `B~xx target` when the target is within ±127 bytes.

**Example** (`repeat/until` loop):
```asm
; Before:                    ; After:
CMP #$03                    CMP #$03
BEQ __ZAP_endrepeat_36      BNE __ZAP_repeat_34
JMP __ZAP_repeat_34
__ZAP_endrepeat_36:
```
Saves 3 bytes per inverted branch (the JMP is eliminated).

**Fix** (`compiler_pipeline.py`): Added `cg.code = cg._branch_inversion(cg.code)` unconditionally before `jump_threading()`.

**Test results:** 166 pass / 125 fail — all OK.

---

## Optimisation: Eliminate Redundant RTS Before RTS (2026-03-17)

**Pattern**: `RTS` followed by labels/comments then another `RTS` — the first `RTS` is redundant because fall-through reaches the second one. Common in `switch/case` with `return` statements.

**Fix** (`jump_threading.py`): Added rule that scans past labels, comments, and blank lines after `RTS`. If the next real instruction is also `RTS`, the first one is dropped.

**Before**: Two separate `RTS` instructions with a label between them.
**After**: Single `RTS` after the label — serves both paths.

**Test results:** 166 pass / 125 fail — all OK.

---

## Optimisation: Eliminate Unnecessary LDX #$00 for BYTE Values (2026-03-17)

**Symptom**: `LDX #$00` was emitted after loading BYTE values in contexts where X is never used:
1. BYTE struct field loads in 8-bit comparisons (`if IOCB[i].ICHID == 255` — X unused by CMP)
2. BYTE variable loads before pointer stores (`dst^ = val` — only A stored via `STA (ptr),Y`)

**Root Cause**: Three locations did not honour `suppress_byte_return_x`:
1. `_emit_field_via_ptr` (BYTE load path) checked `target_is_byte` and `force_word_result` but NOT `suppress_byte_return_x`
2. `_gen_relational` did not set `suppress_byte_return_x` for 8-bit comparisons before evaluating operands
3. `_emit_relational_branch` (used by `if`/`while`) — same issue as above
4. DerefExpr ZP assignment path did not set `suppress_byte_return_x` before `gen_expr(rhs)` for BYTE targets

**Fix** (`codegen_expr.py`):
1. `_emit_field_via_ptr`: Added `and not self.suppress_byte_return_x` to the LDX #$00 guard
2. `_gen_relational`: Set `suppress_byte_return_x = True` for 8-bit comparisons around operand evaluation
3. `_emit_relational_branch`: Wrapper sets `suppress_byte_return_x = True` when both operands are BYTE (non-pointer)
4. DerefExpr ZP assignment: Set `suppress_byte_return_x = True` before `gen_expr(rhs)` when target is BYTE

**Test results:** 166 pass / 125 fail — all OK.

---

## Optimisation: Eliminate TMP2 Round-Trip for Struct Field Stores (2026-03-17)

**Symptom**: Assigning a simple variable or constant to a struct field accessed via pointer/subscript (e.g., `IOCB[ch].ICBL = len`) generated unnecessary `STA __TMP2` / `STX __TMP2+1` stores followed by loads from TMP2. The 9-instruction sequence could be reduced to 6.

**Root Cause**: `gen_assign` always saved the RHS value (A/X) to TMP2 before calling `_gen_field_access`, even when the RHS was a simple variable that could be reloaded directly. The store path in `_emit_field_via_ptr` then loaded from TMP2 instead of the original source.

**Fix** (`codegen_expr.py`):
1. Added `rhs_asm` / `rhs_hi_asm` optional parameters to `_emit_field_via_ptr` — when provided, loads from the original source instead of TMP2.
2. Propagated these parameters through `_gen_field_access` to all store paths (SubscriptExpr, DerefExpr, Identifier base, nested FieldAccess).
3. Added early-exit in `gen_assign` before `gen_expr(rhs)`: when LHS is FieldAccess and RHS is Identifier or IntLiteral, skip `gen_expr(rhs)` and TMP2 save entirely, passing the source ASM name directly.

**Before** (9 instructions):
```asm
LDA _CIO_LEN      ; gen_expr
LDX _CIO_LEN+1
STA __TMP2         ; save to TMP2
STX __TMP2+1
LDY #$08
STA (__TMP0),Y     ; A still had low byte
LDA __TMP2+1       ; reload high byte from TMP2
INY
STA (__TMP0),Y
```

**After** (6 instructions):
```asm
LDA _CIO_LEN       ; load directly from source
LDY #$08
STA (__TMP0),Y
LDA _CIO_LEN+1     ; load high byte directly
INY
STA (__TMP0),Y
```

**Applies to**: All struct field stores via pointer/subscript with Identifier or IntLiteral RHS (BYTE and WORD types). LONG fields are unaffected (use MATH0).

**Test results:** 166 pass / 125 fail — all OK.

---

## IDE: Code Formatting (2026-03-16)

**Document formatter** (`extension.js`): `formatZapDocument()` registered via `registerDocumentFormattingEditProvider`. Triggered by Shift+Alt+F / right-click → Format Document. Normalises indentation using two regex rules:
- Decrease level **before** line: `end`, `else`, `elseif`, `until`, `case`, `.else`, `.endif`
- Increase level **after** line: `proc`, `func`, `if`, `elseif`, `else`, `while`, `for`, `repeat`, `switch`, `case`, `asm`, `struct`, `enum`, `.ifdef`, `.ifndef`, `.else`

**Auto-indent on Enter** (`language-configuration.json`): Added `indentationRules` with `increaseIndentPattern` and `decreaseIndentPattern`. Pressing Enter after a block-opening keyword automatically indents the next line; typing `end`/`else`/etc. auto-de-indents the current line. Patterns are case-insensitive (character class style, consistent with existing folding markers).

---

## Bug Fix: Unknown Type Name Not Detected (2026-03-16)

**Symptom**: Writing `char abc` or `int abc` as a global variable produced no compiler error. The invalid type name was silently ignored.

**Root Cause**: The parser's global-scope loop had a catch-all `elif self.cur.type == TOK_IDENT: self.advance()` branch intended for stray BOM characters. When `char` (an IDENT, not a TOK_TYPE) was followed by `abc` (another IDENT), both were silently skipped.

**Fix** (`parser.py`): In the stray-identifier branch, peek at the next token. If the next token is also `TOK_IDENT` or `TOK_TYPE`, raise `"Unknown type 'X'"` immediately — this is an invalid type declaration, not a stray BOM.

**Secondary fix** (`sema.py`): Added a validation guard in `DeclarationAnalyzer.analyze()` — if the type is not a known struct and not in `{"BYTE", "WORD", "LONG"}`, raise `"Unknown type 'X'"`. This is a defense-in-depth check for declarations that reach sema with invalid types.

**New test**: `tests/fail/invalid-type-name/` — `char abc` at global scope → `1:1: error: Unknown type 'CHAR'`.

**Test results:** 166 pass / 126 fail — all OK.

---

## LONG Datatype Gap Fixes + Subscript Speed-Up (2026-03-16)

### Phase 1: element_size=2 TAY fast path in `_gen_subscript`

For `array[var_index]` where element_size=2 and base is a constant label, added a dedicated fast path that uses direct register shifts instead of TMP3 memory operations. Replaces `STA TMP3 / LDA #$00 / ASL TMP3 / ROL A / TAX / LDA TMP3` with `ASL A / TAX / LDA #$00 / ROL A / TAY / CLC / TXA / ADC #<label / STA TMP0 / TYA / ADC #>label / STA TMP0+1`. Same instruction count but eliminates 3 ZP memory accesses (~10 cycles saved per subscript). Frees TMP3 slot.

### Phase 2: LONG datatype gap fixes

Four concrete LONG gaps fixed:
1. **`_gen_subscript` struct field element_width** (`codegen_expr.py:8357`): Added `elif field_info.base_type == "LONG": element_width = 4`. Previously fell to `else → nested_struct.size or 2`.
2. **`gen_vars_block` ZP allocation** (`codegen_expr.py:6685`): Added `elif sym.type.base == "LONG": element_size = 4`. Previously allocated 1 byte per LONG element.
3. **`_gen_multidim_subscript` LONG load** (`codegen_expr.py`): Added `element_width == 4` branch for multi-dimensional LONG array subscript load (4 bytes via `(TMP0),Y` → MATH0).
4. **`_gen_multidim_subscript` LONG store**: Added `element_width == 4` branch for multi-dimensional LONG array subscript store (MATH0 → 4 bytes via `(TMP0),Y`).

### Phase 3: RPNNode `width == 2` audit

All `width == 2` comparisons in `gen_rpn_expr` are **correctly guarded** — every `== 2` check is preceded by a `> 2` guard that handles LONG first. The `is_16bit = (width >= 2)` pattern routes LONG through `is_32 = left_width > 2 or right_width > 2` before any 16-bit path. No code changes required.

**Test results:** 166 pass / 125 fail — all OK.

---

## Optimization: Constant-Base Array Subscript + Carry Tracking (2026-03-16)

### `_gen_subscript` constant-base optimization

For non-const, non-pointer array identifiers (the common case), the old code loaded the array's base address into `TMP0` (4 instructions: `LDA #<label; LDX #>label; STA TMP0; STX TMP0+1`), then evaluated the index expression, then added the scaled offset to `TMP0`. This had a latent bug: any `JSR` called during index evaluation (e.g., `MUL8_A`) would clobber `TMP0`, corrupting the base address. **Test 121 (`arr[a * b + 1]`) was returning 0 instead of 88 due to exactly this bug** — `MUL8_A` overwrites `TMP0` at its entry point.

The fix: skip the upfront `TMP0` load entirely. Instead, evaluate the index first (in the correct order), then use `ADC #<label; ADC #>label` immediate addressing in the ADD phase. Saves 4 instructions and eliminates the register-clobber hazard.

**Conditions**: `isinstance(base, Identifier)` and `not (sym.type.is_pointer and not sym.is_array)` — i.e., a static array symbol (not a pointer variable with a runtime-determined address).

### OPT-3: Carry-zero tracking after `ROL A` with A=#$00

In `_eliminate_redundant_imm_lda`, added `known_carry_zero: bool` tracking:
- After `ROL A` when `known_a == 0`: carry is provably 0 (old bit 7 of `#$00` = 0). Set `known_carry_zero = True`.
- When `CLC` and `known_carry_zero == True`: CLC is redundant — skip it.
- Reset on: labels, unconditional control flow, conditional branches, `SEC`/`CMP`/`CPX`/`CPY`, and any A-modifying instruction.

This fires for all power-of-2 element sizes (`_gen_index_multiply` emits `LDA #$00; [ASL TMP3; ROL A]×k`) — the `CLC` in the ADD phase is eliminated, saving 1 instruction per array subscript with power-of-2 element size.

**Bug fixed**: `tests/pass/121-expr-contexts/121-expr-contexts.ref` updated: `9C43: 00 → 58` (88 is the correct value of `arr[a*b+1]` = `arr[7]` after `arr[7] = 88`).

**Test results:** 166 pass / 125 fail — all OK.

---

## Bug Fix: OPT-7/OPT-8 Peephole Optimizer Correctness (2026-03-16)

Three correctness bugs fixed in peephole optimizations:

1. **OPT-8 indexed addressing** — `LDA (_MAIN_VRAM),Y` was tracked as `known_a_mem`. After `DEY`, a subsequent `LDA (_MAIN_VRAM),Y` was incorrectly eliminated (same operand string, but Y changed). Fix: don't track or eliminate indexed operands (ending in `,X` or `,Y`).

2. **OPT-8 loop iteration** — `known_a_mem` was not reset on conditional branches (`BNE`, `BEQ`, etc.), so state persisted into post-loop code, causing incorrect LDA elimination across loop iterations. Fix: reset `known_a_mem = None` on conditional branches (keep `known_a` since A register is unchanged by the branch itself).

3. **OPT-7 carry flag safety** — In LONG for-loops, the step-direction check uses `LDA addr; CMP #$00; BNE label` where `label:` has `BEQ ...; BCS ...`. OPT-7 eliminated `CMP #$00` (BNE only uses Z flag), but `CMP #$00` always sets C=1 and the `BCS` at the branch target relied on it. Fix: enhanced OPT-7 forward scan to follow conditional branch targets and check for carry-using instructions (`BCS`/`BCC`) there.

**Pylance fix**: Added `self._line_mapped: bool = False` to `CompileError.__init__` in `errors.py` so the attribute is recognized on all subclasses including `SemanticError`.

**Test results:** 166 pass / 125 fail — all OK.

---

## Bug Fix: Struct WORD/pointer field initialisation (2026-03-13)

Two related bugs fixed:

1. **`symbols.py` `StructFieldInfo.width` property** — compared `self.base_type` with lowercase literals (`"byte"`, `"word"`, `"long"`) but `sema.py` stores `base_type` in uppercase (`"BYTE"`, `"WORD"`, `"LONG"`). Result: `fi.width` always returned 0 for primitive-type fields. Fixed: normalise to uppercase via `base = self.base_type.upper()` before comparisons.

2. **`codegen_expr.py` struct `ListInit` codegen** — the `if is_struct_type` branch in `gen_init()` used `sym.type.base == "WORD"` (always False for struct types) to decide whether to store the high byte. This meant WORD and pointer fields in structs only had their low byte written during initialisation.

**Fix**: replaced the entire struct `ListInit` path with layout-aware codegen using new helper `_build_struct_init_layout(fields)`. For const initialisers emits `LDA #byte / STA dest+offset` per byte. For non-const uses `gen_expr + STA/STX` per field with correct widths. Handles byte, word, pointer, long, array sub-fields, nested structs. Removes spurious `LDX #$00` before byte-field stores.

**Test `177-struct-pointer-fields`** updated: `Target` struct now has `{ byte val1; word wval; byte val2 }`. `$9C45=01` (wval high byte) and `read_wval @$9C54=$2C $01` verify the fix.

**Test results:** 166 pass / 125 fail — all OK.

---

## Optimization: Transfer+Store → Direct Store (OPT-5) (2026-03-13)

`_replace_transfer_sta_with_direct_store()` added to `codegen_expr.py` as fourth peephole pass.

Forward: `TYA; STA addr(s)` → `STY addr(s)`, `TXA; STA addr(s)` → `STX addr(s)` — removes the transfer instruction (saves 1 byte + 2 cycles per group).

Reverse: `TAX; STX addr(s)` → `STA addr(s)`, `TAY; STY addr(s)` → `STA addr(s)` — removes the transfer, keeps STA (saves 1 byte + 2 cycles).

Safety conditions: (1) addressing mode compatible with STY/STX (no `,Y` for STY, no `,X` for STX, no indirect); (2) for forward direction, A must be dead after the STA block (next real instruction reloads A or is JMP). Reverse direction is always safe since TAX/TAY don't modify A.

Confirmed 1 site in test_stdio.zap (fopen CIO zero-init block: `TYA; STA _CIO_LEN; STA _CIO_LEN+1; STA _CIO_AUX2; STA _CIO_AUX3`).

**Test results:** 166 pass / 125 fail — all OK.

---

## Optimization: Register Transfer Instead of Immediate Reload (2026-03-13)

Third-pass peephole `_replace_imm_load_with_transfer()` added to `codegen_expr.py`.

When a register already holds a known immediate value and another register is about to be loaded with the same value, replaces the load with a register transfer instruction:
- `LDA #imm` → `TXA` (when X holds imm) or `TYA` (when Y holds imm)
- `LDX #imm` → `TAX` (when A holds imm)
- `LDY #imm` → `TAY` (when A holds imm)
- X↔Y: no direct transfer on 6502/65C02 (TXY/TYX are 65C816 only) — skipped

Saves 1 byte and 0 cycles per replacement (both `LDx #imm` and `Txy` are 2 cycles; transfer saves 1 byte).
Verified on `work/test_stdio.zap`: 6 replacements including `LDY #$00` → `TAY` and `LDA #$00` → `TYA`.

**Test results:** 166 pass / 125 fail — all OK.

---

## Documentation + Regression Test: Struct Pointer Fields (2026-03-13)

`DOC/ZAP_LANGUAGE_REFERENCE.md` line 2047 updated — pointer types (`byte^`, `word^`, `long^`, struct pointers) added to the list of valid struct field types. New "Pointer Fields" subsection added with code example covering field declaration, address assignment, write/read through pointer fields, and struct-pointer field access. Linked-list example intentionally omitted (no heap allocator).

Regression test `tests/pass/177-struct-pointer-fields` added — 4 checks:
- `byte^` field: write and read through pointer (bdata via h.bptr^)
- `word^` field: write and read through pointer (wdata via h.wptr^)
- `Target^` field: write and read a struct field through pointer (tdata.val1 via h.sptr^.val1)
- Pointer field values themselves verified in memory (h.bptr / h.wptr / h.sptr store correct addresses)

**Test results:** 166 pass / 125 fail — all OK.

**Note:** A pre-existing bug was observed during test design: struct WORD field initialization emits `LDA #lo; LDX #hi; STA addr` but omits `STX addr+1`, so only the low byte is stored. The test avoids word fields inside structs to stay clean. The bug needs a separate fix.

---

## Optimization: Pre-peephole store-reordering pass (2026-03-13)

New `_pre_optimize_reorder_stores()` method (runs before `peephole_optimize()`) detects:

    [Block A: LDA #imm + LDX/LDY #imm + STA/STX/STY/STZ stores]
    [Block B: LDA mem_src + STA/STX/STY stores]
    [Block C: LDA #same_imm + LDX/LDY #imm + STA/STX/STY/STZ stores]

and reorders to [A][C][B] so the subsequent peephole eliminates redundant `LDA #imm`.
Handles `LDX #same_imm` within blocks; safety checks: no PORT, no source/dest overlap; iterates to convergence.

**Effect on fopen() CIO call**: 4 instructions → 7 stores in one A-load.

**Test results:** 165 pass / 125 fail — all OK.

---

## Optimization: Peephole equate-line transparency for redundant LDA elimination (2026-03-13)

ca65 equate lines (e.g. `_FOPEN_I = __LVSLOT_16`) emitted between a `STA addr / STX addr+1` pair and a subsequent `LDA addr` were blocking the peephole redundant-load elimination. Added `_is_equate_line()` helper and made three scan paths treat equates as transparent (like blanks/comments): the STA/STX special-case scan, the general backward scan, and the forward clobber-check. The redundant `LDA _FOPEN_FD` in atari_stdio is now correctly eliminated.

**Test results:** 165 pass / 125 fail — all OK.

---

## Optimization: Phase 4 struct base memoization + O1 zero-word-store peephole (2026-03-13)

### Phase 4: Struct Base Address Memoization

When `arr[idx].field` appears 2+ times in a proc (across branches or JSR calls), the compiler now:
1. Pre-scans the proc body in `_predeclare_struct_base_memos()` (compiler_pipeline.py) and declares a proc-local `WORD` variable `__SBM_N` for each unique `(arr, idx)` pair.
2. On first compute: saves TMP0 to `__SBM_N` (4 extra instructions).
3. On subsequent uses (after branch/label/JSR): restores TMP0 from `__SBM_N` (4 instructions) instead of recomputing from scratch (~23 instructions).

Memo is invalidated only when `idx` is written (e.g. `i = 5`). Unlike Phase 3 (in-register cache), Phase 4 memo is in a proc-local variable that survives JSR calls.

**Net savings** for `cio()`: 2 recomputes eliminated → ~34 instructions saved.

### O1 Peephole Rule G: Redundant LDX elimination for same-immediate pair

Pattern: `LDA #imm / LDX #imm / STA addr / STX addr+1` → `LDA #imm / STA addr / STA addr+1`

When A and X hold the same immediate (most common case: #$00), LDX is redundant because STA can store both bytes. Saves 1 instruction per zero WORD store. Works on both 6502 and 65C02.

**Test results:** 165 pass / 125 fail — all OK.

---

## Feature: Struct array field access optimization + 255-byte struct limit (2026-03-13)

### Three-Phase Struct Field Access Optimization

**Phase 1:** `LDY #field_offset` + `(TMP0),Y` for struct array element field access, replacing the previous `ADC #offset; STA TMP0` approach (~7 instructions saved per access).

**Phase 2:** Direct `(ptr_asm),Y` for `ptr^.field` when the pointer is a confirmed zero-page identifier (`sym.in_zeropage = True`). Non-ZP pointers still route through TMP0.

**Phase 3:** `_struct_base_cache` tuple `(arr_asm, idx_asm)` — skips recomputation of the struct base address for consecutive `array[same_idx].field` accesses within the same expression sequence.

### Bugs Fixed

**Fix 1 — Phase 3 cache not invalidated on idx variable writes:** Cache stored `(arr_asm, idx_asm)` but `emit()` only checked for `STA TMP0`/control flow. Added `STA {_idx_asm}`, `STZ`, `INC`, `DEC` pattern checks to invalidate cache on any write to the indexed variable.

**Fix 2 — ca65 "Range error (Address size 2 does not match fragment size 1)"** for tests 037, 166: Phase 2 emitted `STA (_MAIN_PP),Y` where `_MAIN_PP` was a BSS slot equate (non-ZP). Root cause: slot placement in `gen_vars_block` checked `sym.type.is_struct` before `sym.type.is_pointer`, routing struct-pointers to BSS. Fixed by checking `is_pointer` first (pointer check precedes struct check in 4 locations: 2 in `gen_vars_block`, 2 in `compiler_pipeline.py`).

**Fix 3 — O1 peephole Y-register clobber:** Optimizer eliminated `LDA (__TMP0),Y` because it matched a prior `STA (__TMP0),Y` (same text), but Y had changed between them. Added `_uses_y_index` / `_clobbers_y` guards in the `can_remove` loop.

### 255-Byte Struct Size Limit

Added sema check in `sema.py` (~line 231): rejects any struct whose total size exceeds 255 bytes. Rationale: field offsets are loaded as 8-bit immediates (`LDY #offset`); offset 256 would overflow.

**New tests:**
- `tests/pass/174-struct-field-zp-access/` — Phase 1, 2, 3 with Point/Rect structs and struct pointer (5 checks)
- `tests/pass/175-struct-array-base-cache/` — Phase 3 cache invalidation in for loop (8 checks)
- `tests/fail/struct-too-large/` — struct with 256 bytes rejected with correct error location and message

**Test results:** 164 pass / 125 fail — all OK.

---

## Fix: `ptr += byte_var` high byte reads wrong memory (`ADC sym+1` for BYTE var) (2026-03-12)

**Bug:** `dst += m` where `dst: byte^` and `m: byte` generated:
```
LDA _DST+1
ADC _M+1    ← BUG: M is 1 byte wide, reads garbage
STA _DST+1
```

**Root cause:** Three direct-memory optimization paths in `gen_assign` / var-init handlers assumed both operands of a `var1 + var2` expression were 16-bit. They used raw `sym+1` or `_sym_operand(sym, low_byte=False)` for the high byte of BYTE variables.

- `_sym_operand(sym, low_byte=False)` returned `sym+1` unconditionally for non-const variables
- Lines 5688-5692 (init chained add): raw `x_asm+1` / `y_asm+1` without type check
- Lines 11249-11253 (assign chained add): same pattern
- Lines 11120-11127 (assign direct var+var): used `_sym_operand` (now fixed via fix #1)

**Fix:**
1. `codegen_expr.py:_sym_operand` — when `low_byte=False` and sym is BYTE (non-pointer, non-WORD): return `"#$00"` instead of `sym+1`. BYTE variables have a logical high byte of 0; `ADC #$00` / `LDA #$00` correctly propagates the carry.
2. Lines 5688-5692: replaced raw `x_asm+1` / `y_asm+1` with `self._sym_operand(x_sym/y_sym, low_byte=False)`.
3. Lines 11249-11253: same replacement.

**Test results:** 162 pass / 123 fail — all OK.

---

## Fix: `ptr[i]` element width used pointer size instead of pointed-to type size (2026-03-12)

**Bug:** `dst[3]` on `byte^ dst` computed offset `3*2=6` (WORD size) instead of `3*1=3` (BYTE size).

**Root cause:** `_calculate_element_width` returned 2 for any `is_pointer` symbol. This was correct for arrays of pointers (`byte^ arr[N]` — each stored element IS a pointer = 2 bytes), but wrong for pointer variables (`byte^ dst` — subscript strides through the pointed-to type: 1 for `byte^`, 2 for `word^`, 4 for `long^`, struct-size for struct pointers).

**Fix:** `codegen_expr.py:_calculate_element_width` — added `sym.is_array` check: if pointer and array → element = 2 (pointer slot); if pointer and not array → element = size of `sym.type.base`.

**Test results:** 162 pass / 123 fail — all OK.

---

## Fix: `ptr[i]` subscript through pointer parameter wrong for all types (2026-03-12)

**Extended fix** for all data types (BYTE, WORD, LONG, struct pointer parameters).

Added `_load_sym_base_addr(sym)` helper that replaces `_load_sym_addr` in all subscript code paths:
- `_gen_subscript` single-dim general path (already fixed; now uses the helper)
- `_gen_multidim_subscript` compile-time-constant index path
- `_gen_multidim_subscript` runtime index path

The helper emits `LDA sym / LDX sym+1` for pointer parameters (all types) and `LDA #<sym / LDX #>sym` for static arrays.

**Test results:** 162 pass / 123 fail — all OK.

---

## Fix: `ptr[i] = val` didn't write through pointer parameter (2026-03-12)

**Bug:** Subscript assignment through a pointer parameter (e.g. `dst[3] = 'Y'` where `dst: byte^`) wrote to the wrong address. The generated code loaded `LDA #<_DST / LDX #>_DST` (the static address *of* the pointer variable itself) instead of `LDA _DST / LDX _DST+1` (the runtime address *stored in* the pointer).

**Root cause:** `_gen_subscript` in `codegen_expr.py` (~line 7076) called `_load_sym_addr(sym.asm_name())` for all non-const non-ROM-array cases. This is correct for static arrays (whose address is a compile-time constant) but wrong for pointer-typed variables (whose value must be loaded from memory at runtime).

**Fix:** `codegen_expr.py` — in the `else` branch of `_gen_subscript`, check `sym.type.is_pointer and not sym.is_array`. If true, emit `LDA sym / LDX sym+1` (load pointer value); otherwise emit the static `#<sym / #>sym` address as before.

**Test results:** 162 pass / 123 fail — all OK.

---

## Fix: `return` on its own line consumed next statement as expression (2026-03-12)

**Bug:** `return` (with no expression) followed by code on the next line caused a confusing parse error.
The next line's identifier was consumed as the return expression, leaving the `+=`/`-=` operator stranded.
Example: `return` then `max -= m` on the next line → `error: Expected identifier or '(' in assignment target` at `-=`.

**Root cause:** `parse_stmt` RETURN handler (parser.py ~1615) checked only that the next token was not EOF/keyword, not whether it was on the same line. Any identifier on the following line was greedily consumed as the return expression.

**Fix:** `parser.py` — added `self.cur.line == start_line` guard: expression is only parsed when it appears on the **same line** as `return`.

**Test results:** 162 pass / 123 fail — all OK.

---

## Standard Library Documentation (2026-03-12)

Added comprehensive documentation for all ZAP! standard library files in `work/lib/`.

**New files:**
- `DOC/STDLIB.md` — full API reference: all modules, exports, function signatures, return values, hardware register tables, usage examples, and implementation status matrix
- `work/lib/README.md` — quick-reference index with module names, dependency graph, and summary API tables

**Updated source files (inline header comments added):**
- `work/lib/errno.zap` — module header with description and export list
- `work/lib/types.zap` — module header with description and export list
- `work/lib/string.zap` — module header with full export list and return-value convention note
- `work/lib/stdio.zap` — module header explaining platform-conditional design
- `work/lib/atari/atari_stdio.zap` — detailed module header listing all exported symbols with implementation status
- `work/lib/atari/atari_gtia.zap` — hardware file header explaining dual read/write register model
- `work/lib/atari/atari_pokey.zap` — hardware file header describing 4-channel audio model
- `work/lib/atari/PIA.zap` — hardware file header describing PORTA/PORTB roles

**Updated documentation files:**
- `DOC/README.md` — added "Standard Library" section with module table and link to STDLIB.md
- `DOC/ADVANCED_TOPICS.md` — added stdlib usage examples and reference to STDLIB.md in "Module System Deep Dive" section

No compiler source files changed. Test count unchanged: 162 pass / 123 fail.

---

## Precise identifier error positions (2026-03-12)

**Problem:** Errors about undefined variables pointed to the start of the enclosing *statement* instead of the exact identifier token.
Example: `a = b + undefined_var` reported col 5 (statement start) instead of col 13 (the identifier).

**Root cause:** `sema_expr.py` called `self.symtab.lookup(expr.name)` without `node=expr`, so `SymbolTable.lookup` raised `SemanticError` with `node=None` — `e.line=None, e.col=None`. Error handlers fell back to the statement's position.

**Fix:**
- `sema_expr.py:47` — pass `node=expr` to identifier lookup; removed dead `except KeyError` block
- `sema_expr.py:354` — pass `node=arg` in SIZEOF lookup; changed `except KeyError` → `except SemanticError`
- `symbols.py:ScopedSymbolTable.lookup` — pass `node` through to local table so errors from both local and global scope carry the node

**Updated 5 .err reference files** (column moved to exact identifier): 028, 034, 044, 045, 063.

**Test results:** 162 pass / 123 fail — all OK.

---

## Double-mapped line number fix (2026-03-12)

**Problem:** Error positions off by ~3 lines in multi-file projects (e.g. `string.zap:124:9` instead of `121:9`).

**Root cause:** Line numbers were being mapped from clean-source → original-file *twice*:
- `map_stmt_info()` (in `sema_shared.py`) correctly maps clean→original line, returns it in `(fname, orig_line, col)`
- Error handlers in `sema_proc.py` didn't set `_line_mapped = True` on the resulting error
- `compiler.py`'s except-block then re-applied `orig_map` (121 → 124)

**Files fixed:**
- `sema_proc.py` — 5 sites: `_validate_expr`, `_on_call_stmt`, `_on_return_stmt`, and 2 sites in `analyze_call()`: added `orig_map` guard (`if e.line is not None`) + `_line_mapped = True`
- `sema_shared.py` — `_raise_with_stmt_info()`: same guard + flag
- `sema_func.py` — 2 sites (`validate_expr` + return-stmt handler): guarded the already-present `orig_map` step with `if e_line is not None`
- `codegen_expr.py` — 2 sites (`_raise_error` + `tc_check`): added `e._line_mapped = True`

**Verified:** `string.zap:121:9: error: Undefined variable 'DST1'` ✓
**Test results:** 161 pass tests OK (1 pre-existing UnicodeEncodeError in test 152 — Windows charmap issue unrelated to changes), 123 fail tests OK.

---

## Fail test error message verification (2026-03-11)

- Created `.err` reference files for all 124 fail tests — each contains the portable `line:col: error: message` portion
- Modified `Makefile` fail-test section: captures compiler stderr, strips path prefix, compares against `.err` reference using prefix match
- Modified `make.bat` fail-test section: same logic using Python for reliable cross-platform comparison
- Summary now reports "verified message" vs "no .err reference" counts and "wrong error messages" count
- Special handling for test 131-include-missing: `.err` stores portable prefix (excludes machine-specific path in message body)
- Clean targets updated to remove `*.actual_err` temp files but preserve `.err` references

---

## Error reporting system repair (2026-03-11)

**Phase 1: Critical infrastructure fixes**
- `compiler_pipeline.py:1536`: Fixed "missing main" detection — `ProcTable.lookup()` raises `SemanticError`, not `KeyError`; `except` now catches both. User-friendly message "Program must have a 'main()' procedure" now works.
- `codegen_expr.py`: Fixed 7 error sites using `getattr(self, 'current_expr', None)` (always None) — replaced with actual expression nodes from call context (`operand`, `struct_expr`).
- `errors.py:print_exception()`: No longer leaks Python exception class names (e.g. `SemanticError:`) in user-facing output. `CompileError` subclasses use `e.message`, non-compiler exceptions still show class name for debugging.
- `codegen_expr.py:_str_to_bytes()` and `_str_to_asm_directive()`: converted from `@staticmethod` to instance methods so they can use `_raise_error()` for proper location info.
- `codegen_expr.py:9880`: Changed bare `raise SemanticError(...)` to `self._raise_error(...)` for proper location.

**Phase 2: Preprocessor location info**
- `preprocessor.py`: `.ifdef`/`.ifndef` stack now tracks opening line number; "Unclosed .ifdef/.ifndef" error reports the line of the opening directive.

**Phase 3: Message quality**
- `sema_expr.py`, `sema_proc.py`: Fixed pluralization — "expects 1 parameter" (was "expects 1 parameters"), "1 was provided" (was "1 were provided").

**Phase 4: Stale .ref files updated**
- 002-byte-type-error, 006-if-statement-error, 008-while-loop-error, 013-comparison-operators-error

**Phase 5: Populated 33 empty fail test directories**
- 009, 012, 015, 017, 020, 021, 022, 025, 027, 029, 031, 033, 035, 036, 038, 039, 042, 043, 046, 048, 049, 051, 054, 056, 057, 058, 059, 060, 061, 062, 063, 064, 065

**Phase 6: Created 18 new fail tests for untested error paths**
- missing-asm-end, static-global-error, static-const-error, static-no-init-error, port-const-error, port-no-addr-error, port-array-error, port-pointer-error, port-init-error, const-no-init-error, list-init-scalar-error, switch-no-case-error, repeat-no-until-error, continue-outside-loop, preproc-ifdef-unclosed, preproc-else-no-ifdef, preproc-endif-no-ifdef, sizeof-non-struct-error

**Test results:** 162 pass tests compile, 123 fail tests correctly rejected, 0 regressions.

---

## Generated label numbering fix (2026-03-10)
`__ZAP_NOCARRY_ARRFIELD_{id(expr)}` labels replaced with sequential `new_label()` counter.
All 7 NOCARRY_* sites in `codegen_expr.py` now emit short readable labels like `__ZAP_NOCARRY_ARRFIELD_134`.

---

## Liveness / slot-sharing and codegen fixes (2026-03-10)

**Bug 1: `KeyError` on undefined identifiers reported as `1:1`**
- `SymbolTable.lookup()` now raises `SemanticError("Undefined variable '...'")` instead of leaking `KeyError`
- `ScopedSymbolTable.lookup()` catches `SemanticError` (not `KeyError`) from local table
- `constsubst.py`: wraps lookup in `try/except SemanticError`; unknown identifiers return expr unchanged
- Result: `test.zap:30:5: error: Undefined variable 'TEXT1'` instead of `test.zap:1:1: error: KeyError: 'TEXT1'`

**Bug 2: Wrong second byte argument in two-BYTE-param function calls**
- `_emit_call_args` `reorder_regs` path for `"two_bytes"`: X was loaded first, then A was evaluated — but A evaluation (e.g. pointer field access) clobbers X
- Fix: evaluate A argument first, then load X (IntLiteral/simple Identifier never touches A)
- Example: `CIO(fd^.fd, 9, ...)` was passing command=garbage instead of 9

**Bug 3: Liveness analysis misses call-argument variables in `call_live_across`**
- `CallStmt`: updated `call_live_across` with `live` only, not argument variables (`uses`)
- `AssignStmt`: used `live | uses_lhs` but not `uses_rhs`
- Effect: variables used ONLY as call arguments (not live after) not marked as interfering with callee locals → slot aliasing
- Symptom: `CIO(i, ...)` — `i` aliased with `_CIO_AUX1` when `i` had no uses after the call (e.g. commenting out `putx(i)`)
- Fix: `CallStmt` → `live | uses`; `AssignStmt` → `live | uses_lhs | uses_rhs`

All 162 pass + 73 fail tests pass.

---

## OPT-3: Redundant LDA #imm elimination (wide window) (2026-03-10)

Second-pass peephole optimization: removes `LDA #imm` when A is already known to hold
that immediate value, across arbitrarily long sequences of A-safe instructions.

**Method**: `_eliminate_redundant_imm_lda(code)` in `codegen_expr.py`, called at end of
`peephole_optimize()` after the existing single-pass loop.

**Algorithm**:
- Tracks `known_a: int | None` — current known A immediate value
- `LDA #imm`: if `known_a == imm` → remove (redundant); else set `known_a = imm`
- A-safe instructions (STA/STX/STY/STZ/LDX/LDY/CMP/CPX/CPY/BIT/TAX/TAY/PHA/PHX/PHY/INX/
  INY/DEX/DEY/INC/DEC/flag ops): leave `known_a` unchanged
- Control-flow (JSR/JMP/RTS/RTI/branches) and labels: reset `known_a = None`
- All other instructions (TXA/TYA/PLA/ADC/SBC/AND/ORA/EOR/shifts/LDA mem): reset `known_a = None`

**Example eliminated pattern** (from CIO-style code):
```asm
LDA #$00           ; ← kept
LDX #$00
STA _CIO_ADR
STX _CIO_ADR+1
LDA #$00           ; ← eliminated
STA _CIO_LEN
STX _CIO_LEN+1
LDA #$00           ; ← eliminated
STA _CIO_AUX1
STA _CIO_AUX2
LDA #$00           ; ← eliminated
STA _CIO_AUX3
```

All 162 pass + 73 fail tests pass.

---

## String literal high-byte fix: unified \xHH handling (2026-03-10)

**Bugs fixed:**
1. `UnicodeEncodeError: 'ascii' codec` when string literal with `\x80`–`\xFF` was used as a
   function argument or in a short (≤3 char) variable initializer — reported as `file:1:1`
2. Divergent code paths: `const byte arr[] = "...\x9b"` worked; same string as function
   argument or variable init crashed
3. Raw non-ASCII source characters in string literals silently accepted

**Changes:**
- `codegen_expr.py`: two static helpers `_str_to_bytes()` and `_str_to_asm_directive()`;
  both `.encode('ascii')` calls replaced
- `codegen_expr.py:_gen_string_data()`: emits `.byte "ASCII", $9B, $00` readable mixed format
- `tokenizer.py`: raw chars > 0x7F in string literals → `TokenizerError` with correct line/col
- `DOC/ZAP_LANGUAGE_REFERENCE.md`: documented high-byte rule and assembly output format

**Tests:** `pass/173-string-highbyte` (7 checks); `fail/string-raw-nonascii`.
All 162 pass + 73 fail tests pass.

---

## OPT-1: Compile-time constant array index folding (2026-03-10)

When an array index is a compile-time constant expression (const identifier, enum member,
or arithmetic on consts), the compiler now evaluates the complete byte offset at compile
time and emits a direct `LDA #<offset; LDX #>offset` pair instead of a runtime multiply.

**Helper**: `_try_eval_const(expr)` — wraps `eval_const_expr` from `sema.py`, returns
`int | None`. Returns `None` for any runtime expression.

**Changed locations:**
- `_gen_subscript()` fast path: folded index replaces `isinstance(index, IntLiteral)` check
- `_gen_subscript()` general path: const-fold skips `gen_expr` + multiply block entirely
- `_gen_multidim_subscript()`: per-index fold; all-const → compile-time total offset
- `_gen_address_of()` `@array[index]` path: const-fold produces `LDA #<(label+off); LDX #>(label+off)`
- `_gen_multidim_subscript()` runtime loop bug fixed: replaced ad-hoc multi-case multiply with `_gen_index_multiply(stride_val)` call

**Tests:** `pass/171-const-fold-array-index` (8 checks: byte/word/struct arrays with const,
const-1, and const-expr indices). All 161 pass-tests pass.

---

## OPT-2: Shift-add for explicit multiply by small constant (2026-03-10)

Extended the RPN evaluator MUL power-of-2 optimization block to also handle non-power-of-2
constants with ≤3 set bits when the left operand is BYTE. Calls `_gen_index_multiply(n)`,
eliminating `JSR MUL8`.

Examples: `a * 3`, `a * 5`, `a * 6`, `a * 10`, `a * 12`, `3 * a` (commutative swap).

**Changed:** `codegen_expr.py` RPN evaluator ~line 886 — added `elif` branch after power-of-2
check. `200-ops-byte.ref` updated (ZP layout changed: TMP3/TMP4 now allocated for this test).

**Tests:** `pass/172-mul-small-const` (8 checks: ×3, ×5, ×6, ×10, ×12, commutative, ×4, ×8).
All 161 pass-tests + 72 fail-tests pass.

---

## Compile-time constant multiply optimization: shift-add decomposition (2026-03-10)

Added `_gen_index_multiply(n)` helper to `codegen_expr.py`. Replaces repeated-addition loops
for all compile-time element-size multiplications with optimal shift sequences:

- **n = 2^k**: `k × (ASL TMP3; ROL A)` — pure shifts, zero adds
- **n with ≤3 set bits** (e.g. 3, 5, 6, 10, 12, 24): shift-add decomposition — one `ASL TMP3; (BCC; INC TMP4+1)` pair per bit position + one `CLC/ADC TMP4/STA TMP4/(BCC; INC TMP4+1)` per term
- **n with >3 set bits**: fallback to repeated addition (rare for realistic struct sizes)

**Before** (e.g. struct size 16, `arr[i]`): 85 instructions (16 × 5-instruction add loop)
**After**: 14 instructions (4 shifts + bookkeeping)

**Changed locations:**
- `_gen_subscript()` — array index × element_width (replaces broken elem_width==2 path too)
- `_gen_add()` — pointer arithmetic offset scaling
- `_gen_sub()` — pointer arithmetic offset scaling (had same `ptr_elem_size==2` only bug)
- `@array[index]` — address-of subscript; now supports any element size (was error for >4)

**Tests:** `pass/164-struct-array-pow2-index` (S4/S8/S16), `pass/165-struct-array-mixed-index` (S3/S5/S6/S12). All 231 tests pass.

---

## Peephole: generalized dead LDX #0 + LDX/TXA→LDA rules (2026-03-10)

Replaced the narrow `LDA; LDX #0; STA` triple rule with two independent rules:

**1. Generalized dead LDX #0**: triggers whenever the current line IS `LDX #0` (regardless
of what precedes or follows). Forward liveness scan verifies X is overwritten before being
read; if so, the `LDX #0` is simply skipped. This covers `LDX #0; CMP`, `LDX #0; STA`,
and any other following instruction.

**2. LDX <mem>; [non-X code]; TXA → [non-X code]; LDA <mem>**: when X is loaded from a
memory address and the only subsequent use is `TXA` (copy X→A, before X is overwritten),
replace `TXA` with `LDA <mem>` and remove the `LDX`. Safe because `LDA` does not affect
carry. Both forward scans (scan1: LDX→TXA, scan2: after TXA to X overwrite) are required
to pass. Stops conservatively at JSR/JMP/RTS.

Fired on 7 of 8 occurrences in `work/test_stdio.s`; 8th cannot fire because the scan
hits `RTS` before finding an X overwrite (correct conservative behaviour).

**Tests**: all 229 tests pass. No regressions.

---

## Peephole: dead LDX #0 elimination after LDA/STA (2026-03-10)

Added a forward-liveness peephole rule to `codegen_expr.py` that removes a dead `LDX #0`
in the pattern `LDA <src>; LDX #0; STA <dst>`.

`LDX #0` appears when a BYTE value is zero-extended to WORD (`A=value, X=0`) but only the
low byte is then saved (`STA <dst>`), leaving X=0 unused.

**Liveness check**: scan forward from `i+3`, skipping blank/comment lines and labels,
stopping at JSR/JMP/RTS (unknown control flow).  If X is overwritten (`LDX`, `TAX`, `TSX`,
`PLX`) before being read (`STX`, `TXA`, `TXS`, `DEX`, `INX`, `CPX`, `PHX`, or any `,X`
operand), the `LDX #0` is dead and removed.

Works correctly for the struct-array-index multiplication pattern, where X stays dead
across 100+ lines of `CLC/LDA/ADC/STA/BCC/INC` + labels before X is overwritten.

**Tests**: all 229 tests pass. No regressions.

---

## Peephole: LDX #0 / TXA → LDA #$00 (2026-03-10)

Fixed and generalised an existing (broken) peephole rule in `codegen_expr.py`:

```
Before:  LDX #$00 / CLC / ADC <mem> / STA <mem> / TXA
After:   CLC / ADC <mem> / STA <mem> / LDA #$00
```

`LDX #0` followed by `TXA` is just a slow way to put 0 into A.  Replace with `LDA #$00`
and drop the now-dead `LDX`.  The original rule had two bugs: the `in {…}` set
contained the same string three times (should have covered `#0`, `#00`, `#$00`), and
it hardcoded `TMP0` instead of matching any memory operand.  Also fixed: the rule was
in the section that cannot yet call `_parse_inst` (defined later in the loop body), so
the rewrite uses direct string splitting instead.

**Tests**: all 229 tests pass. No regressions.

---

## Peephole: indirect WORD load + store optimization (2026-03-10)

Added a 7→6 instruction peephole rule for loading a WORD via an indirect ZP pointer and storing it to a memory destination:

| Before | After |
|---|---|
| `LDY #1` | `LDY #1` |
| `LDA (ptr),Y` | `LDA (ptr),Y` |
| `TAX` | `STA dst+1` |
| `DEY` | `DEY` |
| `LDA (ptr),Y` | `LDA (ptr),Y` |
| `STA dst` | `STA dst` |
| `STX dst+1` | |

**Safety**: restricted to internal-temp pointers (`TMP*`, `__TMP*`) to avoid slot-aliased user-variable hazards.  Correctly skipped when the result feeds a `JSR` (X must hold the high byte).

**Tests**: all 229 tests pass. No regressions.

---

## Peephole: 16-bit register shuffle elimination (2026-03-10)

### What was done

Added three new peephole rules to `codegen_expr.py:peephole_optimize()` that eliminate the
`TAY / TAX / TYA` register shuffle emitted whenever a 16-bit arithmetic result is stored
directly to memory.  The shuffle was needed to pass the 16-bit result in `(A, X)` from the
generator back to the caller, but when the caller immediately stores with `STA / STX`, the
three transfer instructions are dead (STA/STX never modify the carry flag or accumulator).

| Pattern | Before | After | Saved |
|---|---|---|---|
| ADD → store | `ADC mem; TAY; LDA x; ADC mem+1; TAX; TYA; STA dst; STX dst+1` | `ADC mem; STA dst; LDA x; ADC dst+1; STA dst+1` | 3 instr |
| SUB → store | `LDA a; SBC b; TAY; LDA c; SBC d; TAX; TYA; STA dst; STX dst+1` | `LDA a; SBC b; STA dst; LDA c; SBC d; STA dst+1` | 3 instr |
| AND/ORA/EOR → store | `op mem; TAY; TXA; op mem+1; TAX; TYA; STA dst; STX dst+1` | `op mem; STA dst; TXA; op mem+1; STA dst+1` | 3 instr |

PORT-mapped destinations are excluded from the optimization.

**Tests**: all 229 tests pass. No regressions.

---

## Dead code removal sweep (2026-03-10)

### What was done

Scanned all 25 compiler `.py` files and removed 5 categories of dead code:

| | File | What | Lines |
|---|---|---|---|
| A | `identifier.py` | Entire file deleted — legacy `Identifier`/`Identifiers` classes, never imported anywhere | −147 |
| B | `label_cleanup.py` L114–116 | Unreachable `if label not in used` inner check — control only reaches that line when `label in used`; removed the dead branch and replaced comment | −5 |
| C | `compiler.py` L41 | `return ""` after unconditional `sys.exit(1)` | −1 |
| D | `compiler.py` L7 | Duplicate `import os` | −1 |
| E | `dce.py` L2 | Duplicate `Expr` in import list | −1 |

| F | `parser.py` L3–35 | 32 redundant `from ast_nodes import X` lines (all superseded by `from ast_nodes import *`) | −32 |

**Tests**: all 229 tests pass. No regressions.

---

## Refactor: parse_declarator() dead code removal (2026-03-10)

### What was done

Deleted ~160 lines of unreachable dead code from `parser.py:parse_declaration`.

**Root cause**: `parse_declaration` contained a complete second copy of its
implementation (pointer parsing, `_is_sqb`/`_expect_sqb` helpers,
`parse_declarator` closure, declarator loop, DECLMOD loop, and return statement)
starting immediately after the first `return Declaration(…)` at line 876.  The
second block was entirely unreachable and was an outdated snapshot from before
`#PORT`, `#RD`, `#WR` support was added to the first path:

| Feature | First path (active) | Second path (dead) |
|---|---|---|
| `CONST`/`STATIC` modifiers | ✅ | ❌ missing |
| `#PORT`, `#RD`, `#WR` | ✅ | ❌ missing |
| `port_rd`/`port_wr` in Declaration | ✅ | ❌ missing |

**Fix**: deleted the entire dead block (−160 lines).  No logic change.

**Tests**: all 229 tests pass. No regressions.

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

---

## 2026-04-02: Regression test fixes

### Changes
- **test 205-peek-poke**: Added missing `.ref` reference file — test was producing correct simulation output but had no reference to compare against.
- **test 111-error-directive**: Fixed expected error location from `3:1` to `1:1` — the `.error` directive is on line 1; the stale `3:1` came from when error directives were processed during codegen rather than in module_system.py.

### Verification
- `make tests`: 173/173 pass-tests pass, 132/132 fail-tests correctly rejected — 0 regressions.
