; Regression test: LONG logical && and || in while/repeat loop conditions.
; Tests the control-flow paths (not just if-statement).
;
; Checks:
;   1: while loop stops when LONG counter reaches 0 via &&
;   2: repeat-until exits when either condition becomes true via ||
;   3: LONG in for-loop condition (indirect: loop body conditional)
;   4: nested &&: (a && b) && c — all three LONG must be non-zero
;
; result @$0200 — expected = 4

byte result @$0200 = 0

proc main()
    long a
    long b
    long c
    byte count

    ; 1: while (a && b) — loop while both are non-zero
    a = 3
    b = 2
    count = 0
    while a && b
        a = a - 1
        b = b - 1
        count = count + 1
    end
    ; b reaches 0 first after 2 iterations
    if count == 2
        result = result + 1
    end

    ; 2: repeat-until with || exit condition
    a = 0
    b = 0
    count = 0
    repeat
        count = count + 1
        if count == 3
            b = 1
        end
    until a || b
    if count == 3
        result = result + 1
    end

    ; 3: LONG in loop body condition
    a = $10000
    c = 0
    b = 0
    while b < 3
        if a && a
            c = c + 1
        end
        b = b + 1
    end
    if c == 3
        result = result + 1
    end

    ; 4: nested: (a && b) && c
    a = 1
    b = $FFFF0000
    c = $12345678
    if (a && b) && c
        result = result + 1
    end
end
