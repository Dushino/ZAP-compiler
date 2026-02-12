# Test 112: Mixed Logical and Comparison in RPN

**Objective:** Validate complex expressions with both logical AND/OR and comparison operators

## Expression
```zap
byte r = ((a < b) && (b < c)) || (a == c)
```

## Test Values
- a = 5
- b = 10
- c = 5

## Expected Evaluation
- (a < b) = (5 < 10) = **TRUE** = 1
- (b < c) = (10 < 5) = **FALSE** = 0
- (a == c) = (5 == 5) = **TRUE** = 1

**Expression evaluation:**
- ((1) && (0)) || (1)
- (0) || (1)
- **TRUE** = **1**

## Expected Result
Value at address $9C40: **0x01** (hex) = **1** (decimal)

## Implementation Notes
- Complex expression with nested logical and comparison operators
- Tests operator precedence: && before ||, comparisons before logical
- All three comparison operators produce BYTE results
- Logical operators combine those results correctly
- Demonstrates RPN stability with multiple operator types

