# Analysis: Non-Zero-Page Pointers in ZAP Compiler

## Problem Statement
The code in `003-pointers.zap` demonstrates the issue:
```zap
byte ^DLIST @560        ; pointer variable placed at address 560 (NOT in zero page)
byte ^ptr25 = DLIST     ; trying to assign this non-ZP pointer to another pointer
```

The 6502 CPU's indirect addressing mode `(ptr),Y` requires the pointer to be in **zero page (0x00-0xFF)**. Currently, the compiler assumes ALL pointers must be in zero page, which causes:

1. **No handling of non-ZP pointers**: Fixed-address pointers outside zero page cannot be dereferenced
2. **Impossible pointer assignment**: Cannot assign a non-ZP pointer value to a ZP pointer
3. **No pointer arithmetic support**: Cannot perform math on non-ZP pointers

## Current Architecture Analysis

### 1. Symbol System (`symbols.py`)
```python
@dataclass(frozen=True)
class SemType:
    base: str            # "byte", "word", "char"
    is_pointer: bool     # ^ marker
    
    @property
    def width(self) -> int:
        if self.is_pointer:
            return 2     # ALL pointers are 2 bytes (16-bit addresses)
```

**Issue**: No distinction between ZP pointers and non-ZP pointers.

### 2. Variable Allocation (`codegen_expr.py::gen_vars()`, lines 1320-1500)
```python
# Zero page offset tracking (starts after emitted system variables)
zp_offset = sum(temp_sizes[n] for n in temps_in_use)
ZEROPAGE_SIZE = 256

# Step 1: ALL POINTERS MUST fit in zero page - fail if they don't
pointers = [s for s in all_vars if not s.is_const and s.address is None and s.type.is_pointer]
if pointers:
    self.emit("; Pointer variables")
    for sym in pointers:
        if zp_offset + 2 > ZEROPAGE_SIZE:
            raise SemanticError(f"Zero page exhausted: pointer '{sym.name}' cannot fit...")
        self.emit(f"{sym.asm_name()}:\t.res 2")
        zp_offset += 2
```

**Hard constraint**: All pointers without explicit addresses are forced into zero page.

### 3. Dereferencing (`codegen_expr.py::_gen_deref()`, lines 1690-1709)
```python
def _gen_deref(self, expr: DerefExpr):
    t = self.tc.check(expr)
    
    # 1) Generate address of pointer → A/X
    self.gen_expr(expr.pointer)
    
    # 2) Store address (word temp uses contiguous bytes)
    self.emit("\tSTA TMP0")
    self.emit("\tSTX TMP0+1")
    
    # 3) Load LOW byte via indirect indexed addressing
    self.emit("\tLDY #0")
    self.emit("\tLDA (TMP0),Y")  # ← Requires TMP0 in zero page!
```

**Assumption**: The pointer address always ends up in `TMP0` (a zero-page temp), so indirect addressing works.

### 4. Assignment to Pointers (`codegen_expr.py::gen_assign()`, lines 2031-2300)
```python
# Fast path: store immediate into dereferenced ZP pointer without temps
if isinstance(lhs, DerefExpr) and isinstance(lhs.pointer, Identifier):
    ptr_sym = self.current_symtab.lookup(lhs.pointer.name)
    if ptr_sym.type.is_pointer and ptr_sym.address is None and not ptr_sym.is_array:
        if isinstance(rhs, IntLiteral) and lhs_t.sem_type.base == "BYTE":
            val = rhs.value & 0xFF
            self.emit(f"\tLDA #${val:02X}")
            if self.is_65c02:
                self.emit(f"\tSTA ({ptr_sym.asm_name()})")  # ← Requires ptr in ZP!
```

**Assumption**: Pointer variables can be dereferenced directly with `(ptr)` addressing, which requires ZP.

