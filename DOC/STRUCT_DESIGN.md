# Struct Implementation Design for ZAP!

**Date**: January 19, 2026  
**Status**: Design Proposal  
**Author**: Design Analysis

## Executive Summary

This document proposes a struct implementation for ZAP! that integrates seamlessly with:
- Pointer arithmetic
- Array operations
- Static initialization
- Zero-page and regular memory allocation
- Type safety

The design maintains ZAP!'s low-level control while providing high-level convenience for composite types.

---

## 1. Proposed Syntax

### 1.1 Struct Definition

```zap
struct Point
    byte x
    byte y
end

struct Rect
    byte top
    byte left
    byte width
    byte height
end

struct Complex
    word address
    byte flags
    word data
end
```

**Key Design Decisions:**
- `struct` keyword (lowercase, consistent with `proc`, `func`)
- Type names are identifiers (capitalized by convention)
- Fields use standard type syntax: `byte`, `word`, or `type^`
- `end` keyword terminates definition
- Definitions are top-level (global scope only initially)

#### Port Modifiers on Structs and Fields 🔌

Struct definitions may optionally include port-related modifiers after the struct name to indicate that instances of the struct represent memory-mapped hardware registers (ports). These modifiers act as defaults for fields and can be overridden at the individual field level.

- `#PORT` placed on a `struct` signals that instances are hardware-mapped (field-level addresses are typically provided).
- `#RD` and `#WR` on a `struct` set default read/write permissions for all fields; individual fields may specify `#PORT`, `#RD`, and/or `#WR` to override the defaults.
- Semantic rules (enforced by `sema.py`): explicit field-level `#RD`/`#WR` take precedence; if a field or struct is `#PORT` and neither `#RD` nor `#WR` is specified, both reads and writes are allowed by default. Attempts to write to an `#RD`-only field or read from an `#WR`-only field will raise a semantic error.

Example:

```zap
struct VIA_STRUCT #PORT #RD
    byte ORB #RD        ; Read-only field
    byte ORA #WR        ; Write-only field
    byte DDRB           ; Inherits #RD default (read-only) unless overridden
end
```

(See also: [PORT Modifier Implementation](PORT_MODIFIER_IMPLEMENTATION.md) for full details and examples.)

### 1.2 Struct Instance Declaration

```zap
; Simple variable
Point p1

; Initialize at declaration
Point p2 = {10, 20}

; Fixed address (hardware structure)
Complex hw_screen @$0400

; Array of structs
Point points[10]
Point points[10] = { {0,0}, {1,1}, {2,2} }

; Pointer to struct
Point^ pptr
Rect^ rect_ptr
```

### 1.3 Field Access Syntax

```zap
; Direct access
p1.x = 5
p1.y = 10
byte val = p1.x

; Array access
points[0].x = 0
points[i].y = 5

; Pointer dereference
pptr^.x = 15
pptr^[0].x = 25    ; if pptr points to array
```

### 1.4 Pointer to Struct Field (Future Enhancement)

Taking addresses of struct fields is not yet defined in the MVP. The `@` operator is reserved **only** for fixed address declarations, not for address-of operations in expressions.

Future enhancement options:
- Define an address-of operator (e.g., `&p1` like in C)
- Or use assembly labels and load them

For MVP phase 1, struct pointers are initialized via assignment from fixed-address struct instances or array elements:

```zap
struct Point 
    byte x
    byte y 
end

Point p1 = {5, 10}
Point points[5]

; Pointer assignment from fixed instance (supported in Phase 2)
; Point^ pp = address_of(p1)  ; NOT YET DEFINED

; Pointer to array element
; Point^ ptr_arr = address_of(points[0])  ; NOT YET DEFINED
```

---

## 2. Memory Layout & Type System

### 2.1 Struct Size Calculation

```zap
struct Point          ; Size: 2 bytes (offset 0-1)
    byte x            ; Offset 0
    byte y            ; Offset 1
end

struct Rect           ; Size: 4 bytes (offset 0-3)
    byte top          ; Offset 0
    byte left         ; Offset 1
    byte width        ; Offset 2
    byte height       ; Offset 3
end

struct Mixed          ; Size: 5 bytes
    byte b1           ; Offset 0
    word w            ; Offset 1-2
    byte b2           ; Offset 3
    byte b3           ; Offset 4
end
```

