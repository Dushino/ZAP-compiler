# Test 002 Error: WORD Type Overflow

## Expected Error
Compile-time error for integer literal exceeding WORD range (0-65535).

## Error Details
- Literal value: 65536 (exceeds max 65535)
- Should produce: "Value 65536 out of range for WORD type (0-65535)"
- Error should indicate the invalid value and allowed range
