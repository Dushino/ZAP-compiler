#!/usr/bin/env python3
"""Test enhanced escape sequences"""

from tokenizer import Tokenizer
from token_types import TOK_STRING, TOK_NUMBER

tests = [
    # Standard escapes (already working)
    ('x = "hello\\nworld"', "hello\nworld", "newline"),
    ('x = "tab\\there"', "tab\there", "tab"),
    ('x = "quote\\"test"', 'quote"test', "double quote"),
    ("x = ' '", ord(' '), "space as char"),
    
    # New: null terminator
    ('x = "hello\\0"', "hello\0", "null terminator"),
    ('x = "\\0\\0"', "\0\0", "multiple nulls"),
    
    # New: hex escapes
    ('x = "\\x00"', "\0", "hex null"),
    ('x = "\\xFF"', "\xFF", "hex 255"),
    ('x = "\\xAB"', "\xAB", "hex mixed case"),
    ('x = "\\x41"', "A", "hex letter A"),
    
    # New: octal escapes
    ('x = "\\0"', "\0", "octal 0"),
    ('x = "\\377"', "\377", "octal 255 (max)"),
    ('x = "\\101"', "A", "octal 65 (letter A)"),
    ('x = "\\12"', "\12", "octal 10 (newline)"),
    
    # New: binary escapes
    ('x = "\\b00000000"', "\0", "binary 0"),
    ('x = "\\b11111111"', "\xFF", "binary 255"),
    ('x = "\\b01000001"', "A", "binary 65 (letter A)"),
    
    # Additional standard escapes
    ('x = "bell\\a"', "bell\a", "bell"),
    ('x = "\\b"', "\b", "backspace"),
    ('x = "\\f"', "\f", "form feed"),
    ('x = "\\v"', "\v", "vertical tab"),
    ('x = "\\r"', "\r", "carriage return"),
    
    # Character literals with escapes
    ("x = '\\0'", 0, "char null"),
    ("x = '\\x41'", ord('A'), "char hex A"),
    ("x = '\\101'", ord('A'), "char octal A"),
    ("x = '\\b01000001'", ord('A'), "char binary A"),
]

print("=" * 70)
print("ENHANCED ESCAPE SEQUENCES TEST SUITE")
print("=" * 70)

passed = 0
failed = 0

for code, expected, description in tests:
    try:
        tokenizer = Tokenizer(code)
        tokenizer.tokenize()
        tokens = tokenizer._getTokens()
        
        # Find the string or number token
        token = None
        for t in tokens:
            if t.type in (TOK_STRING, TOK_NUMBER):
                token = t
                break
        
        if token is None:
            print(f"✗ {description}: No token found")
            failed += 1
            continue
        
        if token.type == TOK_STRING:
            actual = token.value
            expected_val = expected
        else:  # TOK_NUMBER (character literal)
            actual = int(token.value)
            expected_val = expected
        
        if actual == expected_val:
            print(f"✓ {description}")
            passed += 1
        else:
            if isinstance(actual, str):
                print(f"✗ {description}: expected {repr(expected_val)}, got {repr(actual)}")
            else:
                print(f"✗ {description}: expected {expected_val}, got {actual}")
            failed += 1
    except Exception as e:
        print(f"✗ {description}: {e}")
        failed += 1

print()
print("=" * 70)
print(f"RESULTS: {passed}/{len(tests)} tests passed")
print("=" * 70)
