# PORT Modifier Implementation - Complete

## Overview

The `PORT` modifier has been implemented to explicitly mark hardware port-mapped variables. This allows the compiler to distinguish between generic fixed-address variables and hardware port variables, enabling future optimization strategy changes.

## Syntax

```zap
PORT type name @address
```

Example:
```zap
PORT byte POKEY_AUDF1 @$D200
PORT word SCREEN_ADDR @$4000
```

## Restrictions

The `PORT` modifier has the following restrictions:

1. **Requires address specification (@)**: PORT variables must always include an explicit address with the `@` operator
   ```zap
   PORT byte POKEY_AUDF1 @$D200  ; OK
   PORT byte POKEY_AUDF1          ; ERROR: requires @address
   ```

2. **Cannot be combined with CONST**: PORT and CONST modifiers are mutually exclusive
   ```zap
   CONST PORT byte X @$D200      ; ERROR
   PORT byte X @$D200            ; OK
   ```

3. **Cannot be combined with STATIC**: PORT and STATIC modifiers are mutually exclusive
   ```zap
   PROC test()
       STATIC PORT byte X @$D200  ; ERROR
   END
   ```

4. **Cannot be used on arrays**: PORT variables must be scalar types
   ```zap
   PORT byte ARR[10] @$2000      ; ERROR
   PORT byte SINGLE @$2000        ; OK
   ```

5. **Cannot be used on pointers**: PORT variables must be byte or word, not pointers
   ```zap
   PORT byte ^ PTR @$D200         ; ERROR
   PORT byte REG @$D200           ; OK
   ```

6. **Cannot have initializers**: Hardware ports cannot be initialized
   ```zap
   PORT byte POKEY_AUDF1 @$D200 = 0  ; ERROR
   PORT byte POKEY_AUDF1 @$D200      ; OK
   ```

## Use Cases

### Hardware Register Access (Atari Pokey Chip)
```zap
PORT byte POKEY_AUDF1 @$D200    ; Frequency register 1
PORT byte POKEY_AUDF2 @$D201    ; Frequency register 2
PORT byte POKEY_AUDF3 @$D202    ; Frequency register 3
PORT byte POKEY_AUDF4 @$D203    ; Frequency register 4

proc set_tone(byte frequency)
    POKEY_AUDF1 = frequency
end
```

### Memory-Mapped I/O
```zap
PORT byte STATUS_PORT @$FFF0
PORT byte DATA_PORT @$FFF1
PORT byte CONTROL_PORT @$FFF2

proc read_status()
    byte status = STATUS_PORT
    return status
end
```

### Multiple Hardware Registers
```zap
PORT byte GTIA_HPOS0 @$D000
PORT byte GTIA_HPOS1 @$D001
PORT byte GTIA_HPOS2 @$D002
PORT byte GTIA_HPOS3 @$D003

proc set_player_position(byte player, byte x)
    if player = 0 then
        GTIA_HPOS0 = x
    elseif player = 1 then
        GTIA_HPOS1 = x
    endif
end
```

## Implementation Details

### Tokenizer (tokenizer.py)
- Added `"port"` to `TYPEMOD` set
- PORT is recognized as a type modifier keyword

### Parser (parser.py)
- Added `is_port` boolean flag to `Declaration` AST node
- Parser recognizes and tracks PORT modifier in `parse_declaration()`
- PORT modifier can appear at the beginning of declaration like CONST and STATIC

### AST Nodes (ast_nodes.py)
- Added `is_port: bool = False` field to `Declaration` dataclass
- Updated `__repr__()` to include PORT indicator

### Symbol Table (symbols.py)
- Added `is_port: bool = False` field to `Symbol` dataclass
- Tracks which variables are PORT variables throughout compilation

### Semantic Analysis (sema.py)
- Validates PORT modifier restrictions:
  1. Cannot combine with CONST
  2. Cannot combine with STATIC
  3. Requires address specification (@)
  4. Cannot be used on arrays
  5. Cannot be used on pointers
  6. Cannot have initializers
- Propagates `is_port` flag to Symbol during semantic analysis

### Code Generation (codegen_expr.py)
- Added `port_labels: set[str]` to track PORT variables
- PORT variables populate both `fixed_address_labels` and `port_labels`
- Added `_is_port_variable()` method for future optimization strategy changes
- PORT variables are treated as fixed-address variables (never optimized away)

### Syntax Highlighting (zap.tmLanguage.json)
- PORT keyword already included in `storage.modifier` pattern

## Assembly Output

PORT variables are emitted as fixed-address assignments in the assembly, identical to generic fixed-address variables:

```asm
; Fixed-address variables
_POKEY_AUDF1 = $D200
_POKEY_AUDF2 = $D201
```

This ensures:
- Hardware port access is correct
- Reads/writes have proper side effects
- Compiler doesn't optimize away critical hardware access

## Future Optimization Strategy

Currently, PORT variables are treated identically to generic fixed-address variables (both marked as `fixed_address_labels`). In the future, this can be refined:

**Current approach:** "No @ variables can be optimized"
**Future approach:** "No PORT variables can be optimized" (but @ variables that aren't PORT might be optimizable)

The infrastructure is already in place:
- `port_labels` set tracks only PORT variables
- `_is_port_variable()` method available for future checks
- Generic @ address variables use `fixed_address_labels`

## Test Coverage

All 12 test cases pass:
- ✅ PORT byte with address
- ✅ PORT word with address
- ✅ PORT without address (error)
- ✅ PORT with CONST (error)
- ✅ PORT with STATIC (error)
- ✅ PORT on array (error)
- ✅ PORT on pointer (error)
- ✅ PORT read from address
- ✅ PORT write to address
- ✅ Multiple PORT variables
- ✅ PORT global and local (valid)
- ✅ PORT variable initialization (error)

## Examples

### Basic Hardware Register
```zap
PORT byte POKEY_AUDF1 @$D200

proc main()
    POKEY_AUDF1 = 100  ; Set frequency
end
```

### Multiple Registers
```zap
PORT byte STATUS @$D20F
PORT byte CONTROL @$D20E
PORT byte DATA @$D20D

proc init_device()
    CONTROL = 0
    STATUS = 0xFF
end
```

### Reading Hardware Status
```zap
PORT byte IRQ_STATUS @$D20E

proc check_irq()
    byte status = IRQ_STATUS
    if status & 1 then
        ; Handle interrupt
    endif
end
```

## Migration from @ Variables

Existing code using `@address` without PORT still works:

```zap
; Old style - still valid
byte HW_REG @$D200 = 50  ; Regular variable at fixed address

; New style - explicit hardware port
PORT byte POKEY_AUDF1 @$D200  ; Explicit PORT declaration
```

The difference:
- **Old `@address`**: Generic fixed-address variable (can store initial value)
- **New `PORT @address`**: Hardware port-mapped variable (no initializer allowed)
