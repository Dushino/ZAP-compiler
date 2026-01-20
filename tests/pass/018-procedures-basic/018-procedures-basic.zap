proc set42(byte ^dest)
    dest^ = 42
end

byte result @40000 = 0

proc main()
    byte x = 0
    set42(@x)
    result = x
end
