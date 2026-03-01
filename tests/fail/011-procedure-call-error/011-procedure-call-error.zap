func byte add(byte a, byte b)
    byte res = a + b
    return res
end

proc main()
    byte x = add(30)    ; Wrong number of arguments: expects 2, got 1
end
