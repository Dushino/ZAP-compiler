# RPN Refactor Phase 1 - Completion Summary

## What Was Completed

### 1. Helper Routines Added to Math System
Three new routines emitted alongside existing math routines (ADD16, SUB16, MUL8, etc.):

```asm
SET_MATH0:  STA MATH0; STX MATH0+1; RTS  ;3 bytes each
SET_MATH1:  STA MATH1; STX MATH1+1; RTS
GET_MATH0:  LDA MATH0; LDX MATH0+1; RTS
```

**Size**: 9 bytes for all three (shared infrastructure across entire program)
**Benefit**: Eliminates repeated inline STA/STX sequences before JSR

### 2. RPN Infrastructure Classes

```python
class RPNNode:
    node_type: str      # 'OPERAND', 'OPERATOR', 'CONST', 'VAR', etc.
    value: object       # Operator name, variable name, or constant value
    is_16bit: bool      # Whether this produces 16-bit result
```

### 3. Phase 1 Methods Added to CodeGen

- `ast_to_rpn(expr)` - Converts AST to RPN sequence (skeleton complete)
- `rpn_eval_to_code(rpn, target_16bit)` - Evaluates RPN and emits code (skeleton complete)

### 4. New Instance Variables for RPN State

```python
self.rpn_enabled: bool = False              # Enable RPN-based evaluation
self.rpn_eval_stack: list = []              # Stack for runtime evaluation
self.rpn_temp_count: int = 0                # Temp allocation counter
self.rpn_helper_routines_needed: set = {}   # Which helpers actually needed
```

## Current Status

✅ **Code compiles without errors**
✅ **All existing tests still pass** (100% backward compatible)
✅ **Helper routines successfully emitted** (verified in generated code)
✅ **RPN infrastructure ready for population**

## Next Steps: Phase 2-3 (AST-to-RPN Conversion & RPN Evaluation)

### Phase 2 Tasks: Complete ast_to_rpn() Implementation

**Current skeleton only handles**:
- Basic node type detection
- Simple operand/operator separation

**Phase 2 will add**:
- Correct handling of all BinaryExpr operators (see ast_nodes.py BinOp enum)
- Support for UnaryExpr (!, ~, unary -, &, *)
- Traversal of complex nested expressions
- Proper 16-bit type tracking through RPN sequence

**Test cases for Phase 2**:
```zap
; Simple binary
result = a + b       ; RPN: [a, b, +]

; Nested binary  
result = (a + b) * c ; RPN: [a, b, +, c, *]

; Complex nesting
result = a + b * c - d   ; RPN: [a, b, c, *, d, -] or [a, b, c, *, +, d, -]?
                         ; NOTE: Respects operator precedence in AST already

; Unary operations
result = -a + b      ; RPN: [a, -, b, +]
result = !a & b      ; RPN: [a, !, b, &]
```

### Phase 3 Tasks: Implement rpn_eval_to_code()

**Current skeleton only has**:
- Stack frame setup
- Incomplete operand handling

**Phase 3 will implement**:

1. **Operand Evaluation** (CONST, VAR, etc.)
   ```python
   if node.node_type == 'CONST':
       # Load constant into A/X
       # Decide: keep in registers or store to temp?
       eval_stack.push((location, is_16bit))
   ```

2. **Operator Evaluation** (OPERATOR nodes)
   ```python
   elif node.node_type == 'OPERATOR':
       right_loc, right_16 = eval_stack.pop()
       left_loc, left_16 = eval_stack.pop()
       
       # Load operands into MATH0/MATH1
       # Call appropriate routine (ADD16, MUL8, etc.)
       # Push result back
       eval_stack.push(("MATH0", result_16bit))
   ```

3. **Temp Management**
   - When stack full, spill intermediate to ZEROPAGE temps
   - Track which temps are allocated
   - Clean up at expression end

4. **Result Extraction**
   - Copy final result from MATH0 to A/X
   - Ensure proper 16-bit vs 8-bit handling

## Testing Strategy for Phases 2-3

**Unit Test Approach**:
1. Enable `rpn_enabled = True` for specific simple expressions
2. Compare generated code with current (linear) approach
3. Verify both produce identical assembly
4. Measure code size difference
5. Check register/temp state consistency

**Test Expression Set**:
```zap
; Test 099 subset (simpler than full version)
byte r0 = 12 + 13           ; 2 operands, 1 operator
byte r1 = 12 * 13 + 5       ; 3 operands, 2 operators (nested)
word r2 = 300 + 200         ; 16-bit addition
byte r3 = (100 - 50) / 3    ; Complex: division of subtraction
```

## Expected Byte Savings Example

### Before (Current Linear Approach)
```asm
; a + b where a and b are variables
LDA a           ; 3 bytes
STA MATH0       ; 3 bytes
LDA a+1         ; 3 bytes
STA MATH0+1     ; 3 bytes
LDA b           ; 3 bytes
STA MATH1       ; 3 bytes
LDA b+1         ; 3 bytes
STA MATH1+1     ; 3 bytes
JSR ADD16       ; 3 bytes
LDA MATH0       ; 3 bytes
LDX MATH0+1     ; 3 bytes
Total: 36 bytes
```

### After (RPN + Helpers)
```asm
LDA a           ; 3 bytes
LDX a+1         ; 3 bytes
JSR SET_MATH0   ; 3 bytes
LDA b           ; 3 bytes
LDX b+1         ; 3 bytes
JSR SET_MATH1   ; 3 bytes
JSR ADD16       ; 3 bytes
JSR GET_MATH0   ; 3 bytes
Total: 27 bytes

Savings: 9 bytes per operation (-25%)
Helper overhead: 9 bytes (amortized across all operations)
```

## Critical Implementation Notes

1. **Operator Precedence Already Handled**
   - The AST already has correct precedence built-in
   - ast_to_rpn() just linearizes the tree
   - Don't re-sort or modify operators

2. **16-bit Type Tracking**
   - Every RPN node tracks is_16bit
   - During evaluation, check both operands' types
   - Determine result type accordingly

3. **Stack Overflow Handling**
   - MATH_STACK is only 8 bytes
   - RPN eval stack could need more for deep nesting
   - Need spill strategy to ZEROPAGE temps (TMP0-5)

4. **Register Pressure**
   - A/X are primary for operands
   - Y can be used for array indices
   - Don't clobber these carelessly

5. **Helper Routine Tracking**
   - Only emit helper if actually used
   - Don't force all three routines every time
   - Check rpn_helper_routines_needed set

## Performance Expectations

- **Code Size**: 10-15% reduction for math-heavy code
- **Speed**: Same or slightly faster (fewer STA instructions)
- **Memory**: No additional RAM usage (uses existing MATH_STACK + ZEROPAGE)
- **Complexity**: More code to maintain, but cleaner architecture

## Rollback Plan

If issues arise during Phase 2-3:
1. Keep `rpn_enabled = False` by default
2. Can test RPNgen code with specific test inputs
3. Easy to disable and revert if needed
4. Old linear code path remains intact

## Success Criteria

- Phase 2 complete: ast_to_rpn() produces correct RPN for all expressions

 types
- Phase 3 complete: rpn_eval_to_code() generates correct assembly
- Both phases: No test regressions
- Combined: Demonstrable byte savings on test suite
