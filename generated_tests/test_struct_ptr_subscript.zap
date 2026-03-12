struct Point
    byte x
    byte y
end

proc fill(Point^ pts, byte n)
    byte i
    for i = 0 to n
        pts[i].x = i
        pts[i].y = i + 10
    end
end

proc main()
    Point arr[4]
    fill(arr, 3)
end
