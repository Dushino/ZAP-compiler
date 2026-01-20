byte result @40000 = 0

proc main()
    byte arr[5]
    byte i

    for i = 0 to 4
        arr[i] = i * 2
    next i

    result = arr[4]
end
