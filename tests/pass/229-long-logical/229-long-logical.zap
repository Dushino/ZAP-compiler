; Regression test: LONG operands in logical && and || operators.
; Tests both RPN path (simple identifiers) and non-RPN path (complex operands).
;
; Checks (7 total, 6 pass):
;   1: a && a    — $10000 && $10000 == true   → +1
;   2: z && a    — 0 && $10000 == false       → else +1
;   3: a || z    — $10000 || 0 == true        → +1
;   4: z || z    — 0 || 0 == false            → else +1
;   5: larr[0] || larr[1]  — 0||$11111111    → +1 (non-RPN path)
;   6: larr[0] && larr[1]  — 0&&$11111111    → false, no increment
;   7: larr[1] && larr[1]  — nonzero&&nonzero → +1
;
; result @$0200 — expected = 6

byte result @$0200 = 0

long larr[2] = {0, $11111111}

proc main()
    long a = $10000
    long z = 0

    ; 1: non-zero && non-zero → true
    if a && a
        result = result + 1
    end

    ; 2: zero && non-zero → false → else
    if z && a
    else
        result = result + 1
    end

    ; 3: non-zero || zero → true
    if a || z
        result = result + 1
    end

    ; 4: zero || zero → false → else
    if z || z
    else
        result = result + 1
    end

    ; 5: non-RPN: 0 || $11111111 → true
    if larr[0] || larr[1]
        result = result + 1
    end

    ; 6: non-RPN: 0 && $11111111 → false, no increment

    ; 7: non-RPN: $11111111 && $11111111 → true
    if larr[1] && larr[1]
        result = result + 1
    end
end
