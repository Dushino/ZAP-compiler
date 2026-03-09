; Return wrong struct type — must fail
struct Point
    byte x
    byte y
end

struct Vec
    word dx
    word dy
end

func Point bad()
    Vec v
    return v
end

proc main()
    Point p = bad()
end
