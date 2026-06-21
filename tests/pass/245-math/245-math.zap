; Test: random math tests
;

word result @$0200 = 0


proc checkb(byte b1, byte b2)

    if b1 == b2
        result += 1
    end
end

proc checkw(word b1, word b2)

    if b1 == b2
        result += 1
    end
end

proc checkl(long b1, long b2)

    if b1 == b2
        result += 1
    end
end



proc main()
    byte b1, b2
    word w1, w2
    long l1, l2

    b1 = 0
    b2 = 0
    checkb(b1+b1, 0)    ; 1
    checkw(b1+b2, 0)    ; 2
    checkl(b1+b2, 0)    ; 3
   
    b1 = 1
    b2 = 0
    checkb(b1+b2, 1)    ; 4
    checkw(b1+b2, 1)    ; 5
    checkl(b1+b2, 1)    ; 6

    b1 = 128
    b2 = 127
    checkb(b1+b2,255)   ; 7
    checkw(b1+b2,255)   ; 8
    checkl(b1+b2,255)   ; 9

    b1 = 128
    b2 = 128    
    checkb(b1+b2,0)     ; 10
    checkw(b1+b2,0)     ; 11
    checkl(b1+b2,0)     ; 12

    w1 = 0
    b1 = 255
    checkb(low(w1)+b1, 255)  ; 13
    checkw(low(w1)+b1, 255)  ; 14
    checkl(low(w1)+b1, 255)  ; 15

    w1 = 255
    b1 = 255
    checkb(low(w1)+b1,  $FE)    ; $10
    checkw(low(w1)+b1, $1FE)    ; $11
    checkw(w1+b1, $1FE)         ; $12
    checkl(w1+b1, $1FE)         ; $13

    w1 = $1ff
    b1 =  $ff
    checkb(low(w1)+b1,  $FE)    ; $14
    checkw(low(w1)+b1, $1FE)    ; $15
    checkw(w1+b1, $2FE)         ; $16
    checkl(w1+b1, $2FE)         ; $17

    w1 = $fff
    b1 =  $ff
    checkb(low(w1)+b1,  $FE)    ; $18
    checkw(low(w1)+b1, $1FE)    ; $19
    checkw(w1+b1, $10FE)        ; $1a
    checkl(w1+b1, $10FE)        ; $1b

    w1 = $10f
    w2 = $ff1
    b1 = $ff
    b2 = $81
    checkb(low(w1)+low(w2),   $00)      ; $1c
    checkw(low(w1)+low(w2),  $100)      ; $1d
    checkw(w1+w2,           $1100)      ; $1e
    checkl(low(w1)+low(w2),  $100)      ; $1f
    checkl(b1 + low(w1), $10E)          ; $20
    checkl(low(w1) + b1, $10E)          ; $21
    checkl(w1 + w2,   $1100)            ; $22
    checkl(w1 + w2 + b1 + b2, $1280)    ; $23

    l1 = $1fef5a1f
    l2 = $8122FBF2
    checkb(low(loww(l1)) + high(loww(l1)), $79) ; $24
    checkw(low(loww(l1)) + high(loww(l1)), $79) ; $25
    checkl(low(loww(l1)) + high(loww(l1)), $79) ; $26

    checkw(loww(l1) + highw(l1), $7a0e)           ; $27
    checkl(loww(l1) + highw(l1) + loww(l2) + highw(l2), $1f722)     ; $28
    checkl(l1 + l2, $A1125611)                      ; $29

    ; let us hope that other math opeartions are OK as well...

end
