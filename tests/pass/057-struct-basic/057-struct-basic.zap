struct Point
    byte x
    byte y
end

byte result @40000 = 0

proc main()
    Point p
    p.x = 75
    p.y = 25
    result = p.y
end
