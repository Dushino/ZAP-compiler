# Test 007: Procedure Call with Parameters

## Feature
Tests procedure calls with parameter passing and global variable modification.

## Description
Procedure add() takes two BYTE parameters, calculates sum, and stores in global result.

## Test Code
```zap
byte result @40000 = 0

proc add(byte a, byte b)
    byte res = a + b
    result = res
end

proc main()
    add(30, 12)
end
```

## Expected Behavior
- Procedure add() called with a=30, b=12
- Local res calculated: 30 + 12 = 42 (0x2A)
- Global result set to 42
- Main completes

## Memory Validation
- Expected memory at $9C40: 0x2A (42)
