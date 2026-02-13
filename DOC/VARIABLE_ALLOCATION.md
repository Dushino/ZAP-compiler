# Variable Allocation and Slot Sharing

## Overview

The ZAP compiler uses sophisticated variable allocation strategies to optimize memory usage on 6502/65C02 systems. This document explains how local variables are allocated, how slot sharing works, and how variables are prioritized for Zero Page allocation.

## Table of Contents

1. [Memory Segments](#memory-segments)
2. [Variable Types and Storage](#variable-types-and-storage)
3. [Slot Sharing Strategy](#slot-sharing-strategy)
4. [Zero Page Prioritization](#zero-page-prioritization)
5. [Allocation Algorithm](#allocation-algorithm)
6. [Implementation Details](#implementation-details)

## Memory Segments

Variables are stored in different segments based on their properties and type:

### ZEROPAGE Segment (256 bytes, $0000-$00FF)

**Highest priority**: Contains frequently-accessed variables for fast access.

**System variables** (reserved):
- `MATH_STACK`: 8 bytes - Stack for mathematical operations
- `MATH0`: 4 bytes - Math temporary storage
- `MATH1`: 2 bytes - Math temporary storage
- Temporary registers: `TMP0`-`TMP5` - 2-12 bytes (allocated as needed)

**User variables** (allocated after system variables):
- **Shared slots**: Local variables that share storage through aliasing
- **Pointer variables**: ALL pointers must be in zero page (mandatory for fast indexing)
- **Byte variables** (high priority): Short-lived or frequently-used byte locals
- **Word variables** (high priority): Short-lived or frequently-used word locals

### BSS Segment (RAM, typically $0300+)

**Lower priority**: Overflow variables and large structures.

**Contains**:
- Word variables that don't fit in zero page
- Byte variables that don't fit in zero page
- Struct variables (all structs go to BSS by default)
- Array variables (all arrays go to BSS, except pointer arrays which go to ZP)

### CODE Segment

Not typically used for data, but may contain:
- Runtime constant data
- String literals (with null terminators)
- Array initialization data (const arrays)

## Variable Types and Storage

### Fixed-Address Variables

Variables declared with `@address` syntax:
```zap
word port_a @$FF00
```

These are emitted in the ZEROPAGE segment as equates:
```asm
PORT_A = $FF00
```

**Characteristics**:
- Cannot be modified by ZP allocation algorithm
- Used for hardware ports and memory-mapped I/O
- Protected from peephole optimization

### Pointers and Pointer Arrays

**Requirement**: ALL pointers MUST be in zero page.

**Rationale**: 
- 6502 indirect addressing `(addr),Y` requires the address to be in zero page
- Without specific addressing modes, pointers would require 3-4 byte sequences instead of optimal 1-2 byte sequences

**Example**:
```zap
proc print(byte *str)
    ; str pointer is in zero page for efficient `(str),Y` addressing
end
```

### Scalar Variables (BYTE and WORD)

Local variables that can potentially share storage:

```zap
proc calculate()
    byte x = 10
    byte y = 20
    word total = 0
end
```

If `x` and `y` don't overlap in their liveness (x is dead before y is used), they can share the same zero page slot.

### Arrays

All non-pointer arrays are allocated in BSS:

```zap
proc process()
    byte buffer[256]  ; Goes to BSS, too large for ZP
    byte temp[4]      ; Still goes to BSS (arrays don't fit in ZP)
end
```

### Structs

All struct variables are allocated in BSS:

```zap
struct point
    byte x
    byte y
end

proc main()
    point p              ; Goes to BSS
    point *ptr_p = @p    ; ptr_p goes to ZP, points to p in BSS
end
```

## Slot Sharing Strategy

### What is Slot Sharing?

Slot sharing (or variable aliasing) is when multiple local variables use the same storage location because their liveness ranges don't overlap.

### Liveness Analysis

The compiler performs **liveness analysis** on each procedure to determine:
- **Live-in**: Variables that are live at procedure entry
- **Live-out**: Variables that are live at procedure exit
- **Live-gen**: Variables used in this statement
- **Live-kill**: Variables that are dead after this statement

### Example of Slot Sharing

```zap
proc example()
    word x = 100
    word y = 200
    word z = x + y
end
```

All three variables (`x`, `y`, `z`) might share a single 2-byte slot because:
1. `x` is live during `x + y` computation
2. `y` is live during `x + y` computation
3. After assignment to `z`, both `x` and `y` are dead
4. If `z` is not used later, it's also dead

This results in a single `__LVSLOT_1` being used for all three.

### Graph Coloring Algorithm

The compiler uses **greedy graph coloring** to assign slots:

```
Input: Interference graph with nodes (variables) and edges (conflicts)
1. Sort nodes by degree (number of conflicts) - descending
2. For each node:
   a. Collect colors used by neighbors
   b. Assign the lowest available color
3. Group by color
4. For each color group with > 1 variable:
   a. Create a shared slot (`__LVSLOT_n`)
   b. Assign it to all variables in that group
```

### Shared Slot Naming

Shared slots are named sequentially: `__LVSLOT_1`, `__LVSLOT_2`, etc.

In assembly output:
```asm
; Shared slots (for aliased locals)
__LVSLOT_1:     .res 2      ; 2 bytes for word-type variables
__LVSLOT_2:     .res 4      ; 4 bytes for array-type variables
```

In procedure code, individual locals are aliased:
```asm
MAIN:
_MAIN_X = __LVSLOT_1
_MAIN_Y = __LVSLOT_1
_MAIN_Z = __LVSLOT_1
```

This means:
- `_MAIN_X`, `_MAIN_Y`, `_MAIN_Z` all reference the same location
- Assembler replaces all references with `__LVSLOT_1`
- No separate storage is allocated for each variable

## Zero Page Prioritization

### Priority Levels

Variables are prioritized for zero page allocation using a **frequency score** (`zp_priority`):

**Score = loop_depth_weight × access_count**

Where `loop_depth_weight` is exponential:
- **Outside loops**: weight = 1
- **Loop depth 1**: weight = 10
- **Loop depth 2**: weight = 100
- **Loop depth 3+**: weight = 1000+

### Example Priority Calculation

```zap
proc loop_demo()
    byte counter = 0           ; zp_priority = 10 (accessed 1x in loop depth 1)
    byte total = 0             ; zp_priority = 30 (accessed 3x in loop depth 1)
    
    while counter < 10
        total = total + counter
        counter = counter + 1
    end
end
```

Priorities:
- `counter`: Loaded and stored twice per iteration (depth 1) → 2 × 10 = 20
- `total`: Loaded twice and stored once per iteration (depth 1) → 3 × 10 = 30

If space permits, `total` gets priority because it has higher access frequency.

### Allocation Order

1. **Fixed-address variables** - Cannot be moved
2. **All pointers** - Mandatory in zero page
3. **High-frequency scalars** - Sorted by priority, descending
4. **Regular scalars** - Fill remaining space
5. **Overflow** - Spill to BSS

### Example Allocation

```
Available ZP space: 212 bytes (256 - 44 system)

Priority allocation:
1. Pointers (mandatory):
   - ptr_x (2 bytes) → ZP: $34-$35
   - ptr_y (2 bytes) → ZP: $36-$37
   Total used: 4 bytes, 208 remaining

2. High-priority scalars (zp_priority > 0):
   - total (word, priority=30) → ZP: $38-$39
   - count (byte, priority=20) → ZP: $3A
   Total used: 7 bytes, 205 remaining

3. Regular scalars:
   - temp_x (word) → ZP: $3B-$3C
   - temp_y (word) → ZP: $3D-$3E
   Total used: 9 bytes, 203 remaining

4. No overflow needed - all variables fit!
```

## Allocation Algorithm

### Phase 1: Liveness Analysis

For each procedure:
```
1. Compute control flow graph (CFG)
2. For each block in reverse order:
   a. Live-out = union of Live-in of successors
   b. Live-gen = variables used before being defined
   c. Live-kill = variables defined in this block
   d. Live-in = Live-gen ∪ (Live-out - Live-kill)
3. Mark variables as live/dead at each instruction
```

### Phase 2: Interference Graph

Build a graph where:
- **Nodes** = local variables (per procedure)
- **Edges** = conflict (two variables are live simultaneously)

```
if (x and y are both alive at any point)
    add edge(x, y)
```

Also add **call-live-across** constraints:
- Variables live across procedure calls interfere with callee locals

### Phase 3: Greedy Coloring

```python
# Sort by degree (conflicts) descending
variables = sorted(vars, key=lambda v: -len(conflicts[v]))

colors = {}
for var in variables:
    # Find colors used by neighbors
    neighbor_colors = {colors[n] for n in neighbors(var) if n in colors}
    
    # Assign lowest available color
    color = 0
    while color in neighbor_colors:
        color += 1
    colors[var] = color
```

### Phase 4: Slot Assignment

```python
# Group variables by color
color_groups = {}
for var, color in colors.items():
    color_groups.setdefault(color, []).append(var)

# For each color group with multiple variables
slot_counter = 0
for color, group in color_groups.items():
    if len(group) > 1:
        slot_counter += 1
        slot_label = f"__LVSLOT_{slot_counter}"
        for var in group:
            var.shared_slot = slot_label
```

## Implementation Details

### Key Files

- **[compiler_pipeline.py](../compiler_pipeline.py)**
  - `assign_slots_to_locals()`: Performs liveness analysis and graph coloring
  - `_liveness_block()`: Computes live variables in a block
  - `prioritize_locals_to_zp()`: Calculates frequency scores

- **[codegen_expr.py](../codegen_expr.py)**
  - `gen_vars()`: Emits variable declarations in correct segments
  - `gen_proc()`: Emits procedure code with local aliases

- **[symbols.py](../symbols.py)**
  - `Symbol.asm_name()`: Returns `shared_slot` if present, else regular name
  - `Symbol.shared_slot`: Optional field for aliased variables

### Assembly Output Structure

```asm
.segment "ZEROPAGE"
; System variables
MATH_STACK:     .res 8
MATH0:          .res 4
MATH1:          .res 2
TMP0:           .res 2
TMP1:           .res 2

; Fixed-address variables
PORT_A = $FF00

; Shared slots (for aliased locals)
__LVSLOT_1:     .res 2
__LVSLOT_2:     .res 4

; Pointer variables
_PROC_PTR_X:    .res 2
_PROC_PTR_Y:    .res 2

; Byte variables
_PROC_COUNTER:  .res 1

; Word variables
_PROC_TOTAL:    .res 2

.segment "BSS"
; Byte variables (BSS)
_PROC_BUFFER:   .res 256

; Word variables (BSS)
_PROC_DATA:     .res 2

; Array variables (BSS)
_PROC_ARRAY:    .res 100
```

### Local Variable Equates in Procedures

```asm
PROC_NAME:
_PROC_X = __LVSLOT_1      ; X uses shared slot 1
_PROC_Y = __LVSLOT_1      ; Y also uses shared slot 1 (no overlap)
_PROC_Z = __LVSLOT_2      ; Z uses shared slot 2

; Procedure code...
```

This allows inline assembly to reference locals by name while they're physically stored in shared slots.

## Optimization Benefits

### Memory Savings

For a procedure with many short-lived scalar locals:

**Without slot sharing**:
```
x (word, 2 bytes)
y (word, 2 bytes)
z (word, 2 bytes)
temp (byte, 1 byte)
result (word, 2 bytes)
Total: 9 bytes in zero page
```

**With slot sharing** (only overlapping variables):
```
__LVSLOT_1 (word, 2 bytes) - shared by x, y, z
__LVSLOT_2 (byte, 1 byte)  - used by temp
_RESULT (word, 2 bytes)    - result is used after procedure
Total: 5 bytes in zero page (44% reduction!)
```

### Performance

- **Pointers in zero page** → 1-byte addressing for `(ptr),Y` operations
- **High-frequency variables in zero page** → Faster access (avoid absolute addressing)
- **Zero page allocation** → Smaller code size, faster execution

## Common Patterns and Anti-patterns

### Good Pattern: Loop Counters

```zap
proc process_array(byte *arr, byte len)
    byte i = 0
    while i < len
        byte value = arr[i]      ; Reused per iteration
        if value > 100           ; Short-lived
            arr[i] = 0
        end
        i = i + 1
    end
end
```

**Analysis**:
- `i` is live throughout loop → stays in ZP
- `value` is live only for one iteration → can share slot with other temporaries
- High priority due to loop frequency

### Anti-pattern: Global Accumulator

```zap
word global_total = 0           ; Fixed storage

proc add_many(word *data, byte count)
    byte i = 0
    while i < count
        global_total = global_total + data[i]
        i = i + 1
    end
end
```

**Analysis**:
- `global_total` is global, fixed storage (good)
- `i` is high-frequency (good)
- Each iteration does expensive `(ptr),Y` indexing (good due to ZP pointers)

### Anti-pattern: Large Temporary Arrays

```zap
proc bad_practice()
    byte temp[1000]              ; Wastes ZP space!
    ; Use after small amount of data
end
```

**Better approach**:
```zap
byte temp[1000]                  ; Allocate globally once
proc reuse_buffer()
    ; Access global buffer
end
```

## Debugging Slot Sharing

### Enable Debug Output

Search for `__LVSLOT` in generated assembly:

```bash
grep "__LVSLOT" output.s
```

Shows which locals share slots.

### Analyze Liveness

The compiler's internal liveness analysis determines sharing. If a variable isn't being shared despite expectations:

1. Check if it's live across procedure calls
2. Verify it's not in a loop
3. Ensure it hasn't been marked `static`

### Disable Slot Sharing (if needed)

There's currently no compiler flag to disable slot sharing, as it's beneficial for all code. However, you can:
- Mark variables `volatile` (prevents some optimizations)
- Use `static` (allocates at global scope)

## Future Enhancements

Potential improvements:
1. **Profile-guided optimization**: Use runtime statistics to guide ZP allocation
2. **Procedure inlining awareness**: Share slots across inlined procedure boundaries
3. **Register allocation**: Track A, X, Y register usage to further reduce memory pressure
4. **Custom slot sizes**: Support variables larger than their declared size for alignment
