# Test 003: Basic Pointer Operations

## Feature
Tests basic pointer operations and variable copying.

## Description
This test demonstrates storing and retrieving values through variable assignment, simulating basic pointer-like behavior.

## Test Code
```zap
byte value @40000 = 0

proc main()
    byte target = 42
    value = target
end
```

## Expected Behavior
- Variable target initialized to 42 (0x2A)
- Value assigned from target: 42
- Result stored at address $9C40 (40000 decimal) = 0x2A

## Memory Validation
- Expected memory at $9C40: 0x2A (42)
