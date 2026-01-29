byte result @40000 = 0

proc main()
    byte count = 0
    byte sum = 0
    
    while count < 10
        sum = sum + 1
        count = count + 1
    end
    
    result = sum    ; result = 10
end
