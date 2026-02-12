byte result @40000 = 0

proc main()
    byte x = 50
    byte y = 50
    word x1 = 50

    if x == y
        result = result + 1
    end

    if x == x1
        result = result + 16    
    end

    if x1 == y
        result = result + $20
    end

end
