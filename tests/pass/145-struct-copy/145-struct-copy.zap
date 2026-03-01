; Test: struct copy — var→var, const→var, function return
;
; Struct Point has x:byte, y:byte (2 bytes total)
; Struct Rect  has x:byte, y:byte, w:byte, h:byte (4 bytes total)
;
; Checks (result +1 each):
;  1. const Point → var Point:        p2.x == 10
;  2. const Point → var Point:        p2.y == 20
;  3. var Point → var Point:          p3.x == 10
;  4. var Point → var Point:          p3.y == 20
;  5. func return → var Point:        p4.x == 100
;  6. func return → var Point:        p4.y == 200
;  7. const Rect → var Rect:          r2.x == 1
;  8. const Rect → var Rect:          r2.h == 4
;
; Expected result: 8 = $08

byte result @40000 = 0

struct Point
    byte x
    byte y
end

struct Rect
    byte x
    byte y
    byte w
    byte h
end

func Point make_point()
    Point result_val
    result_val.x = 100
    result_val.y = 200
    return result_val
end

proc main()
    const Point p1 = {10, 20}
    Point p2
    Point p3
    Point p4
    const Rect r1 = {1, 2, 3, 4}
    Rect r2

    ; --- 1-2: const → var copy ---
    p2 = p1
    if p2.x == 10
        result = result + 1     ; 1
    end
    if p2.y == 20
        result = result + 1     ; 2
    end

    ; --- 3-4: var → var copy ---
    p3 = p2
    if p3.x == 10
        result = result + 1     ; 3
    end
    if p3.y == 20
        result = result + 1     ; 4
    end

    ; --- 5-6: function return → var ---
    p4 = make_point()
    if p4.x == 100
        result = result + 1     ; 5
    end
    if p4.y == 200
        result = result + 1     ; 6
    end

    ; --- 7-8: const Rect → var Rect ---
    r2 = r1
    if r2.x == 1
        result = result + 1     ; 7
    end
    if r2.h == 4
        result = result + 1     ; 8
    end
end
