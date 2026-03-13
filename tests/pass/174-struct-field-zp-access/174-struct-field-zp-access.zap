; Test 174: struct field access optimizations (Phase 1, 2, 3)
; Phase 1: LDY #field_offset + (TMP0),Y instead of ADC #offset + STA TMP0
; Phase 2: ZP pointer^.field uses (ptr),Y directly (no TMP0)
; Phase 3: consecutive array[same_idx].field accesses cache TMP0
;
; struct Point: byte x, byte y  (2 bytes)
; struct Rect: byte x0, y0, x1, y1  (4 bytes)
;
; Checks (result +1 each):
;  1.  pts[2].x = 10; pts[2].x == 10  (array field write+read, Phase 1)
;  2.  pts[2].y = 20; pts[2].y == 20  (same element, Phase 3 cache hit)
;  3.  pp = @pts[1]; pp^.x = 30; pp^.x == 30  (ptr-to-struct field, Phase 2 ZP)
;  4.  pp^.y = 40; pp^.y == 40  (same ptr, same struct, Phase 2 ZP)
;  5.  r.x0 = 5; r.y0 = 6; r.x1 = 7; r.y1 = 8; r.x0+r.y0+r.x1+r.y1 == 26 (direct struct)
;
; Expected result: 5 = $05

byte result @40000 = 0

struct Point
    byte x
    byte y
end

struct Rect
    byte x0
    byte y0
    byte x1
    byte y1
end

proc main()
    Point pts[4]
    Point ^pp
    Rect r

    ; --- 1-2: array[const-idx] Phase 1 and Phase 3 cache ---
    pts[2].x = 10
    pts[2].y = 20
    if pts[2].x == 10
        result = result + 1     ; 1
    end
    if pts[2].y == 20
        result = result + 1     ; 2
    end

    ; --- 3-4: pointer to struct, Phase 2 ZP pointer ---
    pp = @pts[1]
    pp^.x = 30
    pp^.y = 40
    if pp^.x == 30
        result = result + 1     ; 3
    end
    if pp^.y == 40
        result = result + 1     ; 4
    end

    ; --- 5: direct struct field access (Rect) ---
    r.x0 = 5
    r.y0 = 6
    r.x1 = 7
    r.y1 = 8
    if r.x0 + r.y0 + r.x1 + r.y1 == 26
        result = result + 1     ; 5
    end
end
