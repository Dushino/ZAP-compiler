# Suggested Additional Tests for ZAP! Compiler

Based on current compiler capabilities and the grammar, here are gaps in test coverage with recommended test files:

## Control Flow Tests

### 013-if-then-else
**Tests:** IF/THEN/ELSE/ENDIF statements, nested conditions, zero/non-zero evaluation
```zap
byte result

proc main()
    byte x = 5
    if x == 5 then
        result = 1
    else
        result = 0
    endif
    
    if x > 3 then
        if x < 10 then
            result = 2
        endif
    endif
end
```

### 014-while-loop
**Tests:** WHILE loops, loop counters, early termination
```zap
byte counter

proc main()
    counter = 0
    while counter < 10
        counter = counter + 1
    end
    
    byte x = 5
    while x != 0
        x = x - 1
    end
end
```

### 015-for-loop
**Tests:** FOR loops, NEXT, loop variable scope
```zap
byte arr[] = {0,0,0,0,0} @40000
byte i

proc main()
    for i = 0 to 4
        arr[i] = i
    next i
end
```

### 016-break-in-loops
**Tests:** BREAK statement behavior in loops
```zap
byte result

proc main()
    byte i = 0
    while i < 10
        if i == 5 then
            break
        endif
        i = i + 1
    end
    result = i
end
```

## Arithmetic & Bitwise Operations

### 017-bitwise-operators
**Tests:** Binary operators & (AND) and | (OR), combinations
```zap
byte a, b, result

proc main()
    a = $0f
    b = $f0
    result = a | b  ; Should be $ff
    result = a & b  ; Should be $00
end
```

### 018-modulo-division
**Tests:** Modulo (%), division (/), remainder operations
```zap
byte dividend, divisor, result

proc main()
    dividend = 23
    divisor = 5
    result = dividend / divisor   ; Should be 4
    result = dividend % divisor   ; Should be 3
end
```

### 019-mixed-arithmetic
**Tests:** Mixed + - * / operations, operator precedence
```zap
byte result

proc main()
    result = 2 + 3 * 4          ; Should be 14
    result = 10 - 2 * 3         ; Should be 4
    result = 100 / 5 + 2        ; Should be 22
end
```

## Function Support

### 020-function-return-byte
**Tests:** FUNC with byte return type, multiple return points
```zap
func byte add_one(byte x)
    return x + 1
end

byte result

proc main()
    result = add_one(10)
end
```

### 021-function-return-word
**Tests:** FUNC with word return type
```zap
func word combine(byte low, byte high)
    word result = low + high * 256
    return result
end
```

### 022-nested-function-calls
**Tests:** Functions calling other functions, call depth
```zap
func byte double(byte x)
    return x * 2
end

func byte quad(byte x)
    return double(double(x))
end

byte result

proc main()
    result = quad(5)  ; Should be 20
end
```

## String & Character Handling

### 023-string-literals
**Tests:** String initializers for byte arrays, NUL termination
```zap
byte str1[] = "hello" @40000
byte str2[] = "test123" @40010

proc main()
    str1[0] = 'A'
end
```

### 024-character-literals
**Tests:** Character literals 'a', escape sequences \n, \t, \r, \", \', \\
```zap
byte newline = '\n'
byte tab = '\t'
byte quote = '\''
byte backslash = '\\'
byte cr = '\r'

proc main()
end
```

## Pointer Operations

### 025-pointer-dereference
**Tests:** Reading/writing via pointers, ^ptr syntax
```zap
byte ^ptr
byte target = 42

proc main()
    ptr = ^target
    byte value = ptr^
end
```

### 026-pointer-arithmetic
**Tests:** Pointer + offset, pointer - offset, pointer + pointer semantics
```zap
byte arr[] = {1,2,3,4,5} @40000
byte ^ptr, ^offset_ptr

proc main()
    ptr = ^arr
    offset_ptr = ptr + 2
end
```

### 027-array-pointer-equivalence
**Tests:** Array name as pointer, arr[i] vs ptr+i
```zap
byte arr[] = {10,20,30,40,50} @40000
byte ^ptr = ^arr

proc main()
    byte v1 = arr[2]
    ptr = ^arr + 2
    byte v2 = ptr^
end
```

## Module & Conditional Compilation

### 028-ifdef-basic
**Tests:** `.ifdef`, `.else`, `.endif` directives
```zap
.ifdef DEBUG
    byte debug_flag
.endif

.ifdef RELEASE
    const byte version = 1
.else
    const byte version = 0
.endif

proc main()
end
```

### 029-module-include
**Tests:** `.module`, `.include` directives, cross-file definitions
**File: lib_utils.zap**
```zap
.module "utils"

func byte abs_diff(byte a, byte b)
    if a > b then
        return a - b
    else
        return b - a
    endif
end
``` 

