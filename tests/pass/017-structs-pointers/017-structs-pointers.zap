struct Point
    byte x
    byte y
end

byte result @40000 = 0

proc main()
    Point p
    Point ^pp

    pp = @p
    pp^.x = 3
    pp^.y = 4

    result = p.x + p.y
end
