# Test 004: WORD Pointers

## Feature
Tests pointer operations with 16-bit WORD type.

## Description
Demonstrates taking address of WORD variable and storing result.

## Test Code
```zap
word result @40000 = 0

proc main()
    word target = 3000
    word ptr = 0
    ptr = @target
    result = target
end
```

## Expected Behavior
- target initialized to 3000
- ptr assigned address of target
- result = target = 3000 (0x0BB8)

## Memory Validation
- Expected memory at $9C40-$9C41: 0xB8 0x0B (3000 little-endian)
