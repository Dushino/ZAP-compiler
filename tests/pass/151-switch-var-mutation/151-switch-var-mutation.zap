; Test 151: SWITCH expression variable mutated inside case body
; Verifies that modifying the switch variable inside a case branch does NOT
; cause a different case to execute on re-evaluation, because:
;   - The dispatch table is evaluated once before any case body runs.
;   - After a match is found, subsequent dispatch comparisons are never reached.
;   - BREAK exits the switch; fall-through is purely sequential code flow.
;
; Checks (result +1 each):
;  1.  byte: case 1 modifies var to 2, break → case 2 body NOT reached
;  2.  byte: case 1 modifies var to 2, fall-through → case 2 body IS reached
;            (reached via sequential fall-through, NOT because var == 2)
;  3.  byte: variable value modified inside case is retained after switch ends
;  4.  word: case 100 modifies wval to 200, break → case 200 body NOT reached
;  5.  word: case 100 modifies wval to 200, fall-through → case 200 body IS reached
;  6.  word: variable value modified inside case is retained after switch ends
;
; Expected result: 6 = $06

byte result @40000 = 0

proc main()
    byte bval
    byte hit
    byte cnt
    word wval

    ; --- 1: byte, modify var in case 1, break → case 2 NOT reached ---
    bval = 1
    hit = 0
    switch bval
        case 1
            bval = 2        ; dispatch already matched case 1; changing bval has no effect
            break
        case 2
            hit = 1         ; should NOT execute despite bval now = 2
            break
    end
    if hit == 0
        result = result + 1     ; 1
    end

    ; --- 2: byte, modify var in case 1, fall-through → case 2 IS reached ---
    bval = 1
    cnt = 0
    switch bval
        case 1
            bval = 2        ; changes bval, then falls through (no break)
            cnt = cnt + 1   ; cnt = 1
        case 2
            cnt = cnt + 1   ; cnt = 2 — reached by FALL-THROUGH, not by dispatch
            break
    end
    if cnt == 2
        result = result + 1     ; 2
    end

    ; --- 3: byte, modified value retained after switch ---
    bval = 1
    switch bval
        case 1
            bval = 99
            break
    end
    if bval == 99
        result = result + 1     ; 3
    end

    ; --- 4: word, modify wval in case 100, break → case 200 NOT reached ---
    wval = 100
    hit = 0
    switch wval
        case 100
            wval = 200      ; dispatch already matched case 100
            break
        case 200
            hit = 1         ; should NOT execute
            break
    end
    if hit == 0
        result = result + 1     ; 4
    end

    ; --- 5: word, modify wval in case 100, fall-through → case 200 IS reached ---
    wval = 100
    cnt = 0
    switch wval
        case 100
            wval = 200
            cnt = cnt + 1   ; cnt = 1
        case 200
            cnt = cnt + 1   ; cnt = 2 — reached by FALL-THROUGH
            break
    end
    if cnt == 2
        result = result + 1     ; 5
    end

    ; --- 6: word, modified value retained after switch ---
    wval = 100
    switch wval
        case 100
            wval = 9999
            break
    end
    if wval == 9999
        result = result + 1     ; 6
    end
end
