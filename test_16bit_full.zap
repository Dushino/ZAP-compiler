proc main()
    byte arr[10]
    word sum1
    word sum2
    word sum3
    
    arr[0] = 50
    arr[1] = 100
    arr[2] = 150
    arr[3] = 200
    
    ; Multiple 8-bit adds with 16-bit result (with carry propagation)
    sum1 = arr[0] + arr[1] + arr[2] + arr[3]
    
    ; Test subtraction with 16-bit result
    sum2 = arr[3] - arr[2] - arr[1]
    
    ; Mixed ADD/SUB with 16-bit result
    sum3 = arr[0] + arr[1] + arr[2] - arr[3] + arr[0]
end
