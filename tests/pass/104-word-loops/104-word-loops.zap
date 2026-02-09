

proc main()
    word i
    word result @40000 = 0
    word endv = 280

    ; FOR loop with 16-bit bounds
    for i = 0 to endv
        result = result + 1
    end
    ; result is now 280


    ; WHILE loop with 16-bit bounds
    i = 0
    while i <= endv
        result = result + 1
        i = i + 1
    end
    ; result is now 561 $0231
end
