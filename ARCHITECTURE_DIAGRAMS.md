# Non-ZP Pointers: Architecture Diagrams

## 1. Memory Layout Comparison

### Current System (ZP-Only Pointers)
```
Zero Page (0x00-0xFF)
┌─────────────────────────┐
│ TMP0, TMP1, TMP2, TMP3  │ ← System temps
│ (8 bytes)               │
├─────────────────────────┤
│ ptr1: 2 bytes           │ ← All pointers MUST fit here
│ ptr2: 2 bytes           │   or compilation fails
│ ...                     │
├─────────────────────────┤
│ var_a: 1 byte           │ ← Regular variables
│ var_b: 2 bytes          │
│ ...                     │
└─────────────────────────┘

RAM (0x100-0xFFFF)
┌─────────────────────────┐
│ array[256]              │ ← Arrays always here
│ string_data             │
│ code                    │
└─────────────────────────┘

Hardware Registers (e.g., 0x0560)
┌─────────────────────────┐
│ DLIST @$0560            │ ← Fixed address HW register
│                         │   (NOT a variable, just a constant)
└─────────────────────────┘
```

### After Phase 1 (Non-ZP Pointer Support)
```
Zero Page (0x00-0xFF)
┌─────────────────────────┐
│ TMP0, TMP1, TMP2, TMP3  │ ← System temps
│ (8 bytes)               │
├─────────────────────────┤
│ ptr1: 2 bytes           │ ← ZP pointers only
│ ptr2: 2 bytes           │   (implicit, auto-allocated)
│ ...                     │
├─────────────────────────┤
│ var_a: 1 byte           │ ← Regular variables
│ var_b: 2 bytes          │
│ ...                     │
└─────────────────────────┘

Fixed Addresses (scattered)
┌─────────────────────────┐
│ DLIST = $0560           │ ← Non-ZP pointer (symbolic constant)
│ PMBASE = $0407          │   Not allocated as variable
├─────────────────────────┤
│ ptr_to_dlist: 2 bytes   │ ← ZP pointer holding value $0560
│ (in ZP section)         │   Can be dereferenced
└─────────────────────────┘

RAM (0x100-0xFFFF)
┌─────────────────────────┐
│ array[256]              │ ← Arrays always here
│ string_data             │
│ code                    │
└─────────────────────────┘
```

## 2. Data Flow: Pointer Declaration

### Case A: Implicit ZP Pointer
```
Source Code:
  byte ^ptr1

Parser:
  Declarator(name="ptr1", type=PointerType(byte))

Semantic Analysis:
  Symbol(name="ptr1", type=SemType("byte", is_pointer=True))

Memory Allocation (gen_vars):
  ✓ No address specified
  ✓ Add to ZP allocation
  ✓ Mark: pointer_in_zp = True (default)

Generated Code:
  _ptr1: .res 2  (in ZEROPAGE segment)
```

### Case B: Fixed-Address Pointer
```
Source Code:
  byte ^DLIST @560

Parser:
  Declarator(name="DLIST", type=PointerType(byte), address=560)

Semantic Analysis:
  Symbol(name="DLIST", type=SemType("byte", is_pointer=True), address=560)

Memory Allocation (gen_vars):
  ✓ Address specified
  ✓ NOT added to ZP allocation
  ✓ Mark: pointer_in_zp = False (NEW)
  ✓ Emit as constant: DLIST = $0560

Generated Code:
  DLIST = $0560  (symbolic constant, no memory allocated)
```

## 3. Data Flow: Pointer Assignment

### Assignment: ZP ← Non-ZP Pointer Value

