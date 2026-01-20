# Test 004 Error: Array Out-of-Bounds

## Expected Error
Runtime or compile-time error when accessing array beyond allocated size.

## Error Details
- Array size: 3 elements (indices 0-2)
- Attempted access: arr[5]
- Should produce: "Array index out of bounds: index 5, array size 3"
- Error clearly indicates both index and array size
