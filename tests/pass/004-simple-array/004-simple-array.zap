byte result @40000 = 0

proc main()
    byte arr[3]
    byte sum
    arr[0] = 10
    arr[1] = 20
    arr[2] = 30
    sum = arr[0] + arr[1] + arr[2]  ; 10 + 20 + 30 = 60
    result = sum
end
