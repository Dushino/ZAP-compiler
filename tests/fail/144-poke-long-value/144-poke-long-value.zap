; POKE with LONG value must fail — use LOW()/HIGH()/LOWW()/HIGHW()
long lval = $12345678

proc main()
    POKE($D400, lval)
end
