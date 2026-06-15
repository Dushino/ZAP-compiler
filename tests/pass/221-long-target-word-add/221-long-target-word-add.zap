; Regression test: LONG target widens WORD operands to 32-bit operations.
; Crossing the 16-bit boundary: $8000 + $8000 = $10000 (65536).
; Without 32-bit ADD the carry into bit 16 would be lost.
;
; Each passed check increments result; expected = 3.

byte result @$0200 = 0

proc main()
    word wa
    word wb
    long ll

    ; 1: ADD crossing 16-bit boundary: $8000 + $8000 = 65536 = $00010000
    wa = $8000
    wb = $8000
    ll = wa + wb
    if ll == 65536
        result = result + 1
    end

    ; 2: SUB with word operands: $C000 - $4000 = $8000 = 32768
    wa = $C000
    wb = $4000
    ll = wa - wb
    if ll == 32768
        result = result + 1
    end

    ; 3: MUL word*word: $100 * $100 = $10000 = 65536
    wa = $0100
    wb = $0100
    ll = wa * wb
    if ll == 65536
        result = result + 1
    end
end
