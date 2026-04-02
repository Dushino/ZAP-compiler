; PEEK with LONG address must fail — use LOWW() or HIGHW()
long laddr = $12345678
byte result

proc main()
    result = PEEK(laddr)
end
