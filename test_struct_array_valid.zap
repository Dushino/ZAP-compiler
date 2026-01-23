struct Point
    byte x
    byte y
end

.ifdef DEBUG
    byte debug_flag = 1
.endif

proc main()
    Point arr[2] = { { 1, 2 }, { 3, 4 } }
end
