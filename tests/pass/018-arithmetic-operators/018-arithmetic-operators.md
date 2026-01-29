# Test 009: Multiple Arithmetic Operations

## Feature
Tests multiple arithmetic operations in sequence.

## Description
Tests addition, subtraction, and multiplication with proper operator precedence.

## Test Code
```zap
byte result @40000 = 0

proc main()
    byte a = 100
    byte b = 50
    
    ; Test different operators
    byte sum = a + b        ; 150
    byte diff = a - b       ; 50
    byte prod = 10 * 5      ; 50
    
    result = diff           ; Store diff = 50
end
```

## Expected Behavior
- sum = 100 + 50 = 150 (0x96)
- diff = 100 - 50 = 50 (0x32)
- prod = 10 * 5 = 50 (0x32)
- result = diff = 50

## Memory Validation
- Expected memory at $9C40: 0x32 (50)
