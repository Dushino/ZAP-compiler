; Regression test: word target widens byte*byte (non-power-of-2, runtime) to MUL16.
; a=200, b=200 -> word result = 40000 = $9C40.
; Without widening MUL8 returns $40 (low byte only).

byte result_lo @$0200
byte result_hi @$0201

proc main()
    byte a
    byte b
    word w
    a = 200
    b = 200
    w = a * b       ; WORD target -> MUL16 -> 40000 = $9C40
    result_lo = low(w)
    result_hi = high(w)
end
