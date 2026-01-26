
byte result @40000 = 0

func byte add2(byte a, byte b)

    if a > 5 then
        return a
    endif

    return a + b
end

proc main()
    result = add2(2, 4)
end
