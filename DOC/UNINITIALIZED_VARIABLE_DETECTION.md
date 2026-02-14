# Uninitialized Variable Detection

**Compile-Time Detection of Uninitialized Variable Usage**

**Version**: 1.0  
**Date**: February 2026

---

## Overview

The ZAP! compiler performs **definite-assignment analysis** to detect when local variables are read before being initialized. This catches a common class of bugs at compile time, preventing runtime errors and undefined behavior.

### What is Detected

The compiler tracks the initialization state of all local variables (including procedure and function parameters) and reports an error if a variable is read before it has been assigned a value.

**Reads that are checked** include:
- Variable use in expressions, returns, and conditions
- Index expressions (e.g., `arr[i]`, where `i` must be initialized)
- Pointer dereference expressions (the pointer variable must be initialized)
- Any arithmetic or logical use on the right-hand side

**Scope of analysis**:
- This analysis applies to **local variables** in procedures and functions
- Parameters are treated as initialized at entry
- Globals are not tracked with definite-assignment; they follow normal declaration and initialization rules

### Example

```zap
proc example()
    byte x
    byte y = x + 10    ; ERROR: Use of uninitialized variable 'X'
end
```

This code will fail to compile with the error message:
```
example.zap:3:14: error: Use of uninitialized variable 'X'
```

---

## Initialization Methods

The compiler recognizes several ways a variable can be initialized:

### 1. Explicit Initializer

Variables with explicit initialization expressions are considered initialized:

```zap
proc test()
    byte x = 42        ; x is initialized
    byte y = x + 10    ; OK: x is initialized, y becomes initialized
end
```

### 2. Assignment Statement

Variables become initialized after assignment:

```zap
proc test()
    byte x
    x = 42             ; x becomes initialized here
    byte y = x + 10    ; OK: x is initialized
end
```

### 3. FOR Loop Variables

The loop variable in a FOR loop is considered initialized before the loop body:

```zap
proc test()
    byte i
    for i = 0 to 10    ; i is initialized by the FOR loop
        result = i     ; OK: i is initialized
    end
end
```

---

## Control Flow Handling

The compiler tracks initialization state through control flow constructs:

### IF Statements

Variables initialized in one branch are not considered initialized after the IF unless both branches initialize them:

```zap
proc test(byte flag)
    byte x
    
    if flag
        x = 10
    end
    
    result = x         ; ERROR: x not initialized in else branch
end
```

To fix this, initialize in both branches:

```zap
proc test(byte flag)
    byte x
    
    if flag
        x = 10
    else
        x = 20
    end
    
    result = x         ; OK: x initialized in all paths
end
```

### WHILE Loops

The loop body may execute zero times, so the compiler assumes variables initialized only inside the loop are not initialized after:

```zap
proc test()
    byte x
    byte i = 0
    
    while i < 10
        x = i          ; x initialized in loop
        i = i + 1
    end
    
    result = x         ; ERROR: x might not be initialized (loop might not run)
end
```

### REPEAT-UNTIL Loops

The loop body always executes at least once, so variables initialized in the body are considered initialized after:

```zap
proc test()
    byte x
    
    repeat
        x = 42
    until x > 100
    
    result = x         ; OK: x is initialized (loop runs at least once)
end
```

### SWITCH Statements

Variables must be initialized in all cases (including DEFAULT) to be considered initialized after the SWITCH:

```zap
proc test(byte n)
    byte x
    
    switch n
        case 0
            x = 10
        case 1
            x = 20
        default
            x = 30
    end
    
    result = x         ; OK: x initialized in all cases
end

### Nested Control Flow

Initialization tracking works across nested conditionals and loops. A variable is considered initialized after a nested block only if **all possible paths** within that block assign it.

```zap
proc test(byte a, byte b)
    byte x
    
    if a
        if b
            x = 1
        else
            x = 2
        end
    end
    
    result = x         ; ERROR: outer if might skip initialization entirely
end
```
```

---

## Special Cases

### Address-of Operator

