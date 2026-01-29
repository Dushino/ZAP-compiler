# Test 006: WHILE Loop Accumulation

## Feature
Tests WHILE loop with counter and accumulator patterns.

## Description
Standard accumulation pattern: loop from 0 to 9, incrementing sum each iteration.

## Test Code
```zap
byte result @40000 = 0

proc main()
    byte count = 0
    byte sum = 0
    
    while count < 10
        sum = sum + 1
        count = count + 1
    end
    
    result = sum    ; result = 10
end
```

## Expected Behavior
- count starts at 0, sum starts at 0
- Loop iterates 10 times (count 0-9)
- Each iteration: sum += 1, count += 1
- Final: sum = 10, result = 10 (0x0A)

## Memory Validation
- Expected memory at $9C40: 0x0A (10)
