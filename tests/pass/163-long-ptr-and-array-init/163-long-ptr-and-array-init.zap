; GAP-19 bug fixes: long^ pointer and LONG array list-init
;
; Checks:
;   1: long^ assign + write + read ($11223344 round-trip)
;   2: long^ step by 1 (stride 4) → reads larr[1] = $AABBCCDD
;   3: LONG const array, 1 element inline init → larr1[0] = $12345678
;   4: LONG const array, 2 elements inline init → larr2[1] = $DEADBEEF
;   5: LONG const array, 3 elements (12 bytes → COPY_BYTES) → larr3[2] = $CAFEBABE
;   6: LONG const array, 10 elements (40 bytes → COPY_BYTES) → larr10[9] = 10
;   7: LONG non-const array, element from variable → larr_nc[0] = $BABE0001
;   8: LONG const array, 64 elements (256 bytes → COPY_BYTES16) → larr64[63] = 63
;
; result @40000 — each passed check adds 1, expected = 8 = $08

byte result @40000 = 0

long lval  = $11223344
long larr[2] = {$55667788, $AABBCCDD}

proc main()
    ; All declarations must come before executable statements
    long ^lptr
    long larr1[1] = {$12345678}
    long larr2[2] = {$11111111, $DEADBEEF}
    long larr3[3] = {$00000001, $00000002, $CAFEBABE}
    long larr10[10] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
    long lv2 = $BABE0001
    long larr_nc[2] = {lv2, 0}
    long larr64[64] = {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,
                       16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,
                       32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,
                       48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63}

    ; --- 1: long^ assign address, write $11223344, read back ---
    lptr = @lval
    lptr^ = $11223344
    if lval == $11223344
        result = result + 1
    end

    ; --- 2: long^ step by 1 (stride 4 bytes) → larr[1] = $AABBCCDD ---
    lptr = @larr
    lptr = lptr + 1
    if lptr^ == $AABBCCDD
        result = result + 1
    end

    ; --- 3: LONG const array, 1 element inline ---
    if larr1[0] == $12345678
        result = result + 1
    end

    ; --- 4: LONG const array, 2 elements inline ---
    if larr2[1] == $DEADBEEF
        result = result + 1
    end

    ; --- 5: LONG const array, 3 elements (12 bytes → COPY_BYTES) ---
    if larr3[2] == $CAFEBABE
        result = result + 1
    end

    ; --- 6: LONG const array, 10 elements (40 bytes → COPY_BYTES) ---
    if larr10[9] == 10
        result = result + 1
    end

    ; --- 7: LONG non-const array, element from variable ---
    if larr_nc[0] == $BABE0001
        result = result + 1
    end

    ; --- 8: LONG const array, 64 elements (256 bytes → COPY_BYTES16) ---
    if larr64[63] == 63
        result = result + 1
    end
end
