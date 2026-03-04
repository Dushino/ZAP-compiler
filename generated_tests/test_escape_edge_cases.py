#!/usr/bin/env python3
"""Test escape sequence edge cases: shorter digit counts, errors, char literals."""

import sys
sys.path.insert(0, '.')

from tokenizer import Tokenizer

passed = 0
failed = 0

def test(code, desc, expect_value=None, expect_error=False):
    global passed, failed
    try:
        t = Tokenizer(code)
        t.tokenize()
        tokens = t._getTokens()
        if expect_error:
            print(f"FAIL {desc}: expected error but got none")
            failed += 1
            return
        for tok in tokens:
            if tok.type in ('STRING', 'NUMBER'):
                if tok.type == 'STRING':
                    actual = [ord(c) for c in tok.value]
                else:
                    actual = [int(tok.value)]
                if actual == expect_value:
                    print(f"PASS {desc}")
                    passed += 1
                else:
                    print(f"FAIL {desc}: expected {expect_value}, got {actual}")
                    failed += 1
                return
        print(f"FAIL {desc}: no STRING/NUMBER token found")
        failed += 1
    except Exception as e:
        if expect_error:
            print(f"PASS {desc} (error: {e})")
            passed += 1
        else:
            print(f"FAIL {desc}: unexpected error: {e}")
            failed += 1


print("=" * 70)
print("ESCAPE SEQUENCE EDGE CASES")
print("=" * 70)

# --- HEX: 1-digit ---
print("\n--- Hex escapes: short digit counts ---")
test('byte x = "\\xF"', r'\xF (1 hex digit) => 15', [15])
test('byte x = "\\x0"', r'\x0 (1 hex digit) => 0', [0])
test('byte x = "\\xA"', r'\xA (1 hex digit) => 10', [10])

# --- HEX: 2-digit (normal) ---
print("\n--- Hex escapes: 2 digits (normal) ---")
test('byte x = "\\xFF"', r'\xFF => 255', [255])
test('byte x = "\\x00"', r'\x00 => 0', [0])
test('byte x = "\\x41"', r'\x41 => 65 (A)', [65])

# --- HEX: errors ---
print("\n--- Hex escapes: errors ---")
test('byte x = "\\xGG"', r'\xGG (no valid hex digits)', expect_error=True)
test('byte x = "\\x"', r'\x (no digits at all, EOF)', expect_error=True)

# --- BINARY: fewer than 8 digits ---
print("\n--- Binary escapes: short digit counts ---")
test('byte x = "\\b1"', r'\b1 (1 binary digit) => 1', [1])
test('byte x = "\\b0"', r'\b0 (1 binary digit) => 0', [0])
test('byte x = "\\b1111"', r'\b1111 (4 binary digits) => 15', [15])
test('byte x = "\\b10"', r'\b10 (2 binary digits) => 2', [2])
test('byte x = "\\b111"', r'\b111 (3 binary digits) => 7', [7])

# --- BINARY: 8-digit (normal) ---
print("\n--- Binary escapes: 8 digits (normal) ---")
test('byte x = "\\b11111111"', r'\b11111111 => 255', [255])
test('byte x = "\\b00000000"', r'\b00000000 => 0', [0])
test('byte x = "\\b01000001"', r'\b01000001 => 65 (A)', [65])

# --- BINARY: errors ---
print("\n--- Binary escapes: errors ---")
test('byte x = "\\b2"', r'\b2 (invalid binary digit)', expect_error=True)
test('byte x = "\\bx"', r'\bx (non-digit after \b)', expect_error=True)

# --- OCTAL: 1-3 digit variants ---
print("\n--- Octal escapes: digit count variants ---")
test('byte x = "\\0"', r'\0 (1 octal digit) => 0', [0])
test('byte x = "\\7"', r'\7 (1 octal digit) => 7', [7])
test('byte x = "\\77"', r'\77 (2 octal digits) => 63', [63])
test('byte x = "\\12"', r'\12 (2 octal digits) => 10', [10])
test('byte x = "\\101"', r'\101 (3 octal digits) => 65 (A)', [65])
test('byte x = "\\377"', r'\377 (3 octal digits) => 255', [255])

# --- OCTAL: errors ---
print("\n--- Octal escapes: errors ---")
test('byte x = "\\400"', r'\400 (octal overflow > 255)', expect_error=True)

# --- CHAR LITERALS with short escapes ---
print("\n--- Char literals with escape edge cases ---")
test("byte x = '\\xF'", r"'\xF' char hex 1-digit => 15", [15])
test("byte x = '\\b1111'", r"'\b1111' char binary 4-digit => 15", [15])
test("byte x = '\\7'", r"'\7' char octal 1-digit => 7", [7])
test("byte x = '\\77'", r"'\77' char octal 2-digit => 63", [63])
test("byte x = '\\377'", r"'\377' char octal max => 255", [255])

# --- MIXED in one string ---
print("\n--- Mixed escapes in single string ---")
test('byte x = "\\x41\\101\\b01000001"', r'\x41\101\b01000001 => AAA', [65, 65, 65])
test('byte x = "\\xF\\7\\b1"', r'\xF\7\b1 => 15,7,1', [15, 7, 1])

print()
print("=" * 70)
total = passed + failed
print(f"RESULTS: {passed}/{total} tests passed, {failed} failed")
print("=" * 70)
