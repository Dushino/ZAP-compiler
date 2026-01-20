# Test 004: Simple Array Indexing

## Feature
Tests single-dimensional array indexing and element access.

## Description
Simple BYTE array with three elements. Tests array initialization, element indexing, and arithmetic operations on array elements.

## Test Code
```zap
byte result @40000 = 0

proc main()
    byte arr[3]
    byte sum
    arr[0] = 10
    arr[1] = 20
    arr[2] = 30
    sum = arr[0] + arr[1] + arr[2]  ; 10 + 20 + 30 = 60
    result = sum
end
```

## Expected Behavior
- Array arr[3] allocated
- Elements set: arr[0]=10, arr[1]=20, arr[2]=30
- Sum calculated: 10 + 20 + 30 = 60 (0x3C)
- Result stored at address $9C40 = 0x3C

## Memory Validation
- Expected memory at $9C40: 0x3C (60)
