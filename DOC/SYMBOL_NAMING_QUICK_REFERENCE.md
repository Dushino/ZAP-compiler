# ZAP! Symbol Naming Quick Reference

**Cheat Sheet for Assembly Label Name Mangling**

**Version**: 1.0  
**Date**: February 2026

---

## The Golden Rule

- **Your source identifiers** → Prefixed with **single underscore** (`_`)
- **Compiler-generated symbols** → Prefixed with **double underscore** (`__`)

**Why?** ZAP forbids identifiers starting with `_` in source code, so this creates a collision-free namespace.

---

## Quick Lookup Tables

### Source Identifiers (Single `_` Prefix)

| ZAP Source Code | Assembly Label | Usage Example |
|-----------------|----------------|---------------|
| `byte counter` | `_COUNTER` | `LDA _COUNTER` |
| `word address` | `_ADDRESS` | `STA _ADDRESS` |
| `byte data[]` | `_DATA` | `LDX _DATA,Y` |
| `proc setup()` | `_SETUP` | `JSR _SETUP` |
| `func calculate()` | `_CALCULATE` | `JSR _CALCULATE` |
| `struct Point p` | `_P` | `LDA _P` |

### Compiler-Generated Symbols (Double `__` Prefix)

#### System Temporaries (Zero Page)
| Symbol | Size | Purpose |
|--------|------|---------|
| `__TMP0` | 2 bytes | General temporary |
| `__TMP1` | 2 bytes | General temporary |
| `__TMP2` | 2 bytes | General temporary |
| `__TMP3` | 2 bytes | General temporary |
| `__TMP4` | 2 bytes | General temporary |
| `__TMP5` | 2 bytes | General temporary |
| `__MATH_STACK` | 8 bytes | Math expression stack |
| `__MATH0` | 4 bytes | Math operand 0 |
| `__MATH1` | 2 bytes | Math operand 1 |

#### Runtime Helper Routines
| Helper | Purpose |
|--------|---------|
| `__ADD16` | 16-bit addition |
| `__SUB16` | 16-bit subtraction |
| `__MUL8` | 8-bit multiplication |
| `__MUL16` | 16-bit multiplication |
| `__DIV8` | 8-bit division |
| `__DIV16` | 16-bit division |
| `__MOD8` | 8-bit modulo |
| `__MOD16` | 16-bit modulo |
| `__COPY_BYTES` | Block memory copy |
| `__ARRCPY` | Array copy |
| `__CMP16_EQ` | 16-bit equality |
| `__CMP16_LT` | 16-bit less-than |
| `__CMP16_GT` | 16-bit greater-than |

#### Control Flow Labels
| Pattern | Example |
|---------|---------|
| `__ZAP_while_N` | While loop start |
| `__ZAP_while_end_N` | While loop end |
| `__ZAP_if_N` | If statement start |
| `__ZAP_then_N` | Then branch |
| `__ZAP_else_N` | Else branch |
| `__ZAP_if_end_N` | If statement end |
| `__ZAP_for_N` | For loop start |
| `__ZAP_switch_N` | Switch statement |
| `__ZAP_case_N` | Case label |

#### Data Labels
| Pattern | Purpose | Example |
|---------|---------|---------|
| `__STR_DATA_N` | String literal in ROM | `__STR_DATA_1: .byte "Hello", 0` |
| `__ARRAY_DATA_N` | Array literal in ROM | `__ARRAY_DATA_2: .byte 1,2,3` |
| `__LVSLOT_N` | Shared local variable slot | `__LVSLOT_1: .res 2` |

---

## Common Usage Patterns

### Calling Your Procedures
```zap
proc initialize()
    ; Setup code
end

proc main()
    asm
        JSR _INITIALIZE    ; Always use _ prefix!
    end
end
```

### Accessing Variables
```zap
byte x = 0
word addr = $2000

proc update()
    asm
        LDA #42
        STA _X           ; Store to byte variable
        
        LDA #$00
        STA _ADDR        ; Store to low byte of word
        LDA #$20
        STA _ADDR+1      ; Store to high byte of word
    end
end
```

### Using Arrays
```zap
byte buffer[256]

proc fill_buffer()
    asm
        LDX #0
    LOOP:
        TXA
        STA _BUFFER,X    ; Access array with _ prefix
        INX
        BNE LOOP
    end
end
```

### Local Variables
```zap
proc compute()
    byte result = 0
    
    asm
        LDA #100
        STA _RESULT      ; Local variables also use _ prefix
    end
end
```

---

## Safety Rules

### ✅ DO THIS

1. **Always use `_` prefix** for your ZAP variables, procedures, functions
2. **Use simple labels** in ASM blocks (no prefix): `LOOP:`, `SKIP:`, `DONE:`
3. **Check generated .s file** when in doubt about a symbol name
4. **Read compiler errors** - they show the exact mangled names

### ❌ DON'T DO THIS

1. **Never create labels** starting with `_` or `__` in ASM blocks
2. **Don't reference `__` symbols** unless you're doing advanced optimization
3. **Don't assume temp values persist** - compiler reuses `__TMP0-5` between statements
4. **Don't forget the `_` prefix** when calling procedures or accessing variables

---

## Debugging Tips

### View All Symbols
```bash
# Compile your program
python compiler.py myprogram.zap -o myprogram.s

# View all source symbols (yours)
cat myprogram.s | grep "^_[^_]"

# View all compiler-generated symbols
cat myprogram.s | grep "^__"
```

### Common Mistakes

**Forgot the underscore:**
```zap
; WRONG
asm
    JSR SETUP    ; Error: undefined symbol!
end

; CORRECT
asm
    JSR _SETUP   ; Works!
end
```

**Using wrong prefix:**
```zap
; WRONG
asm
    LDA COUNTER   ; Error: undefined symbol!
end

; CORRECT
asm
    LDA _COUNTER  ; Works!
end
```

---

## Complete Example

```zap
; Define some variables
byte score = 0
word timer = 0
byte buffer[16]

proc update_score(byte points)
    score = score + points
end

proc main()
    ; Call procedure normally
    update_score(10)
    
    ; Use inline assembly
    asm
        ; Access variables with _ prefix
        LDA _SCORE
        CMP #100
        BCC NOT_MAX
        
        ; Call procedure with _ prefix
        LDA #50
        STA _SCORE
        JSR _UPDATE_SCORE
        
    NOT_MAX:
        ; Access array with _ prefix
        LDX #0
        LDA #$FF
        STA _BUFFER,X
        
        ; Don't reference compiler internals
        ; (these are used automatically)
        ; __TMP0, __MATH_STACK, __ADD16, etc.
    end
end
```

---

## See Also

- **[Advanced Topics - Inline Assembly](ADVANCED_TOPICS.md#inline-assembly)** - Complete documentation
- **[Advanced Topics - Assembly Label Naming Convention](ADVANCED_TOPICS.md#assembly-label-naming-convention)** - Detailed explanation
- **[ZAP Language Reference](ZAP_LANGUAGE_REFERENCE.md)** - Full language specification

---

**Remember**: When in doubt, compile with `-o` and check the `.s` file to see exact symbol names!
