proc main()
    byte x = test(5)
end

func byte test(byte a)
    if a > 10 then
        return 100
    endif
    
    if a > 5 then
        return 50
    endif
    
    return a
end
