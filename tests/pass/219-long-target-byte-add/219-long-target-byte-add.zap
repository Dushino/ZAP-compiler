; Regression test: LONG target widens byte operands to 32-bit ADD/SUB.
; Without widening byte a=200 + byte b=200 would overflow to 144 ($90).
; With LONG widening, ADD32 gives 400 = $00000190.
;
; Each passed check increments result; expected = 4.

byte result @$0200 = 0

proc main()
    byte a
    byte b
    long l

    ; 1: ADD with overflow (200+200=400, not 144)
    a = 200
    b = 200
    l = a + b
    if l == 400
        result = result + 1
    end

    ; 2: ADD with carry into bit 8 (1+255=256)
    a = 1
    b = 255
    l = a + b
    if l == 256
        result = result + 1
    end

    ; 3: SUB no borrow
    a = 201
    b = 200
    l = a - b
    if l == 1
        result = result + 1
    end

    ; 4: ADD with const: 100+100+100 = 300
    a = 100
    b = 100
    l = a + b + 100
    if l == 300
        result = result + 1
    end
end
