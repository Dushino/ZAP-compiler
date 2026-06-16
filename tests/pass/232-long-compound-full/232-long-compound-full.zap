; Regression test: LONG compound assignment operators *=, /=, %=, &=, |=, ^=.
; (+=, -= already covered by test 140)
;
; Checks:
;   1: l *= 2     — 1000 * 2 = 2000
;   2: l /= 4     — 2000 / 4 = 500
;   3: l %= 300   — 500 % 300 = 200
;   4: l &= $FF   — 200 & $FF = 200 ($C8)
;   5: l |= $100  — $C8 | $100 = $1C8
;   6: l ^= $FF   — $1C8 ^ $FF = $137
;
; result @$0200 — expected = 6

byte result @$0200 = 0

proc main()
    long l = 1000

    ; 1
    l *= 2
    if l == 2000
        result = result + 1
    end

    ; 2
    l /= 4
    if l == 500
        result = result + 1
    end

    ; 3
    l %= 300
    if l == 200
        result = result + 1
    end

    ; 4
    l &= $FF
    if l == $C8
        result = result + 1
    end

    ; 5
    l |= $100
    if l == $1C8
        result = result + 1
    end

    ; 6
    l ^= $FF
    if l == $137
        result = result + 1
    end
end
