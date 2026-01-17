# Non-ZP Pointers: Quick Reference Card

## Problem in One Sentence
Pointers at fixed addresses outside zero page (like `byte ^DLIST @560`) can't be used because the compiler assumes all pointers must be in zero page for the 6502's indirect addressing mode `(ptr),Y` to work.

---

## Current Limitations

| Operation | Works? | Issue |
|-----------|--------|-------|
| Declare fixed-address pointer | ✅ | Symbolic only (`DLIST = $0560`) |
| Assign non-ZP pointer to ZP pointer | ✅ | Works normally |
| Dereference ZP pointer | ✅ | Works normally |
| Dereference non-ZP pointer | ❌ | Fails: must be in ZP |

---

## The Fix: 3 Phases

### Phase 1: Assignment Support (EASY)
```
What:   byte ^DLIST @560; byte ^ptr = DLIST  ← NOW WORKS
Action: Mark non-ZP pointers with flag, allow assignment
Files:  symbols.py (1 line), codegen_expr.py (10 lines)
```

### Phase 2: Dereferencing (MEDIUM)
```
What:   byte value = DLIST^  ← WILL WORK
Action: Copy non-ZP pointer to temp, then dereference
Files:  codegen_expr.py (20 lines)
```

### Phase 3: Pointer Arithmetic (HARD)
```
What:   byte ^offset_ptr = DLIST + 16  ← WILL WORK
Action: Support math operations on non-ZP pointers
Files:  sema_expr.py (10 lines), codegen_expr.py (20 lines)
```

---

## One-Page Implementation Summary

### 1. Add Flag to Symbol (symbols.py)
```python
class Symbol:
    ...existing fields...
    pointer_in_zp: bool = True  # NEW: Can use indirect addressing?
```

### 2. Mark Non-ZP Pointers (codegen_expr.py::gen_vars)
```python
fixed = [s for s in all_vars if s.address is not None]
if fixed:
    for sym in fixed:
        if sym.type.is_pointer:
            sym.pointer_in_zp = False  # NEW: Mark as non-ZP
```

### 3. Check in Dereferencing (codegen_expr.py::_gen_deref)
```python
if isinstance(expr.pointer, Identifier):
    sym = self.current_symtab.lookup(expr.pointer.name)
    if not getattr(sym, 'pointer_in_zp', True):
        # Phase 1: Error
        raise SemanticError("Cannot dereference non-ZP pointer")
        # Phase 2: Copy to temp first
        # self.gen_expr(expr.pointer)
        # self.emit("\tSTA TMP0")
        # self.emit("\tSTX TMP0+1")
```

---

## Key Insight

```
Mistake:  Pointer Variable = Must Be In Zero Page
Reality:  Pointer Variable = 2-byte Address Value
          Can be stored anywhere, but:
          - DEREFERENCE only works if pointer is in ZP
          - Can ASSIGN/MOVE/MATH regardless of storage location
```

---

## Test This Works

### Phase 1 Test
```zap
byte ^DLIST @560
byte ^ptr = DLIST      ; ✅ Should compile
proc main() end
```

### Phase 2 Test
```zap
byte ^DLIST @560
byte value
proc main()
    value = DLIST^     ; ✅ Should compile (after Phase 2)
end
```

### Workaround (Works Now)
```zap
byte ^DLIST @560
byte ^temp = DLIST
byte value
proc main()
    value = temp^      ; ✅ Works now (temp is in ZP)
end
```

---

## Generated Assembly Examples

### Example 1: Assign Non-ZP Pointer (Phase 1)
```zap
byte ^DLIST @560
byte ^ptr = DLIST
```

```asm
DLIST = $0560          ; Fixed address
_ptr: .res 2           ; In zero page

; Initialization
LDA #$60               ; Load address low byte
STA _ptr
LDX #$05               ; Load address high byte
STX _ptr+1
```

### Example 2: Dereference Non-ZP Via Temp (Phase 2)
```zap
byte ^DLIST @560
byte data
proc main()
    data = DLIST^      ; Phase 2 will support this
end
```

```asm
; Copy DLIST address to temp
LDA #$60
STA TMP0
LDX #$05
STX TMP0+1

; Dereference via temp
LDY #0
LDA (TMP0),Y
STA _data
```

---

## Files to Modify

| File | Lines | Change | Risk |
|------|-------|--------|------|
| `symbols.py` | ~30 | Add field | 🟢 Low |
| `codegen_expr.py` | ~1360-1365, 1690-1709 | Mark non-ZP, check, error | 🟡 Medium |
| `sema_expr.py` | ~44-48 | Optional validation | 🟢 Low |

**Total: ~60 lines for Phase 1 & 2**

---

## Validation Checklist

- [ ] Symbol has `pointer_in_zp` field with default True
- [ ] Fixed-address pointers marked as `pointer_in_zp = False`
- [ ] Error message clear when dereferencing non-ZP pointer
- [ ] 003-pointers.zap compiles (assignment part)
- [ ] Generated assembly is correct
- [ ] Existing tests still pass
- [ ] Zero-page allocation unchanged for implicit pointers

---

## Error Messages to Expect (Phase 1)

```
✅ Compiles:
   byte ^DLIST @560
   byte ^ptr = DLIST

❌ Fails with:
   "Cannot dereference non-ZP pointer 'DLIST' - 
    must be in zero page (place in ZP variable or use explicit temp)"

✅ Workaround compiles:
   byte ^DLIST @560
   byte ^ptr = DLIST
   byte value = ptr^
```

---

## Performance Impact

- **Phase 1**: None (assignment only)
- **Phase 2**: One extra copy per non-ZP dereference (negligible)
- **Phase 3**: One extra load/store per arithmetic operation (negligible)

**Typical Program**:
- ~1-3 fixed-address pointers (hardware registers)
- ~5-10 implicit ZP pointers (temporary/working variables)
- Impact: <1% performance difference in typical code

---

## Why This Matters

### Use Cases Currently Broken
```zap
; Atari hardware access
byte ^DLIST @560       ; Can't assign
byte ^PMBASE @$D407    ; Can't assign

; Large memory structures
byte ^sprite_table @$A000
byte ^buffer @$8000
```

### Fixed by This Implementation
- ✅ Assign pointer from hardware register to ZP pointer
- ✅ Use pointer values without dereferencing
- ✅ (Phase 2) Dereference any pointer via temp optimization
- ✅ (Phase 3) Do math on pointer addresses

---

## Decision Tree (Dereferencing)

```
Dereference pointer 'X'
    ↓
Is X in symbol table?
    NO  → Error: "Identifier not found"
    YES ↓
Is X a pointer?
    NO  → Error: "Cannot dereference non-pointer"
    YES ↓
Is X.pointer_in_zp == True?
    YES → ✅ Generate: LDY #0; LDA (X),Y
    NO  ↓
    (Phase 1) Error: "Cannot dereference non-ZP pointer"
    (Phase 2) ✅ Generate: Copy to TMP0, then dereference
```

---

## Summary Table

| Phase | Feature | ZP Pointer | Non-ZP Pointer | Effort |
|-------|---------|-----------|----------------|--------|
| 1 | Assignment | ✅ | ✅ | 2-4h |
| 1 | Dereference | ✅ | ❌ Error | |
| 2 | Dereference | ✅ | ✅ Temp | +4-6h |
| 3 | Arithmetic | ✅ | ✅ Via temp | +6-8h |

---

**Status**: Ready to implement | **Complexity**: Medium | **Priority**: Enables hardware register patterns
