; Return struct where byte expected — must fail
struct Point
    byte x
    byte y
end

func byte bad()
    Point p
    p.x = 1
    p.y = 2
    return p
end

proc main()
    byte r = bad()
end
