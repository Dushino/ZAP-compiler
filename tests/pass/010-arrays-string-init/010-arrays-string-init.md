# Test 010: Array Initialization with String Literal

## Feature
Initialize a byte array using a string literal and verify element values.

## Description
A 6-byte array is initialized with the literal "hello". The compiler should place the ASCII bytes for the five characters and a trailing NUL. The test sums the first five characters and stores the result.

## Test Code
```zap
word result @40000 = 0

proc main()
    byte greeting[6] = "hello"
    word sum

    ; Sum characters (h+e+l+l+o = 532 / 0x0214)
    sum = greeting[0] + greeting[1] + greeting[2] + greeting[3] + greeting[4]
    result = sum
end
```

## Expected Behavior
- Array `greeting` contains `['h','e','l','l','o',0]`
- Sum of first five characters = 532 (0x0214)
- Memory at $9C40 holds 0x14 0x02 (little endian)

## Memory Validation
- Expected memory at $9C40: 0x14 0x02
