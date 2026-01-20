# Test 029: Escape Sequences

## Purpose
Tests escape sequence values and arithmetic operations.

## Memory Validation
- tab = 9 (0x09) - represents \t
- newline = 10 (0x0A) - represents \n
- cr = 13 (0x0D) - represents \r
- result @40000 ($9C40) = tab + newline = 19 (0x13)

## Expected Output
Successful compilation and execution with result = 0x13 at address $9C40.
