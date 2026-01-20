# Test 028: String Literals

## Purpose
Tests string literal initialization and character access.

## Memory Validation
- str[5] = "ZAPA": byte array initialized with string literal
- str[0] = 'Z' (ASCII 0x5A)
- result @40000 ($9C40) = str[0] = 0x5A

## Expected Output
Successful compilation and execution with result = 0x5A at address $9C40.
