; Regression test: WORD compound assignment operators *=, /=, %=, &=, |=, ^=.
; (+=, -= already covered by test 140)
;
; Checks:
;   1: w *= 3     — 100 * 3 = 300
;   2: w /= 5     — 300 / 5 = 60
;   3: w %= 17    — 60 % 17 = 9
;   4: w &= $0F   — 9 & $0F = 9
;   5: w |= $F0   — 9 | $F0 = $F9
;   6: w ^= $FF   — $F9 ^ $FF = 6
;
; result @$0200 — expected = 6

byte result @$0200 = 0

proc main()
    word w = 100

    ; 1
    w *= 3
    if w == 300
        result = result + 1
    end

    ; 2
    w /= 5
    if w == 60
        result = result + 1
    end

    ; 3
    w %= 17
    if w == 9
        result = result + 1
    end

    ; 4
    w &= $0F
    if w == 9
        result = result + 1
    end

    ; 5
    w |= $F0
    if w == $F9
        result = result + 1
    end

    ; 6
    w ^= $FF
    if w == 6
        result = result + 1
    end
end
