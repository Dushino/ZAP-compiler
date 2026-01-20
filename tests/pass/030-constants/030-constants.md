# Test 030: Constants

## Purpose
Tests const keyword and constant value substitution.

## Memory Validation
- MAX_VALUE = 100 (0x64) [const]
- x = MAX_VALUE (assigns constant value to variable)
- result @40000 ($9C40) = x = 100

## Expected Output
Successful compilation and execution with result = 0x64 at address $9C40.
