# Phase 7: Logical Operators in RPN - PLANNING

**Status:** IN PROGRESS  
**Date Started:** February 12, 2026  
**Objective:** Add logical operators (&&, ||) to RPN evaluation with proper short-circuit semantics

## Phase 7 Scope

### Target Operators
1. **&&** (Logical AND)
   - Short-circuit: Stop if left is falsy
   - Returns BYTE (0 or 1)
   - Used in: conditions, expressions, assignments
2. **||** (Logical OR)
   - Short-circuit: Stop if left is truthy
   - Returns BYTE (0 or 1)
   - Used in: conditions, expressions, assignments

### Why These Operators
- Existing tests use them: 058, 061, 063
- Short-circuit behavior provides optimization opportunity
- Combine with comparison results for efficient conditional logic
- Enable expressions like: `(a < b) && (a == c)` with single evaluation

## Implementation Strategy

### Challenge: Short-Circuit Semantics
Unlike arithmetic operators, logical operators must not always evaluate both operands:

```c
Example: (expr1) && (expr2)
- If expr1 is false, expr2 should NOT be evaluated
- Result is false regardless
```

This differs from RPN's normal stack-based evaluation which evaluates all operands before the operator.

### Solution: Special Codegen
For logical operators, generate conditional branch code instead of function calls:

```asm
; (a < 10) && (b > 5)
; First comparison
LDA A
CMP #10
BCS LAND_LEFT_FALSE      ; If a >= 10, skip to set result = 0
  
; First left was true, evaluate right
LDA B
CMP #5
BCS LAND_RIGHT_TRUE
LDA #0
BRA LAND_END
LAND_RIGHT_TRUE:
LDA #1
BRA LAND_END
  
LAND_LEFT_FALSE:
LDA #0
  
LAND_END:
STA MATH0
LDX #0
```

## Code Location Changes

**Files to Modify:**
1. `codegen_expr.py` lines ~5684 in `gen_expr()`
   - Update RPN gate to recognize AND/OR operators
2. `codegen_expr.py` lines ~437 in `rpn_eval_to_code()`
   - Add AND/OR case for special short-circuit codegen

## Test Strategy

### Test 110: basic-logical-and
- Expression: `(a < b) && (c == d)`
- Values: a=5, b=10, c=3, d=3
- Expected: (true) && (true) = 1
- Result: 0x01 at $9C40

### Test 111: basic-logical-or
- Expression: `(a > b) || (c < d)`
- Values: a=5, b=10, c=3, d=3
- Expected: (false) || (false) = 0
- Result: 0x00 at $9C40

### Test 112: mixed-logical-comparison
- Expression: `(a < b) && (b < c) || (a == c)`
- Values: a=5, b=10, c=5
- Expected: ((5<10) && (10<5)) || (5==5) = (true && false) || true = 0 || 1 = 1
- Result: 0x01 at $9C40

## Implementation Phases within Phase 7

### Phase 7.1: Logical AND (&&)
- [ ] Update `_is_rpn_safe()` to include `BinOp.AND`
- [ ] Add AND case to `rpn_eval_to_code()`
- [ ] Generate short-circuit branch code
- [ ] Create test 110: basic-logical-and
- [ ] Verify test 110 passes

### Phase 7.2: Logical OR (||)
- [ ] Update `_is_rpn_safe()` to include `BinOp.OR`
- [ ] Add OR case to `rpn_eval_to_code()`
- [ ] Generate short-circuit branch code
- [ ] Create test 111: basic-logical-or
- [ ] Verify test 111 passes

### Phase 7.3: Complex Mixed Expressions
- [ ] Test mixed AND/OR/comparisons
- [ ] Create test 112: mixed-logical-comparison
- [ ] Regression testing with tests 058, 061, 063
- [ ] Verify no performance regressions

## Code Generation Patterns

### AND Implementation
```python
elif node.value == BinOp.AND:
    # Both operands should be BYTE results from comparisons
    lbl_right = self.new_label("AND_RIGHT")
    lbl_end = self.new_label("AND_END")
    
    # Load left operand to MATH0
    # Check if left is zero
    self.emit(f"\tLDA MATH0")
    self.emit(f"\tBEQ {lbl_end}")  # If left=0, skip to result
    
    # Load right operand to MATH1
    # Check if right is zero
    self.emit(f"\tLDA MATH1")
    self.emit(f"\tBEQ {lbl_end}")
    
    # Both true, result = 1
    self.emit(f"\tLDA #$01")
    self.emit(f"\tJMP {lbl_end}")
    
    self.emit(f"{lbl_end}:")
    self.emit(f"\tSTA MATH0")
    self.emit(f"\tLDX #$00")
```

### OR Implementation
```python
elif node.value == BinOp.OR:
    lbl_left_true = self.new_label("OR_LEFT_TRUE")
    lbl_end = self.new_label("OR_END")
    
    # Load left operand to MATH0
    self.emit(f"\tLDA MATH0")
    self.emit(f"\tBNE {lbl_left_true}")  # If left!=0, skip to set 1
    
    # Left is false, check right
    self.emit(f"\tLDA MATH1")
    self.emit(f"\tBNE {lbl_left_true}")
    
    # Both false, result = 0
    self.emit(f"\tLDA #$00")
    self.emit(f"\tJMP {lbl_end}")
    
    self.emit(f"{lbl_left_true}:")
    self.emit(f"\tLDA #$01")
    
    self.emit(f"{lbl_end}:")
    self.emit(f"\tSTA MATH0")
    self.emit(f"\tLDX #$00")
```

## Integration Points

1. **Operator Type System** (`token_types.py`)
   - AND and OR operators should be recognized
   - Return type: BYTE (0 or 1)

2. **Semantic Analysis** (`sema_expr.py`)
   - Both operands should support "truthiness" conversion
   - Result is BYTE

3. **Code Generation** (`codegen_expr.py`)
   - RPN gate recognizes AND/OR in binary operators
   - Special case codegen for short-circuit evaluation
   - No temporary register save needed (MATH0/MATH1 sufficient)

## Performance Impact
- No additional memory overhead
- Minimal instruction count (BEQ/BNE + conditional stores)
- Short-circuit should show benefits on conjunction chains

## Backward Compatibility
- Existing tests (058, 061, 063) should continue passing
- May improve code quality for complex boolean expressions

## Remaining Work After Phase 7
- Phase 8: Bitwise NOT (~), Logical NOT (!) optimizations
- Phase 9: Ternary operator (?:) support
- Phase 10: Function call optimization in RPN context
