# Multi-Dimensional Arrays Implementation Design

**Date**: January 20, 2026  
**Status**: Design Phase  
**Priority**: Phase 4 - Remaining Language Features

## Overview

This document specifies the design for multi-dimensional array support in the ZAP! compiler. Multi-dimensional arrays will support all element types including BYTE, WORD, pointers, and structs, with all data allocated in the BSS segment.

## Current State (1D Arrays)

### AST Representation
```python
class Declarator(ASTNode):
    array_size: Optional[Expr]  # Single dimension size
```

### Type Representation
```python
class Symbol:
    is_array: bool
    array_len: Optional[int]    # Single dimension length
```

### Indexing
```python
class SubscriptExpr(Expr):
    array: Expr       # Must be Identifier for 1D
    index: Expr       # Single index expression
```

## Proposed Design

### 1. AST Changes

#### Extended Declarator
```python
class Declarator(ASTNode):
    name: str
    array_sizes: List[Optional[Expr]]  # [] for each dimension
    address: Optional[Expr]
    initializer: Optional[InitValue]
    line: int = 0
    col: int = 0
```

**Backward Compatibility**: Single dimension `array_size` maps to `array_sizes[0]`

#### Extended SubscriptExpr
```python
class SubscriptExpr(Expr):
    array: Expr           # Can be nested SubscriptExpr or Identifier
    indices: List[Expr]   # One index per dimension
```

**Note**: `SubscriptExpr(array, index)` becomes `SubscriptExpr(array, [index])`

**Chaining Support**: `arr[i][j][k]` becomes:
```
SubscriptExpr(
  SubscriptExpr(
    SubscriptExpr(Identifier("arr"), [i]),
    [j]
  ),
  [k]
)
```

### 2. Parser Changes

#### Grammar Extension
```ebnf
declarator = ident [ array_dimension { array_dimension } ] 
             [ initializer ] [ address_spec ] ;

array_dimension = "[" [ expr ] "]" ;
```

#### Example Syntax
```zap
BYTE arr[10]              ; 1D array
BYTE arr[3][4]            ; 2D array (3×4)
BYTE arr[2][3][4]         ; 3D array (2×3×4)
BYTE arr[]                ; Infer 1D
BYTE arr[3][]             ; INVALID - only trailing [] can be inferred
BYTE arr[3][4] = { ... }  ; Initialize
```

#### Parser Implementation
```python
def parse_declarator():
    name = self.cur.value
    self.expect(TOK_IDENT)
    
    array_sizes = []
    while self.cur.type == TOK_LSQB:
        self.advance()
        if self.cur.type == TOK_RSQB:
            # Empty []
            array_sizes.append(IntLiteral(-1))  # -1 = infer
        else:
            array_sizes.append(self.parse_expr())
        self.expect(TOK_RSQB)
    
    # array_sizes will be empty list for non-arrays
    # Single element for 1D, multiple for ND
    ...
```

### 3. Type System Changes

#### Extended Symbol
```python
class Symbol:
    name: str
    type: SemType
    is_array: bool
    array_dims: List[int]      # [10, 20, 30] for 3D array
    array_elem_type: SemType   # Type of actual elements
```

**Key**: Track dimensions separately from element type

#### Symbol Size Calculation
```python
def get_array_total_size(sym: Symbol) -> int:
    """Calculate total bytes for multi-dimensional array"""
    if not sym.is_array:
        return 0
    
    # Product of all dimensions × element size
    total = sym.type.width  # Element width
    for dim in sym.array_dims:
        total *= dim
    return total
```

### 4. Code Generation Changes

#### Variable Allocation (gen_vars)
Current implementation:
```python
total_size = size * element_size
self.emit(f"{sym.asm_name()}:\t.res {total_size}")
```

**No changes needed** - Already calculates `total_size` correctly!
The BSS allocation will work with any multi-dimensional array.

#### Subscript Expression Code Generation

**Current 1D Implementation**:
```
arr[i] @ address A
  1. Load base address → TMP0/TMP0+1
  2. Calculate index offset = i × element_size
  3. Add to base: A = base + offset
  4. Access memory at A
```

