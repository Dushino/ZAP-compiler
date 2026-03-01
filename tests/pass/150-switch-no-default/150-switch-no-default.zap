; Test 150: SWITCH with no default clause — GAP-07
; Verifies that when no case matches and there is no default clause,
; execution falls through to the statement after the switch normally.
;
; Checks (result +1 each):
;  1.  byte switch, value matches case → body runs
;  2.  byte switch, no match, no default → body skipped, continues
;  3.  word switch, value matches case → body runs
;  4.  word switch, no match, no default → body skipped, continues
;  5.  long switch, value matches case → body runs
;  6.  long switch, no match, no default → body skipped, continues
;  7.  stacked cases (case A / case B), match A, no default → body runs
;  8.  stacked cases, match B, no default → body runs
;  9.  stacked cases, no match, no default → body skipped, continues
; 10.  fall-through (no break), match first case → both bodies execute (cnt=2)
; 11.  fall-through, match second case only → one body executes (cnt=1)
; 12.  fall-through, no match, no default → body completely skipped (cnt=0)
;
; Expected result: 12 = $0C

byte result @40000 = 0

proc main()
    byte bval
    byte hit
    word wval
    long lval
    byte cnt

    ; --- 1: byte switch, match, no default ---
    bval = 5
    hit = 0
    switch bval
        case 5
            hit = 1
            break
    end
    if hit == 1
        result = result + 1     ; 1
    end

    ; --- 2: byte switch, no match, no default → continues normally ---
    bval = 7
    hit = 0
    switch bval
        case 5
            hit = 1
            break
    end
    if hit == 0
        result = result + 1     ; 2
    end

    ; --- 3: word switch, match, no default ---
    wval = 1000
    hit = 0
    switch wval
        case 1000
            hit = 1
            break
    end
    if hit == 1
        result = result + 1     ; 3
    end

    ; --- 4: word switch, no match, no default ---
    wval = 999
    hit = 0
    switch wval
        case 1000
            hit = 1
            break
    end
    if hit == 0
        result = result + 1     ; 4
    end

    ; --- 5: long switch, match, no default ---
    lval = 131072
    hit = 0
    switch lval
        case 131072
            hit = 1
            break
    end
    if hit == 1
        result = result + 1     ; 5
    end

    ; --- 6: long switch, no match, no default ---
    lval = 131071
    hit = 0
    switch lval
        case 131072
            hit = 1
            break
    end
    if hit == 0
        result = result + 1     ; 6
    end

    ; --- 7: stacked cases, match first, no default ---
    bval = 10
    hit = 0
    switch bval
        case 10
        case 20
            hit = 1
            break
    end
    if hit == 1
        result = result + 1     ; 7
    end

    ; --- 8: stacked cases, match second, no default ---
    bval = 20
    hit = 0
    switch bval
        case 10
        case 20
            hit = 1
            break
    end
    if hit == 1
        result = result + 1     ; 8
    end

    ; --- 9: stacked cases, no match, no default ---
    bval = 30
    hit = 0
    switch bval
        case 10
        case 20
            hit = 1
            break
    end
    if hit == 0
        result = result + 1     ; 9
    end

    ; --- 10: fall-through, match first case → cnt = 2 (both bodies run) ---
    bval = 1
    cnt = 0
    switch bval
        case 1
            cnt = cnt + 1
        case 2
            cnt = cnt + 1
            break
    end
    if cnt == 2
        result = result + 1     ; 10
    end

    ; --- 11: fall-through, match second case only → cnt = 1 ---
    bval = 2
    cnt = 0
    switch bval
        case 1
            cnt = cnt + 1
        case 2
            cnt = cnt + 1
            break
    end
    if cnt == 1
        result = result + 1     ; 11
    end

    ; --- 12: fall-through, no match, no default → cnt = 0 ---
    bval = 3
    cnt = 0
    switch bval
        case 1
            cnt = cnt + 1
        case 2
            cnt = cnt + 1
            break
    end
    if cnt == 0
        result = result + 1     ; 12
    end
end
