word result @40000 = 0

proc main()
    byte arr[3] = {5, 10, 15}
    byte ^p = @arr[0]
    byte value

    ; Move pointer two elements forward to arr[2]
    p = p + 2
    value = p^
    result = value
end
