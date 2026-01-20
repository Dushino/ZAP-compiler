# Test 010: Global Variable Storage

## Feature
Tests global variable declaration, initialization, and access.

## Description
Global variable declared at module scope, initialized with value, accessed from main procedure.

## Test Code
```zap
byte global_value = 55

proc main()
    byte result = global_value
end
```

## Expected Behavior
- global_value initialized to 55 (0x37) at program start
- Stored in data section at load time
- main() reads global_value and assigns to local result

## Memory Validation
- Expected memory at $4000: 0x37 (55) [global data storage]
