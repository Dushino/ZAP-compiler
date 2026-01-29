byte result @40000 = 0

proc main()
    byte expr = ((1 + 2) * (3 + 4)) - ((5 - 2) * 2)   ; 3*7 - 3*2 = 21 - 6 = 15

    if ((expr > 5) && (expr < 20)) || (expr == 0) then
        result = 1
    else
        result = 0
    endif
end
