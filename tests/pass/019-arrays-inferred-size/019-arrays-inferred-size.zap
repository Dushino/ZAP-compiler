word result @40000 = 0

proc main()
    byte arr[] = {10, 20, 30, 40, 50}
    byte sum
    
    ; Array size should be inferred from initializer (5 elements)
    sum = arr[0] + arr[1] + arr[2] + arr[3] + arr[4]
    ; 10 + 20 + 30 + 40 + 50 = 150 (0x96)
    
    result = sum
end
