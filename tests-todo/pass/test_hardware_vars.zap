; Test that fixed-address (hardware) variables are never optimized
; All reads/writes must be preserved as they may have side effects

; Simulated hardware registers at fixed addresses
byte PORTA @40000
byte PORTB @40002
word PORTC @40004
word PORTD @40006 = $6160

byte normalVarB         ; Normal variable (can be optimized)
word normalVarW         ; Normal variable (can be optimized)

proc main()
    ; Test 1: Duplicate stores to hardware (must NOT be optimized)
    PORTA = 1
    PORTA = 64      ; Both writes must happen (clearing then setting bits)
    
    ; Test 2: Store then load from hardware (must NOT be optimized)
    PORTA = 2
    normalVarB = PORTA
    PORTA = PORTA
    PORTB = PORTA
    
    ; Test 3: Multiple reads from hardware (must NOT be optimized)
    normalVarB = PORTA
    normalVarB = PORTA    

    ; Test 4: Word-sized hardware register
    PORTC = $3130
    PORTC = $3332

    normalVarW = PORTC
    normalVarW = PORTC
end

