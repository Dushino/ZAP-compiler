byte result @40000 = 0

proc main()
    byte a = 5
    byte b = 10
    byte c = 5

    byte r = ((a < b) && (b < c)) || (a == c)
    result = r
end

