; Fail test: array-of-struct assignment is not supported.
; The compiler must reject this with an error.

byte result @40000 = 0

struct Point
    byte x
    byte y
end

proc main()
    Point src[3]
    Point dst[3]
    dst = src
end
