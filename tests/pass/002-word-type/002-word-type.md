# Test 002: WORD Type

## Feature
Tests 16-bit signed/unsigned integer type (WORD).

## Description
WORD type is a 16-bit value, capable of storing integers from 0 to 65535 (unsigned) or -32768 to 32767 (signed).

## Test Code
```zap
word result @40000 = 0

proc main()
    word x = 1000
    word y = 2000
    word z = x + y     ; z = 3000
    result = z
end
```

## Expected Behavior
- Variable x initialized to 1000 (0x03E8)
- Variable y initialized to 2000 (0x07D0)
- Sum z = x + y = 3000 (0x0BB8)
- Result stored at address $9C40 (40000 decimal) = 0x0BB8

## Memory Validation
- Expected memory dump at $9C40-$9C41: [0xB8, 0x0B] (little-endian)
- Decimal: 3000
- Hex: 0x0BB8
