# Non-ZP Pointers: Complete Analysis Package

## Overview

This package contains a comprehensive analysis of the non-zero-page pointer problem in the ZAP! compiler and a detailed implementation roadmap.

**Problem**: Pointers at fixed addresses outside zero page (like `byte ^DLIST @560`) cannot be used effectively because the compiler assumes all pointers must be in zero page for dereferencing.

**Root Cause**: The 6502's indirect addressing mode `(ptr),Y` only works with zero-page pointers. The compiler currently:
1. Forces all pointers into zero page (or fails if exhausted)
2. Doesn't track pointer storage location
3. Assumes pointers are always dereferenceable

**Solution**: Three-phase implementation to distinguish between pointer storage location and dereferenceability.

---

## Documents in This Package

### 1. **NON_ZP_POINTERS_SUMMARY.md** - START HERE
- Executive summary of the problem
- Why it matters (use cases)
- Three-phase solution overview
- Impact assessment
- **Best for**: Getting up to speed quickly

### 2. **ANALYSIS_NON_ZP_POINTERS.md** - DEEP DIVE
- Complete technical breakdown
- Current architecture analysis (5 components)
- Root cause analysis with code citations
- Solution architecture (5 parts)
- Implementation stages with checkpoints
- Test case specifications
- **Best for**: Understanding the full technical picture

### 3. **ARCHITECTURE_DIAGRAMS.md** - VISUAL REFERENCE
- Memory layout comparisons (before/after)
- Data flow diagrams for pointer declarations
- Dereferencing decision tree
- Symbol table evolution
- Memory allocation algorithm
- Phase roadmap
- Test matrix
- **Best for**: Visual learners and quick reference

### 4. **IMPLEMENTATION_GUIDE.md** - HANDS-ON CODING
- Exact file/line locations for changes
- Code snippets for each modification
- Change complexity table
- Phase 1 behavior specification
- Testing strategy
- Edge case handling
- Validation checklist
- **Best for**: Implementing the solution

### 5. **This File** - NAVIGATION
- Package overview
- Reading guide
- Quick reference

---

## Reading Guide by Role

### For Project Managers / Decision Makers
1. Read: **NON_ZP_POINTERS_SUMMARY.md** (5 min)
2. Skim: Phase sections in **ARCHITECTURE_DIAGRAMS.md** (3 min)
3. Decision: Is this a priority? (Look at "Use Cases That Should Work But Don't")

### For Code Reviewers / Architects
1. Read: **NON_ZP_POINTERS_SUMMARY.md** (5 min)
2. Read: **ANALYSIS_NON_ZP_POINTERS.md** sections:
   - "Current Architecture Analysis" (20 min)
   - "Root Causes" (10 min)
3. Review: **IMPLEMENTATION_GUIDE.md** changes (15 min)
4. Validate: Against **ARCHITECTURE_DIAGRAMS.md** (10 min)

### For Implementers / Developers
1. Skim: **NON_ZP_POINTERS_SUMMARY.md** (3 min)
2. Study: **ARCHITECTURE_DIAGRAMS.md** (20 min)
   - Focus on "Data Flow" and "Dereferencing" sections
3. Reference: **IMPLEMENTATION_GUIDE.md** (ongoing)
   - Code locations and exact changes needed
4. Validate: Using test cases in both IMPLEMENTATION_GUIDE and ANALYSIS documents

### For Future Maintainers
1. Read: **NON_ZP_POINTERS_SUMMARY.md** (context)
2. Bookmark: **IMPLEMENTATION_GUIDE.md** (reference)
3. Refer: **ARCHITECTURE_DIAGRAMS.md** when debugging pointer issues

---

## Key Insights Summary

### The Fundamental Misconception (Root Cause)
```
WRONG: "Pointer variable" = "Variable stored in zero page"
RIGHT: "Pointer variable" = "2-byte value holding an address"
       These are orthogonal concepts!
```

### The Architecture Gap
| Concept | Current | Needed |
|---------|---------|--------|
| Pointer storage location | Forced ZP | ZP or fixed address |
| Pointer dereferenceability | Always possible | Conditional (ZP only) |
| Tracking | No flag | `pointer_in_zp: bool` |
| Codegen strategy | Assume ZP | Check flag, handle temp |

### The Three Phases

**Phase 1: Assignment Support**
- What: Non-ZP pointers can be assigned to ZP pointers
- How: Mark fixed-address pointers with `pointer_in_zp=False`
- Why: Foundation for later phases, enables common pattern
- Cost: ~20 LOC
- Benefit: Unblocks pointer values from HW registers

**Phase 2: Dereferencing Support**
- What: Non-ZP pointers can be dereferenced via temp
- How: Detect `pointer_in_zp=False`, copy to `TMP0`, dereference
- Why: Enables direct dereferencing without workaround
- Cost: ~30 LOC
- Benefit: More efficient code generation

**Phase 3: Pointer Arithmetic**
- What: Math operations on non-ZP pointer values
- How: Load to accumulator, compute, store back
- Why: Complete feature parity
- Cost: ~40 LOC
- Benefit: Full expression support

---

## Code Change Summary

### Files Modified
1. **symbols.py** - Add 1 field (~1 line)
2. **codegen_expr.py** - Three methods (~50 lines total)
3. **sema_expr.py** - Optional validation (~0-20 lines)

