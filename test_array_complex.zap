proc main()
    byte arr[5]
    byte i
    byte value
    
    ; Immediate index assignments (optimized to 2 instructions)
    arr[0] = 10
    arr[1] = 20
    arr[2] = 30
    arr[3] = 40
    arr[4] = 50
    
    ; Runtime index assignment (optimized to inline address calc)
    i = 2
    value = 99
    arr[i] = value
end
