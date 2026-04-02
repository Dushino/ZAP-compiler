; LONG argument to BYTE parameter must fail — use LOW()/HIGH()/LOWW()/HIGHW()
proc take_byte(byte x)
end

long l = $12345678

proc main()
    take_byte(l)
end
