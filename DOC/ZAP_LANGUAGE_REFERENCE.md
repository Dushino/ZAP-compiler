# ZAP! Language Reference Manual

**Complete Guide to the ZAP! Programming Language**

**Version**: 1.0  
**Date**: January 2026  
**Target Platforms**: Atari 8-bit, 6502-based systems

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Concepts](#basic-concepts)
3. [Data Types](#data-types)
4. [Variables](#variables)
5. [Operators](#operators)
6. [Control Flow](#control-flow)
7. [Procedures & Functions](#procedures--functions)
8. [Arrays & Strings](#arrays--strings)
9. [Pointers](#pointers)
10. [Module System](#module-system)
11. [Advanced Topics](#advanced-topics)

---

## Getting Started

### Your First ZAP Program

```zap
proc main()
    putc('H')
    putc('i')
end
```

This simple program defines a main procedure that outputs two characters. Every ZAP program must have a `main` procedure as its entry point.

### Compilation

```bash
python compiler.py program.zap -o program.s
```

This generates 6502 assembly code ready for linking with the Atari 8-bit development tools.

---

## Basic Concepts

### Program Structure

A ZAP program consists of:
- **Global variable declarations** - Data shared across procedures
- **Procedure definitions** - Blocks of code called by other procedures
- **Function definitions** - Procedures that return values
- **Module directives** - For multi-file compilation

### Case Sensitivity

ZAP! is case-insensitive for identifiers:
```zap
byte myVar
byte MYVAR      ; Same variable - error: duplicate!
byte x = myvar  ; Reference to myVar - valid
```

However, strings and character literals preserve case:
```zap
byte x = 'A'    ; Character 'A' (value 65)
byte msg[] = "Hello"  ; String preserved as-is
```

### Comments

Single-line comments begin with `;` and extend to end of line:
```zap
proc main()
    ; This is a comment
    byte x = 5  ; Initialize x to 5
end
```

### Semicolon Requirement

Statements do NOT require semicolons (they're optional and ignored).

---

## Data Types

ZAP! supports three fundamental data types for 6502 systems:

### byte - 8-bit Unsigned Integer

```zap
byte x              ; Uninitialized byte variable
byte y = 42         ; Byte with initializer
byte z = $FF        ; Hex notation
byte w = %10101010  ; Binary notation
```

**Range**: 0-255

### word - 16-bit Unsigned Integer

```zap
word address        ; Uninitialized word variable
word counter = 1000 ; Word with initializer
word value = $1234  ; Hex notation (4 digits for 16-bit)
```

**Range**: 0-65535

### Character Literals

Character literals are written with single quotes and are converted to their ASCII numeric values:

```zap
byte c = 'A'        ; Character literal (value 65)
byte newline = '\n' ; Newline character (value 10)
byte tab = '\t'     ; Tab character (value 9)
byte quote = '\''
  ; Single quote (value 39)
byte backslash = '\\' ; Backslash (value 92)
```

**Character Escapes** (in character and string literals):
- `\n` - Newline (10)
- `\t` - Tab (9)
- `\r` - Carriage return (13)
- `\"` - Double quote
- `\'` - Single quote
- `\\` - Backslash

### Type Modifiers

#### const - Constant Values

```zap
const byte VERSION = 1     ; Compile-time constant
const word MAX_SIZE = 1024
```

Constants are evaluated at compile-time and cannot be modified.

#### Pointer Types

```zap
byte ^ptr           ; Pointer to byte
word ^addr          ; Pointer to word
```

See [Pointers](#pointers) section for detailed information.

---

## Variables

### Variable Declaration

Basic syntax:
```zap
[const] type name [@ address] [= initializer]
```

### Global Variables

```zap
byte global_x = 0       ; Global variable
byte screen = 40000 @0x9C00  ; Using hex address
word counter = 0
```

### Local Variables

```zap
proc main()
    byte local_var          ; Local to main
    byte temp = 0           ; Local with initialization
    
    ; Use variables here
end
```

### Variable Scope

**Global variables** are visible from all procedures and functions.

**Local variables** are visible only within their procedure/function:
```zap
byte global_x = 10

proc test1()
    byte x = 20         ; Local x shadows global
    x = x + 1           ; Uses local x, not global
end

proc test2()
    x = x + 1           ; Uses global x
end
```

### Fixed-Address Variables

Specify exact memory address for hardware registers or memory-mapped I/O:

```zap
byte SCREEN_DMA @$D400      ; ANTIC DMA control
word DISPLAY_LIST_PTR @$D402
byte PLAYER0_X @$D000       ; Atari GTIA register
```

Fixed-address variables are always preserved (never optimized away) regardless of usage.

### Variable Initialization

**Scalar initialization**:
```zap
byte x = 42
word y = 1000
```

**Array initialization** (see [Arrays](#arrays--strings)):
```zap
byte arr[] = {1, 2, 3, 4, 5}
```

**String initialization** (see [Strings](#strings)):
```zap
byte text[] = "Hello"
```

### Static Local Variables

Local variables maintain their values between procedure calls:

```zap
proc counter_increment()
    byte count          ; Persists between calls
    count = count + 1
end

proc main()
    counter_increment() ; count = 1
    counter_increment() ; count = 2
    counter_increment() ; count = 3
end
```

**Note**: Local variables are not automatically initialized on first call. Use an initialization flag if needed:

```zap
byte init_flag = 1

proc initialize_once()
    byte state
    
    if init_flag then
        state = 0
        init_flag = 0
    end
    
    state = state + 1
end
```

### Multiple Declarations

```zap
byte x, y, z           ; Three bytes
byte a = 1, b = 2      ; With initialization
byte ^p1, ^p2          ; Two byte pointers
```

---

## Operators

### Arithmetic Operators

| Operator | Example | Result | Notes |
|----------|---------|--------|-------|
| `+` | `5 + 3` | `8` | Addition (8/16-bit) |
| `-` | `5 - 3` | `2` | Subtraction (8/16-bit) |
| `*` | `5 * 3` | `15` | Multiplication (8/16-bit) |
| `/` | `15 / 3` | `5` | Integer division |
| `%` | `17 % 5` | `2` | Modulo (remainder) |

```zap
proc arithmetic_example()
    byte a = 10
    byte b = 3
    byte sum = a + b        ; 13
    byte diff = a - b       ; 7
    byte prod = a * b       ; 30
    byte quot = a / b       ; 3
    byte rem = a % b        ; 1
end
```

### Comparison Operators

| Operator | Example | Meaning |
|----------|---------|---------|
| `==` | `x == 5` | Equal |
| `!=` | `x != 5` | Not equal |
| `<` | `x < 5` | Less than |
| `>` | `x > 5` | Greater than |
| `<=` | `x <= 5` | Less than or equal |
| `>=` | `x >= 5` | Greater than or equal |

```zap
proc comparison_example()
    byte x = 42
    
    if x == 42 then
        ; x equals 42
    endif
    
    if x > 40 && x < 50 then
        ; x is between 40 and 50
    endif
end
```

### Logical Operators

| Operator | Example | Meaning |
|----------|---------|---------|
| `&&` | `a && b` | Logical AND (short-circuit) |
| `\|\|` | `a \|\| b` | Logical OR (short-circuit) |
| `!` | `!a` | Logical NOT |

```zap
proc logical_example()
    byte x = 5
    byte y = 10
    
    ; AND operator
    if x > 0 && y > 0 then
        ; Both conditions true
    endif
    
    ; OR operator
    if x == 5 || y == 5 then
        ; At least one condition true
    endif
    
    ; NOT operator
    if !(x == 0) then
        ; x is not zero
    endif
end
```

### Unary Operators

```zap
byte x = 5
byte neg = -x       ; Negation
byte neg2 = -10     ; Can be applied to literals

byte flag = 1
byte notflag = !flag  ; Logical negation
```

### Operator Precedence

From lowest to highest:

1. `||` (Logical OR)
2. `&&` (Logical AND)
3. `==`, `!=` (Equality)
4. `<`, `>`, `<=`, `>=` (Comparison)
5. `+`, `-` (Addition, Subtraction)
6. `*`, `/`, `%` (Multiplication, Division, Modulo)
7. `-`, `!` (Unary)
8. Primary (literals, variables, parentheses)

```zap
proc precedence_example()
    byte result
    
    ; Standard precedence
    result = 2 + 3 * 4      ; 14 (multiply first)
    result = (2 + 3) * 4    ; 20 (parentheses first)
    
    ; Logical precedence
    byte a = 1, b = 0, c = 1
    if a && b || c then     ; (a && b) || c = true
    endif
end
```

---

## Control Flow

### if-then-else Statement

```zap
proc if_example()
    byte x = 5
    
    ; Simple if
    if x == 5 then
        ; This executes
    endif
    
    ; if-else
    if x > 10 then
        ; x is greater than 10
    else
        ; x is 10 or less
    endif
    
    ; Nested if
    if x > 0 then
        if x < 100 then
            ; x is between 0 and 100
        endif
    endif
end
```

### while Loop

```zap
proc while_example()
    byte count = 0
    
    while count < 10
        count = count + 1
    end
    
    ; Loop with break
    byte x = 0
    while 1         ; Infinite loop
        x = x + 1
        if x == 100 then
            break   ; Exit loop
        endif
    end
end
```

### for Loop

```zap
proc for_example()
    byte i
    
    ; Basic for loop
    for i = 0 to 9
        ; Execute 10 times (0-9)
    next i
    
    ; For loop with step
    for i = 0 to 100 step 10
        ; i = 0, 10, 20, ..., 100
    next i
    
    ; Descending
    for i = 10 to 0 step -1
        ; i = 10, 9, 8, ..., 0
    next i
    
    ; With break
    for i = 0 to 255
        if i == 128 then
            break
        endif
    next i
end
```

### break Statement

```zap
proc break_example()
    ; In while loop
    byte x = 0
    while x < 1000
        x = x + 1
        if x == 500 then
            break
        endif
    end
    
    ; In for loop
    byte i
    for i = 0 to 255
        if i == 50 then
            break
        endif
    next i
end
```

### Zero/Non-Zero Evaluation

In conditional statements, numbers evaluate as:
- **Zero** - False
- **Non-zero** - True

```zap
proc zero_evaluation()
    byte x = 0
    byte y = 1
    
    if x then        ; False (x is 0)
    endif
    
    if y then        ; True (y is non-zero)
    endif
    
    if 0 then        ; False
    else
        ; This executes
    endif
    
    if 1 then        ; True
        ; This executes
    endif
end
```

---

## Procedures & Functions

### Procedures

Procedures are blocks of code that perform actions but don't return values.

```zap
proc procedure_name()
    ; Procedure body
end

proc procedure_with_params(byte x, word y)
    ; Use parameters
end

proc main()
    procedure_name()            ; Call without params
    procedure_with_params(5, 1000)  ; Call with params
end
```

### Functions

Functions return values to their caller.

```zap
func byte add_one(byte x)
    return x + 1
end

func word multiply(byte a, byte b)
    return a * b
end

proc main()
    byte result = add_one(10)   ; result = 11
    word prod = multiply(5, 6)  ; prod = 30
end
```

### Parameters

```zap
proc three_params(byte x, word y, byte c)
    ; Use x, y, c
end

; Parameters are procedure locals
proc param_example(byte value)
    byte value      ; ERROR: duplicate declaration
end

; But you can declare other locals
proc param_with_locals(byte value)
    byte temp = 0   ; OK: different name
end
```

### Local Variables

```zap
proc with_locals()
    byte x          ; Local variable
    byte y = 10     ; Local with initializer
    word counter = 0
    
    ; Use locals
    x = y + 1
    counter = counter + 1
end
```

### Return Statement

In procedures (returns to caller, no value):
```zap
proc early_exit(byte x)
    if x == 0 then
        return      ; Exit early
    endif
    
    ; More code
end
```

In functions (required, must have value):
```zap
func byte get_value()
    byte x = 42
    return x
end

func word calculate(byte a, byte b)
    return a + b
end
```

### Parameter Passing

Parameters are passed by value (copies created):

```zap
proc modify(byte x)
    x = 0           ; Modifies local copy only
end

proc main()
    byte value = 42
    modify(value)
    ; value still 42 - not affected by modify
end
```

### Recursive Calls

Procedures can call themselves:

```zap
proc countdown(byte n)
    putc(n + 48)    ; Print digit
    
    if n > 0 then
        countdown(n - 1)
    endif
end

proc main()
    countdown(5)    ; Prints: 5 4 3 2 1 0
end
```

---

## Arrays & Strings

### Array Declaration

```zap
byte arr1[10]           ; Array of 10 bytes, uninitialized
byte arr2[10] = 0       ; All initialized to 0
word arr3[5]            ; Array of 5 words
```

### Array Initialization

```zap
; With initializer list
byte values[] = {1, 2, 3, 4, 5}

; With specified size (fills with values)
byte data[8] = {255, 0, 127}    ; Rest are 0

; Word arrays
word addresses[] = {$2000, $3000, $4000}
```

### Array Subscripting

```zap
proc array_example()
    byte arr[5] = {10, 20, 30, 40, 50}
    byte i
    byte value
    
    ; Read from array
    value = arr[0]      ; value = 10
    value = arr[2]      ; value = 30
    
    ; Write to array
    arr[1] = 99
    
    ; Dynamic subscripts
    for i = 0 to 4
        arr[i] = i * 10
    next i
end
```

### Strings

Strings are byte arrays with NUL termination:

```zap
byte message[] = "Hello"    ; Stored as {72,101,108,108,111,0}
```

```zap
proc string_example()
    byte greeting[] = "Hi"
    
    ; Access characters
    byte first = greeting[0]    ; 'H' = 72
    byte second = greeting[1]   ; 'i' = 105
    byte nul = greeting[2]      ; 0 (terminator)
end
```

### Array Address Specification

```zap
byte screen_buffer[256] @$8000     ; Fixed address
word sprite_data[32] @$6000        ; Fixed address for word array
```

### Multidimensional Arrays

Not directly supported; simulate with calculation:

```zap
byte grid[16]   ; 4x4 grid in linear array

proc access_grid()
    byte x = 2, y = 3
    byte value = grid[y * 4 + x]    ; Row-major order
    grid[y * 4 + x] = 42
end
```

---

## Pointers

### Pointer Declaration

```zap
byte ^ptr           ; Pointer to byte
word ^addr          ; Pointer to word
```

### Taking Addresses

```zap
byte x = 42
byte ^ptr = ^x      ; ptr now points to x
```

### Dereferencing

```zap
byte x = 42
byte ^ptr = ^x
byte y = ptr^       ; y now = 42
ptr^ = 99           ; x now = 99
```

### Pointer Arithmetic

Pointers support addition and subtraction. Offsets are automatically scaled by the pointed-to type:

```zap
proc pointer_arithmetic()
    byte arr[] = {10, 20, 30, 40, 50}
    byte ^ptr = ^arr        ; ptr points to arr[0]
    
    ; BYTE pointers: +1 moves 1 byte
    ptr = ptr + 1           ; Now points to arr[1]
    byte value = ptr^       ; value = 20
    
    word addresses[] = {$1000, $2000, $3000}
    word ^wptr = ^addresses
    
    ; WORD pointers: +1 moves 2 bytes
    wptr = wptr + 1         ; Skips to next WORD
    word addr2 = wptr^      ; addr2 = $2000
end
```

### Pointer to Pointers (Limited)

```zap
byte ^ptr = ^some_var
; Further pointer-to-pointer not directly supported
```

### Fixed-Address Pointers

```zap
byte ^DISPLAY_LIST @$D402       ; Hardware register
word ^COUNTER @$0600             ; Fixed address, no ZP
```

These cannot be dereferenced if not in zero-page.

### Pointer Constraints

- Regular pointers must fit in zero-page (0x00-0xFF for address storage)
- Fixed-address pointers are always at their specified location
- Dereferencing is only safe for zero-page pointers

---

## Module System

### .module Directive

Mark a file as a module that can be included:

```zap
; lib_math.zaplib
.module "lib_math"

func byte abs_diff(byte a, byte b)
    if a > b then
        return a - b
    else
        return b - a
    endif
end
```

### .include Directive

Include another module's declarations and functions:

```zap
; program.zap
.include "lib_math.zaplib"

proc main()
    byte result = abs_diff(10, 3)   ; Use included function
end
```

### Module Search

Includes are resolved relative to the including file's directory:

```
project/
  main.zap          (includes "lib/math.zaplib")
  lib/
    math.zaplib
```

### Multiple Includes

```zap
.include "lib_math.zaplib"
.include "lib_graphics.zaplib"
.include "lib_sound.zaplib"
```

### Circular Dependency Detection

The compiler detects and reports circular includes:

```zap
; lib_a.zaplib
.include "lib_b.zaplib"

; lib_b.zaplib
.include "lib_a.zaplib"    ; ERROR: Circular dependency
```

### Module Organization

Best practices:

```
.zaplib files - Library modules with utilities, no main()
.zap files    - Applications with main() procedure
```

---

## Advanced Topics

### Inline Assembly

Embed raw 6502 assembly:

```zap
proc assembly_example()
    asm
        LDA #10         ; Load accumulator with 10
        STA $D400       ; Store to hardware register
    end
end
```

### Memory Layout

Variables are allocated to memory in this order:

1. **Pointers** - Zero-page (must fit)
2. **Byte variables** - Zero-page, then BSS
3. **Word variables** - Zero-page, then BSS
4. **Arrays/Strings** - BSS (high memory)
5. **Temporary variables** - Zero-page (TMP0-TMP4)

```zap
byte ^ptr           ; 2 bytes in zero-page (address storage)
byte x              ; 1 byte in zero-page
byte y              ; 1 byte in zero-page
byte arr[256]       ; 256 bytes in BSS
```

### Zero-Page Allocation

Zero-page is precious (only 256 bytes). Compiler optimizes:

- Unused local variables are removed
- Unused global variables are removed
- Only necessary temporary variables (TMP0-TMP4) are emitted

### Const Folding and Optimization

Constant expressions are evaluated at compile-time:

```zap
const byte SIZE = 100
byte arr[SIZE + 50]         ; Array size is 150
const byte X = 2 + 3 * 4    ; X = 14 (computed at compile time)

proc main()
    byte y = SIZE * 2       ; y = 200 (compile-time)
end
```

### Dead Code Elimination

Unreachable code is removed:

```zap
proc dce_example()
    return
    ; This code never executes - removed by optimizer
    byte unused = 42
    
    if 0 then        ; Condition always false
        byte never_used = 1
    endif
end
```

### Control Flow Quirks

#### Static Local Variables

Local variables are NOT re-initialized on each call:

```zap
proc counter()
    byte count = 0   ; NOT re-initialized each call!
    count = count + 1
    putc(count + 48) ; Prints: 1, 2, 3, 4, ...
end

proc main()
    counter()    ; Prints 1
    counter()    ; Prints 2
    counter()    ; Prints 3
end
```

Solution: Use initialization flags or global variables:

```zap
byte initialized = 0

proc counter_correct()
    byte count
    
    if !initialized then
        count = 0
        initialized = 1
    endif
    
    count = count + 1
end
```

#### Identifiers Shadow Global Names

Local variables completely shadow globals with the same name:

```zap
byte global_x = 10

proc test()
    byte global_x = 20      ; Shadows global
    global_x = global_x + 1 ; Uses local (= 21)
    ; No way to access global_x from here
end
```

### Atari-Specific Features

#### Hardware Registers

```zap
byte GTIA_HPOS0 @$D000      ; Atari GTIA player 0 horizontal position
byte GTIA_SIZE0 @$D008      ; Player/missile size
word ANTIC_DLIST @$D402     ; Display list pointer

proc move_player()
    GTIA_HPOS0 = 100        ; Move player 0 to X=100
end
```

#### Atari Memory Map

```
$0000-$00FF   Zero-page and stack
$0100-$3FFF   RAM (often used for display list, screen memory)
$4000-$FFFF   Extended RAM, cartridge ROM
$D000-$D4FF   Hardware registers
```

### Type Mixing in Expressions

```zap
proc type_mixing()
    byte b = 100
    word w = 1000
    
    byte result1 = b + 10       ; 8-bit arithmetic
    word result2 = w + 10       ; 16-bit arithmetic
    word mixed = b + w          ; Byte promoted to word
end
```

### Function Return Type Coercion

```zap
func byte get_byte()
    return 50
end

func word get_word()
    return 1000
end

proc main()
    byte b = get_byte()
    word w = get_word()
end
```

---

## Common Patterns

### Counted Loop with Break

```zap
proc count_until_condition()
    byte i, found = 0
    
    for i = 0 to 255
        if some_condition(i) then
            found = 1
            break
        endif
    next i
    
    if found then
        ; Found at index i
    endif
end
```

### Initialization on First Call

```zap
byte first_call = 1

proc initialize_once()
    byte data
    
    if first_call then
        data = 0
        first_call = 0
    endif
end
```

### Table Lookup

```zap
byte lookup_table[] = {10, 20, 30, 40, 50}

proc lookup(byte index)
    byte value = lookup_table[index]
    return value
end
```

### Pointer-Based Iteration

```zap
proc iterate_with_pointer()
    byte data[] = {1, 2, 3, 4, 5}
    byte ^ptr = ^data
    byte i
    
    for i = 0 to 4
        byte value = ptr^
        ptr = ptr + 1
    next i
end
```

### Bit Testing

```zap
proc test_bit()
    byte flags = $0F
    
    if flags & $01 then
        ; Bit 0 is set
    endif
end
```

---

## Compilation and Linking

### Compile to Assembly

```bash
python compiler.py program.zap -o program.s
```

### Assemble (with cc65 tools)

```bash
ca65 -I lib -t none --cpu 65c02 -g program.s -o program.o
```

### Link for Atari

```bash
ld65 -C cfg/my_atari.cfg program.o lib/atari/exehdr.o -o program.com
```

### Full Build Script

```bash
#!/bin/bash
# Compile
python3 compiler.py program.zap -o program.s

# Assemble
ca65 -I lib -t none --cpu 65c02 -g program.s -o program.o
ca65 -I lib -t none --cpu 65c02 -g lib/atari/exehdr.s -o exehdr.o

# Link
ld65 -C cfg/my_atari.cfg program.o exehdr.o -o program.com
```

---

## Error Messages and Debugging

### Common Errors

**"Undefined variable"**
```zap
proc main()
    x = 5   ; ERROR: x not declared
end
```

**"Duplicate declaration"**
```zap
byte x = 5
byte x = 10  ; ERROR: x already declared
```

**"Type mismatch"**
```zap
byte b = some_word_value    ; May lose data warning
```

**"Procedure not found"**
```zap
proc main()
    undefined_proc()    ; ERROR: undefined_proc doesn't exist
end
```

### Debugging Tips

1. Check generated assembly (.s file) for actual output
2. Use labels and comments to trace execution
3. Test with simple cases before complex logic
4. Verify variable addresses don't collide with hardware
5. Use fixed-address variables cautiously

---

## Performance Considerations

### 8-bit Constraints

- Only 256 bytes of zero-page memory
- Multiplication/division use runtime routines (not hardware)
- Pointer operations limited to zero-page locations
- Array access requires computed addressing

### Code Size vs Speed Tradeoffs

The compiler automatically optimizes:
- Short loops → inline code
- Long loops → loop routines
- Short strings → inline init
- Long strings → ROM copy loops

### Optimization Levels

```bash
# Default
python compiler.py program.zap

# With peephole optimizations
python compiler.py --peepholes program.zap

# 65C02 optimizations (default)
python compiler.py program.zap

# For older 6502 systems
python compiler.py -6502 program.zap
```

---

## Appendix: Complete Example Program

```zap
; Fibonacci sequence generator
; Outputs Fibonacci numbers

.include "lib_graphics.zaplib"

const byte MAX_FIBO = 20

func byte fibonacci(byte n)
    if n <= 1 then
        return n
    endif
    return fibonacci(n - 1) + fibonacci(n - 2)
end

proc print_number(byte num)
    byte tens = num / 10
    byte ones = num % 10
    
    putc(tens + 48)
    putc(ones + 48)
    putc(' ')
end

proc main()
    byte i
    
    for i = 0 to MAX_FIBO
        byte result = fibonacci(i)
        print_number(result)
    next i
end
```

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| Jan 2026 | 1.0 | Initial comprehensive reference |

---

## Additional Resources

- [ZAP Language Grammar (EBNF)](grammar.ebnf)
- [Project State and Implementation Details](project_state.md)
- [Advanced Implementation Notes](advanced_notes.md)
- [Quick Reference Guide](QUICK_REFERENCE.md)

---

**For questions, issues, or suggestions regarding the ZAP! language, please visit the repository:**
https://github.com/Dushino/ZAP-compiler
