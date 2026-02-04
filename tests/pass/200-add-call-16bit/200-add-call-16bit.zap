word result @40000 = 0

func word addw(word a, word b = 300)
    return a + b
end

proc main()
    result = addw(1000) ; 1000 + 300 = 1300 (0x0514)
end
