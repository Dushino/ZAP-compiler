# Test 025: Assignment Chain

## Purpose
Tests chained variable assignments (a -> b -> result).

## Memory Validation
- a = 5 (0x05)
- b = a (assigns from a to b)
- result @40000 ($9C40) = b = 5

## Expected Output
Successful compilation and execution with result = 0x05 at address $9C40.
