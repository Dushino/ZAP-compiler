# Test 005: 1D BYTE Arrays

## Feature
Tests single-dimensional arrays of BYTE type with multiple elements.

## Description
5-element BYTE array with element access and summation.

## Test Code
```zap
byte result @40000 = 0

proc main()
    byte arr[5]
    byte sum
    arr[0] = 10
    arr[1] = 20
    arr[2] = 30
    arr[3] = 40
    arr[4] = 50
    sum = arr[0] + arr[1] + arr[2] + arr[3] + arr[4]
    result = sum
end
```

## Expected Behavior
- Array arr[5] allocated
- Elements: [10, 20, 30, 40, 50]
- sum = 150 (0x96)

## Memory Validation
- Expected memory at $9C40: 0x96 (150)
