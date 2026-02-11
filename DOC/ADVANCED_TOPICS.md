# ZAP! Advanced Programming Topics

**Advanced Concepts and Techniques for Expert ZAP! Programmers**

**Version**: 1.0  
**Date**: January 2026

---

## Table of Contents

1. [Pointer Operations](#pointer-operations)
2. [Memory Management](#memory-management)
3. [Inline Assembly](#inline-assembly)
4. [Hardware Access](#hardware-access)
5. [Optimization Techniques](#optimization-techniques)
6. [Module System Deep Dive](#module-system-deep-dive)
7. [Performance Profiling](#performance-profiling)
8. [Advanced Patterns](#advanced-patterns)
9. [Debugging Assembly Output](#debugging-assembly-output)
10. [Compiler Internals](#compiler-internals)

---

## Pointer Operations

### Understanding Pointers

Pointers store memory addresses. In ZAP!, pointers are 16-bit values (word-sized):

```zap
byte x = 42
byte ^ptr           ; Pointer type
ptr = @x            ; Store address of x (address-of operator)
byte value = ptr^   ; Dereference (read from address)
ptr^ = 99           ; Dereference (write to address)
```

### Taking Addresses

The `@` operator (address-of) retrieves an address:

```zap
byte data = 100
byte ^ptr = @data   ; Get address of data, store in ptr
```

**What's stored in `ptr`?**
- The 16-bit memory address where `data` lives
- Compiler assigns this address automatically

**Alternative syntax with `^` operator** (also supported):

```zap
byte data = 100
byte ^ptr = ^data   ; Equivalent to @data
```

### Getting Addresses of Complex Expressions

The `@` operator works with arrays and struct fields:

```zap
; Array element address
byte arr[] = {10, 20, 30}
word elem_addr = @arr[1]    ; Address of arr[1]

; Struct field address
struct Point
    byte x
    byte y
end

Point p = {50, 100}
word field_addr = @p.x      ; Address of p.x field
```

### Dereferencing

The `^` operator also reads/writes through pointers:

```zap
byte x = 50
byte ^ptr = @x

; Read through pointer
byte value = ptr^   ; value = 50

; Write through pointer
ptr^ = 99
; Now x = 99
```

### Pointer Arithmetic

Pointers support addition and subtraction. **Type matters**:

```zap
; BYTE pointer: +1 moves 1 byte
byte arr[] = {10, 20, 30}
byte ^ptr = @arr
ptr = ptr + 1           ; Points to second element
byte second = ptr^      ; second = 20

; WORD pointer: +1 moves 2 bytes (word size)
word addresses[] = {$1000, $2000, $3000}
word ^wptr = @addresses
wptr = wptr + 1         ; Points to second WORD (2 bytes later)
word addr2 = wptr^      ; addr2 = $2000
```

**The scaling is automatic:**
- `byte ^ptr + 1` moves 1 byte
- `word ^ptr + 1` moves 2 bytes

### Pointer Arrays

Array of pointers to data:

```zap
byte data1[] = "First"
byte data2[] = "Second"
byte ^ptrs[2]
ptrs[0] = @data1
ptrs[1] = @data2

; Access through array
byte char1 = ptrs[0]^   ; 'F' from data1
byte char2 = ptrs[1]^   ; 'S' from data2
```

**Note:** Pointer arrays are stored in zero page, just like scalar pointers.

### Pointer to Pointer (Limited)

ZAP! doesn't support full pointer-to-pointer chains, but you can simulate:

```zap
byte x = 100
byte ^ptr1 = ^x
byte ^ptr2 = ptr1       ; NOT pointer to ptr1, but copy of address
```

### Common Pointer Pitfalls

**Invalid Dereference:**
```zap
byte x = 10
byte y = ^x    ; ERROR: y is byte, not pointer!
```

**Non-ZP Pointers:**
```zap
byte ^ptr @$2000   ; Fixed address, not in zero-page
ptr^                ; ERROR: Can't dereference non-ZP pointer!
```

### Pointer Optimization

The compiler can optimize pointer usage:

```zap
; Compiler optimizes this:
byte ^ptr = ^array
byte val1 = ptr^
ptr = ptr + 1
byte val2 = ptr^

; Into:
; LDA array+0     ; Load first value
; LDA array+1     ; Load second value
```

### Advanced Example: Linked List

```zap
; Simple linked list node structure (simulated with arrays)
byte value[10]              ; Node values
byte next_index[10]         ; Next node index (255 = end)
byte list_start = 0         ; Start of list

proc traverse_list()
    byte current = list_start
    
    while current != 255
        byte node_value = value[current]
        current = next_index[current]
    end
end
```

---

## Memory Management

### Zero-Page (ZP)

Special 256-byte area for fast operations:

```
$00-$FF = Zero-page
```

Fastest and smallest code for:
- Variables
- Pointers
- Temporary values

```zap
byte x              ; Goes to zero-page (if space available)
byte arr[256]       ; Too big - goes to BSS (high RAM)
```

### ZP Allocation Order

Compiler allocates in this order:

1. **Pointers** - Must be in ZP (address storage)
2. **Byte variables** - ZP first, then BSS
3. **Word variables** - ZP first, then BSS
4. **Arrays** - Always BSS (except pointer arrays, which must be in ZP)
5. **Temporaries** - TMP0-TMP4 in ZP

Example layout:

```
$00-$01     System variables
$02-$03     User pointer 1
$04-$05     User pointer 2
$06         User byte variable
$07-$08     System temporaries (if used)
$09+        More variables
...
$FF         Last ZP byte

High RAM    Arrays and strings
```

### BSS (Uninitialized RAM)

Memory pool starting at high address (e.g., $3000):

```zap
byte large_array[256]  @0x3000    ; Fixed address
byte another[512]                  ; Auto-placed in BSS
```

### Fixed-Address Variables

Explicitly place variables for hardware access:

```zap
byte GTIA_HPOS0 @$D000    ; Hardware register
byte screen_data[256] @$4000  ; Screen memory

proc set_player_pos(byte x)
    GTIA_HPOS0 = x          ; Direct hardware access
end
```

**Benefits:**
- Access hardware-mapped registers
- Reserve specific memory for cartridge/OS
- Create custom memory maps

### Memory Collision

Be careful with fixed addresses:

```zap
byte var1 @$2000
byte var2 @$2000   ; ERROR: Collision!
```

### Dynamic Memory (Not Supported)

ZAP! doesn't support malloc/free. All memory is static.

**Workaround:** Pre-allocate pools:

```zap
; Object pool
const byte MAX_OBJECTS = 20
byte object_x[MAX_OBJECTS]
byte object_y[MAX_OBJECTS]
byte object_active[MAX_OBJECTS]
byte object_count = 0

proc allocate_object()
    if object_count < MAX_OBJECTS then
        object_count = object_count + 1
        byte idx = object_count - 1
        object_x[idx] = 0
        object_y[idx] = 0
        object_active[idx] = 1
    endif
end
```

### Static Local Variables (Persistent State)

Static variables are local variables that retain their values between procedure calls. Unlike regular local variables (which are re-initialized on each entry), static variables are initialized only once at program startup.

**Syntax and Behavior:**

```zap
proc increment_counter()
    static byte counter = 0    ; Initialized once at program start
    counter = counter + 1
    return counter
end

proc main()
    byte x1 = increment_counter()  ; Returns 1, counter now = 1
    byte x2 = increment_counter()  ; Returns 2, counter now = 2
    byte x3 = increment_counter()  ; Returns 3, counter now = 3
end
```

**Initialization Flow:**

1. Program starts
2. Global variables are initialized
3. Static local variables are initialized (in order of procedures)
4. MAIN is called
5. During execution, static variables persist across procedure calls

**Rules:**

- Only for **local variables** (inside procedures/functions)
- Cannot combine with `CONST` modifier
- Must have an initializer (static variables can't be uninitialized)
- Storage is in zero-page (ZP) if space available, otherwise in BSS

**Use Cases:**

1. **Call counters:**
```zap
proc get_object_id()
    static byte next_id = 1
    byte id = next_id
    next_id = next_id + 1
    return id
end
```

2. **State machines:**
```zap
proc game_state()
    static byte state = 0  ; 0=menu, 1=playing, 2=paused
    
    if state = 0 then
        ; Handle menu
        state = 1
    elseif state = 1 then
        ; Handle game
        if player_pressed_pause then
            state = 2
        endif
    elseif state = 2 then
        ; Handle pause
        if player_pressed_resume then
            state = 1
        endif
    endif
end
```

3. **Resource pools:**
```zap
const byte MAX_SPRITES = 10

proc allocate_sprite()
    static byte sprite_count = 0
    
    if sprite_count < MAX_SPRITES then
        byte id = sprite_count
        sprite_count = sprite_count + 1
        return id
    else
        return 255  ; Error code
    endif
end
```

**Memory Considerations:**

Static local variables occupy memory like global variables - they're allocated in zero-page or BSS at compile time, not on the stack. Therefore:

- Each static variable takes permanent memory
- Static variables are always available (no stack overhead)
- Good for values that need to persist but shouldn't be global

---

## Inline Assembly


### Basic ASM Block

Embed raw 6502 assembly:

```zap
proc setup_display()
    asm
        LDA #$40
        STA $D400
    end
end
```

### Assembly Labels

Create local labels:

```zap
proc loop_example()
    byte i = 0
    
    asm
    LOOP:
        INC $D000
        DEC _I          ; Decrement local i (internal name: _I)
        BNE LOOP
    end
end
```

### Accessing ZAP Variables

Variables are prefixed with `_`:

```zap
byte my_var = 0
word my_word = 0

asm
    LDA _MY_VAR     ; Load byte variable
    LDX _MY_WORD    ; Load low byte of word
    LDY _MY_WORD+1  ; Load high byte of word
end
```

### System Temporaries

System uses TMP0-TMP4:

```zap
asm
    LDA #100
    STA TMP0        ; OK: Can use TMP0-TMP4
end
```

### Calling Procedures from Assembly

Procedures become labels:

```zap
proc setup()
    ; Setup code
end

proc main()
    asm
        JSR SETUP   ; Call setup procedure
    end
end
```

### Assembler-only directives

Assembler directives like `.segment` and `.incbin` are only recognized inside `asm ... end` blocks and are not supported as top-level ZAP directives. Example:

```zap
proc load_font()
    asm
        .segment "FONT"
        .incbin "font.dat"
        .segment "CODE"    ; Switch back
    end
end
```

For compile-time diagnostics, ZAP provides the following directives (used outside of `asm` blocks):

```zap
.error "This is a compile error"    ; Emits an error and stops compilation
.warning "This is a warning"        ; Emits a warning but continues compilation
.info "Informational message"       ; Emits an info message but continues compilation
```

### Assembly Gotchas

**Don't forget to restore segments:**
```zap
asm
    .segment "DATA"
    .byte 1, 2, 3
    .segment "CODE"    ; MUST restore!
end
```

**Be careful with labels:**
```zap
asm
    JMP MY_LABEL       ; Unique names only
MY_LABEL:
    RTS
end
```

**Don't use END in assembly:**
```zap
asm
    LOOP: INC A
    JMP LOOP
    END             ; ERROR: This ends the ASM block!
end
```

---

## Hardware Access

### Atari 8-Bit Registers

The Atari has memory-mapped hardware registers:

```zap
; GTIA (Graphics) Registers
byte GTIA_M0PL @$D00C           ; Missile 0 / Player collision
byte GTIA_P0PL @$D00D           ; Player 0 collision
byte GTIA_HPOS0 @$D000          ; Player 0 horizontal position

; ANTIC (Display) Registers
word ANTIC_DLIST @$D402         ; Display list pointer
byte ANTIC_HSCROL @$D404        ; Horizontal scroll

; POKEY (Sound/I/O) Registers
byte POKEY_AUDF1 @$D200         ; Audio frequency 1
byte POKEY_AUDC1 @$D201         ; Audio control 1
```

### Reading Registers

```zap
proc check_collision()
    byte collision = GTIA_M0PL
    if collision != 0 then
        ; Collision detected!
    endif
end
```

### Writing to Registers

```zap
proc move_player(byte x)
    GTIA_HPOS0 = x      ; Set player X position
end

proc set_display_list(word address)
    ANTIC_DLIST = address
end
```

### Sound Output

```zap
proc play_note(byte frequency, byte duration)
    POKEY_AUDF1 = frequency
    POKEY_AUDC1 = $A8      ; Enable audio
    
    ; Wait
    byte i
    for i = 0 to duration
        ; Busy-wait
    end
    
    POKEY_AUDC1 = 0        ; Stop audio
end
```

### Interrupt-like Patterns

Monitor register changes:

```zap
byte last_joystick = 0

proc poll_joystick()
    byte joystick = POKEY_STICK0    ; Read joystick
    
    if joystick != last_joystick then
        ; Joystick changed
        handle_input(joystick)
    endif
    
    last_joystick = joystick
end
```

### Game Loop with Hardware

```zap
proc game_loop()
    while game_running
        ; Update physics
        update_game()
        
        ; Check collisions
        check_collisions()
        
        ; Poll input
        poll_joystick()
        
        ; Render
        draw_frame()
    end
end
```

---

## Optimization Techniques

### Compiler Optimizations

The compiler applies several passes:

```bash
# Basic compilation
python compiler.py program.zap

# With all peephole optimizations
python compiler.py --peepholes program.zap

# For 6502 (older CPU, may be slower)
python compiler.py -6502 program.zap
```

### Constant Folding

Compiler evaluates constants at compile-time:

```zap
const byte SIZE = 100
byte data[SIZE + 50]    ; Array size = 150 (compile-time)

proc init()
    byte x = 2 + 3 * 4  ; x = 14 (computed at compile-time)
end
```

**Compiler generates:**
```asm
data:   .res 150        ; Not calculated at runtime
x:      .byte 14        ; Not calculated at runtime
```

### Dead Code Elimination

Unreachable code is removed:

```zap
proc dce_example()
    return
    byte unused = 42    ; Never reaches here - removed!
    
    if 0 then           ; Condition always false
        byte x = 1      ; Removed
    endif
end
```

### Loop Unrolling for Small Loops

Manual optimization:

```zap
; Original (5 iterations)
byte i
for i = 0 to 4
    process(i)
end

; Unrolled (faster, more code)
process(0)
process(1)
process(2)
process(3)
process(4)
```

### Lookup Tables vs Calculation

```zap
; Slow: calculated each time
func byte sin_approx(byte angle)
    return (angle * 127) / 128
end

; Fast: lookup table (pre-computed)
byte sine_table[] = {0, 13, 26, 38, 50, ...}

proc sin_table_lookup()
    byte angle = 10
    byte value = sine_table[angle]
end
```

### Cache Data in Registers

```zap
proc process_loop()
    byte index = 0
    byte temp = data[index]
    
    for index = 0 to 255
        process_value(temp)
        temp = data[index + 1]  ; Pre-load next
    next index
end
```

### Byte vs Word

```zap
; Use byte when possible (faster, smaller)
byte small_value = 100

; Use word only if necessary
word large_value = 40000
```

### Minimize Pointer Dereference

```zap
; Slow: multiple dereferences
byte ^ptr = ^data
byte v1 = ptr^
byte v2 = ptr^
byte v3 = ptr^

; Faster: cache value
byte ^ptr = ^data
byte value = ptr^
byte v1 = value
byte v2 = value
byte v3 = value
```

### Profile Your Code

Check generated assembly for hotspots:

```bash
python compiler.py program.zap -o program.s
# Review program.s for performance-critical sections
```

---

## Module System Deep Dive

### Module Structure

**library.zaplib** - Reusable module:
```zap
.module "math"

func byte abs(byte x)
    if x < 0 then
        return -x
    endif
    return x
end
```

**program.zap** - Main program:
```zap
.include "library.zaplib"

proc main()
    byte result = abs(-5)
end
```

### Multi-Level Includes

```
main.zap
├── lib_graphics.zaplib
│   └── lib_colors.zaplib
├── lib_math.zaplib
└── lib_physics.zaplib
    └── lib_math.zaplib (already loaded)
```

### Symbol Visibility

Included modules' symbols become available:

```zap
; vector.zaplib
func word cross_product(byte ax, byte ay, byte bx, byte by)
    return (ax * by) - (ay * bx)
end

; main.zap
.include "vector.zaplib"

proc main()
    word result = cross_product(1, 2, 3, 4)
end
```

### Include Organization

Best practices:

```
project/
├── main.zap
├── lib/
│   ├── graphics.zaplib
│   ├── sound.zaplib
│   ├── physics.zaplib
│   └── util.zaplib
└── game/
    ├── player.zaplib
    ├── enemies.zaplib
    └── items.zaplib
```

### Avoiding Circular Dependencies

**Bad:**
```zap
; a.zaplib
.include "b.zaplib"

; b.zaplib
.include "a.zaplib"    ; Circular!
```

**Good:**
```zap
; a.zaplib
func byte func_a() ... end

; b.zaplib
func byte func_b() ... end

; main.zap
.include "a.zaplib"
.include "b.zaplib"
```

---

## Performance Profiling

### Analyzing Generated Assembly

```bash
python compiler.py program.zap -o program.s
```

Look for:
- Excessive address calculations
- Repeated dereferences
- Inefficient loop bodies

### Code Size Analysis

```asm
; program.s - Check for:
; - Size of procedures
; - Repetitive patterns
; - Unused code (optimized away)
```

### Timing Critical Sections

Count assembly instructions:

```zap
proc critical_inner_loop()
    byte i, sum = 0
    
    ; This loop is critical - minimize instructions
    for i = 0 to 255
        sum = sum + data[i]
    end
end
```

### Memory Usage

Track variable allocation:

```
Zero-page usage:
- Pointers: ~10 bytes
- Variables: ~20 bytes
- Temporaries: ~5 bytes
Total: ~35 bytes (plenty remaining)

High RAM:
- Arrays: ~1KB
```

---

## Advanced Patterns

### State Machine

```zap
const byte STATE_INIT = 0
const byte STATE_PLAY = 1
const byte STATE_PAUSE = 2
const byte STATE_OVER = 3

byte game_state = STATE_INIT

proc update_state()
    if game_state == STATE_INIT then
        initialize_game()
        game_state = STATE_PLAY
    endif
    
    if game_state == STATE_PLAY then
        update_game()
        check_pause()
        check_game_over()
    endif
    
    if game_state == STATE_PAUSE then
        check_unpause()
    endif
    
    if game_state == STATE_OVER then
        show_game_over()
    endif
end
```

### Event Handling

```zap
; Event flags
byte event_collision = 0
byte event_powerup = 0
byte event_death = 0

proc handle_events()
    if event_collision then
        on_collision()
        event_collision = 0
    endif
    
    if event_powerup then
        on_powerup()
        event_powerup = 0
    endif
    
    if event_death then
        on_death()
        event_death = 0
    endif
end
```

### Object Pooling

```zap
const byte MAX_SPRITES = 10

byte sprite_x[MAX_SPRITES]
byte sprite_y[MAX_SPRITES]
byte sprite_active[MAX_SPRITES]
byte sprite_count = 0

proc spawn_sprite(byte x, byte y)
    if sprite_count < MAX_SPRITES then
        sprite_x[sprite_count] = x
        sprite_y[sprite_count] = y
        sprite_active[sprite_count] = 1
        sprite_count = sprite_count + 1
    endif
end

proc update_sprites()
    byte i
    for i = 0 to sprite_count
        if sprite_active[i] then
            sprite_y[i] = sprite_y[i] + 1
            
            if sprite_y[i] > 191 then
                sprite_active[i] = 0
            endif
        endif
    end
end
```

### Message Passing

```zap
const byte MAX_MESSAGES = 5
byte message_queue[MAX_MESSAGES]
byte message_count = 0

proc send_message(byte msg)
    if message_count < MAX_MESSAGES then
        message_queue[message_count] = msg
        message_count = message_count + 1
    endif
end

proc process_messages()
    byte i
    for i = 0 to message_count
        process_message(message_queue[i])
    end
    message_count = 0
end
```

### Frame Timing

```zap
byte frame_counter = 0

proc game_update()
    frame_counter = frame_counter + 1
    
    ; Every 30 frames
    if frame_counter == 30 then
        do_expensive_operation()
        frame_counter = 0
    endif
    
    ; Do fast updates every frame
    do_fast_operation()
end
```

---

## Debugging Assembly Output

### Reading Generated Assembly

```asm
; C:\path\to\program.zap 4: proc main()
; -- Procedure MAIN --
MAIN:
    ; Actual assembly instructions
    JSR FUNCTION    ; Call function
    RTS             ; Return
```

### Following Execution

```asm
LDA #10         ; Load 10 into accumulator
STA _VAR        ; Store into variable
; At this point, _VAR = 10
```

### Analyzing Procedure Calls

```asm
JSR SETUP       ; Jump to subroutine (saves return address)
                ; ... SETUP executes ...
                ; RTS (return to here)

JMP LOOP        ; Jump (no return)
```

### Checking Variable Addresses

```asm
.segment "ZEROPAGE"
_MY_VAR:  .res 1        ; _MY_VAR at some ZP address
_MY_PTR:  .res 2        ; _MY_PTR at ZP address
```

---

## Compiler Internals

### Compilation Pipeline

1. **Tokenization** - Convert source to tokens
2. **Parsing** - Build AST
3. **Semantic Analysis** - Type checking, symbol resolution
4. **Optimization** - Constant folding, DCE, etc.
5. **Code Generation** - Emit assembly
6. **Assembly Optimization** - Peephole, jump threading

### How Variables Are Named

```
Global byte x          → _X
Local byte x in TEST   → _TEST_X
Pointer ptr            → _PTR (2 bytes)
Procedure P1           → P1 (label)
Parameter in P1        → _P1_PARAM
```

### Math Runtime Registers (6502)

The compiler uses a dedicated zero-page math area when lowering `*`, `/`, and `%`:

```asm
.segment "ZEROPAGE"
MATH_STACK: .res 8      ; 4x 16-bit slots for expression evaluation
MATH0:      .res 4      ; 32-bit accumulator (result)
MATH1:      .res 2      ; 16-bit operand
```

- `MATH0` holds the final result (low word in `MATH0`/`MATH0+1`).
- `MATH1` holds the second operand for math routines.
- `MATH_STACK` is used to spill intermediate operands in complex expressions.
- Runtime math routines use `TMP0..TMP4` as scratch and will reserve them when emitted.

### Accumulator-Mode Arithmetic (ADD16/SUB16)

For better efficiency with chained arithmetic, the compiler uses `ADD16` and `SUB16` runtime routines:

```asm
; ADD16 - Accumulator-style 16-bit addition
; Input:  MATH0 (left operand), MATH1 (right operand)
; Output: MATH0 (sum)
ADD16:
    LDA MATH0
    CLC
    ADC MATH1
    STA MATH0
    LDA MATH0+1
    ADC MATH1+1
    STA MATH0+1
    RTS

; SUB16 - Accumulator-style 16-bit subtraction  
; Input:  MATH0 (left operand), MATH1 (right operand)
; Output: MATH0 (difference)
SUB16:
    LDA MATH0
    SEC
    SBC MATH1
    STA MATH0
    LDA MATH0+1
    SBC MATH1+1
    STA MATH0+1
    RTS
```

When evaluating expressions like `a + b * (c + 1) - 10`:
1. `b * (c + 1)` is evaluated and stored in MATH0
2. `ADD16` is called to compute MATH0 += a
3. Immediate subtraction handles the final `-10`

This avoids repeated temp spilling compared to fully inline arithmetic, reducing code size and improving instruction cache locality for complex expressions.

**Note on SUB16 with immediate constants:** The compiler uses SUB16 (subroutine) instead of inline SBC instructions for 16-bit immediate subtractions of constants. This unifies the subtraction ABI and allows for future optimization opportunities where intermediate results are cached in MATH0.

### Future Optimization: MATH0 Result Caching

The accumulator-based architecture supports a future optimization: **keeping results in MATH0 across expression chains** to eliminate unnecessary temp shuttling. Currently, each operation loads its result to A/X for downstream use, then the next operation in a chain loads from A/X back to MATH0 for its computation.

**Proposed enhancement:**
- Add `result_location` parameter to `gen_expr()` ("A/X" or "MATH0")
- For nested expressions, keep intermediate results in MATH0
- Only load to A/X at expression boundaries (assignments, function calls, external returns)
- Would save ~10+ bytes of ZP temp pressure and improve code efficiency
  
**Implementation notes:**
- Infrastructure partially in place (result_location parameter added)
- Requires propagating result_location through all recursive `gen_expr()` calls
- Needs special handling for each expression type (literals, identifiers, math ops, etc.)
- May require two-pass or lookahead logic to determine when result will be immediately re-used in another math operation

### How Arrays Are Accessed

```zap
byte arr[5]
byte index = 2
byte value = arr[index]
```

Compiles to:
```asm
; Calculate: base + index
LDA #<ARR           ; Low byte of array address
CLC
ADC _INDEX          ; Add index
STA TMP0            ; Store in temp
; Load value
LDY #0
LDA (TMP0),Y        ; Indirect addressing
```

### Binary Number Literals

```zap
byte b1 = %10101010     ; Binary
byte b2 = 0b1010        ; 0b prefix
byte h1 = $FF           ; Hex (dollar sign)
byte h2 = 0xFF          ; 0x prefix (decimal also works)
byte d1 = 255           ; Decimal
```

---

## Best Practices

1. **Profile before optimizing** - Measure first
2. **Use appropriate types** - byte when possible
3. **Precompute when possible** - Lookup tables
4. **Organize with modules** - Keep code maintainable
5. **Document hardware access** - Comments for registers
6. **Test incrementally** - Small, verifiable changes
7. **Check generated assembly** - Understand output
8. **Use fixed addresses carefully** - Avoid collisions
9. **Monitor zero-page usage** - Most precious resource
10. **Leverage compiler optimizations** - Use --peepholes

---

## Troubleshooting Advanced Issues

### "Zero-page exhausted"

Too many pointers or small variables:

```zap
; Current:
byte ^ptr1, ^ptr2, ^ptr3  ; 6 bytes
byte x, y, z              ; 3 bytes
; Total: 9 bytes

; Solution: Reduce pointer count
byte ^ptr1                ; Only needed pointer
word address1, address2   ; Use word arrays instead
```

### "Circular dependency"

Modules include each other:

```zap
; Break cycle:
; a.zaplib - defines func_a
; b.zaplib - defines func_b
; main.zap - includes both
```

### Performance unexpectedly poor

```bash
python compiler.py -o program.s program.zap
# Review program.s for:
# - Repeated dereferences
# - Inefficient loops
# - Unnecessary multiplications
```

---

## Further Reading

- [ZAP! Language Reference](ZAP_LANGUAGE_REFERENCE.md)
- [Getting Started Guide](GETTING_STARTED.md)
- [Atari 8-Bit Hardware Guide](https://www.atariarchives.org/)
- [6502 Assembly Language](https://www.masswerk.at/6502/6502_instruction_set.html)

---

**Master ZAP! and create incredible retro software!**
