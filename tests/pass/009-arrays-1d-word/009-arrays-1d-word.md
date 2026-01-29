# Test 006: 1D WORD Arrays

## Feature
Tests single-dimensional arrays of WORD type.

## Description
3-element WORD array with element access and summation.

## Test Code
```zap
word result @40000 = 0

proc main()
    word arr[3]
    word sum
    arr[0] = 1000
    arr[1] = 2000
    arr[2] = 3000
    sum = arr[0] + arr[1] + arr[2]
    result = sum
end
```

## Expected Behavior
- Array arr[3] of WORD allocated
- Elements: [1000, 2000, 3000]
- sum = 6000 (0x1770)

## Memory Validation
- Expected memory at $9C40-$9C41: 0x70 0x17 (6000 little-endian)
