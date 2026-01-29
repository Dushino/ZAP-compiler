proc add(byte ^dst, byte v)
    dst^ = dst^ + v
end

byte result @40000 = 0

proc main()
    byte x = 5
    add(@x, 3)
    result = x
end
