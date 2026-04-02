; LONG argument to WORD parameter must fail — use LOWW() or HIGHW()
proc take_word(word x)
end

long l = $12345678

proc main()
    take_word(l)
end
