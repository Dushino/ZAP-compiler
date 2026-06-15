# ToDO

[ ] check if HIGH(BYTE) or HIGHW(BYTE) or HIGHW(WORD) allways results in 0 - issue a warning

Here is the full audit report with implementation plan.

ZAP! Compiler — Datatype Coverage Audit
Coverage Matrix
Datatype	Arith (+-*/%)	Logic (&&||!)	Bitwise (&|^~<<>>)	Unary (-~!)	Assign (same)	Assign (cross)	Compare (==<>)	Ptr arith	Array idx	Compound (+=etc)
BYTE	✓	✓	✓	✓	✓	✓	✓	n/a	✓	✓
WORD	✓	~ no &&|| test	~ byte→word only	~ only ! tested	✓	✓	✓	n/a	✓	~ +=−= only
LONG	✓	✗ missing	✓	✗ -LONG crashes linker	✓	✓	~ only in if, not as value	n/a	✓	~ +=−= only
byte^	~	~	n/a	~	✓	n/a	✓	✓	~	~
word^	~	~	n/a	~	✓	n/a	✓	✓	~	✗ untested
long^	~	~	n/a	~	✓	n/a	✓	✓	✓	~
struct^	n/a	n/a	n/a	n/a	✓	n/a	~	✓	n/a	✗ untested
Array[BYTE]	~	n/a	n/a	n/a	✓	n/a	n/a	n/a	✓	✓
Array[WORD]	~	n/a	n/a	n/a	✓	n/a	n/a	n/a	✓	~
Array[LONG]	✓	n/a	n/a	n/a	✓	n/a	n/a	n/a	✓	~
Struct	~ field ops	n/a	n/a	n/a	✓	n/a	✗ not supported	n/a	n/a	~ LONG only
Array[Struct]	~	n/a	n/a	n/a	✗ rejected	n/a	n/a	n/a	✓	~ LONG only
Legend: ✓ tested · ~ code exists, untested · ✗ gap/missing/broken

P1 — Critical Bugs (definite failures today)
Bug 1: NEG32 emitter is missing
Any z = -long_var compiles and assembles to JSR NEG32, but _gen_math_routines has no entry for NEG32. Result: linker fails with undefined symbol. No test exercises this.

Bug 2: _gen_logical has no BinOp.LOR branch
When operands are not RPN-safe (array subscript, field access, deref, call), gen_expr falls back to _gen_logical. Only LAND is handled there; LOR silently generates no code at all. Example: if arr[i] || arr[j] compiles to a no-op.

Bug 3: _gen_relational value-context path is 16-bit only
flag = (long_a == long_b) uses _gen_relational (not _emit_relational_branch_impl). The is-16-bit check only branches for WORD, not LONG — falls into 8-bit CMP. The result is wrong for any LONG pair where bytes 1-3 differ.

P2 — Semantic Bugs (wrong results for valid programs)
Bug 4: _gen_logical truncates LONG to low byte
For LONG operands, _is_word_value returns False (it only checks for WORD), so _branch_if_zero emits a plain BEQ that tests only A (low byte). A LONG like $FF000000 has zero low byte — treated as false.

Bug 5: RPN LAND/LOR section also checks only MATH0 byte 0
Same issue in the fast path: LAND/LOR in the RPN evaluator tests only MATH0 (1 byte). LONG values with zero low byte are treated as false.

P2 — Untested Paths (code likely correct, no regression coverage)
#	Gap	Notes
P2.1	WORD bitwise: word & word, word | word, word ^ word, ~word	Only byte-widened-to-word tested
P2.2	WORD unary: -word, ~word	Only !word tested indirectly
P2.3	LONG && and || in conditions	All existing cond-tests use simple idents → fast path
P2.4	LONG compound: *=, /=, %=, &=, |=, ^=	Only +=, -=, <<=, >>= tested
P2.5	WORD compound: *=, /=, %=, &=, |=, ^=	Same gap
P2.6	Cross-type LONG vs BYTE/WORD compare in if-condition	e.g. if long_var == byte_var
P2.7	Deref compound assign: wptr^ += N, lptr^ += N	Only byte deref compound tested
P2.8	Struct WORD field compound: s.wfield += N	Only LONG field compound tested (test 225)
P2.9	Array[LONG] compound: larr[i] += N	Only scalar LONG += tested
P2.10	LONG comparison as value: byte f = (long_a < long_b)	Only if-context comparison tested
P3 — Documentation Gaps
KNOWN_LIMITATIONS.md — no entry for unary negation of LONG (linker crash)
KNOWN_LIMITATIONS.md — no entry for &&/|| upper-byte truncation on LONG
ZAP_LANGUAGE_REFERENCE.md — no note that || with complex LONG operands generates no code
ZAP_LANGUAGE_REFERENCE.md — cross-type comparison described as supported but value-context LONG compare is broken
ARCHITECTURE.md — _gen_relational description does not note the 32-bit value-context gap
Implementation Plan
Priority	Task	Files	New tests
P1-A	Add emit_neg32 routine + register it in _gen_math_routines emitters list	codegen_expr.py	226
P1-B	Add BinOp.LOR branch to _gen_logical (mirror of LAND, with _branch_if_nonzero)	codegen_expr.py	227
P1-C	Fix _gen_relational to detect LONG and delegate to 32-bit comparison path	codegen_expr.py	228
P2-A	Fix _gen_logical + RPN LAND/LOR section to check all 4 bytes for LONG operands	codegen_expr.py	229
P2-B	Add tests: WORD bitwise ops (& | ^ ~)	tests/pass/230	230
P2-C	Add tests: WORD unary - and ~	tests/pass/231	231
P2-D	Add tests: LONG compound *= /= %= &= |= ^=	tests/pass/232	232
P2-E	Add tests: WORD compound *= /= %= &= |= ^=	tests/pass/233	233
P2-F	Add tests: cross-type LONG vs BYTE/WORD comparisons	tests/pass/234	234
P2-G	Add tests: wptr^ += N, lptr^ += N	tests/pass/235	235
P2-H	Add tests: s.wfield += N struct WORD compound	tests/pass/236	236
P2-I	Add tests: larr[i] += N Array[LONG] compound	tests/pass/237	237
P2-J	Add tests: LONG && and || in conditions	tests/pass/238	238
P3	Update docs: KNOWN_LIMITATIONS, LANGUAGE_REFERENCE, ARCHITECTURE	docs/	—
Suggested order: P1-A → P1-B → P1-C (all are small, isolated fixes) → P2-A (touches same area as P1-B/C) → P2-B through P2-J (pure test additions, no code changes expected) → P3 docs.

Should I proceed with implementation, starting from P1-A (NEG32 emitter)?