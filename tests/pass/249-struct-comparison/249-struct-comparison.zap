; Test: == and != on structs of same size.
; Expected result: 1+10+100 = 111 (0x6F)

struct Point
    byte x
    byte y
end

struct Vec2
    byte dx
    byte dy
end

byte result @40000 = 0

proc main()
    Point a
    Point b
    Vec2 v

    a.x = 3
    a.y = 7
    b.x = 3
    b.y = 7

    ; Same contents: equal
    if a == b
        result = result + 1
    end

    ; Modify b: no longer equal
    b.y = 99
    if a != b
        result = result + 10
    end

    ; Different struct type, same size (both 2 bytes): raw bytes match
    v.dx = 3
    v.dy = 7
    if a == v
        result = result + 100
    end
end
