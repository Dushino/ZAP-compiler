; POKE with WORD value must fail — use LOW() or HIGH()
word wval = $1234

proc main()
    POKE($D400, wval)
end