### Backward Compatibility
✅ 100% backward compatible
- Existing pointers (implicit ZP) unchanged
- Default `pointer_in_zp=True` maintains current behavior
- Only fixed-address pointers affected

### Test Coverage
- 3 test scenarios per phase
- Edge cases handled (pointer chains, expressions, arrays)
- Full test matrix in ARCHITECTURE_DIAGRAMS.md

---

## Common Questions Answered

### Q: Why is this a problem now?
A: The test file `003-pointers.zap` uses fixed-address pointers (`@560`), which aren't in zero page. Users who try:
```zap
byte ^DLIST @560
byte ^ptr = DLIST  ; Assign non-ZP pointer
```
will face issues because the compiler doesn't support this pattern.

### Q: Can't users just avoid fixed-address pointers?
A: Not for hardware registers or memory-mapped I/O:
```zap
byte ^DLIST @560      ; Atari DLIST register
byte ^PMBASE @$D407   ; Playfield memory base
```
These are at specific hardware addresses and can't be relocated to zero page.

### Q: Isn't copying to temp already supported?
A: Manually, yes, but it requires a workaround. Phase 2 automates it:
```zap
; Current workaround
byte ^DLIST @560
byte ^temp = DLIST
byte data = temp^     ; Indirect via workaround

; Phase 2 will allow
byte data = DLIST^    ; Direct (compiler adds temp internally)
```

### Q: What about pointer arithmetic?
A: Phase 3 will support it. For now, can assign and dereference:
```zap
byte ^base = DLIST
byte ^offset_ptr = base + 16   ; Phase 3 feature
```

### Q: Performance impact?
A: Minimal:
- Phase 1: No impact (assignment only)
- Phase 2: One temp usage per non-ZP dereference (acceptable)
- Phase 3: No impact (load address, compute, store)

### Q: How many pointers typically use this?
A: Few per program:
- Implicit pointers (ZP): ~5-10 typical
- Fixed-address pointers (non-ZP): ~1-3 typical
- Most are hardware registers in embedded code

---

## Implementation Checklist

### Pre-Implementation
- [ ] Review ANALYSIS_NON_ZP_POINTERS.md completely
- [ ] Study ARCHITECTURE_DIAGRAMS.md data flows
- [ ] Understand decision tree for dereferencing
- [ ] Identify test cases to validate

### Phase 1 Implementation
- [ ] Add `pointer_in_zp` field to Symbol class
- [ ] Update gen_vars() to mark non-ZP pointers
- [ ] Add error check in _gen_deref()
- [ ] Test: 003-pointers.zap assigns and validates
- [ ] Test: Error message clear on dereference attempt
- [ ] Regression: Existing pointer tests still pass

### Phase 1 Validation
- [ ] Unit test: pointer allocation
- [ ] Unit test: assignment codegen
- [ ] Unit test: error messages
- [ ] Integration test: compile 003-pointers.zap
- [ ] Integration test: verify generated assembly
- [ ] Regression: run full test suite

### Phase 2 Preparation
- [ ] Design temp management for non-ZP dereferencing
- [ ] Identify optimization opportunities
- [ ] Plan for consecutive accesses

### Phase 2 Implementation
- [ ] Modify _gen_deref() to support temp-based dereferencing
- [ ] Handle both direct and indirect pointer expressions
- [ ] Optimize common patterns
- [ ] Test: Dereference non-ZP pointers
- [ ] Test: Verify generated assembly correctness

---

## References

### 6502 Instruction Set
- Indirect addressing modes:
  - `($XX),Y` - Indirect indexed (requires zero page address)
  - `$XXXX,Y` - Absolute indexed (no indirect mode for 16-bit addresses)
  
### ZAP Language Features Used
- Pointer declarations: `byte ^ptr`
- Fixed addresses: `byte ^ptr @address`
- Pointer dereferencing: `ptr^`
- Pointer assignment: `ptr1 = ptr2`
- Initialization: `byte ^ptr = value`

### Related ZAP Files
- [symbols.py](symbols.py) - Symbol table and type system
- [codegen_expr.py](codegen_expr.py) - Code generation
- [sema_expr.py](sema_expr.py) - Type checking
- [tests/pass/003-pointers.zap](tests/pass/003-pointers.zap) - Test case

---

## Glossary

| Term | Definition |
|------|-----------|
| **ZP (Zero Page)** | Memory addresses 0x00-0xFF, required for certain 6502 addressing modes |
| **Indirect addressing** | `(ptr),Y` mode; requires pointer in ZP |
| **Pointer variable** | A 2-byte value holding an address (can be stored anywhere) |
| **Fixed-address** | Variable stored at a specific address (e.g., `@560`) |
| **Dereference** | Access memory location pointed to by a pointer (read/write) |
| **Temp** | Temporary storage variable (TMP0, TMP1, etc.) |
| **Phase** | Implementation stage with clear objectives and milestones |

---

## Next Steps

1. **Review** this analysis package
2. **Decide** which phases to implement
3. **Plan** implementation timeline
4. **Implement** using IMPLEMENTATION_GUIDE.md
5. **Test** using specifications from ANALYSIS_NON_ZP_POINTERS.md
6. **Validate** using test cases in all documents
7. **Document** lessons learned

---

**Last Updated**: 2026-01-16
**Status**: Analysis Complete, Ready for Implementation
**Estimated Phase 1 Effort**: 2-4 hours
**Estimated Phase 2 Effort**: 4-6 hours
**Estimated Phase 3 Effort**: 6-8 hours
