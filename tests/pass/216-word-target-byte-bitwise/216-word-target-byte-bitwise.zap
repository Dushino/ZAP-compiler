; Regression test: word target widens byte & byte, byte | byte, byte ^ byte to 16-bit.
; a=$FF, b=$FF -> AND=$00FF, OR=$00FF, XOR=$0000.
; Without widening the high byte stays $00 but the 16-bit result is checked explicitly.

byte result_and_lo @$0200
byte result_and_hi @$0201
byte result_or_lo  @$0202
byte result_or_hi  @$0203
byte result_xor_lo @$0204
byte result_xor_hi @$0205

proc main()
    byte a
    byte b
    word w
    a = $FF
    b = $FF
    w = a & b
    result_and_lo = low(w)
    result_and_hi = high(w)

    w = a | b
    result_or_lo = low(w)
    result_or_hi = high(w)

    w = a ^ b
    result_xor_lo = low(w)
    result_xor_hi = high(w)
end