```
Source Code:
  byte ^DLIST @560
  byte ^ptr = DLIST

AST:
  VarDecl(name="ptr", type=PointerType, init=Identifier("DLIST"))

Type Checking:
  lhs: SemType("byte", is_pointer=True, in_zp=True)
  rhs: SemType("byte", is_pointer=True, in_zp=False)
  ✓ Compatible - both pointers

Code Generation:
  ┌─ Load DLIST address ──────┐
  │ LDA #$60                  │ Load low byte
  │ LDX #$05                  │ Load high byte
  │ (both are constants)      │
  │                           │
  ├─ Store to ZP pointer ────┤
  │ STA _ptr                  │ Store in zero page
  │ STX _ptr+1                │
  └───────────────────────────┘

Result:
  _ptr (in ZP) = $0560 ✓
  Can be dereferenced normally
```

## 4. Dereferencing: Three Scenarios

### Scenario A: ZP Pointer (Direct - Works Always)
```
Code:     byte ^ptr = some_zp_address
          byte value = ptr^

Compiler:
  ptr is in ZP (pointer_in_zp = True)
  
Generated:
  LDY #0          ← Setup indirect addressing
  LDA (_ptr),Y    ← Direct dereference
                    (requires ptr to be in ZP)
  
Status: ✅ WORKS (Phase 1 & beyond)
```

### Scenario B: Non-ZP Fixed Address Pointer (Phase 1 - ERROR)
```
Code:     byte ^DLIST @560
          byte value = DLIST^

Compiler:
  DLIST is not in ZP (pointer_in_zp = False)
  
Generated:
  ERROR: "Cannot dereference non-ZP pointer 'DLIST' - 
           must be in zero page"

Status: ❌ ERROR (Phase 1)
        ✅ WORKS (Phase 2 via temp)
```

### Scenario C: Non-ZP Pointer via Assignment (Workaround)
```
Code:     byte ^DLIST @560
          byte ^temp = DLIST
          byte value = temp^

Compiler:
  DLIST non-ZP but assigned to temp (which IS in ZP)
  temp is in ZP (pointer_in_zp = True)
  
Generated:
  ; Initialization
  LDA #$60        ← Load DLIST address
  LDX #$05
  STA _temp       ← Store in ZP pointer temp
  STX _temp+1
  
  ; Dereferencing
  LDY #0
  LDA (_temp),Y   ← Works! temp is in ZP
  
Status: ✅ WORKS (Phase 1)
        Better: ✅ DIRECT (Phase 2)
```

## 5. Decision Tree: Can We Dereference This Pointer?

```
Dereferencing pointer 'X':
│
├─ Is X in the symbol table?
│  │
│  ├─ NO → ERROR: "Identifier not found"
│  │
│  └─ YES → Continue
│
├─ Is X actually a pointer?
│  │
│  ├─ NO → ERROR: "Cannot dereference non-pointer"
│  │
│  └─ YES → Continue
│
├─ Is X.pointer_in_zp == True?
│  │
│  ├─ YES → ✅ GENERATE: LDY #0; LDA (X),Y
│  │        (direct zero page indirect)
│  │
│  └─ NO → Continue
│
├─ Phase 1: Is this a fixed-address pointer?
│  │
│  ├─ YES → ❌ ERROR: "Cannot dereference non-ZP pointer"
│  │
│  └─ NO → Continue
│
└─ Phase 2: Can we copy to temp?
   │
   ├─ TMP0 available? → ✅ GENERATE: Copy to TMP0, then dereference
   │
   └─ NO temps? → ❌ ERROR: "Out of temporary registers"
```

## 6. Symbol Table Evolution

### Before Processing
```python
Symbol(
    name="DLIST",
    type=SemType("byte", is_pointer=True),
    address=560,
    # pointer_in_zp field doesn't exist yet
)
```

### After Phase 1 Implementation
```python
Symbol(
    name="DLIST",
    type=SemType("byte", is_pointer=True),
    address=560,
    pointer_in_zp=False  # NEW: Can't use indirect addressing
)

Symbol(
    name="ptr",
    type=SemType("byte", is_pointer=True),
    address=None,  # Auto-allocated
    pointer_in_zp=True  # NEW: CAN use indirect addressing
)
```

## 7. Code Generation Examples