Taking the address of a variable does **not** initialize it. The address-of operator (`@`) is not considered a read operation:

```zap
proc set_ptr(byte ^ptr)
    ptr^ = 99
end

proc test()
    byte x
    set_ptr(@x)        ; OK: taking address doesn't require initialization
    result = x         ; ERROR: x not initialized (taking address doesn't count)
end
```

However, if you initialize the variable before passing its address, it's valid:

```zap
proc test()
    byte x = 0         ; Initialize first
    set_ptr(@x)        ; OK
    result = x         ; OK: x was initialized
end
```

### Subscript and Field Access

Array subscripts and struct field accesses are considered reads only of the base variable (for the address), not the contents. The index expression is fully checked:

```zap
proc test()
    byte arr[10]
    byte i
    
    arr[i] = 42        ; ERROR: i is uninitialized
end
```

The array `arr` itself doesn't trigger an error because we're computing its address, not reading its value. But the index `i` must be initialized.

Field access on structs is treated similarly: the base struct variable is considered initialized (see below), while any index or expression inside the access is fully checked.

### Const Variables

Const variables are always considered initialized since their values are known at compile time:

```zap
proc test()
    const byte x = 42
    result = x         ; OK: const variables are always initialized
end
```

### Fixed-Address Variables

Variables declared with fixed addresses (hardware ports) are considered always initialized:

```zap
byte PORT_A @$D000

proc test()
    result = PORT_A    ; OK: fixed-address variables are always initialized
end
```

### Struct Variables

Struct variables are always considered initialized because:
1. They can be partially initialized through field-by-field assignments
2. They can be initialized through pointers (alias analysis is complex)
3. Tracking individual field initialization would require sophisticated analysis

```zap
struct Point
    byte x
    byte y
end

proc test()
    Point p
    Point ^pp = @p
    pp^.x = 3
    pp^.y = 4
    result = p.x       ; OK: structs are considered initialized
end
```

### Parameters

Procedure and function parameters are always considered initialized (they receive values from the caller):

```zap
proc test(byte x)
    result = x         ; OK: parameters are always initialized
end

---

## What Is Not Detected (Current Limitations)

The current analysis is intentionally simple and does **not** attempt to prove every safe case. It errs on the side of caution and may report false positives in these scenarios:

- **Inter-procedural initialization**: If a procedure initializes a variable via pointer, the caller will still see it as uninitialized unless it was already initialized.
- **Pointer aliasing**: The compiler does not track that `ptr^ = 42` initializes the pointed-to variable.
- **Partial struct initialization**: The analysis does not track per-field initialization.
- **Conditional pointer writes**: Pointer-based assignments are not recognized as definite initialization.
- **Globals**: Local definite-assignment tracking does not extend to globals.
```

---

## Error Messages

When an uninitialized variable is detected, the compiler reports:

```
filename.zap:line:col: error: Use of uninitialized variable 'NAME'
```

The error points to the location where the uninitialized read occurs.

### Example

```zap
proc example()
    byte x
    byte y
    y = x + 10
end
```

Produces:

```
example.zap:4:9: error: Use of uninitialized variable 'X'
```

---

## Best Practices

### 1. Initialize Variables at Declaration

The safest approach is to initialize variables when you declare them:

```zap
proc safe_example()
    byte x = 0         ; Always initialized
    byte y = 10        ; Always initialized
    result = x + y     ; No errors possible
end
```

### 2. Initialize Before Conditional Branches

If a variable is used after an IF statement, initialize it before:

```zap
proc example(byte flag)
    byte x = 0         ; Initialize with default value
    
    if flag
        x = 42         ; Override if flag is set
    end
    
    result = x         ; OK: x is initialized in all paths
end
```

### 3. Check Loop Conditions Carefully

Remember that WHILE loops might not execute:

```zap
proc safe_loop()
    byte x = 0         ; Initialize with default
    byte i = 0
    
    while i < 10
        x = x + i
        i = i + 1
    end
    
    result = x         ; OK: x initialized before loop
end
```

---

## Implementation Details

### Algorithm

