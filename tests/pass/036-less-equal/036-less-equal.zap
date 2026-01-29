byte result @40000 = 0

proc main()
    byte x = 10
    byte y = 20
    word x1 = $0a10

    if x <= y then
        result = 1
    endif

    if x <= x1 then
        result = result + $10 
    endif
end