### Example 1: Initialize Pointer from Non-ZP Constant

```
ZAP:  byte ^ptr = DLIST where DLIST @560

ASM:  _ptr: .res 2
      DLIST = $0560
      
      ; Initialization code
      LDA #$60
      STA _ptr
      LDX #$05
      STX _ptr+1
```

### Example 2: Copy Between Pointers

```
ZAP:  byte ^src = DLIST    (non-ZP)
      byte ^dst = SOMETHING (ZP)
      dst = src             (copy pointer)

ASM:  LDA #$60     ; Load src value (which is DLIST address)
      LDX #$05
      STA _dst     ; Store to ZP pointer dst
      STX _dst+1
```

### Example 3: Dereference with Temp (Phase 2 Preview)

```
ZAP:  byte ^DLIST @560
      byte value = DLIST^  (when Phase 2 supports it)

ASM:  ; Copy DLIST address to ZP temp
      LDA #$60
      STA TMP0
      LDX #$05
      STX TMP0+1
      
      ; Dereference via temp
      LDY #0
      LDA (TMP0),Y
```

## 8. Memory Allocation Algorithm (Phase 1)

```
gen_vars() flow:
│
├─ Collect all variables (globals + locals)
├─ Emit fixed-address items
│  └─ Mark their pointer_in_zp = False
│
├─ Calculate ZP offset (after system temps)
│
├─ Process POINTERS
│  ├─ Find: pointers with NO fixed address
│  ├─ These must go in ZP (pointer_in_zp = True)
│  ├─ Check ZP space available
│  └─ Allocate 2 bytes each
│
├─ Process BYTE variables
│  ├─ Try to fit in remaining ZP space
│  └─ Overflow to BSS if necessary
│
├─ Process WORD variables
│  ├─ Try to fit in remaining ZP space
│  └─ Overflow to BSS if necessary
│
└─ Process ARRAYS
   └─ Always go to BSS (never in ZP)
```

## 9. Phase Implementation Roadmap

```
Phase 1: Support Non-ZP Pointer Assignment
┌──────────────────────────────────────────┐
│ ✅ Fixed-address pointers (non-ZP)       │
│ ✅ Assign to ZP pointers                 │
│ ✅ Use as pointer values                 │
│ ❌ Dereference non-ZP pointers          │
│ ❌ Pointer arithmetic on non-ZP         │
└──────────────────────────────────────────┘
         ↓ (after Phase 1 validated)
         
Phase 2: Non-ZP Pointer Dereferencing
┌──────────────────────────────────────────┐
│ ✅ Dereference via temp (copy & use)     │
│ ✅ Optimize consecutive accesses         │
│ ❌ Pointer arithmetic                    │
└──────────────────────────────────────────┘
         ↓ (after Phase 2 validated)
         
Phase 3: Pointer Arithmetic
┌──────────────────────────────────────────┐
│ ✅ ptr + offset operations               │
│ ✅ Work with both ZP and non-ZP         │
│ ✅ 16-bit math support                   │
└──────────────────────────────────────────┘
```

## 10. Test Matrix

| Scenario | ZP Pointer | Non-ZP Pointer | Phase 1 | Phase 2 |
|----------|-----------|----------------|---------|---------|
| Declare | ✅ | ✅ | ✅ | ✅ |
| Assign value | ✅ | ✅ | ✅ | ✅ |
| Read as address | ✅ | ✅ | ✅ | ✅ |
| Dereference (read) | ✅ | ❌ | ❌ | ✅ |
| Dereference (write) | ✅ | ❌ | ❌ | ✅ |
| Pointer arithmetic | ✅ | ❌ | ❌ | ✅ |
| Via temp workaround | ✅ | ✅ | ✅ | ✅ |

---

**Note**: "Via temp workaround" means users can create a ZP pointer and assign the non-ZP value to it, then dereference the ZP pointer. This works in Phase 1 but is inefficient. Phase 2 automates this optimization.
