proc main()
    byte arr[10]
    byte result1
    byte result2
    byte result3
    
    arr[0] = 10
    arr[1] = 20
    arr[2] = 30
    arr[3] = 40
    arr[4] = 50
    
    ; Multiple adds
    result1 = arr[0] + arr[1] + arr[2] + arr[3]
    
    ; Multiple subs
    result2 = arr[4] - arr[3] - arr[2] - arr[1]
    
    ; Mixed: 2 adds, 3 subs
    result3 = arr[0] + arr[1] + arr[2] - arr[3] - arr[4] - arr[0]
end
