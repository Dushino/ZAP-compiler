# Fix: Pointer Dereference and Array Subscript in Expressions

## Problem
Previously, the compiler rejected using pointer dereferences (`ptr^`) and array subscripts (`arr[i]`) on the right-hand side of expressions, causing errors like:
```
Error: Invalid use of lvalue in expression
```

This prevented useful code patterns like:
- `ptr2^ = ptr2^ + 1` (increment value pointed to)
- `ptr4^ = ptr4^ + 1` (word pointer version)
- `x = arr[0] + arr[1]` (array element arithmetic)
- `if ptr1^ == ptr2^ then ...` (comparing dereferenced values)

## Root Cause
The semantic expression type checker (`sema_expr.py`) classified pointer dereferences (`DerefExpr`) and array subscripts (`SubscriptExpr`) as `LVALUE` (locations that can be written to), which is correct. However, when these appeared in expression contexts (like the RHS of an assignment or in binary/unary operations), they should be treated as reading from that location, which should be classified as `VALUE`.

The type checker was rejecting any `LVALUE` in expressions without first converting it to `VALUE` for reading.

## Solution
Modified the semantic expression type checker to automatically convert `LVALUE` to `VALUE` when used in expression contexts:

1. **Binary expressions** - When an operand is an LVALUE, treat it as reading the value
2. **Unary expressions** - When the operand is an LVALUE, treat it as reading the value

This matches standard C semantics where:
- `ptr^ = 5` - `ptr^` is an LVALUE (write to location)
- `x = ptr^` - `ptr^` is reading a VALUE
- `y = ptr^ + 1` - `ptr^` is reading a VALUE and adding to it

## Changes Made
File: `sema_expr.py`

### Change 1: Binary Expressions
```python
if isinstance(expr, BinaryExpr):
    lt = self.check(expr.left)
    rt = self.check(expr.right)
    op = expr.op

    # Convert LVALUE to VALUE when used in expression context (reading)
    # LVALUE means "location that can be written to", but when used in
    # an expression, we're reading from it (e.g., ptr^ + 1 or arr[i] + 1)
    if lt.kind == ExprKind.LVALUE:
        lt = ExprType(lt.sem_type, ExprKind.VALUE)
    if rt.kind == ExprKind.LVALUE:
        rt = ExprType(rt.sem_type, ExprKind.VALUE)
```

### Change 2: Unary Expressions
```python
if isinstance(expr, UnaryExpr):
    t = self.check(expr.expr)
    # Convert LVALUE to VALUE when reading (e.g., !ptr^ or -ptr^)
    if t.kind == ExprKind.LVALUE:
        t = ExprType(t.sem_type, ExprKind.VALUE)
    if t.kind != ExprKind.VALUE:
        raise SemanticError("Logical NOT requires value")
    return ExprType(SemType("BYTE", False), ExprKind.VALUE)
```

## What Now Works

### Byte Pointer Operations
```zap
byte ^ptr1
byte ^ptr2

proc main()
    ptr1 = $1000
    ptr2 = $2000
    
    ; Read dereferenced values in expressions
    byte x = ptr1^ + 5
    byte y = ptr1^ + ptr2^
    
    ; Self-modification
    ptr1^ = ptr1^ + 1
    ptr1^ = ptr1^ - 1
    ptr1^ = ptr1^ + ptr2^
end
```

### Word Pointer Operations
```zap
word ^ptr3
word ^ptr4

proc main()
    ptr3 = $3000
    ptr4 = $4000
    
    ; Read dereferenced values
    word w = ptr3^ + 10
    word v = ptr3^ + ptr4^
    
    ; Self-modification
    ptr3^ = ptr3^ + 1
    ptr3^ = ptr3^ - 1
    ptr3^ = ptr3^ + ptr4^
end
```

### Array Subscripts
```zap
byte arr[] = {10, 20, 30}
word warr[] = {100, 200, 300}

proc main()
    ; Array elements in expressions
    byte x = arr[0] + 1
    byte y = arr[0] + arr[1]
    
    ; Array self-modification
    arr[0] = arr[0] + 1
    arr[1] = arr[1] + arr[2]
    
    ; Word arrays
    word w = warr[0] + 1
    warr[0] = warr[0] + warr[1]
end
```

### Mixed Operations
```zap
byte ^ptr
byte arr[] = {1, 2, 3}

proc main()
    ptr = $1000
    
    ; Mix pointer deref and array subscript
    byte x = ptr^ + arr[0]
    
    ; Comparisons
    if ptr^ == arr[1] then
        x = 1
    endif
    
    ; Logical operations
    byte b = !ptr^
    if !arr[0] then
        b = 2
    endif
end
```

## Tests
- All existing tests continue to pass
- New test: `tests/pass/011-pointer-conv/011-pointer-conv.zap` now compiles successfully
- New test: `tests/pass/012-deref-in-expr/012-deref-in-expr.zap` demonstrates comprehensive usage

## Generated Code Quality
The generated assembly correctly:
1. Loads the pointer address into TMP0
2. Dereferences to read the value
3. Performs the operation
4. Stores the result back (for assignments to dereferenced pointers)
5. Handles both byte and word pointers with proper multi-byte operations

For word pointers, the code properly handles 16-bit arithmetic with carry propagation.
