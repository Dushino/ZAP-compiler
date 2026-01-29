byte result @40000 = 0

proc main()
    byte a = 1
    byte b = 0
    
    while a == 1
        result = result + 1
        a = b
    end
end
