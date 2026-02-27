; Test suite for code-generation optimisations:
;   1. Grouped STA by value for LONG/WORD constants (gen_init and gen_assign paths)
;   2. Direct 32-bit comparison without MATH0/MATH1 spill (all 6 operators)
;   3. SWITCH direct compare from source variable (no temp copy) for BYTE/WORD/LONG
;   4. LONG FOR-loop bound check via direct 32-bit comparison
;
; Each successful check increments `result`.  Expected final value: 18 ($12).

byte result @40000 = 0

proc main()
    ; All declarations first (ZAP requires this)

    ; Grouped STA test values - init with repeated-byte patterns
    long la = $01010101     ; 16843009: all bytes $01, so 1 LDA + 4 STA
    long lb = 65536         ; $00010000: groups {$00:[0,1,3], $01:[2]} -> 2 LDA
    long lc = $01000001     ; 16777217: groups {$01:[0,3], $00:[1,2]} -> 2 LDA
    word wa = $0303         ; lo==hi -> 1 LDA + 2 STA

    ; Direct 32-bit comparison operands
    long x = 100            ; $00000064
    long y = 200            ; $000000C8

    ; SWITCH direct compare targets
    byte bsw = 7
    word wsw = $0303
    long lsw = $01000001

    ; FOR loop variables
    long cnt = 0
    long s = 65536          ; $00010000
    long e = 65540          ; $00010004

    ; -----------------------------------------------------------------------
    ; 1. Grouped STA - LONG/WORD gen_init: verify correct values were stored

    if la == $01010101
        result = result + 1     ; 1
    end
    if lb == 65536
        result = result + 1     ; 2
    end
    if lc == $01000001
        result = result + 1     ; 3
    end
    if wa == $0303
        result = result + 1     ; 4
    end

    ; -----------------------------------------------------------------------
    ; 2. Direct 32-bit comparison - all 6 operators

    if x < y                ; 100 < 200 -> true
        result = result + 1 ; 5
    end
    if y > x                ; 200 > 100 -> true
        result = result + 1 ; 6
    end
    if x <= 100             ; 100 <= 100 -> true
        result = result + 1 ; 7
    end
    if x >= 100             ; 100 >= 100 -> true
        result = result + 1 ; 8
    end
    if x == 100             ; 100 == 100 -> true
        result = result + 1 ; 9
    end
    if y != 100             ; 200 != 100 -> true
        result = result + 1 ; 10
    end

    ; Identifier vs identifier
    if lb < la              ; 65536 < 16843009 -> true
        result = result + 1 ; 11
    end
    if lc == lb             ; 16777217 == 65536 -> false, skip
        result = 255
    end
    if lc > lb              ; 16777217 > 65536 -> true
        result = result + 1 ; 12
    end

    ; -----------------------------------------------------------------------
    ; 3. SWITCH direct compare (no temp copy) for BYTE, WORD, LONG

    switch bsw
        case 7
            result = result + 1 ; 13
            break
        default
            result = 255
    end

    switch wsw
        case $0303
            result = result + 1 ; 14
            break
        default
            result = 255
    end

    switch lsw
        case $01000001
            result = result + 1 ; 15
            break
        default
            result = 255
    end

    ; -----------------------------------------------------------------------
    ; 4. Grouped STA - LONG gen_assign (runtime assignments)

    la = $01010101          ; runtime: 1 LDA #$01 + 4 STA
    if la == $01010101
        result = result + 1 ; 16
    end

    la = 65536              ; runtime: grouped $00 and $01
    if la == 65536
        result = result + 1 ; 17
    end

    ; -----------------------------------------------------------------------
    ; 5. LONG FOR-loop: direct 32-bit comparison in loop condition
    ;    s=65536 to 65540 exclusive -> 4 iterations

    for s = s to e step 1
        cnt = cnt + 1
    end
    if cnt == 4
        result = result + 1 ; 18
    end

end
