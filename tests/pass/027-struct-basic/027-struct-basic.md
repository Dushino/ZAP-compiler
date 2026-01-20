# Test 027: Struct Basic

## Purpose
Tests basic struct definition and member access.

## Memory Validation
- struct Point with members: x (byte), y (byte)
- Instance p: p.x = 25 (0x19), p.y = 75 (0x4B)
- result @40000 ($9C40) = p.x = 25

## Expected Output
Successful compilation and execution with result = 0x19 at address $9C40.