### 5. Semantic Type Checking (`sema_expr.py`, lines 35-46)
```python
if sym.type.is_pointer:
    return ExprType(
        sym.type,        # ← is_pointer = True
        ExprKind.ADDR
    )

if isinstance(expr, DerefExpr):
    base = self.check(expr.pointer)
    if base.kind != ExprKind.ADDR or not base.sem_type.is_pointer:
        raise SemanticError("Cannot dereference non-pointer")
    return ExprType(
        SemType(base.sem_type.base, False),
        ExprKind.LVALUE
    )
```

**No distinction**: Treats all pointers the same way semantically.

## Root Causes

### 1. **Conflation of "Pointer Variable" with "Zero-Page Location"**
- A pointer variable is a 2-byte value holding an address
- The pointer variable itself can be anywhere (ZP or not)
- Only when using `(ptr),Y` addressing does it need to be in ZP
- Fixed-address pointer variables (like `^DLIST @560`) can exist outside ZP

### 2. **No Indirect Addressing Flexibility**
- The 6502 has limited indirect addressing modes:
  - `(zp),Y` — requires zp pointer
  - `(zp,X)` — requires zp pointer  
  - Absolute addressing `$XXXX` and `$XXXX,Y` — NO indirect mode!
  
- For non-ZP pointers, we must:
  - **Option A**: Copy non-ZP pointer to a ZP temp, then dereference
  - **Option B**: Use indexed addressing if target is in known memory area
  - **Option C**: Don't dereference non-ZP pointers (copy pointer value only)

### 3. **Missing Use-Case Support**
Current code assumes:
- ✅ Pointers are in ZP for fast dereferencing
- ❌ Non-ZP pointers exist for hardware registers or fixed data structures
- ❌ Need to transfer pointers between ZP and non-ZP locations
- ❌ Need pointer arithmetic on non-ZP pointers

## Solution Architecture

### 1. **Pointer Classification**
Distinguish three pointer types:

```
Type A: ZP Pointers (can be dereferenced directly)
  - Variables without fixed address: `byte ^ptr`
  - Allocated in zero page automatically
  - Can use (ptr),Y addressing directly
  
Type B: Fixed-Address Pointers (outside ZP, cannot dereference directly)
  - Variables with fixed address: `byte ^DLIST @560`
  - Not allocated in ZP
  - Can assign pointer VALUE but must copy to temp to dereference
  
Type C: Pointer Values (address constants)
  - Literal addresses in expressions
  - Can be assigned to either Type A or B
```

### 2. **Extended Symbol Type**
```python
@dataclass(frozen=True)
class SemType:
    base: str              # "byte", "word", "char"
    is_pointer: bool       # ^
    pointer_location: str = "zp"  # NEW: "zp", "fixed", or "any"
```

Or simpler:
```python
# Pointer type information in Symbol:
class Symbol:
    ...
    pointer_in_zp: bool = True  # Can be dereferenced directly?
                                 # False if fixed-address and outside ZP
```

### 3. **Memory Allocation Strategy**

**For non-ZP pointers (with fixed address)**:
- Store as a simple `= $XXXX` assignment (no .res directive)
- Mark that they cannot be dereferenced directly
- Flag as `pointer_in_zp = False`

**For ZP pointers (no fixed address)**:
- Allocate in zero page as before
- Mark as `pointer_in_zp = True`
- Can be dereferenced directly

### 4. **Dereferencing Strategy**

**Type A (ZP pointer) - Direct**:
```asm
; ptr25 is in ZP
LDY #0
LDA (ptr25),Y
```

**Type B (Fixed non-ZP pointer) - Via Temp**:
```asm
; DLIST is at $0560
; Step 1: Load pointer value from non-ZP location
LDA #$60          ; Low byte of $0560
LDX #$05          ; High byte of $0560
STA TMP0          ; Copy pointer to ZP temp
STX TMP0+1

; Step 2: Dereference via ZP temp
LDY #0
LDA (TMP0),Y      ; Now we can dereference
```

### 5. **Pointer Assignment Strategy**

**ZP ← non-ZP**:
```asm
; ptr25 = DLIST (where DLIST is fixed at $0560)
LDA #$60
LDX #$05
STA ptr25         ; ptr25 is in ZP
STX ptr25+1
```

