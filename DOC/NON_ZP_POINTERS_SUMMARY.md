# Non-Zero-Page Pointers: Executive Summary

## The Problem

In `003-pointers.zap`:
```zap
byte ^DLIST @560        ; Pointer at fixed address 560 (outside zero page)
byte ^ptr25 = DLIST     ; Trying to assign this pointer value
```

The ZAP compiler currently **requires all pointers to be in zero page** because:
- The 6502 indirect addressing mode `(ptr),Y` only works with zero-page pointers
- The compiler hard-codes this assumption in three key places:
  1. **Memory allocation** forces all pointers to ZP (or fails with exhaustion error)
  2. **Dereferencing code** assumes pointer is in ZP (`TMP0` is a ZP temp)
  3. **Semantic checking** doesn't distinguish pointer location types

## Why This Matters

**Use Cases That Should Work But Don't:**

1. **Hardware Register Pointers** (Atari example):
   ```zap
   byte ^PMBASE @$D407    ; Playfield memory base pointer (fixed HW register)
   byte ^ptr = PMBASE     ; Copy this pointer to ZP for dereferencing
   ptr^ = data            ; NOW safe to dereference
   ```

2. **Large Data Structure Pointers:**
   ```zap
   byte ^sprite_table @$A000  ; Large sprite table pointer (RAM)
   byte ^temp_ptr = sprite_table
   temp_ptr^ = new_sprite
   ```

3. **Pointer Math Without Moving Values:**
   ```zap
   byte ^base_ptr = get_address()
   byte ^offset_ptr = base_ptr + 16  ; Needs support
   ```

## Technical Breakdown

### Where It Fails

**1. Memory Allocation (`gen_vars()` lines 1360-1365)**
```python
pointers = [s for s in all_vars if s.type.is_pointer and s.address is None]
if pointers:
    for sym in pointers:
        if zp_offset + 2 > ZEROPAGE_SIZE:
            raise SemanticError(f"Zero page exhausted: pointer cannot fit")
        # Force into ZP
        self.emit(f"{sym.asm_name()}:\t.res 2")
```
→ All pointers without fixed address MUST fit in ZP or compilation fails.

**2. Fixed-Address Pointers**
```python
fixed = [s for s in all_vars if s.address is not None]
# Emitted as: DLIST = $0560
```
→ These are NOT allocated space - they're just symbolic labels. Can't be stored as variables holding pointer values.

**3. Dereferencing (`_gen_deref()` lines 1691-1709)**
```asm
LDA (TMP0),Y    ; Requires TMP0 to be in zero page
```
→ Assumes pointer is always accessible as a ZP location.

### What Needs to Happen

| Operation | ZP Pointer | Fixed Non-ZP Pointer |
|-----------|-----------|----------------------|
| **Store** | `STA ptr` in ZP | Can't store multiple-byte value at fixed address (needs helper) |
| **Load address** | Works directly | Must build address or copy from label |
| **Dereference** | `(ptr),Y` works | Must copy to ZP temp first |
| **Pointer math** | Can do in-place | Must load, compute, store |

## The Solution in 3 Phases

### Phase 1: Support Non-ZP Pointer Assignment (No Dereferencing)
```python
# In symbols.py
class Symbol:
    pointer_in_zp: bool  # Can be dereferenced with indirect addressing?
    
# In gen_vars()
for sym in pointers_with_fixed_address:
    sym.pointer_in_zp = False  # Mark that it can't be dereferenced directly
```

**Code generated:**
```asm
DLIST = $0560              ; Fixed address (just a constant)
_ptr25: .res 2             ; In ZP, can dereference

; Init: copy DLIST value to ptr25
LDA #$60
LDX #$05
STA _ptr25
STX _ptr25+1
```

**Restrictions:** 
- ✅ Can assign non-ZP pointer to ZP pointer
- ✅ Can read non-ZP pointer value (as constant)
- ❌ Cannot dereference non-ZP pointer directly (error: "pointer must be in ZP to dereference")

### Phase 2: Support Non-ZP Pointer Dereferencing (Via Temp)
```python
def _gen_deref(self, expr: DerefExpr):
    # Determine if pointer is in ZP
    if isinstance(expr.pointer, Identifier):
        sym = self.current_symtab.lookup(expr.pointer.name)
        if not getattr(sym, 'pointer_in_zp', True):
            # Non-ZP pointer: must copy to temp first
            self.gen_expr(expr.pointer)
            self.emit("\tSTA TMP0")
            self.emit("\tSTX TMP0+1")
        else:
            # ZP pointer: use directly
            self.gen_expr(expr.pointer)
            # Falls through to use TMP0 as usual
    # ... rest of dereferencing
    self.emit("\tLDY #0")
    self.emit("\tLDA (TMP0),Y")
```

**Code generated:**
```asm
; When dereferencing DLIST (@$0560):
LDA #$60          ; Build address
LDX #$05
STA TMP0          ; Copy to ZP temp
STX TMP0+1
LDY #0
LDA (TMP0),Y      ; Now dereference works
```

### Phase 3: Support Pointer Arithmetic
- Add rules for pointer + offset operations
- Implement in ZP temp for non-ZP pointers
- Handle WORD arithmetic (16-bit)

## Files to Modify

1. **symbols.py** (~5 lines added)
   - Add `pointer_in_zp: bool = True` field to Symbol

2. **codegen_expr.py** (~50 lines changed/added)
   - `gen_vars()`: Mark non-ZP pointers
   - `_gen_deref()`: Check pointer_in_zp, copy to temp if needed
   - `gen_assign()`: Handle non-ZP pointer assignments

3. **sema_expr.py** (~20 lines added)
   - Add validation that non-ZP pointer dereferencing is only via assignment path
   - Clear error message when attempting unsupported operations

## Validation with Test Case

Current code fails or doesn't support:
```zap
byte ^DLIST @560
byte ^ptr25 = DLIST  ; Assignment
ptr25^ = 123         ; Dereferencing (works after Phase 2)
DLIST^ = 123         ; Dereferencing (error: must use ZP pointer)
```

After implementation, should generate:
```asm
; Phase 1: Assignment works
_ptr25: .res 2
DLIST = $0560

; Init code
LDA #$60
LDX #$05
STA _ptr25
STX _ptr25+1

; Dereferencing ptr25 (in ZP - Phase 1 works)
LDY #0
LDA (_ptr25),Y

; Dereferencing DLIST (Phase 2 - via temp)
; Error prevented or supported by copying to temp first
```

## Impact Assessment

- **Backward compatible**: Existing code (pointers in ZP) works unchanged
- **New capability**: Fixed-address pointers can now be used as values
- **Phase 2 enables**: Dereferencing fixed-address pointers via temp
- **No performance hit**: Only affects non-ZP pointers (typically few per program)

## Next Steps

See [detailed analysis](./ANALYSIS_NON_ZP_POINTERS.md) for:
- Complete technical breakdown of current code
- Root cause analysis
- Line-by-line implementation guidance
- Test case specifications
- Edge case handling
