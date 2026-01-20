
byte result @ 40000

proc main()
    byte i @40001 = 0
    while i < 10
        if i == 5 then
            break
        endif
        i = i + 1
    end
    result = i
end
