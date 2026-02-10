proc set42(byte ^dest, byte var1)
    dest^ = var1

end

byte result @40000 = 0

proc main()
    byte x = 0
    set42(@x, 42)
    result = x
end
