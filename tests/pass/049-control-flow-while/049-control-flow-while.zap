byte result @40000 = 0

proc main()
    byte count = 3
    byte sum = 0

    while count > 0
        sum = sum + 2
        count = count - 1
    end

    result = sum
end
