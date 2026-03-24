byte result @$9C40 = 0

struct MyPt
    byte x
    byte y
end

byte  barr[3] = {$AA, $BB, $CC}
MyPt  sarr[3] = {{1, 2}, {3, 4}, {5, 6}}

proc main()
    byte  ^bptr
    MyPt  ^sptr
    bptr = @barr
    sptr = @sarr

    ; --- bit 6: STRUCT write via (sptr + 1)^.x = 99 ---
    (sptr + 1)^.x = 99
    if sarr[1].x == 99
        result = result | 64
    end

    ; --- bit 7: compound (bptr + 1)^ += 1 ---
    (bptr + 1)^ += 1
    if barr[1] == $BC
        result = result | 128
    end
end
