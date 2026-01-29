# Test 009: Arrays with Inferred Size

## Feature
Tests array declarations with size inferred from initializer list.

## Description
Array declared with empty brackets `[]` and initialized with a list of values. The size is automatically inferred from the number of initializer elements.

## Test Code
```zap
word result @40000 = 0

proc main()
    byte arr[] = {10, 20, 30, 40, 50}
    byte sum
    
    ' Array size should be inferred from initializer (5 elements)
    sum = arr[0] + arr[1] + arr[2] + arr[3] + arr[4]
    ' 10 + 20 + 30 + 40 + 50 = 150
    
    result = sum
end
```

## Expected Behavior
- Array arr[] allocated with 5 elements (inferred from initializer)
- Elements initialized to: [10, 20, 30, 40, 50]
- Sum of all elements: 10 + 20 + 30 + 40 + 50 = 150 (0x96)

## Memory Validation
- Expected memory at $9C40: 0x96 (150 decimal)
