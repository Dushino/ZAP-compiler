byte result @40000 = 0

proc main()
    byte x = 0x0F  ; 0000 1111 in binary
    byte y = ~x    ; Should be 1111 0000 = 0xF0
    if y == 0xF0
        result = 1
    else
        result = 0
    end
end
