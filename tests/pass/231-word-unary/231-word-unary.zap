; Regression test: WORD unary negation and bitwise NOT.
;
; Checks:
;   1: -100w == $FF9C  (2's complement of 100 in 16 bits)
;   2: -1w == $FFFF
;   3: -0w == 0
;   4: ~$1234 == $EDCB
;   5: x + (-x) == 0  (negation roundtrip)
;
; result @$0200 — expected = 5

byte result @$0200 = 0

proc main()
    word x
    word y

    ; 1: -100
    x = 100
    y = -x
    if y == $FF9C
        result = result + 1
    end

    ; 2: -1
    x = 1
    y = -x
    if y == $FFFF
        result = result + 1
    end

    ; 3: -0
    x = 0
    y = -x
    if y == 0
        result = result + 1
    end

    ; 4: bitwise NOT
    x = $1234
    y = ~x
    if y == $EDCB
        result = result + 1
    end

    ; 5: x + (-x) == 0
    x = $ABCD
    y = x + (-x)
    if y == 0
        result = result + 1
    end
end
