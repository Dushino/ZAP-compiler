byte result @40000 = 0

proc main()
    byte arr[5] = { 1, 2, 3, 4, 5}
    byte sum
    arr[0] = 10
    arr[1] = 20
    arr[2] = 30
    arr[3] = 40
    arr[4] = 50
    sum = arr[0] + arr[1] + arr[2] + arr[3] + arr[4]
    result = sum
end
