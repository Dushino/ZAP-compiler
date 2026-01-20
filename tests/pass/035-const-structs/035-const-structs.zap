struct Point
    byte x
    byte y
end

const Point ORIG = {1, 2}
byte result @40000 = 0

proc main()
    Point p = ORIG
    result = p.x + p.y
end
