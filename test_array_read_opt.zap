proc main()
    byte arr[3]
    byte sum
    
    ; Write optimization: 2 instructions each
    arr[0] = 10
    arr[1] = 20
    arr[2] = 30
    
    ; Read optimization: Direct loads with immediate indices
    sum = arr[0] + arr[1] + arr[2]
end
