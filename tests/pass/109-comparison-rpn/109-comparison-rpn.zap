byte result @40000 = 0

proc main()
    byte a = 10
    byte b = 20
    byte c = 10

    byte r = (a < b) + (a == c) + (b > c) + (a >= c)
    result = r
end
