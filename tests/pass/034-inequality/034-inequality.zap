byte result @40000 = 0

proc main()
    byte x = 30
    byte y = 20
    word x1 = $1030

    if x != y 
        result = 1
    end

    if x1 != x 
        result = result + $10
    end
end
