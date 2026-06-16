; Regression test: LONG unary negation (-long_var).
; Tests that NEG32 routine is emitted and works correctly.
;
; Checks:
;   1: -0L == 0
;   2: -10L has low byte $F6 (i.e. $FFFFFFF6 & $FF)
;   3: double negation: -(-1L) == 1
;   4: negation in expression: 0L - x == -x (verify via addition)
;
; result @$0200 — each passed check adds 1, expected = 4

byte result @$0200 = 0

proc main()
    long x
    long y

    ; 1: -0 == 0
    x = 0
    y = -x
    if y == 0
        result = result + 1
    end

    ; 2: -10 == $FFFFFFF6
    x = 10
    y = -x
    if y == $FFFFFFF6
        result = result + 1
    end

    ; 3: -(-1) == 1
    x = $FFFFFFFF
    y = -x
    if y == 1
        result = result + 1
    end

    ; 4: negation in arithmetic: x + (-x) == 0
    x = $12345678
    y = x + (-x)
    if y == 0
        result = result + 1
    end
end
