byte result @40000 = 0

proc main()
    byte arr[10]
    byte i
    i = 0
    
    while i < 10
        arr[i] = i
        i = i + 1
    end
    
    result = arr[9]
end
