struct Row
    byte values[3]
end

byte result @40000 = 0

proc main()
    Row r
    r.values[0] = $02
    r.values[1] = $14
    r.values[2] = $06
    result = r.values[0] + r.values[1] + r.values[2] ; $1C
end