**New ND Implementation** - Row-major layout (C-style):
```
arr[i][j][k] @ address A

Dimensions: [d1][d2][d3] with element size E
Strides: [s1, s2, s3] = [d2×d3×E, d3×E, E]

Offset = i×s1 + j×s2 + k×s3
       = i×(d2×d3×E) + j×(d3×E) + k×E

Nested SubscriptExpr:
  Inner: arr[i] evaluates to address of arr[i][0][0]
  Middle: arr[i][j] evaluates to address of arr[i][j][0]
  Outer: arr[i][j][k] evaluates to actual element
```

**Algorithm**:
```python
def _gen_subscript(self, expr: SubscriptExpr):
    # expr.array can be:
    #   1. Identifier (innermost dimension)
    #   2. SubscriptExpr (recursive case)
    # expr.indices: List[Expr] (one or more indices)
    
    if isinstance(expr.array, Identifier):
        # Base case: Load array base address
        sym = lookup(expr.array.name)
        self._load_sym_addr(sym.asm_name())  # → TMP0/TMP0+1
        
        # Calculate offset for innermost dimension
        offset = self._calculate_offset(sym, expr.indices[0])
    else:
        # Recursive case: Get address from arr[i][j]
        addr = self._gen_subscript(expr.array)  # → TMP0/TMP0+1
        
        # Calculate additional offset for next dimension
        dimensions = self._get_array_dimensions(expr.array)
        offset = self._calculate_offset_for_dim(dimensions, expr.indices[0])
    
    # Add offset to address
    self._add_offset_to_address(TMP0, offset)
    
    return address_in_TMP0
```

### 5. Initialization Changes

#### Current ListInit for 1D
```zap
BYTE arr[3] = { 1, 2, 3 }
```

#### New ListInit for 2D
```zap
BYTE arr[2][3] = {
  { 1, 2, 3 },    ; Row 0
  { 4, 5, 6 }     ; Row 1
}
```

#### Parser Support (Already Exists!)
```python
class ListInit(InitValue):
    values: List["Expr | InitValue"]  # Already recursive!
```

✅ The `ListInit` structure already supports nesting!

#### Code Generation for Initialization
Flatten nested lists into linear memory layout:
```
Logical:  arr[2][3] = { {1,2,3}, {4,5,6} }
Linear:   [1, 2, 3, 4, 5, 6]
```

```python
def _flatten_init_values(init: InitValue, dims: List[int]) -> List[int]:
    """Convert nested ListInit to flat list matching array layout"""
    if isinstance(init, ListInit):
        result = []
        for val in init.values:
            result.extend(_flatten_init_values(val, dims[1:]))
        return result
    elif isinstance(init, ExprInit):
        return [init.expr]
    else:
        return []
```

### 6. Semantic Analysis Changes

#### Validation Rules
1. **Dimension Count Consistency**: Declaration dimensions must match usage
   ```zap
   BYTE arr[3][4]
   arr[i][j]         ; ✓ OK - 2 indices
   arr[i]            ; ✓ OK - Getting pointer to arr[i][0..]
   arr[i][j][k]      ; ✗ ERROR - Too many indices
   ```

2. **Index Type Checking**: All indices must be byte/word expressions
   ```zap
   BYTE arr[3][4]
   arr[1][2]         ; ✓ OK
   arr[1.5][2]       ; ✗ ERROR - Float not allowed
   ```

3. **Initialization Compatibility**: Shape must match
   ```zap
   BYTE arr[2][3] = { 1, 2, 3, 4, 5, 6 }  ; ✓ OK - 6 elements
   BYTE arr[2][3] = { {1,2,3}, {4,5,6} }   ; ✓ OK - 2×3 structure
   BYTE arr[2][3] = { 1, 2 }               ; ✗ ERROR - Only 2 elements
   ```

### 7. Type Expression Result

**Current**:
```python
arr[i] → VALUE type (element type)
arr → ADDR type (pointer to first element)
```

**New**:
```python
# For BYTE arr[3][4]
arr → ADDR type (pointer to first element, i.e., BYTE ^)
arr[i] → ADDR type (pointer to row, i.e., BYTE ^)
arr[i][j] → VALUE type (element, i.e., BYTE)
```

**Rule**: Each `[]` reduces dimensionality by 1. Last `[]` gives VALUE.

## Implementation Strategy

### Phase 1: Infrastructure
1. Update AST nodes (`Declarator`, `SubscriptExpr`)
2. Update `Symbol` type system
3. Update parser for multi-dimensional syntax

