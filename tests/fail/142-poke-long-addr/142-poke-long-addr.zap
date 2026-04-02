; POKE with LONG address must fail — use LOWW() or HIGHW()
long laddr = $12345678

proc main()
    POKE(laddr, $42)
end
