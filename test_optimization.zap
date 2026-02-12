proc main()
    byte a = 10
    byte b = 20
    byte c
    
    c = a + b
    c = a - b
    c = a & b
    c = a | b
    c = a ^ b
    
    if a == b
        c = 1
    end
    
    if a < b
        c = 2
    end
    
    if a > b
        c = 3
    end
end
