# Phase 3.2: Struct Arrays and Pointer Arithmetic - Implementation Status

## ✅ Completed

### 1. **Arrays of Struct Variables**
- ✅ Parsing: `Point arr[3]` parses correctly
- ✅ Semantic Analysis: Array element types preserve struct info (is_struct=True, struct_info populated)
- ✅ Code Generation: Array subscript field access generates correct code (e.g., `arr[0].x = 1`)
- ✅ Assembly Generation: Proper address calculations with field offsets

**Key Fix**: In `sema_expr.py`, preserved `is_struct` and `struct_info` when:
1. Creating array element types from subscript expressions
2. Creating array address types from identifier lookup

### 2. **Struct Field Access on Array Elements**
- ✅ Direct struct: `pt.x = 1` works
- ✅ Array element: `arr[0].x = 1` now works
- ✅ Multiple elements: `arr[1].x`, `arr[2].y` all work correctly

**Generated Assembly** (example for `arr[0].x = 1` where x is at offset 0):
```asm
LDA #<_MAIN_ARR       ; Load array base address
LDX #>_MAIN_ARR
STA TMP0
STX TMP0+1
LDA #0                ; Index 0
CLC
ADC TMP0              ; Add to base address
STA TMP0              ; Store element address
LDY #0
LDA (TMP0),Y          ; Load field at offset 0
LDA TMP2              ; Load RHS value
STA (TMP0),Y          ; Store to field
```

## 🚧 In Progress

### 3. **Pointer Arithmetic with Struct Size**
- ✅ Infrastructure: ptr_elem_size is calculated for struct pointers
- 🚧 Code Generation: Need to handle arbitrary struct sizes in _gen_add / _gen_sub
- Status: Can handle size=1,2 but arbitrary sizes need different multiplication logic

**What's needed**:
- When `ptr = ptr + 1` and ptr points to struct of size N
- Need to multiply offset by N before adding
- Current code handles size=2 (uses ASL), needs general case

## ❌ Not Started / Issues Found

### 4. **Local Struct Variable Memory Allocation** 
- ❌ **ISSUE**: Local struct variables like `Point local_pt` are not allocated in any segment (not in ZEROPAGE, BSS, or CODE)
- Generated assembly references `_MAIN_LOCAL_PT` but doesn't define it
- This breaks program execution
- **Root Cause**: Code generator doesn't allocate storage for local struct variables

**Next Steps for Fix**:
1. Check codegen where it allocates local variable storage
2. Add struct variables to allocation logic
3. Allocate full struct size (not just 1 byte)

### 5. **Global Struct Variables**
- ❌ Global struct instances (`Point global_pt`) are not yet supported
- Parser recognizes them, but symbol table issues during compilation
- Need to verify declaration analysis for global struct variables

### 6. **BSS Segment for Struct Arrays**
- ⚠️ **ISSUE**: Struct arrays allocate in BSS but with WRONG size
  - Test: `Point arr[3]` (3 elements × 2 bytes = 6 bytes)
  - Generated: `.res 3` (only 3 bytes!)
  - **Root Cause**: Array size calculation doesn't multiply by element size for structs

**Fix Needed**:
```
Array allocation size = array_len * sizeof(struct_element)
Not just: array_len
```

## Test Results

```
✅ test_struct_codegen.py       - 3/3 passed (direct field access)
✅ test_struct_arrays.py         - 2/2 passed (parsing + pointer arithmetic setup)
   - Struct Array Access:        ✅ PASS
   - Pointer Arithmetic:         ✅ PASS (ptr assignment works, no struct sizeof test yet)

❌ test_bss_allocation.py       - Local struct variables not allocated
```

## Code Changes Made

1. **sema_expr.py** (lines 28-42):
   - Fixed array type lookup to preserve struct metadata
   - Fixed subscript element type to preserve struct metadata

2. **sema_expr.py** (lines 147-159):
   - Allow LVALUE expressions (array elements) for direct field access
   - Was only allowing VALUE (strict struct variables)

3. **codegen_expr.py** (lines 2857-2910):
   - Added SubscriptExpr handling for direct field access
   - Generate proper address calculation for array element field access
   - Handle both read and write for array element fields

4. **codegen_expr.py** (lines 2959-2970):
   - Calculate ptr_elem_size from struct size when available
   - Pass struct size to pointer arithmetic functions

5. **parser.py** (lines 97-137):
   - Added `.include` directive handling at top level
   - Skip unknown identifiers (BOM characters)
   - Support struct type declarations at top level

6. **parser.py** (lines 8-20):
   - Remove UTF-8 BOM from source code (platform-dependent encoding)

## Known Limitations

- Struct arrays size calculation broken (allocates too little space)
- Local struct variables not allocated in memory
- Global struct variables not supported yet
- Pointer arithmetic only tested with non-struct pointers
- Odd-sized structs may not work with pointer arithmetic

## Next Priority Fixes

1. **FIX LOCAL STRUCT ALLOCATION** - Blocker for basic functionality
2. **FIX ARRAY SIZE CALCULATION** - Blocker for arrays
3. **Test pointer arithmetic with struct sizes**
4. **Support global struct variables**
