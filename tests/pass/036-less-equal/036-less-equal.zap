byte result @40000 = 0

proc main()
    byte x = 10
    byte y = 20
    word x1 = $0a10

    if x <= y 
        result = 1
    end

    if x <= x1
        result = result + $10 
    end
end
