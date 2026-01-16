# Implementation Guide: Non-ZP Pointer Support

## Quick Reference: Code Change Locations

### 1. symbols.py - Add pointer location tracking

**Location**: After the Symbol class definition (around line 30)
**Change**: Add flag to track if pointer is in zero page

```python
@dataclass
class Symbol:
    name: str
    type: SemType
    is_const: bool
    const_value: int | None    
    is_array: bool
    array_len: Optional[int]
    init: Optional[object]
    address: Optional[int] = None          # Fixed address (existing)
    is_volatile: bool = False              # (existing)
    proc_name: str = ""                    # (existing)
    pointer_in_zp: bool = True  # NEW: Can use indirect addressing directly?
```

### 2. codegen_expr.py - Three key methods

#### 2a. Mark non-ZP pointers in gen_vars()

**Location**: [codegen_expr.py](codegen_expr.py#L1360-L1365), after pointers loop  
**Current code** (lines 1360-1365):
```python
pointers = [s for s in all_vars if not s.is_const and s.address is None and s.type.is_pointer]
if pointers:
    self.emit("; Pointer variables")
    for sym in pointers:
        if zp_offset + 2 > ZEROPAGE_SIZE:
            raise SemanticError(f"Zero page exhausted: pointer '{sym.name}' cannot fit...")
        self.emit(f"{sym.asm_name()}:\t.res 2")
        zp_offset += 2
```

**After fixed addresses emit** (lines 1349-1354):
```python
fixed = [s for s in all_vars if getattr(s, "address", None) is not None]
if fixed:
    self.emit("; Fixed-address variables")
    for sym in fixed:
        self.emit(f"{sym.asm_name()} = ${sym.address:04X}")
        self.fixed_address_labels.add(sym.asm_name())
        # NEW: Mark fixed-address pointers as non-ZP
        if sym.type.is_pointer:
            sym.pointer_in_zp = False  # Can't dereference directly
    self.emit("")
```

**Change**:
- After processing fixed addresses, mark pointers with addresses as `pointer_in_zp = False`
- Pointers without fixed addresses remain `pointer_in_zp = True` (default)

#### 2b. Handle non-ZP pointers in _gen_deref()

**Location**: [codegen_expr.py](codegen_expr.py#L1690-L1709), method `_gen_deref()`  
**Current code**:
```python
def _gen_deref(self, expr: DerefExpr):
    t = self.tc.check(expr)

    # 1) vygeneruj adresu pointeru → A/X
    self.gen_expr(expr.pointer)

    # 2) ulož adresu (word temp uses contiguous bytes)
    self.emit("\tSTA TMP0")
    self.emit("\tSTX TMP0+1")

    # 3) načti LOW byte
    self.emit("\tLDY #0")
    self.emit("\tLDA (TMP0),Y")

    # 4) WORD? načti HIGH byte
    if t.sem_type.base == "WORD":
        self.emit("\tINY")
        self.emit("\tLDX (TMP0),Y")
```

**Change**: Add check for non-ZP pointer BEFORE generating the expression:
```python
def _gen_deref(self, expr: DerefExpr):
    t = self.tc.check(expr)

    # Check if this is a fixed-address (non-ZP) pointer that we can't dereference
    if isinstance(expr.pointer, Identifier):
        sym = self.current_symtab.lookup(expr.pointer.name)
        if not getattr(sym, 'pointer_in_zp', True):
            # For now, this is an error (Phase 1)
            # Later (Phase 2), implement via-temp dereferencing:
            # self.gen_expr(expr.pointer)
            # self.emit("\tSTA TMP0")
            # self.emit("\tSTX TMP0+1")
            # Then continue with normal dereferencing below
            raise SemanticError(f"Cannot dereference non-ZP pointer '{sym.name}' - "
                              f"must be in zero page (place in ZP variable or use explicit temp)")

    # 1) vygeneruj adresu pointeru → A/X
    self.gen_expr(expr.pointer)
    # ... rest unchanged
```

#### 2c. Support non-ZP pointer assignment in gen_assign()

**Location**: [codegen_expr.py](codegen_expr.py#L2031-L2050), after pointer assignment validation  
**Current code** (lines 2045-2055):
```python
# Allow ADDR = ADDR for pointer assignments
if lhs_t.kind == ExprKind.ADDR and lhs_t.sem_type.is_pointer:
    if rhs_t.kind != ExprKind.ADDR and rhs_t.kind != ExprKind.VALUE:
        raise SemanticError("Cannot assign to pointer")
    # Type compatibility for pointers (WORD base for all pointers)
```

**Add after pointer assignment block**:
```python
# Pointer-to-pointer assignments (including non-ZP pointers)
if lhs_t.kind == ExprKind.ADDR and lhs_t.sem_type.is_pointer and \
   rhs_t.kind == ExprKind.ADDR and rhs_t.sem_type.is_pointer:
    # Assigning pointer to pointer - check if RHS is non-ZP
    rhs_in_zp = True
    if isinstance(rhs, Identifier):
        rhs_sym = self.current_symtab.lookup(rhs.name)
        rhs_in_zp = getattr(rhs_sym, 'pointer_in_zp', True)
    # Assignment works regardless of pointer location
    # Code generation (below) will handle loading the address correctly
```

### 3. sema_expr.py - Add semantic validation (optional for Phase 1)

**Location**: [sema_expr.py](sema_expr.py#L44-L48), in DerefExpr checking  
**Current code**:
```python
if isinstance(expr, DerefExpr):
    base = self.check(expr.pointer)
    if base.kind != ExprKind.ADDR or not base.sem_type.is_pointer:
        raise SemanticError("Cannot dereference non-pointer")
    return ExprType(
        SemType(base.sem_type.base, False),
        ExprKind.LVALUE
    )
```

**No change needed for Phase 1** - error will be caught in codegen

## Summary Table: Change Complexity

| File | Lines | Type | Impact | Difficulty |
|------|-------|------|--------|------------|
| **symbols.py** | ~1 | Add field | Medium - new tracking | Easy |
| **codegen_expr.py - gen_vars** | ~10 | Mark non-ZP | Medium - affects allocation | Easy |
| **codegen_expr.py - _gen_deref** | ~8 | Error check | Medium - Phase 1 only | Easy |
| **codegen_expr.py - gen_assign** | ~0 | (works as-is) | None for Phase 1 | N/A |
| **sema_expr.py** | ~0 | (works as-is) | None for Phase 1 | N/A |

**Total Phase 1 Changes**: ~20 lines of code added/modified

## Phase 1 Behavior

After Phase 1 implementation:

### ✅ What Works
```zap
byte ^DLIST @560           ; Fixed non-ZP pointer (compiles)
byte ^ptr25 = DLIST        ; Assign pointer value (compiles, initializes correctly)
byte ^ptr26                ; Normal ZP pointer (compiles, unchanged)
```

### ✅ Code Generated
```asm
_ptr25: .res 2             ; In ZP
_ptr26: .res 2             ; In ZP
DLIST = $0560              ; Fixed address (constant)

; Init code
LDA #$60                   ; Load non-ZP pointer value
LDX #$05
STA _ptr25                 ; Store in ZP pointer
STX _ptr25+1
```

### ✅ Dereferencing Works
```zap
byte ^ptr25 = DLIST
byte data = ptr25^         ; ✅ Works - ptr25 is in ZP
```

### ❌ Not Yet Supported
```zap
byte ^DLIST @560
byte data = DLIST^         ; ❌ Error: "Cannot dereference non-ZP pointer"
```

This will work in Phase 2.

## Testing Strategy

### Test 1: Assignment from Non-ZP Pointer
```zap
byte ^DLIST @560
byte ^ptr = DLIST

proc main()
    ; ptr should now hold address $0560
end
```
Expected: Compiles and initializes ptr with $0560

### Test 2: Dereferencing via ZP Pointer (Phase 1)
```zap
byte ^DLIST @560
byte ^ptr = DLIST
byte value

proc main()
    value = ptr^           ; ✅ Should work
    ptr^ = 42             ; ✅ Should work
end
```

### Test 3: Direct Non-ZP Dereference (Phase 1 - should error)
```zap
byte ^DLIST @560

proc main()
    byte value = DLIST^   ; ❌ Error: cannot dereference non-ZP pointer
end
```
Expected: Clear error message

## Edge Cases to Handle

1. **Multiple pointers to same fixed address**
   ```zap
   byte ^DLIST @560
   byte ^ptr1 = DLIST
   byte ^ptr2 = DLIST     ; Both valid
   ```

2. **Pointer assignment chains**
   ```zap
   byte ^A @560
   byte ^B = A
   byte ^C = B            ; Should work (transitively)
   ```

3. **Pointer in expression**
   ```zap
   byte ^DLIST @560
   byte ^ptr = DLIST + 0  ; Address arithmetic
   ```

4. **Array of pointers**
   ```zap
   byte ^DLIST @560
   word ^ptrs[3] = {DLIST, ...}  ; Mixed pointer types
   ```

## Validation Checklist

- [ ] Symbol class has `pointer_in_zp` field with default True
- [ ] gen_vars() marks fixed-address pointers as `pointer_in_zp = False`
- [ ] _gen_deref() checks pointer_in_zp and raises error for Phase 1
- [ ] Test case 003-pointers.zap compiles (assignment part)
- [ ] Test case fails with clear message on dereference (Phase 1)
- [ ] Existing pointer tests still pass
- [ ] Zero page allocation unchanged for implicit pointers

## Phase 2 Preparation

For Phase 2 (via-temp dereferencing), keep these in mind:

1. Ensure TMP0/TMP1 are always available as ZP temps
2. Track temp usage to avoid conflicts
3. Handle nested dereferencing (ptr1^ = ptr2^)
4. Consider optimizing consecutive accesses to same non-ZP pointer

---

**Next**: Create Phase 2 implementation guide after Phase 1 testing passes.
