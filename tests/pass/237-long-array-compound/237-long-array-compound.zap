; Regression test: Array[LONG] compound assignment (larr[i] += N, etc.).
;
; Checks:
;   1: larr[0] += 1000  — 0+1000 = 1000
;   2: larr[1] *= 2     — $11111111 * 2 = $22222222
;   3: larr[2] |= $F    — $33333333 | $F = $3333333F
;   4: larr[i] += 1 (i=0, from loop 3 times) — 1000+3 = 1003
;
; result @$0200 — expected = 4

byte result @$0200 = 0

long larr[3] = {0, $11111111, $33333333}

proc main()
    byte i

    ; 1
    larr[0] += 1000
    if larr[0] == 1000
        result = result + 1
    end

    ; 2
    larr[1] *= 2
    if larr[1] == $22222222
        result = result + 1
    end

    ; 3
    larr[2] |= $F
    if larr[2] == $3333333F
        result = result + 1
    end

    ; 4: loop compound
    i = 0
    while i < 3
        larr[0] += 1
        i = i + 1
    end
    if larr[0] == 1003
        result = result + 1
    end
end
