; Test comprehensive enum operations

enum byte State
    INIT = 5
    START = 10
    RUNNING = 15
    STOPPED = 20
end

enum word BigState
    IDLE = 1000
    ACTIVE = 2000
    DONE = 3000
end

proc main()
    ; Byte enum arithmetic
    byte a1 = State.INIT + 5        ; 10
    byte a2 = State.RUNNING - 5     ; 10
    byte a3 = State.START * 2       ; 20
    byte a4 = State.STOPPED / 2     ; 10
    
    ; Word enum arithmetic
    word w1 = BigState.IDLE + 500   ; 1500
    word w2 = BigState.DONE - 1000  ; 2000
    
    ; Logical & Bitwise
    byte b1 = State.START & 15      ; 10 & 15 = 10
    byte b2 = State.INIT | 2        ; 5 | 2 = 7
    byte b3 = ~State.INIT           ; ~5 (bitwise not)
    
    ; Comparison
    byte c1 = State.START < State.RUNNING   ; true (1)
    byte c2 = State.STOPPED > State.START   ; true (1)
    byte c3 = State.INIT == 5               ; true (1)
    byte c4 = BigState.ACTIVE >= 2000       ; true (1)
    byte c5 = BigState.IDLE <= 500          ; false (0)
    byte c6 = State.START != 10             ; false (0)
    
    ; Other operators: modulo, shifts, xor, logical
    byte z1 = State.RUNNING % 6     ; 15 % 6 = 3
    byte z2 = State.INIT ^ 3        ; 5 ^ 3 = 6
    byte z3 = State.INIT << 1       ; 5 << 1 = 10
    byte z4 = State.STOPPED >> 1    ; 20 >> 1 = 10
    byte z5 = (State.INIT == 5) && (State.START == 10)  ; 1 && 1 = 1
    byte z6 = (State.INIT == 0) || (State.START == 10)  ; 0 || 1 = 1
    byte z7 = !(State.INIT == 0)    ; !0 = 1
    
    ; Use them to avoid dead code elimination
    a1 = a1 + a2 + a3 + a4
    w1 = w1 + w2
    b1 = b1 + b2 + b3
    c1 = c1 + c2 + c3 + c4 + c5 + c6
    z1 = z1 + z2 + z3 + z4 + z5 + z6 + z7
end
