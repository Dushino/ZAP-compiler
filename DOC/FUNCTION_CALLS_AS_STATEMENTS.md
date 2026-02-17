# Function Calls Without Return Value Assignment

## Overview

Functions can now be called as statements without requiring the return value to be captured or used. This allows treating functions more flexibly—they can be used for their side effects rather than exclusively for their return values.

## Syntax

```zap
func word test1(byte a)    
    return a + 1
end

proc main()
    test1(10)  ; Function call as statement - return value is discarded
end
```

## Behavior

When a function is called as a statement:

1. **Arguments are passed normally** - All parameters are provided according to the function signature
2. **Function executes** - A `JSR` (Jump to Subroutine) instruction is issued to call the function
3. **Return value is ignored** - The registers A, X (or A, X, Y) containing the return value are not used
4. **Execution continues** - After the function returns, the next statement executes

## Code Generation

For a function call as a statement, the compiler generates:

```asm
; Function call with arguments
        LDA #<param_value
        LDX #>param_value
        JDX param_sym
        ...
        JSR _FUNCTION_NAME
        ; Return value in A (and/or X) is discarded
        ; Execution continues with next statement
```

Compare to a function call with return value assignment:

```asm
; Function call where return value is used
        LDA #<param_value
        ...
        JSR _FUNCTION_NAME
        STA result_var        ; Capture return value
        STX result_var+1
```

## Use Cases

### 1. Functions for Their Side Effects

```zap
func word log_event(byte event_id)
    ; Write event to memory-mapped register
    log_register^ = event_id
    return 0
end

proc main()
    log_event(42)  ; Call for side effect, ignore return value
end
```

### 2. Conditional Execution Patterns

```zap
func word validate_input(byte value)
    ; Returns nonzero on error
    if value > 100
        return 1
    end
    return 0
end

proc main()
    ; Just check if validation passes - ignore return value if success
    validate_input(50)
end
```

### 3. Complex Data Processing

```zap
func word process_data(byte ^ptr, byte len)
    ; Process memory region, return status
    return 0
end

proc main()
    process_data(some_buffer, 256)  ; Discard status code
end
```

## Comparison with Procedures

| Feature | Procedure | Function |
|---------|-----------|----------|
| **Has return value** | No | Yes |
| **Call as statement** | `name(args)` | `name(args)` (NEW) |
| **Use return value** | N/A | `var = name(args)` |
| **Can discard result** | N/A (no result) | Yes (with this feature) |

## Parameter Validation

When calling a function as a statement, parameter count validation is identical to function calls with return value assignment:

```zap
func word add(byte a, byte b)
    return a + b
end

proc main()
    add(1, 2)           ; ✓ Valid: 2 parameters
    add(1)              ; ✗ Error: Expected 2 parameters
    add(1, 2, 3)        ; ✗ Error: Expected 2 parameters
end
```

## Implementation Details

**Modified File**: [sema_proc.py](../sema_proc.py)

**Function**: `ProcAnalyzer.analyze_call()`

The semantic analyzer was updated to recognize that `CallStmt` (procedure call statement) can reference either:
- A procedure from the procedure table (existing behavior)
- A function from the function table (new behavior)

When a `CallStmt` references an undefined identifier:
1. First, attempt to find it as a procedure
2. If not found, attempt to find it as a function
3. If found as a function, validate parameter counts and return
4. If not found in either table, report "Undefined procedure/function" error

**Code Generation**: The code generator in [codegen_expr.py](../codegen_expr.py) already supported emitting function calls as statements, so no changes were required there.

## Testing

The test file [118-stdio.zap](../tests/pass/118-stdio/118-stdio.zap) demonstrates this feature:

```zap
func word test1(MyStruct s)
    return s.a + s.b + s.c + s.ptr + s.e + s.p.x + s.p.y
end

proc main()
    ; ... previous code ...
    
    ; Function called as statement - return value discarded
    test1({1, 2, 1204, 40000, MyEnum.B, {10, 20}})
end
```

Compiled assembly output:
```asm
        JSR _TEST1
```

## Notes

- **Return value registers**: After the function call, registers A and X (or A, X for wider returns) may contain the return value, but it is not captured or used
- **Memory safety**: Functions with side effects (such as modifying memory-mapped registers) work correctly when called as statements
- **Performance**: There is no performance difference between calling a function as a statement vs. with return value assignment—the function still executes completely
- **Style consideration**: For clarity, functions called purely for side effects (with unused return values) might benefit from being refactored as procedures instead