### Phase 2: Semantic Analysis
1. Dimension validation
2. Index type checking
3. Shape validation for initialization
4. Expression type inference for partial subscripts

### Phase 3: Code Generation
1. Stride calculation for offset computation
2. Nested subscript code generation
3. Multi-dimensional initialization flattening

### Phase 4: Testing & Documentation
1. Unit tests for each dimension count (1D through 4D)
2. Tests for all element types (BYTE, WORD, pointers, structs)
3. Tests for partial subscripting (arr[i] returns pointer)
4. Tests for initialization in various formats
5. Integration tests with existing features

## Example Programs

### Example 1: 2D Matrix Operations
```zap
BYTE matrix[3][4] = {
  { 1, 2, 3, 4 },
  { 5, 6, 7, 8 },
  { 9, 10, 11, 12 }
}

PROC print_element(BYTE row, BYTE col)
  BYTE val = matrix[row][col]
  ; ... print val
END

PROC main
  print_element(0, 0)   ; Prints 1
  print_element(2, 3)   ; Prints 12
END
```

### Example 2: 3D Coordinate Array
```zap
STRUCT Point
  BYTE x
  BYTE y
  BYTE z
END

Point space[4][3][2]  ; 4×3×2 grid of points

PROC init_space
  BYTE i = 0
  BYTE j = 0
  BYTE k = 0
  WHILE i < 4
    j = 0
    WHILE j < 3
      k = 0
      WHILE k < 2
        space[i][j][k].x = i
        space[i][j][k].y = j
        space[i][j][k].z = k
        k = k + 1
      END
      j = j + 1
    END
    i = i + 1
  END
END
```

### Example 3: Pointer Array
```zap
BYTE ^ptrs[5]  ; Array of 5 pointers

PROC setup
  BYTE data1[3] = {1, 2, 3}
  BYTE data2[3] = {4, 5, 6}
  
  ptrs[0] = @data1[0]
  ptrs[1] = @data2[0]
END
```

## Compatibility Notes

- **Backward Compatible**: Existing 1D array code unchanged
- **Parser**: Extends grammar but doesn't break existing syntax
- **Semantics**: Partial subscripting (`arr[i]`) returns pointer (new behavior, but logical)
- **BSS Allocation**: Already works correctly for multi-dimensional arrays

## Performance Considerations

1. **Memory**: Row-major layout matches C conventions
2. **Access Speed**: 
   - Innermost dimension: Single multiplication (like 1D)
   - Outer dimensions: Multiple additions (faster than nested array pointers)
3. **Code Size**: Offset calculation adds ~10-20 bytes per subscript operation
4. **No Runtime Overhead**: All calculations done at compile-time where possible

## Open Questions

1. **Jagged Arrays**: Support variable-length dimensions?
   - Decision: No - require all dimensions known at compile-time
   
2. **Single-Index Flat Access**: `arr[i*3 + j]` for matrix?
   - Decision: Yes - users can flatten manually if needed; multi-indexed version is primary

3. **Dynamic Dimensions**: `BYTE arr[n][m]` where n/m are variables?
   - Decision: No - dimensions must be compile-time constants (like 1D arrays)

4. **Partial Initialization**: Specify only some elements?
   - Decision: Yes - rest zero-filled (like 1D arrays)

## Testing Strategy

### Unit Tests (codegen_expr.py)
- Test offset calculation for 2D, 3D, 4D arrays
- Test stride computation for different element types

### Integration Tests (test files)
- `test_multidim_2d_basic.py` - 2D BYTE arrays
- `test_multidim_3d_basic.py` - 3D BYTE arrays
- `test_multidim_pointer_arrays.py` - Arrays of pointers
- `test_multidim_struct_arrays.py` - Arrays of structs
- `test_multidim_initialization.py` - Various init formats
- `test_multidim_partial_subscript.py` - Partial indexing behavior

### Regression Tests
- Run existing array tests to ensure 1D compatibility

## Documentation Requirements

1. **Language Reference**: Grammar update, examples
2. **Implementation Guide**: Offset calculation, code generation patterns
3. **User Examples**: Common patterns and idioms
4. **Performance Notes**: Memory layout, access patterns

---

**Next Steps**: Proceed with Phase 1 (Infrastructure) implementation
