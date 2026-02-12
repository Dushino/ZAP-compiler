proc main()
    byte a = 10
    byte b = 20
    byte c
    
    c = a + b
    c = a - b
    c = a & b
    c = a | b
    c = a ^ b
    
    if a == b then
        c = 1
    endif
    
    if a < b then
        c = 2
    endif
    
    if a > b then
        c = 3
    endif
end
