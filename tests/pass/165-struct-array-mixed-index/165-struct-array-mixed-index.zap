; Test struct array subscripting for non-power-of-2 struct sizes (3, 5, 6, 12).
; The compiler uses shift-add decomposition (sum of two powers of 2).

struct S3
    byte a
    byte b
    byte c
end

struct S5
    byte a
    byte b
    byte c
    byte d
    byte e
end

struct S6
    byte a
    byte b
    byte c
    byte d
    byte e
    byte f
end

struct S12
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
end

S3  arr3[5]  @50000
S5  arr5[4]  @50032
S6  arr6[4]  @50064
S12 arr12[3] @50096

byte out0 @40000 = 0
byte out1 @40001 = 0
byte out2 @40002 = 0
byte out3 @40003 = 0
byte out4 @40004 = 0
byte out5 @40005 = 0

proc main()
    byte i

    ; S3 (size 3 = 2+1): shift-add decomposition
    arr3[0].a = $10
    arr3[1].a = $20
    arr3[2].a = $30
    arr3[3].a = $40
    arr3[4].a = $50
    i = 1
    out0 = arr3[i].a    ; expect $20
    i = 4
    out1 = arr3[i].a    ; expect $50

    ; S5 (size 5 = 4+1): shift-add decomposition
    arr5[0].a = $11
    arr5[1].a = $22
    arr5[2].a = $33
    arr5[3].a = $44
    i = 2
    out2 = arr5[i].a    ; expect $33

    ; S6 (size 6 = 4+2): shift-add decomposition
    arr6[0].a = $AA
    arr6[1].a = $BB
    arr6[2].a = $CC
    arr6[3].a = $DD
    i = 3
    out3 = arr6[i].a    ; expect $DD

    ; S12 (size 12 = 8+4): shift-add decomposition
    arr12[0].f0 = $01
    arr12[1].f0 = $02
    arr12[2].f0 = $03
    i = 1
    out4 = arr12[i].f0  ; expect $02
    i = 2
    out5 = arr12[i].f0  ; expect $03
end
