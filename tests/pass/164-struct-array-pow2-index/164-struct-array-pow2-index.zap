; Test struct array subscripting for power-of-2 struct sizes (4, 8, 16 bytes).
; The compiler must use shift-based index scaling instead of repeated addition.

struct S4
    byte a
    byte b
    byte c
    byte d
end

struct S8
    byte a
    byte b
    byte c
    byte d
    byte e
    byte f
    byte g
    byte h
end

struct S16
    byte f0
    byte f1
    byte f2
    byte f3
    byte f4
    byte f5
    byte f6
    byte f7
    byte f8
    byte f9
    byte f10
    byte f11
    byte f12
    byte f13
    byte f14
    byte f15
end

S4  arr4[4]  @50000
S8  arr8[3]  @50016
S16 arr16[2] @50040

byte out0 @40000 = 0
byte out1 @40001 = 0
byte out2 @40002 = 0
byte out3 @40003 = 0
byte out4 @40004 = 0
byte out5 @40005 = 0

proc main()
    byte i

    ; S4 (element size 4 = 2^2): index*4 via 2 left shifts
    arr4[0].a = $10
    arr4[1].a = $20
    arr4[2].a = $30
    arr4[3].a = $40
    i = 0
    out0 = arr4[i].a    ; expect $10
    i = 2
    out1 = arr4[i].a    ; expect $30

    ; S8 (element size 8 = 2^3): index*8 via 3 left shifts
    arr8[0].a = $AA
    arr8[1].a = $BB
    arr8[2].a = $CC
    i = 1
    out2 = arr8[i].a    ; expect $BB
    i = 2
    out3 = arr8[i].a    ; expect $CC

    ; S16 (element size 16 = 2^4): index*16 via 4 left shifts
    arr16[0].f0 = $11
    arr16[1].f0 = $22
    i = 0
    out4 = arr16[i].f0  ; expect $11
    i = 1
    out5 = arr16[i].f0  ; expect $22
end
