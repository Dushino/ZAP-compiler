byte result @40000 = 0

proc main()
    byte a = 2
    byte b = 3
    byte c = a + b * (a + 1) - 1 ; 2 + 3 * 3 - 1 = 10
    result = c
end
