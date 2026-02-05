; literals

byte result @40000 = 0

proc main()
    byte a = 10
    byte b = 0x0A
    byte c = a + b + 'A' + $10 + 0b00000010 ; 10+10+65+16+2=103
    result = c
end
