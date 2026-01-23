proc main()
    byte arr[10]
    byte a
    byte b
    byte result1
    byte result2
    byte result3
    byte result4
    
    arr[0] = 10
    arr[1] = 20
    arr[2] = 30
    a = 5
    b = 15
    
    ; Test: arr[i] + immediate
    result1 = arr[0] + 5
    
    ; Test: arr[i] + variable
    result2 = arr[1] + a
    
    ; Test: variable + arr[i]
    result3 = b + arr[2]
    
    ; Test: arr[i] - immediate
    result4 = arr[0] - 3
end
