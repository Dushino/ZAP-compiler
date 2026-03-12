proc append_plus(byte^ dst, byte m)
    dst += m
    dst^ = '+'
    dst += 1
    dst^ = 0
end

proc main()
    byte arr[8]
    byte i
    for i = 0 to 7
        arr[i] = 0
    end
    arr[0] = 'H'
    arr[1] = 'I'
    arr[2] = 0
    append_plus(arr, 2)
end