**Memory Alignment:**
- No automatic alignment (6502 has no alignment requirements)
- Fields laid out sequentially in declaration order
- Total struct size = sum of all field sizes
- Compiler must track and calculate offsets

### 2.2 Type System Extension

**Current types:**
```python
base_type ::= "byte" | "word" ;
```

**Extended types:**
```python
base_type ::= "byte" | "word" | struct_ref ;
struct_ref ::= STRUCT_NAME ;    # Any defined struct
```

**Symbol Table Addition:**

```python
@dataclass
class StructDef:
    name: str
    fields: List[StructField]   # [(name, type, offset), ...]
    size: int                    # Total size in bytes
    
@dataclass
class StructField:
    name: str
    type: SemType               # byte, word, or pointer
    offset: int                 # Offset from struct start
```

**Type Extension:**

```python
@dataclass(frozen=True)
class SemType:
    base: str            # "byte", "word", or struct_name
    is_pointer: bool     # True if ^
    is_struct: bool = False
    struct_def: Optional[StructDef] = None
    
    @property
    def width(self) -> int:
        if self.is_pointer:
            return 2
        if self.is_struct:
            return self.struct_def.size
        if self.base == "byte":
            return 1
        if self.base == "word":
            return 2
        raise ValueError(self.base)
```

---

## 3. Grammar Changes

### 3.1 Add Struct Definition

```ebnf
top_level   ::= declaration
              | segment_directive
              | proc_decl
              | func_decl
              | module_decl
              | include_decl
              | struct_decl ;                    (* NEW *)

struct_decl ::= "struct" IDENT struct_body "end" ;
struct_body ::= { struct_field } ;
struct_field ::= type IDENT [ address_spec ] ;

(* Type system extended *)
base_type   ::= "byte" | "word" | STRUCT_IDENT ;
```

### 3.2 Field Access Expression

```ebnf
(* Add to expression rules *)
postfix_expr ::= primary_expr
               | postfix_expr "[" expression "]"
               | postfix_expr "." IDENT              (* NEW: field access *)
               | postfix_expr "^"
               | postfix_expr "^" "." IDENT         (* NEW: deref + field *)
               ;
```

---

## 4. Semantic Analysis

### 4.1 Struct Definition Validation

1. **Duplicate field names** - Error if struct has duplicate fields
2. **Invalid field types** - Error if field type is:
   - Another struct (no nesting initially)
   - Unsupported type
3. **Recursive structs** - Disallow self-references

### 4.2 Variable Declaration with Struct Type

```zap
struct Point { byte x; byte y; end

; Valid
Point p1                                ; ✓ Instance
Point p2 = {5, 10}                     ; ✓ Initialized
Point arr[10]                          ; ✓ Array
Point arr[5] = { {0,0}, {1,1} }       ; ✓ Array init
Point^ ptr                             ; ✓ Pointer
Point hw @$2000                        ; ✓ Fixed address

; Invalid
struct S1 { Point p; end               ; ✗ Struct nesting
const Point cp = {1, 2}                ; ? Const struct (see section 4.3)
```

### 4.3 Field Access Type Checking

```zap
Point p = {5, 10};
p.x = 15              ; ✓ Valid: byte field
p.y = 300             ; ✗ Error: 300 > 255, type mismatch
byte val = p.x        ; ✓ Valid: byte field → byte
word w = p.x          ; ✓ Valid: implicit byte→word
```

### 4.4 Pointer to Struct Operations

```zap
Point p = {5, 10};
Point^ pp = @p;

pp^.x = 20            ; ✓ Valid: dereference + field access
byte b = pp^.y        ; ✓ Valid: dereference + field access
pp^.x + pp^.y         ; ✓ Valid: both expressions yield byte
```

### 4.5 Struct Arrays and Indexing

```zap
Point points[10] = { {0,0}, {1,1}, {2,2} };

points[0].x = 5       ; ✓ Valid: array[idx].field
points[i].y = 10      ; ✓ Valid: variable index
Point p = points[0]   ; ✓ Valid: copy entire struct
Point^ pp = @points[0] ; ✓ Valid: pointer to struct in array
```

