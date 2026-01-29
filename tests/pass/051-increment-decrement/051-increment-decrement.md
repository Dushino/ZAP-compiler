# Test 024: Increment/Decrement

## Purpose
Tests increment operation on byte values (x = x + 1).

## Memory Validation
- x = 10 initially
- x = x + 1 = 11 (0x0B)
- result @40000 ($9C40) = x = 11

## Expected Output
Successful compilation and execution with result = 0x0B at address $9C40.
