; Regression test: comparisons between different datatypes (cross-type).
; LONG vs BYTE, LONG vs WORD, WORD vs BYTE in if-conditions.
;
; Checks:
;   1: long 256 == word 256  → true
;   2: long 256 > byte 0     → true
;   3: long 256 != byte 0    → true
;   4: word 1000 > byte 200  → true
;   5: byte 100 < word 1000  → true
;   6: long $10000 > word $FFFF  → true
;   7: long 0 == byte 0      → true
;
; result @$0200 — expected = 7

byte result @$0200 = 0

proc main()
    long lv = 256
    word wv = 256
    byte bv = 0

    ; 1
    if lv == wv
        result = result + 1
    end

    ; 2
    if lv > bv
        result = result + 1
    end

    ; 3
    if lv != bv
        result = result + 1
    end

    ; 4
    wv = 1000
    bv = 200
    if wv > bv
        result = result + 1
    end

    ; 5
    if bv < wv
        result = result + 1
    end

    ; 6
    lv = $10000
    wv = $FFFF
    if lv > wv
        result = result + 1
    end

    ; 7
    lv = 0
    bv = 0
    if lv == bv
        result = result + 1
    end
end
