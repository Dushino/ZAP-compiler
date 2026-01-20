struct Point
    byte x
    byte y
end

byte result @40000 = 0

proc main()
    Point p
    p.x = 25
    p.y = 75
    result = p.x
end
