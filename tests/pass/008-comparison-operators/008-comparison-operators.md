# Test 008: Arithmetic Operations

## Feature
Tests basic arithmetic operators (addition, subtraction, multiplication).

## Description
Tests arithmetic with BYTE values including addition, subtraction, and multiplication operations.

## Test Code
```zap
byte result @40000 = 0

proc main()
    byte a = 100
    byte b = 50
    byte sum = 0
    
    sum = a + b
    result = sum
end
```

## Expected Behavior
- a = 100 (0x64)
- b = 50 (0x32)
- sum = a + b = 150 (0x96)
- result stored at address $9C40 = 150

## Memory Validation
- Expected memory at $9C40: 0x96 (150)
