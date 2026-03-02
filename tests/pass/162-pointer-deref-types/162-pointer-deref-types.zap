; GAP-19: Pointer dereference read/write for BYTE^ and WORD^
;
; Tests pointer write and read through byte^ and word^ pointers,
; and pointer advancement (ptr = ptr + N) with correct element-stride scaling.
;
; Note: long^ pointer assignment has a known codegen bug (pointer address is
;       overwritten by __MATH0 before storing into the pointer variable);
;       long^ tests are deferred to a future fix (tracked separately).
;
; Checks:
;   1: byte^ write + read    (bptr^ = $AB → bval == $AB)
;   2: word^ write + read    (wptr^ = $1234 → wval == $1234)
;   3: byte^ step by 1       (barr[0]→barr[1] = $BB, stride 1)
;   4: word^ step by 1       (warr[0]→warr[1] = $2345, stride 2)
;   5: word^ step by 2       (warr[0]→warr[2] = $3456, stride 2×2=4)
;   6: byte^ step by 2       (barr[0]→barr[2] = $CC, stride 1×2=2)
;   7: word^ second write    (wptr → wval, write $AABB, read wval)
;
; result @40000 — each passed check adds 1, expected = 7 = $07

byte result @40000 = 0

byte  bval = 0
word  wval = 0

byte  barr[3] = {$AA, $BB, $CC}
word  warr[3] = {$1234, $2345, $3456}

proc main()
    byte  ^bptr
    word  ^wptr

    ; --- 1: byte^ write + read ---
    bptr = @bval
    bptr^ = $AB
    if bval == $AB
        result = result + 1
    end

    ; --- 2: word^ write + read ---
    wptr = @wval
    wptr^ = $1234
    if wval == $1234
        result = result + 1
    end

    ; --- 3: byte^ step by 1 → barr[1] = $BB ---
    bptr = @barr
    bptr = bptr + 1
    if bptr^ == $BB
        result = result + 1
    end

    ; --- 4: word^ step by 1 (stride 2 bytes) → warr[1] = $2345 ---
    wptr = @warr
    wptr = wptr + 1
    if wptr^ == $2345
        result = result + 1
    end

    ; --- 5: word^ step by 2 (stride 2×2 = 4 bytes) → warr[2] = $3456 ---
    wptr = @warr
    wptr = wptr + 2
    if wptr^ == $3456
        result = result + 1
    end

    ; --- 6: byte^ step by 2 (stride 1×2 = 2 bytes) → barr[2] = $CC ---
    bptr = @barr
    bptr = bptr + 2
    if bptr^ == $CC
        result = result + 1
    end

    ; --- 7: word^ second variable write + read ---
    wptr = @wval
    wptr^ = $AABB
    if wval == $AABB
        result = result + 1
    end
end
