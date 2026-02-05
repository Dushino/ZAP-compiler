byte result @40000 = 0

func word getw()
    return $1234
end

proc main()
    word v = getw()
    byte hi = (v >> 8) & 0xFF
end
