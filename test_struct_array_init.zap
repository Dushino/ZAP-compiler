; Test: Struct array initialization with nested braces

struct Point
    byte X
    byte Y
    byte Z
end

; Declare and initialize a struct array
Point points[3] @40000 = {
    {1, 2, 3},
    {4, 5, 6},
    {7, 8, 9}
}

proc main()
    ; The array is already initialized in memory
    ; points[0] = {1, 2, 3}
    ; points[1] = {4, 5, 6}
    ; points[2] = {7, 8, 9}
end
