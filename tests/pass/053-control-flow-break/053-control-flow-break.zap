byte result @40000 = 0

proc main()
    byte i = 0

    while i < 10
        if i == 5
            break
        endif
        i = i + 1
    end

    result = i
end
