# Test 012: Pointer Arithmetic

## Feature
Pointer arithmetic on byte pointers and dereference of the resulting address.

## Description
A byte array is initialized to `{5,10,15}`. A pointer is set to the start of the array, advanced by 2 bytes, and the value at the new location is read and stored to the result.

## Test Code
```zap
word result @40000 = 0

proc main()
    byte arr[3] = {5, 10, 15}
    byte ^p = @arr[0]
    byte value

    ; Move pointer two elements forward to arr[2]
    p = p + 2
    value = p^
    result = value
end
```

## Expected Behavior
- Pointer arithmetic correctly advances by element size (1 byte for byte pointers)
- Dereference after `p = p + 2` yields 15
- Memory at $9C40 holds 0x0F 0x00

## Memory Validation
- Expected memory at $9C40: 0x0F 0x00
