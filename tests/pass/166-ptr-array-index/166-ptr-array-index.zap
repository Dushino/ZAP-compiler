; GAP-24: Pointer dereferencing via array index for all types
;
; Checks pointer arithmetic (ptr = @arr, ptr += N) and address-of-element
; syntax (@arr[N]) for BYTE, WORD, LONG, STRUCT, and ENUM (word) types.
;
; Checks (bit N set = check N+1 passed):
;   bit 0: LONG ptr += 2  → larr[2]
;   bit 1: STRUCT ptr += 1 → sarr[1].x + sarr[1].y
;   bit 2: STRUCT ptr += 2 → sarr[2].x
;   bit 3: ENUM (word) ptr += 1 → earr[1] (200)
;   bit 4: @barr[2]  → barr[2] = $CC
;   bit 5: @warr[2]  → warr[2] = $3333
;   bit 6: @larr[2]  → larr[2] = $33333333
;   bit 7: @sarr[1]  → sarr[1].y = 4
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
word  earr[3] = {100, 200, 300}             ; ENUM values stored as WORD

proc main()
    byte  ^bptr
    word  ^wptr
    long  ^lptr
    MyPt  ^sptr
    byte  tmp

    ; --- bit 0: LONG ptr += 2 → larr[2] = $33333333 ---
    lptr = @larr
    lptr += 2
    if lptr^ == $33333333
        result = result | 1
    end

    ; --- bit 1: STRUCT ptr += 1 → sarr[1].x=3, sarr[1].y=4, sum=7 ---
    sptr = @sarr
    sptr += 1
    tmp = sptr^.x + sptr^.y
    if tmp == 7
        result = result | 2
    end

    ; --- bit 2: STRUCT ptr += 2 → sarr[2].x = 5 ---
    sptr = @sarr
    sptr += 2
    if sptr^.x == 5
        result = result | 4
    end

    ; --- bit 3: ENUM (word) ptr += 1 → earr[1] = 200 ---
    wptr = @earr
    wptr += 1
    if wptr^ == 200
        result = result | 8
    end

    ; --- bit 4: @barr[2] → $CC ---
    bptr = @barr[2]
    if bptr^ == $CC
        result = result | 16
    end

    ; --- bit 5: @warr[2] → $3333 ---
    wptr = @warr[2]
    if wptr^ == $3333
        result = result | 32
    end

    ; --- bit 6: @larr[2] → $33333333 ---
    lptr = @larr[2]
    if lptr^ == $33333333
        result = result | 64
    end

    ; --- bit 7: @sarr[1] → sarr[1].y = 4 ---
    sptr = @sarr[1]
    if sptr^.y == 4
        result = result | 128
    end
end
