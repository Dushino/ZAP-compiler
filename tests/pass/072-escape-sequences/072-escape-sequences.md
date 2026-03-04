# Test 072: Hex, Octal, and Binary Escape Sequences

## Purpose
Tests numeric escape sequences in character and string literals:
- `\xHH` — hex (1-2 digits)
- `\OOO` — octal (1-3 digits)
- `\bBBBBBBBB` — binary (1-8 digits)

Tests both full-length and short (fewer digits) variants.

## Memory Validation
- r1 @40000 = 0xFF (255) — `\xFF` hex full
- r2 @40001 = 0x0F (15) — `\xF` hex short
- r3 @40002 = 0xFF (255) — `\377` octal max
- r4 @40003 = 0x41 (65) — `\101` octal 'A'
- r5 @40004 = 0x07 (7) — `\7` octal short
- r6 @40005 = 0xFF (255) — `\b11111111` binary full
- r7 @40006 = 0x0F (15) — `\b1111` binary short
- r8 @40007 = 0x41 (65) — mixed string `\x41\101\b01000001` first byte

## Expected Output
All escape sequences produce correct byte values at their respective addresses.
