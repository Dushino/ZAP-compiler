# Test 005: WHILE Loop Control Flow

## Feature
Tests WHILE loop execution and loop condition evaluation.

## Description
Demonstrates conditional loop that executes based on a boolean condition, modifying result when condition is met.

## Test Code
```zap
byte result @40000 = 0

proc main()
    byte x = 50
    byte y = 100
    
    result = 0
    while result == 0
        result = 1
    end
end
```

## Expected Behavior
- result initialized to 0
- Loop condition: result == 0 (TRUE initially)
- Loop body executes: result = 1
- Loop condition checked again: result == 0 (FALSE, exit)
- Final result = 1 (0x01)

## Memory Validation
- Expected memory at $9C40: 0x01 (1)
