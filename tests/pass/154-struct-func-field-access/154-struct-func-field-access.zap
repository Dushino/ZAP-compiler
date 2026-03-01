; Test 154: Struct-returning function + field access on result — GAP-10
; Verifies `myfunc().field` syntax: reading a scalar field from a struct
; returned by a function call, both as a standalone expression and as the
; RHS of a struct field assignment.
;
; struct Vec  { byte x, byte y }  (2 bytes, offsets 0 and 1)
; struct WVec { word wx, word wy } (4 bytes, offsets 0 and 2)
;
; Checks (result +1 each):
;  1. byte bx = make_vec(10, 20).x          → bx == 10  (byte field, offset 0)
;  2. byte by = make_vec(10, 20).y          → by == 20  (byte field, offset 1)
;  3. v.x = make_vec(3, 4).x               → v.x == 3  (assign struct.field from call.field)
;  4. v.y = make_vec(3, 4).y               → v.y == 4
;  5. word wx = make_wvec(100, 200).wx      → wx == 100 (word field, offset 0)
;  6. word wy = make_wvec(100, 200).wy      → wy == 200 (word field, offset 2)
;  7. w.wx = make_wvec(50, 60).wx           → w.wx == 50
;  8. w.wy = make_wvec(50, 60).wy           → w.wy == 60
;  9. Vec tmp = make_vec(5, 6)  → tmp.x == 5  (declaration with call initializer)
; 10. tmp.y == 6
; 11. WVec wtmp = make_wvec(300, 400) → wtmp.wx == 300
; 12. wtmp.wy == 400
;
; Expected result: 12 = $0C

byte result @40000 = 0

struct Vec
    byte x
    byte y
end

struct WVec
    word wx
    word wy
end

func Vec make_vec(byte a, byte b)
    Vec v
    v.x = a
    v.y = b
    return v
end

func WVec make_wvec(word a, word b)
    WVec w
    w.wx = a
    w.wy = b
    return w
end

proc main()
    byte bx
    byte by
    Vec v
    Vec tmp = make_vec(5, 6)        ; declaration with call initializer (checks 9-10)
    word wx
    word wy
    WVec w
    WVec wtmp = make_wvec(300, 400) ; declaration with call initializer (checks 11-12)

    ; --- 1,2: read byte fields from call result ---
    bx = make_vec(10, 20).x
    if bx == 10
        result = result + 1     ; 1
    end
    by = make_vec(10, 20).y
    if by == 20
        result = result + 1     ; 2
    end

    ; --- 3,4: assign struct field from call result field ---
    v.x = make_vec(3, 4).x
    if v.x == 3
        result = result + 1     ; 3
    end
    v.y = make_vec(3, 4).y
    if v.y == 4
        result = result + 1     ; 4
    end

    ; --- 5,6: read word fields from call result ---
    wx = make_wvec(100, 200).wx
    if wx == 100
        result = result + 1     ; 5
    end
    wy = make_wvec(100, 200).wy
    if wy == 200
        result = result + 1     ; 6
    end

    ; --- 7,8: assign word struct field from call result field ---
    w.wx = make_wvec(50, 60).wx
    if w.wx == 50
        result = result + 1     ; 7
    end
    w.wy = make_wvec(50, 60).wy
    if w.wy == 60
        result = result + 1     ; 8
    end

    ; --- 9,10: declaration with call initializer (Vec tmp = make_vec(5,6) at proc top) ---
    if tmp.x == 5
        result = result + 1     ; 9
    end
    if tmp.y == 6
        result = result + 1     ; 10
    end

    ; --- 11,12: declaration with call initializer (WVec wtmp = make_wvec(300,400) at proc top) ---
    if wtmp.wx == 300
        result = result + 1     ; 11
    end
    if wtmp.wy == 400
        result = result + 1     ; 12
    end
end
