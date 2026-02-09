byte result @40000 = 0

proc main()
    byte arr[5]
    byte i

    for i = 0 to 5
        arr[i] = i * 2
    end

    for i = 0 to 5 STEP 2
        arr[i] = arr[i] + 1
    end

    result = arr[4]
end
