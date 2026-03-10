; Test shift-add decomposition for multiply by small non-power-of-2 constants.
; e.g. *3=*2+*1, *5=*4+*1, *6=*4+*2, *10=*8+*2, *12=*8+*4

byte out0 @40000 = 0
byte out1 @40001 = 0
byte out2 @40002 = 0
byte out3 @40003 = 0
byte out4 @40004 = 0
byte out5 @40005 = 0
byte out6 @40006 = 0
byte out7 @40007 = 0

proc main()
    byte a
    byte b

    a = 7
    b = a * 3      ; 7 * 3  = 21 = $15
    out0 = b

    a = 5
    b = a * 5      ; 5 * 5  = 25 = $19
    out1 = b

    a = 4
    b = a * 6      ; 4 * 6  = 24 = $18
    out2 = b

    a = 3
    b = a * 10     ; 3 * 10 = 30 = $1E
    out3 = b

    a = 2
    b = a * 12     ; 2 * 12 = 24 = $18
    out4 = b

    ; Test with literal left operand (commutative: 3*a)
    a = 6
    b = 3 * a      ; 3 * 6  = 18 = $12
    out5 = b

    ; Power-of-2 (already works, regression check)
    a = 7
    b = a * 4      ; 7 * 4  = 28 = $1C
    out6 = b

    a = 7
    b = a * 8      ; 7 * 8  = 56 = $38
    out7 = b
end
