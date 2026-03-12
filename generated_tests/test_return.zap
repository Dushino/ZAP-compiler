proc test_early_return(byte x)
    byte y
    y = 10
    if x == 0
        return
    end
    y = y + x
end

proc main()
    test_early_return(0)
    test_early_return(5)
end
