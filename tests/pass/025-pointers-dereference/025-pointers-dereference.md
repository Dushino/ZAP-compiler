# Test 011: Pointer Dereference

## Feature
Read a byte through a pointer using the dereference operator.

## Description
A byte variable is initialized to 77. A pointer is set to its address, the value is read via `ptr^`, and stored into the result location.

## Test Code
```zap
word result @40000 = 0

proc main()
    byte data = 77
    byte ^ptr = @data
    byte value

    value = ptr^
    result = value
end
```

## Expected Behavior
- Pointer loads the byte at `data` correctly
- `result` holds 77 (0x4D)

## Memory Validation
- Expected memory at $9C40: 0x4D 0x00
