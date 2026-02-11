# RPN Code Generation Refactor - Implementation Plan

## Overview
Convert from linear (left-to-right) AST-based code generation to Reverse Polish Notation (RPN) stack-based evaluation. This enables reuse of helper routines and reduces code size.

## Architecture Changes

### Current (Linear) Flow
```
gen_expr(BinOp: a + b)
  → evaluate left (a) → STA MATH0/STX MATH0+1   # Note - user corrected type from STA MATH0+1 to STX MATH0+1
  → evaluate right (b) → STA MATH1/STX MATH1+1  # Note - user corrected type from STA MATH0+1 to STX MATH0+1
  → JSR ADD16
  → LDA MATH0 / LDX MATH0+1
```

### Target (RPN) Flow
```
gen_expr(BinOp: a + b)
  → convert to RPN: [a, b, ADD]
  → evaluate a → LDA/LDX → JSR SET_MATH0
  → evaluate b → LDA/LDX → JSR SET_MATH1
  → JSR ADD16
  → JSR GET_MATH0 (result in A/X)
```

## Helper Routines (NEW)

### SET_MATH0: A/X → MATH0/MATH0+1
```
SET_MATH0:
    STA MATH0
    STX MATH0+1
    RTS
```

### SET_MATH1: A/X → MATH1/MATH1+1
```
SET_MATH1:
    STA MATH1
    STX MATH1+1
    RTS
```

### GET_MATH0: MATH0/MATH0+1 → A/X
```
GET_MATH0:
    LDA MATH0
    LDX MATH0+1
    RTS
```

## Implementation Phases

### Phase 1: Helper Routine Infrastructure
- [ ] Add SET_MATH0, SET_MATH1, GET_MATH0 routines to math routines emitter
- [ ] Add tracking for which helper routines are needed
- [ ] Define RPN structure/classes
- [ ] Set up RPN evaluation stack framework

### Phase 2: AST-to-RPN Converter
- [ ] Implement recursive AST walker to build RPN sequence
- [ ] Handle BinOp expressions (all operators)
- [ ] Handle UnaryOp expressions
- [ ] Handle variable/constant leaf nodes
- [ ] Handle function calls
- [ ] Handle array subscripts
- [ ] Handle struct field access
- [ ] Handle pointer dereference
- [ ] Handle casts
- [ ] Test on simple expressions first

### Phase 3: RPN Evaluator Core
- [ ] Implement stack-based RPN evaluation
- [ ] Temp allocation for intermediate results
- [ ] Handle A/X register state
- [ ] Manage evaluation stack in MATH_STACK region
- [ ] Implement push/pop of intermediate results
- [ ] Handle branch conditions (comparisons)

### Phase 4: Binary Operators Implementation
- [ ] Arithmetic: +, -, *, /, %
- [ ] Bitwise: &, |, ^, <<, >>
- [ ] Comparison: ==, !=, <, >, <=, >=
- [ ] Logical: &&, || (short-circuit evaluation)
- [ ] Pointer arithmetic (element size adjustment)
- [ ] Test each operator type thoroughly

### Phase 5: Unary Operators Implementation
- [ ] Logical NOT (!)
- [ ] Bitwise NOT (~)
- [ ] Address-of (&var)
- [ ] Dereference (*ptr)
- [ ] Negation (unary -)
- [ ] Type casts

### Phase 6: Complex Expressions & Side-Effects
- [ ] Function calls within expressions
- [ ] Array subscripts with computed indices
- [ ] Struct field access chains
- [ ] Nested pointer dereferences
- [ ] Assignment within expressions (a = (b = c))
- [ ] Increment/decrement pre/post (++a, a++)

### Phase 7: Assignment Handling
- [ ] Simple variable assignment
- [ ] Array element assignment
- [ ] Struct field assignment
- [ ] Pointer dereference assignment
- [ ] Compound assignments (+=, -=, etc.)
- [ ] Multiple assignment (a = b = c)

### Phase 8: Temporary Storage Management
- [ ] Define temp variable allocation strategy
- [ ] Track temp usage per expression scope
- [ ] Implement temp cleanup/reuse
- [ ] Handle nested expression temps
- [ ] Document ZEROPAGE layout
- [ ] Verify no conflicts with MATH_STACK

### Phase 9: Refactor gen_expr() Main Flow
- [ ] Add RPN mode flag (can coexist with old code during transition)
- [ ] Integrate AST-to-RPN converter
- [ ] Route through RPN evaluator
- [ ] Gradually remove old linear code paths
- [ ] Handle both modes in parallel for testing

### Phase 10: Integration & Cleanup
- [ ] Remove old linear gen_expr code paths
- [ ] Clean up unused temp allocation
- [ ] Verify all optimizations still work
- [ ] Update documentation
- [ ] Code review and hardening

### Phase 11: Regression Testing
- [ ] Compile all 100+ tests
- [ ] Verify correct results for each test case
- [ ] Compare generated code size before/after
- [ ] Performance benchmarking
- [ ] Memory usage validation

### Phase 12: Performance Analysis
- [ ] Measure byte savings per operation type
- [ ] Identify best/worst cases
- [ ] Optimization opportunities from Phases 1-10
- [ ] Document performance gains

## Key Technical Decisions

### RPN Stack Storage
- Primary: MATH_STACK (8 bytes min, up to 32 bytes possible)
- Overflow: Spill to ZEROPAGE temps (TMP0-TMP4, TMP1-TMP4+1)
- Strategy: Keep 2-3 intermediate results on stack, rest on disk

### Temp Allocation
- Per-expression temps: Allocated at expression start, freed at end
- Nested expression temps: Stack-based allocation
- Register allocation: A/X remain primary; Y for index operations

### Helper Routine Strategy
- Always emit SET_MATH0, SET_MATH1, GET_MATH0 (tiny overhead, big reuse)
- Conditional: Only emit math routines that are actually used
- Ordering: Load left operand first (SET_MATH0), then right (SET_MATH1), then operate

### Optimization Constraints
- Preserve fast-path optimizations (+1 INC, -1 DEC inline)
- Preserve short-circuit evaluation for && and ||
- Preserve assignment-in-expression behavior
- Preserve function call side-effect ordering

## Success Criteria

1. **Functional Correctness**: All 100+ tests pass with same results
2. **Code Size**: Achieve 10-15% reduction in generated code for math-heavy expressions
3. **Performance**: No regression in execution speed
4. **Maintainability**: Code is well-documented and modular
5. **Robustness**: Handles all operator combinations correctly

## Estimated Effort
- 80-120 hours of development
- 20-40 hours of testing
- 10-20 hours of optimization/refinement

## Rollback Plan
- Keep old gen_expr code in comments until Phase 10
- Maintain git commits at each phase boundary
- Can revert to Phase N if critical issues found
- Helper routines are backwards-compatible

## Testing Strategy

### Unit Tests (Per Phase)
- Test simple expressions: `a + b`
- Test nested expressions: `(a + b) * (c - d)`
- Test all operators in each phase
- Test edge cases (constants, variables, mixed)

### Integration Tests
- Run full test suite after each phase
- Verify generated code correctness
- Check assembly compiles cleanly
- Validate memory layout

### Regression Tests
- Compare output against current known-good baseline
- Binary comparison of test outputs
- Performance metrics collection

## Documentation Requirements
- Update ADVANCED_TOPICS.md with RPN explanation
- Add inline comments in RPN evaluator
- Document temp allocation strategy
- Create RPN architecture diagram
