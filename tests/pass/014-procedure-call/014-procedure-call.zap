byte result @40000 = 0

proc add(byte a, byte b)
    byte res = a + b
    result = res
end

proc main()
    add(30, 12)
end
