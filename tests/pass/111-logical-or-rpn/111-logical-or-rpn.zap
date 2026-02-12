byte result @40000 = 0

proc main()
    byte a = 5
    byte b = 10
    byte c = 3
    byte d = 5

    byte r = (a > b) || (c < d)
    result = r
end