---

## 5. Code Generation

### 5.1 Struct Instance Storage

**Direct instance:**
```zap
struct Point { byte x; byte y; end
Point p1 = {5, 10}
```

**Generated:**
```asm
_p1:        .byte 5, 10     ; 2 bytes
```

**Array:**
```zap
Point pts[3] = { {0,0}, {1,1}, {2,2} }
```

**Generated:**
```asm
_pts:       .byte 0, 0      ; pts[0]
            .byte 1, 1      ; pts[1]
            .byte 2, 2      ; pts[2]
```

### 5.2 Field Access Code Generation

**Direct field assignment:**
```zap
p1.x = 5
```

**Generated:**
```asm
lda #5
sta _p1       ; offset 0 for x
```

**Field in array:**
```zap
points[2].y = 10
```

**Generated:**
```asm
lda #10
sta _points + 2*2 + 1    ; 2 * sizeof(Point) + offset_of_y
```

**Pointer field access:**
```zap
pp^.x = 20
```

**Generated:**
```asm
lda #20
ldy #0              ; offset of x
sta (pp), y
```

### 5.3 Struct Copy Operations

**Struct assignment:**
```zap
Point p1 = {5, 10};
Point p2;
p2 = p1;   ; Copy all fields
```

**Generated:**
```asm
; Load source fields
lda _p1
ldx _p1 + 1
; Store to destination
sta _p2
stx _p2 + 1
```

For larger structs, use loop:
```asm
ldx #0          ; field counter
.loop:
  lda _p1, x
  sta _p2, x
  inx
  cpx #size
  bne .loop
```

---

## 6. Initialization

### 6.1 Declaration-Time Initialization

```zap
struct Point { byte x; byte y; end

Point p1 = {5, 10}              ; ✓ List init
Point p2 = {5}                  ; ✗ Error: incomplete
Point p3 = {5, 10, 20}          ; ✗ Error: too many
```

### 6.2 Zero Initialization

```zap
Point p;                        ; Zero init by default
; Equivalent to: Point p = {0, 0}
```

### 6.3 Nested Initialization

```zap
struct Pair { Point a; Point b; end

; Not initially supported - requires struct nesting
; Future enhancement
```

---

## 7. Pointer Arithmetic with Structs

### 7.1 Array of Structs Pointer

```zap
struct Point { byte x; byte y; end
Point points[5];

Point^ p = @points[0];
p = p + 1;          ; Advance by sizeof(Point) = 2
byte val = p^.x;    ; Access x field of points[1]
```

**Code generation:**
```asm
; p = p + 1  (with sizeof(Point) = 2)
lda ptr
clc
adc #2          ; Add 2 (sizeof)
sta ptr
bcc skip
inc ptr+1
skip:
```

### 7.2 Field Pointer Arithmetic

```zap
struct Record { byte a; word b; byte c; end
Record r;

byte^ pa = @r.a;      ; Pointer to field a
word^ pb = @r.b;      ; Pointer to field b
pa = pa + 1;          ; sizeof(byte) = 1
pb = pb + 1;          ; sizeof(word) = 2
```

---

## 8. Compatibility Considerations

### 8.1 ✓ Compatible Features

- **Procedures with struct parameters:**
  ```zap
  proc modify_point(Point^ p)
      p^.x = p^.x + 1
  end
  
  Point my_point = {5, 10};
  modify_point(@my_point);
  ```

- **Functions returning struct pointers:**
  ```zap
  func Point^ find_point(byte idx) -> Point^
      ; search logic
      return @points[idx]
  end
  ```

- **Structs in arrays:**
  ```zap
  Point points[100];
  points[0] = {1, 2};
  ```

- **Structs with pointers as fields:**
  ```zap
  struct Node { byte val; Node^ next; end    ; NOT initially - recursion
  ```

### 8.2 Future Extensions

- **Nested structs** (requires recursive type checking)
- **Struct inheritance** (complex, maybe out of scope)
- **Union types** (different memory layout)
- **Method-like syntax** (struct.method instead of standalone functions)

---

