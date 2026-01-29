byte result @40000 = 0

proc main()
    byte x = 50
    byte y = 50
    word x1 = 50

    if x == y then
        result = result + 1
    endif

    if x == x1 then
        result = result + 16    
    endif

    if x1 == y then
        result = result + $20
    endif

end
