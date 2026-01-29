word result @40000 = 0

proc main()
    byte greeting[6] = "hello"
    word sum

    ; Sum characters (h+e+l+l+o = 532 / 0x0214)
    sum = greeting[0] + greeting[1] + greeting[2] + greeting[3] + greeting[4]
    result = sum
end
