; math tests
; test_math_1.zap

const byte c1 = 3

byte ^ptr1 = 40000
word ^ptr2 = 40000+32

proc math1(byte b1, byte b2)    ; 2, 9
    byte r
    
    r = b1 + 0
    r = b1 - 0
    r = b1 + 1
    r = b1 - 1                 
    ptr1^ = r               ; 0: 1
    ptr1 = ptr1+1

    r = b1 * 5
    ptr1^ = r
    ptr1 = ptr1+1           ; 1: $3D

    r = b2 / 4              
    ptr1^ = r
    ptr1 = ptr1+1           ; 2: 2

    r = b2 / 3
    ptr1^ = r
    ptr1 = ptr1+1           ; 3: 3

    r = b2 % 7
    ptr1^ = r
    ptr1 = ptr1+1           ; 4: 2

    r = b2 % 1
    ptr1^ = r
    ptr1 = ptr1+1           ; 5: 9
end

proc math2(word b1, word b2)    ; $fa02, $1209
    byte r
    
    r = b1 + 0
    r = b1 - 0
    r = b1 + 1
    r = b1 - 1                 
    ptr1^ = r               ; 6: 1
    ptr1 = ptr1+1

    r = b1 * 5
    ptr1^ = r
    ptr1 = ptr1+1           ; 7: $3D

    r = b2 / 4              
    ptr1^ = r
    ptr1 = ptr1+1           ; 8: 2

    r = b2 / 3
    ptr1^ = r
    ptr1 = ptr1+1           ; 9: 3

    r = b2 % 7
    ptr1^ = r
    ptr1 = ptr1+1           ; $0a: 2

    r = b2 % 1
    ptr1^ = r
    ptr1 = ptr1+1           ; $0b 9

end


proc math3(byte b1, byte b2)    ; $fa02, $1209
    word r
    
    r = b1 + 0
    r = b1 - 0
    r = b1 + 1
    r = b1 - 1                 
    ptr2^ = r               ; $10: 1
    ptr2 = ptr2+1

    r = b1 * 5
    ptr2^ = r
    ptr2 = ptr2+1           ; $12: $3D

    r = b2 / 4              
    ptr2^ = r
    ptr2 = ptr2+1           ; $14: 2

    r = b2 / 3
    ptr2^ = r
    ptr2 = ptr2+1           ; $16: 3

    r = b2 % 7
    ptr2^ = r
    ptr2 = ptr2+1           ; $18: 2

    r = b2 % 1
    ptr2^ = r
    ptr2 = ptr2+1           ; $1a: 9

end


proc math4(byte b1, byte b2)    ; $fa02, $1209
    word r
    
    r = b1 + 0
    r = b1 - 0
    r = b1 + 1
    r = b1 - 1                 
    ptr2^ = r               ; $1c: $fa01
    ptr2 = ptr2+1

    r = b1 * 5
    ptr2^ = r
    ptr2 = ptr2+1           ; $1e: $0004 e20A

    r = b2 / 4              
    ptr2^ = r
    ptr2 = ptr2+1           ; $20: $0482

    r = b2 / 3
    ptr2^ = r
    ptr2 = ptr2+1           ; $22: $0603

    r = b2 % $0309
    ptr2^ = r
    ptr2 = ptr2+1           ; $24: $02dc

    r = b2 % 1
    ptr2^ = r
    ptr2 = ptr2+1           ; $26: $1209

end


; main -----------------------------------------
proc main()
    math1(2, 9)    
    math2($fa02, $1209)
    math3(2, 9)
    math4($fa02, $1209)    
end

