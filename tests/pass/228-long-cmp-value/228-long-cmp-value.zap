; Regression test: LONG comparison used as a value (flag = long_a op long_b).
; Previously _gen_relational had no 32-bit path — used 8-bit CMP, giving wrong results.
;
; Checks:
;   1: flag = (65536L == 65536L)  → 1
;   2: flag = (65536L == 65537L)  → 0
;   3: flag = (65536L != 65537L)  → 1
;   4: flag = (65537L > 65536L)   → 1
;   5: flag = (65536L < 65537L)   → 1
;   6: flag = ($FF000000 == $FF000000)  → 1 (upper-byte test, was broken with 8-bit CMP)
;   7: flag = ($FF000000 != $FE000000)  → 1
;
; result @$0200 — expected = 7

byte result @$0200 = 0

proc main()
    long a
    long b
    byte flag

    ; 1: equal
    a = 65536
    b = 65536
    flag = (a == b)
    if flag == 1
        result = result + 1
    end

    ; 2: not equal
    a = 65536
    b = 65537
    flag = (a == b)
    if flag == 0
        result = result + 1
    end

    ; 3: !=
    flag = (a != b)
    if flag == 1
        result = result + 1
    end

    ; 4: >
    flag = (b > a)
    if flag == 1
        result = result + 1
    end

    ; 5: <
    flag = (a < b)
    if flag == 1
        result = result + 1
    end

    ; 6: upper-byte equality — was broken before fix
    a = $FF000000
    b = $FF000000
    flag = (a == b)
    if flag == 1
        result = result + 1
    end

    ; 7: upper-byte inequality
    a = $FF000000
    b = $FE000000
    flag = (a != b)
    if flag == 1
        result = result + 1
    end
end
