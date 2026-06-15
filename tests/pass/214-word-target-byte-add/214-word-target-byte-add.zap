; Regression test: word target widens byte+byte addition to 16-bit.
; byte_a=200, byte_b=100 -> word result = 300 = $012C.
; Without widening the sum overflows to $2C (8-bit truncation).

byte result_lo @$0200
byte result_hi @$0201

proc main()
    byte a
    byte b
    word w
    a = 200
    b = 100
    w = a + b       ; WORD target -> 16-bit ADD -> 300 = $012C
    result_lo = low(w)
    result_hi = high(w)
end