**ZP ← ZP**:
```asm
; ptr1 = ptr2 (both in ZP)
LDA ptr2
LDX ptr2+1
STA ptr1
STX ptr1+1
```

**Fixed non-ZP ← anything** (if needed):
```asm
; DLIST = ptr1
LDA ptr1          ; Load from ZP
LDX ptr1+1
STA __DLIST_LO    ; Store via indirect (would need special handling)
STX __DLIST_HI
```

## Implementation Stages

### Stage 1: Detection & Semantic Analysis
- [ ] Add `pointer_in_zp` flag to Symbol
- [ ] In `gen_vars()`: mark pointers with fixed addresses as `pointer_in_zp=False`
- [ ] In semantic checking: determine if pointer can be dereferenced directly
- [ ] Add check: reject dereferencing of non-ZP pointers with clear error message

### Stage 2: Non-ZP Pointer Support (No Dereferencing)
- [ ] Allow fixed-address pointers to exist outside ZP
- [ ] Support assigning non-ZP pointer values to ZP pointers
- [ ] Support pointer arithmetic on loaded non-ZP pointers (as values)
- [ ] Fail gracefully when attempting to dereference non-ZP pointers

### Stage 3: Non-ZP Pointer Dereferencing (Via Temp)
- [ ] Implement temp-based dereferencing for non-ZP pointers
- [ ] Modify `_gen_deref()` to detect pointer location
- [ ] If non-ZP: copy to ZP temp first, then dereference
- [ ] Ensure temp management doesn't conflict with existing code

### Stage 4: Pointer Arithmetic
- [ ] Support operations like `ptr + offset`
- [ ] For ZP pointers: do arithmetic in-place or via temps
- [ ] For non-ZP pointers: load to accumulator, compute, store back

## Code Change Summary

### Modified Files
1. **symbols.py**: Add `pointer_in_zp` flag
2. **codegen_expr.py**: 
   - `gen_vars()`: Detect non-ZP pointers
   - `_gen_deref()`: Handle via-temp dereferencing
   - `gen_assign()`: Handle non-ZP pointer assignments
3. **sema_expr.py**: Add validation for pointer dereferencing capabilities

### New/Clarified Semantics
- Fixed-address pointers can be ASSIGNED but not DEREFERENCED directly
- Dereferencing requires pointer to be in zero page or explicitly copied to temp
- Pointer VALUES can be used regardless of storage location
- Pointer ARITHMETIC requires temp storage or ZP location

## Test Case Validation

From `003-pointers.zap`:
```zap
byte ^DLIST @560        ; Fixed pointer outside ZP
byte ^ptr25 = DLIST     ; Assign pointer value from non-ZP to ZP

; Expected behavior:
; 1. DLIST is stored as constant $0560
; 2. ptr25 gets initialized with value $0560 in ZP
; 3. ptr25 can be dereferenced normally
; 4. DLIST cannot be dereferenced directly
```

Generated code should be:
```asm
; Initialize ptr25 with DLIST value
_ptr25:     .res 2
DLIST = $0560

; In init code:
LDA #$60
LDX #$05
STA _ptr25
STX _ptr25+1

; When dereferencing ptr25:
LDY #0
LDA (_ptr25),Y    ; Valid - ptr25 is in ZP

; Attempting to dereference DLIST:
; ✗ Should error or require:
;   LDA #$60
;   LDX #$05
;   STA TMP0
;   STX TMP0+1
;   LDY #0
;   LDA (TMP0),Y
```

## Summary

The core issue is treating pointer storage location and pointer dereferenceability as the same thing. The fix involves:

1. **Semantic**: Distinguish between "pointer variable location" and "can use indirect addressing"
2. **Allocation**: Allow pointers to be stored outside ZP (especially fixed-address ones)
3. **Codegen**: Implement temp-based dereferencing when pointer is not in ZP
4. **Error handling**: Clear messages when operations aren't supported

This maintains backward compatibility (all implicit pointers still in ZP) while adding flexibility for fixed-address hardware registers and other non-ZP pointer scenarios.
