; GAP-25: (pointer + N)^ = value syntax
;
; Tests parenthesized pointer expression dereference assignment
; for BYTE, WORD, LONG types and struct field access.
; Verifies correct stride scaling for each pointer type.
;
; Checks (bit N set = check N+1 passed):
;   bit 0: BYTE  (bptr + 2)^ = $EE   → barr[2] == $EE (stride 1)
;   bit 1: WORD  (wptr + 1)^ = $ABCD → warr[1] == $ABCD (stride 2)
;   bit 2: LONG  (lptr + 1)^ = $DEADBEEF → larr[1] == $DEADBEEF (stride 4)
;   bit 3: BYTE  read (bptr + 1)^    → reads barr[1] == $BB
;   bit 4: WORD  read (wptr + 2)^    → reads warr[2] == $3333
;   bit 5: LONG  read (lptr + 2)^    → reads larr[2] == $33333333
;   bit 6: STRUCT (sptr + 1)^.x      → write sarr[1].x = 99
;   bit 7: compound (bptr + 1)^ += 1 → barr[1] == $BC (was $BB + 1)
;
; Expected result @$9C40: $FF

byte result @$9C40 = 0

struct MyPt
    byte x
    byte y
end

byte  barr[3] = {$AA, $BB, $CC}
word  warr[3] = {$1111, $2222, $3333}
long  larr[3] = {$11111111, $22222222, $33333333}
MyPt  sarr[3] = {{1, 2}, {3, 4}, {5, 6}}

proc main()
    byte  ^bptr
    word  ^wptr
    long  ^lptr
    MyPt  ^sptr

    bptr = @barr
    wptr = @warr
    lptr = @larr
    sptr = @sarr

    ; --- bit 0: BYTE write via (bptr + 2)^ = $EE ---
    (bptr + 2)^ = $EE
    if barr[2] == $EE
        result = result | 1
    end

    ; --- bit 1: WORD write via (wptr + 1)^ = $ABCD ---
    (wptr + 1)^ = $ABCD
    if warr[1] == $ABCD
        result = result | 2
    end

    ; --- bit 2: LONG write via (lptr + 1)^ = $DEADBEEF (stride 4) ---
    (lptr + 1)^ = $DEADBEEF
    if larr[1] == $DEADBEEF
        result = result | 4
    end

    ; --- bit 3: BYTE read via (bptr + 1)^ ---
    if (bptr + 1)^ == $BB
        result = result | 8
    end

    ; --- bit 4: WORD read via (wptr + 2)^ ---
    if (wptr + 2)^ == $3333
        result = result | 16
    end

    ; --- bit 5: LONG read via (lptr + 2)^ ---
    if (lptr + 2)^ == $33333333
        result = result | 32
    end

    ; --- bit 6: STRUCT write via (sptr + 1)^.x = 99 ---
    (sptr + 1)^.x = 99
    if sarr[1].x == 99
        result = result | 64
    end

    ; --- bit 7: compound assignment (bptr + 1)^ += 1 ---
    (bptr + 1)^ += 1
    if barr[1] == $BC
        result = result | 128
    end
end
