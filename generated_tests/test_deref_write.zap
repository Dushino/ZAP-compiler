proc write_plus(byte^ dst)
    dst^ = '+'
end

proc main()
    byte arr[4]
    arr[0] = 0
    arr[1] = 0
    write_plus(arr)
end
