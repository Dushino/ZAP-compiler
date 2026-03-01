; Test 148: expression evaluation consistency — GAP-05
; Verifies that the same expression produces correct results in every
; context the compiler evaluates it: assignment RHS, if/while condition,
; for bounds (start and end), func call argument, return expr, switch expr.
;
; Anchor values: val=7
;   val+5     = 12  (simple addition)
;   val*2-2   = 12  (compound: multiply then subtract)
;   val+5     = 12  (loop iterations: for i=0 to 12 → 12 runs)
;   val+5..val*3 = 12..21 → 9 iterations (for start and end bounds)
;
; Checks (result +1 each):
;  1.  Assignment RHS:      x = val+5; x==12
;  2.  If condition:        if val+5 == 12
;  3.  While condition:     while n < val+5; n==12 after loop
;  4.  For upper bound:     for i=0 to val+5; count==12 (12 iterations)
;  5.  For start+end bound: for i=val+5 to val*3; count==9 (i:12..20)
;  6.  Func call arg:       id(val+5)==12
;  7.  Return expr:         make_val() returns val+5 == 12
;  8.  Switch expr:         switch val+5; case 12: result++
;  9.  Compound if:         if val*2-2 == 12
; 10.  Compound assign:     x = val*2-2; x==12
; 11.  Compound func arg:   id(val*2-2)==12
; 12.  Compound switch:     switch val*2-2; case 12: result++
;
; Expected result: 12 = $0C

byte result @40000 = 0
byte val = 7

func byte id(byte x)
    return x
end

func byte make_val()
    return val + 5
end

proc main()
    byte x
    byte n
    byte i
    byte cnt

    ; --- 1: assignment RHS ---
    x = val + 5
    if x == 12
        result = result + 1     ; 1
    end

    ; --- 2: if condition ---
    if val + 5 == 12
        result = result + 1     ; 2
    end

    ; --- 3: while condition ---
    n = 0
    while n < val + 5
        n = n + 1
    end
    if n == 12
        result = result + 1     ; 3
    end

    ; --- 4: for upper bound (val+5=12 iterations) ---
    cnt = 0
    for i = 0 to val + 5
        cnt = cnt + 1
    end
    if cnt == 12
        result = result + 1     ; 4
    end

    ; --- 5: for start and end bounds (val+5=12 to val*3=21: 9 iterations) ---
    cnt = 0
    for i = val + 5 to val * 3
        cnt = cnt + 1
    end
    if cnt == 9
        result = result + 1     ; 5
    end

    ; --- 6: func call argument ---
    if id(val + 5) == 12
        result = result + 1     ; 6
    end

    ; --- 7: return expression ---
    if make_val() == 12
        result = result + 1     ; 7
    end

    ; --- 8: switch expression ---
    switch val + 5
        case 12
            result = result + 1     ; 8
            break
        default
            break
    end

    ; --- 9: compound expression in if ---
    if val * 2 - 2 == 12
        result = result + 1     ; 9
    end

    ; --- 10: compound expression in assignment ---
    x = val * 2 - 2
    if x == 12
        result = result + 1     ; 10
    end

    ; --- 11: compound expression as func arg ---
    if id(val * 2 - 2) == 12
        result = result + 1     ; 11
    end

    ; --- 12: compound expression in switch ---
    switch val * 2 - 2
        case 12
            result = result + 1     ; 12
            break
        default
            break
    end
end
