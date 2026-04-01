byte result @40000 = 0

proc main()
    ; Test case insensitivity
    Poke($9C40, 42)
    result = Peek($9C40)
    POKE($9C41, result)
    result = peek($9C41)
    poke($9C42, PEEK($9C41))
end
