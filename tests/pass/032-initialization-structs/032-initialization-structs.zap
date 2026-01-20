struct Point
    byte x
    byte y
end

byte result @40000 = 0

proc main()
    Point p = {10, 20}
    result = p.y
end
