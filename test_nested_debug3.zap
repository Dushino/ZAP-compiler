; Debug: Chained field access

struct Point
    byte X
    byte Y
end

struct Container
    Point p
    byte flag
end

Container c1 @40000

proc main()
    c1.p.x = 1
end
