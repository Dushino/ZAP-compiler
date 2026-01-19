; struct test


struct Point
    byte X
    byte Y
    byte Z
end

Point p1 @40000

const byte len = 3
Point p2[3] @40016

proc main()
    byte i

    p1.x = 1
    p1.y = 2

    for i = 0 to 2
        p2[i].x = i*3        
        p2[i].y = i*3+1
        p2[i].z = i*3+2
    next i
end
