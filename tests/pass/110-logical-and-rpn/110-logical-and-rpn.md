# Test 110: Logical AND in RPN

**Objective:** Validate logical AND operator (&&) in RPN expression context

## Expression
```zap
byte r = (a < b) && (c == d)
```

## Test Values
- a = 5
- b = 10
- c = 3
- d = 3

## Expected Evaluation
- (a < b) = (5 < 10) = **TRUE** = 1
- (c == d) = (3 == 3) = **TRUE** = 1
- (1) && (1) = **TRUE** = **1**

## Expected Result
Value at address $9C40: **0x01** (hex) = **1** (decimal)

## Implementation Notes
- Uses RPN evaluation with logical AND operator
- Both operands are comparison expressions (return BYTE 0 or 1)
- Result is BYTE (0 for false, 1 for true)
- Tests proper operand loading and logical AND evaluation

