; struct test


struct Point
    byte X
    byte Y
    byte Z
end

struct str1
    Point pt
    byte another
end


Point p1 @40000
str1  xs @40032 = {{$11, $12, $13}, $f1}

const byte len = 3
Point p2[len] @40016 = {{1,2,3}, {4,5,6}, {7,8,9}}

proc main()
    byte i

    p1.x = 1
    p1.y = 2

    for i = 1 to len-1
        p2[i].x = i*3   + $10        
        p2[i].y = i*3+1 + $10         
        p2[i].z = i*3+2 + $10        
    next i
    xs.pt.y = $22
    xs.another = $24
end
