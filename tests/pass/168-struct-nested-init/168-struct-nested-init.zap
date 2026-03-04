; Test 168: Struct list init with nested struct field
; Verifies that {val, {nested_vals}} correctly initializes
; all fields including nested struct members.

struct Inner
    byte a
    byte b
end

struct Outer
    byte x
    Inner inner
end

struct Deep
    byte tag
    Outer outer
end

byte r1 @40000 = 0
byte r2 @40001 = 0
byte r3 @40002 = 0
byte r4 @40003 = 0
byte r5 @40004 = 0
byte r6 @40005 = 0
byte r7 @40006 = 0

proc main()
    ; Declarations first (all with nested struct list init)
    Outer o = {10, {20, 30}}
    Deep d = {1, {2, {3, 4}}}

    ; Test 1: Two-level nested struct init
    r1 = o.x            ; expect 10 = 0x0A
    r2 = o.inner.a      ; expect 20 = 0x14
    r3 = o.inner.b      ; expect 30 = 0x1E

    ; Test 2: Three-level nested struct init
    r4 = d.tag           ; expect 1  = 0x01
    r5 = d.outer.x       ; expect 2  = 0x02
    r6 = d.outer.inner.a ; expect 3  = 0x03
    r7 = d.outer.inner.b ; expect 4  = 0x04
end