The compiler uses **definite-assignment tracking** with these steps:

1. **Initialization Set**: Track which variables are definitely initialized at each program point
2. **Statement Analysis**: Update the initialization set as statements execute
3. **Control Flow Merging**: At join points (after IF, loops, etc.), only variables initialized in **all** paths remain in the set
4. **Read Checking**: Before each variable read, verify it's in the initialization set

### Tracked Statements

- **Assignment**: Marks left-hand side variable as initialized
- **FOR loop**: Marks loop variable as initialized before body
- **Declaration with initializer**: Marks variable as initialized
- **IF/ELSE**: Merges initialization sets from both branches
- **WHILE**: Body initialization doesn't propagate (might not execute)
- **REPEAT-UNTIL**: Body initialization propagates (always executes once)
- **SWITCH**: Merges initialization from all cases

### Files

The implementation is in:
- `sema_proc.py`: Definite-assignment for procedures
- `sema_func.py`: Definite-assignment for functions

Key functions:
- `_is_considered_initialized()`: Determines if a symbol is inherently initialized
- `_check_uninitialized()`: Walks expressions checking for uninitialized reads
- `_mark_initialized_from_lhs()`: Marks variables initialized by assignments
- `validate_stmt_exprs()`: Tracks initialization through statement lists

---

## Limitations

### No Inter-Procedural Analysis

The compiler doesn't track initialization across procedure calls:

```zap
proc init_value(byte ^ptr)
    ptr^ = 42
end

proc test()
    byte x
    init_value(@x)     ; Compiler doesn't know this initializes x
    result = x         ; ERROR: x considered uninitialized
end
```

**Workaround**: Initialize the variable before passing its address:

```zap
proc test()
    byte x = 0         ; Initialize first
    init_value(@x)     ; Now modify it
    result = x         ; OK
end
```

### No Pointer Alias Tracking

The compiler doesn't track when pointers point to uninitialized variables:

```zap
proc test()
    byte x
    byte ^ptr = @x
    ptr^ = 42          ; Compiler doesn't know this initializes x
    result = x         ; ERROR: x considered uninitialized
end
```

### Struct Field Tracking

Individual struct fields are not tracked. The entire struct is either considered initialized or not:

```zap
struct Point
    byte x
    byte y
end

proc test()
    Point p
    p.x = 10           ; Struct becomes initialized
    result = p.y       ; OK (but y was never set!)
end
```

This is a conservative approximation to avoid complex analysis.

---

## Comparison with Other Languages

### C/C++

Most C/C++ compilers warn about uninitialized variables but don't enforce it:

```c
// C code - compiles with warning
void example() {
    int x;
    int y = x + 10;    // Warning: 'x' is used uninitialized
}
```

ZAP! makes this a **compile-time error**, preventing the code from compiling.

### Rust

Rust enforces definite-initialization strictly:

```rust
// Rust code - does not compile
fn example() {
    let x: i32;
    let y = x + 10;    // Error: borrow of possibly-uninitialized variable
}
```

ZAP!'s approach is similar to Rust's, catching errors at compile time.

### Java/C#

These languages initialize all variables to zero/null by default, avoiding the problem but with a runtime cost. ZAP! requires explicit initialization for better performance and cleaner semantics.

---

## Summary

- ZAP! detects uninitialized variable reads at **compile time**
- Variables must be initialized through **explicit initializers**, **assignments**, or **FOR loops**
- Control flow is tracked: initialization must occur in **all paths**
- Special cases: **const**, **fixed-address**, **structs**, and **parameters** are always considered initialized
- **Address-of** operator doesn't require initialization
- Errors are reported with precise **file**, **line**, and **column** information

This feature prevents a common source of bugs and makes ZAP! programs more reliable.

---

## See Also

- [Variable Allocation](VARIABLE_ALLOCATION.md) - How variables are stored in memory
- [Getting Started](GETTING_STARTED.md) - Basic ZAP! language features
- [Advanced Topics](ADVANCED_TOPICS.md) - Advanced programming techniques
