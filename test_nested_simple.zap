; Simple nested struct test

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
    c1.p.y = 2
    c1.flag = 3
end
