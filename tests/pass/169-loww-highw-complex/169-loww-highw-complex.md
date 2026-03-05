# Test 169: LOWW/HIGHW on Complex Expressions

## Purpose
Tests LOWW() and HIGHW() on complex expressions (not just identifiers/literals):
- Arithmetic: `LOWW(la + lb)`, `HIGHW(la + lb)`
- Struct field access: `LOWW(ls.val)`, `HIGHW(ls.val)`
- Also LOW/HIGH on long arithmetic for completeness

## Memory Validation
- result @40000 = 0x06 (6 checks passed)

## Checks
1. `LOWW(la + lb) == $5679` — low word of $12345679
2. `HIGHW(la + lb) == $1234` — high word of $12345679
3. `LOW(la + lb) == $79` — low byte of $12345679
4. `HIGH(la + lb) == $56` — byte 1 of $12345679
5. `LOWW(ls.val) == $0011` — low word of struct field
6. `HIGHW(ls.val) == $AABB` — high word of struct field
