; Test that fixed-address (hardware) variables are never optimized
; All reads/writes must be preserved as they may have side effects

; Simulated hardware registers at fixed addresses
byte PORTA @$D300        ; Atari PIA port A
byte PORTB @$D301        ; Atari PIA port B
byte RANDOM @$D20A       ; Atari POKEY random register
word DLISTL @$D402       ; Atari ANTIC display list pointer

byte normalVar           ; Normal variable (can be optimized)

proc main()
    ; Test 1: Duplicate stores to hardware (must NOT be optimized)
    PORTA = 0
    PORTA = 1            ; Both writes must happen (clearing then setting bits)
    
    ; Test 2: Store then load from hardware (must NOT be optimized)
    PORTB = 5
    normalVar = PORTB    ; Read may return different value (status register)
    
    ; Test 3: Multiple reads from hardware (must NOT be optimized)
    normalVar = RANDOM
    normalVar = RANDOM
    normalVar = RANDOM   ; Each read gets new random value
    
    ; Test 4: Word-sized hardware register
    DLISTL = $4000
    DLISTL = $5000       ; Both writes must occur
    
    ; Test 5: Normal variable optimization should still work
    normalVar = 10
    normalVar = 20       ; This can be optimized to single write
end

