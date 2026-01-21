struct Row
    byte values[3]
end

byte result @40000 = 0

proc main()
    Row r
    r.values[0] = 2
    r.values[1] = 4
    r.values[2] = 6
    result = r.values[0] + r.values[1] + r.values[2] 
end
