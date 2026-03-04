# Test 168: Struct List Init with Nested Struct Field

## Purpose
Tests struct initialization with `{val, {nested_vals}}` syntax, including:
- Two-level nesting: `Outer o = {10, {20, 30}}`
- Three-level nesting: `Deep d = {1, {2, {3, 4}}}`

Verifies that all fields (including deeply nested ones) receive correct values.

## Memory Validation
- r1 @40000 = 0x0A (10) — `o.x`
- r2 @40001 = 0x14 (20) — `o.inner.a`
- r3 @40002 = 0x1E (30) — `o.inner.b`
- r4 @40003 = 0x01 (1)  — `d.tag`
- r5 @40004 = 0x02 (2)  — `d.outer.x`
- r6 @40005 = 0x03 (3)  — `d.outer.inner.a`
- r7 @40006 = 0x04 (4)  — `d.outer.inner.b`

## Expected Output
All nested struct fields correctly initialized at their respective memory offsets.
