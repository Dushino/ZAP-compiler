# Test: BYTE Type Declaration and Usage

**Purpose**: Validates BYTE type variables work correctly

## Feature
BYTE data type for small integer values (0-255)

## Test Code
- Declares a global BYTE result at address 40000 ($9C40)
- Creates local BYTE variables x and y
- Performs arithmetic (addition)
- Stores result at the fixed address for verification

## Expected Behavior
- x = 42
- y = 100
- z = 142 (result of x + y)
- Memory at $9C40 contains 142 (0x8E)

## BYTE Characteristics Tested
- ✅ Range: 0-255
- ✅ Declaration with initializer
- ✅ Arithmetic operations
- ✅ Value storage at fixed address
- ✅ Fixed-address variable (@)

## Memory Validation
Memory address $9C40 (40000 decimal) should contain: 0x8E (142)

## Related Tests
- 002-word-type (16-bit integer)
- 003-byte-pointers (pointer to BYTE)
