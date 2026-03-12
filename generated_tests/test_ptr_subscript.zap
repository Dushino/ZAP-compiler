; Test: subscript write/read through a pointer parameter
proc fill3(byte^ buf, byte val)
    buf[0] = val
    buf[1] = val + 1
    buf[2] = val + 2
end

proc main()
    byte arr[4]
    arr[0] = 0
    arr[1] = 0
    arr[2] = 0
    fill3(arr, 10)
    ; arr should now be {10, 11, 12}
end
