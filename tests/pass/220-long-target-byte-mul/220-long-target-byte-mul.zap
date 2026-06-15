; Regression test: LONG target widens byte operands to 32-bit MUL/DIV/MOD.
; Without widening: byte 200 * byte 200 = 8-bit overflow.
; With LONG widening: MUL32 gives 40000 = $00009C40.
;
; Each passed check increments result; expected = 3.

byte result @$0200 = 0

proc main()
    byte aa
    byte bb
    long ll

    ; 1: MUL 200*200 = 40000 (overflows 8-bit)
    aa = 200
    bb = 200
    ll = aa * bb
    if ll == 40000
        result = result + 1
    end

    ; 2: DIV 200/5 = 40
    aa = 200
    bb = 5
    ll = aa / bb
    if ll == 40
        result = result + 1
    end

    ; 3: MOD 200/7 = 4 remainder
    aa = 200
    bb = 7
    ll = aa % bb
    if ll == 4
        result = result + 1
    end
end