**File: 029-module-include.zap**
```zap
.include "lib_utils.zap"

byte result

proc main()
    result = abs_diff(10, 3)
end
```

## Error Detection Tests (in `tests/fail/`)

### test_uninitialized_var.zap
**Tests:** Using uninitialized local variable should fail
```zap
proc main()
    byte x
    byte y = x + 1  ; Error: x not initialized
end
```

### test_undefined_func.zap
**Tests:** Calling undefined function should fail
```zap
proc main()
    byte result = undefined_func(5)  ; Error: undefined_func not declared
end
```

### test_type_mismatch.zap
**Tests:** Type mismatches in assignment/return
```zap
func byte get_value()
    word w = 1000
    return w  ; Error: word doesn't fit in byte return
end
```

### test_array_bounds.zap
**Tests:** Compile-time array bounds checking
```zap
byte arr[5] = {1,2,3,4,5}

proc main()
    arr[10] = 99  ; Error: index out of bounds
end
```

### test_invalid_pointer_deref.zap
**Tests:** Dereferencing non-pointer types
```zap
proc main()
    byte x = 5
    byte y = x^  ; Error: x is not a pointer
end
```

### test_wrong_param_count.zap
**Tests:** Function/proc called with wrong parameter count
```zap
proc add(byte a, byte b)
end

proc main()
    add(1)  ; Error: missing second parameter
    add(1, 2, 3)  ; Error: too many parameters
end
```

## Optimization Validation

### 030-const-folding
**Tests:** Constant expressions evaluated at compile time
```zap
const byte result1 = 2 + 3
const byte result2 = 10 * 5 + 3
const byte result3 = 255 - 100

proc main()
    const byte x = (1 + 2) * (3 + 4)
end
```

### 031-dead-code
**Tests:** Unreachable code detection/elimination
```zap
proc main()
    return
    byte unused = 42  ; This code is unreachable
    
    if 0 then  ; Always false
        byte never_runs = 1
    endif
end
```

## Edge Cases

### 032-zero-and-boundary-values
**Tests:** Edge values: 0, 255, 256, -1
```zap
byte b1 = 0
byte b2 = 255
word w1 = 0
word w2 = 65535

proc main()
    b1 = b1 + 1  ; Overflow behavior
    w1 = w1 - 1  ; Underflow behavior
end
```

### 033-deeply-nested-expressions
**Tests:** Complex nested arithmetic and comparisons
```zap
proc main()
    byte result = ((1 + 2) * (3 + 4)) - ((5 - 2) * 2)
    if ((result > 5) && (result < 20)) || (result == 0) then
        result = 1
    endif
end
```

### 034-large-array
**Tests:** Large array allocations and indexing
```zap
byte large_arr[256] @40000
word index

proc main()
    for index = 0 to 255
        large_arr[index] = index & 255
    next index
end
```

## Architecture-Specific Tests

### 035-6502-vs-65c02
**Tests:** CPU-specific instruction set differences (compile with both `--6502` and default)
```zap
proc main()
    byte x = 5
    ; Some operations may use 65c02-specific instructions like STZ
end
```

### 036-peephole-effectiveness
**Tests:** Code that should benefit from peephole optimizations
```zap
byte result

proc main()
    result = 0
    result = result + 1
    byte temp = result
    result = temp  ; Redundant load/store pair
end
```

## Summary Table

| Category | Test Range | Count | Current Gap |
|----------|-----------|-------|------------|
| Control Flow | 013-016 | 4 | None yet |
| Arithmetic | 017-019 | 3 | Bitwise &\|, %/ |
| Functions | 020-022 | 3 | None yet |
| Strings/Chars | 023-024 | 2 | None yet |
| Pointers | 025-027 | 3 | Advanced ptr arith |
| Modules | 028-029 | 2 | None yet |
| Error Cases | test_* | 6+ | Many categories |
| Optimizations | 030-031 | 2 | None yet |
| Edge Cases | 032-034 | 3 | None yet |
| Architecture | 035-036 | 2 | None yet |
| **TOTAL** | | **30+** | |

## Recommended Implementation Order

1. **Phase 1 (High Priority):** Tests 013-016 (control flow) — critical language features
2. **Phase 2:** Tests 017-019, 023-024 (arithmetic, strings) — core language
3. **Phase 3:** Tests 020-022 (functions) — function returns
4. **Phase 4:** Tests 025-027 (advanced pointers) — validates pointer semantics
5. **Phase 5:** Error cases — comprehensive error message validation
6. **Phase 6:** Optimization tests 030-031 — validates codegen improvements

## Notes

- Each test should have a `.zap` source file, `.ref` expected reference output, and `.json` metadata
- Error cases should be in `tests/fail/` directory with appropriate error message checking
- Consider adding `.txt` verbose output for manual inspection
- Peephole tests (036) should generate `.dis65` disassembly for review