## 9. Implementation Roadmap

### Phase 1: Core Struct Support (MVP)
- [ ] Grammar: Add `struct_decl` and field access expressions
- [ ] AST: Add `StructDef`, `StructField`, `FieldAccess` nodes
- [ ] Parser: Parse struct definitions and field access
- [ ] Symbols: Track struct definitions and calculate offsets
- [ ] Semantic: Validate struct definitions and field access
- [ ] Codegen: Generate assembly for struct operations

### Phase 2: Arrays and Pointers
- [ ] Support arrays of structs
- [ ] Support pointers to structs
- [ ] Pointer arithmetic with struct size
- [ ] Field access through pointers

### Phase 3: Advanced Features
- [ ] Nested struct definitions (if needed)
- [ ] Const structs
- [ ] Struct literals in expressions
- [ ] Pattern matching on structs (future)

---

## 10. Example Programs

### 10.1 Simple Graphics

```zap
struct Pixel
    byte x
    byte y
    byte color
end

Pixel sprite[8] = {
    {0, 0, 1},
    {1, 0, 2},
    {0, 1, 3},
    {1, 1, 4}
}

proc draw_sprite(byte sprite_id, byte screen_x, byte screen_y)
    byte i = 0
    while i < 4
        sprite[i].x = screen_x + i
        sprite[i].y = screen_y
        draw_pixel(@sprite[i])
        i = i + 1
    end
end

proc draw_pixel(Pixel^ p)
    ; Use p^.x, p^.y, p^.color
end
```

### 10.2 Game Object

```zap
struct GameObject
    byte x
    byte y
    byte type
    byte health
end

GameObject player = {10, 10, 1, 100}
GameObject enemies[10]

proc update_player()
    if player.health > 0
        move_player()
    end
end

proc move_player()
    player.x = player.x + 1
end
```

### 10.3 Hardware Structure

```zap
struct AtariScreen
    byte color0
    byte color1
    byte color2
    byte color3
end

AtariScreen palette @$2C0

proc set_colors()
    palette.color0 = 0
    palette.color1 = 15
    palette.color2 = 10
end
```

---

## 11. Testing Strategy

### Unit Tests

1. **Parser**: Parse valid/invalid struct definitions
2. **Semantic**: Type check field access, initialization
3. **Codegen**: Generate correct assembly for struct operations
4. **Integration**: Full compilation of struct-using programs

### Test Cases

```zap
; test_struct_basic.zap
struct Point
    byte x
    byte y
end

Point p = {5, 10}
; Verify: _p contains 5, 10

; test_struct_array.zap
Point points[3] = { {0,0}, {1,1}, {2,2} }
; Verify: _points contains correct values

; test_struct_pointer.zap
Point p = {5, 10}
Point^ pp = @p
pp^.x = 20
; Verify: p.x changed to 20

; test_struct_proc.zap
proc modify(Point^ p)
    p^.x = p^.x + 1
end
; Verify: parameter passing and modification
```

---

## 12. Open Questions

1. **Struct nesting**: Should we support `struct S1 { struct S2 { ... } }`?
   - *Answer*: Phase 2+, not in MVP

2. **Const structs**: Can we have `const Point p = {5, 10}`?
   - *Answer*: Yes, but all fields must be const

3. **Struct comparison**: Should `p1 == p2` compare all fields?
   - *Answer*: Not in MVP; explicit field comparison required

4. **Struct methods**: `p.draw()` or `draw(p)`?
   - *Answer*: MVP uses `draw(p)` style; methods as future extension

5. **Default initialization**: What if struct declaration omits values?
   - *Answer*: Zero-initialize by default (all fields → 0)

6. **Bit fields**: Do we need `byte flag : 1`?
   - *Answer*: Not in MVP; use manual bit operations

---

## Conclusion

This design provides a practical struct implementation that:
- ✅ Integrates seamlessly with existing ZAP! features
- ✅ Maintains low-level 6502 control
- ✅ Supports common use cases (graphics, game objects, hardware)
- ✅ Has a clear MVP and extension path
- ✅ Generates efficient assembly code

The staged implementation approach allows core struct support to ship first, with advanced features added based on user feedback and demand.
