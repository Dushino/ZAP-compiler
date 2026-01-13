; variables declaration tests
; test_variables_decl.zap

const byte A4 = 3
const byte a5 = 'a'

proc test1(byte p1, byte p2)
    byte t1
    t1 = p1 + p2
end


proc test2(word b1, word b2)
    word t1
    t1 = b1 + b2
end


proc test3(word b1, word b2)
    word t1

    t1 = b1 - b2
end



; main -----------------------------------------
proc main()
    byte a1 = 5
    word b1
    
    a1 = a4 + a5 + 2
    ; byte parameters
    test1(a1, 3)
    test2(a1, 4)

    ; word parameetrs
    b1 = a4 + a5 + 5
    test3(10, 6)
    test3(10, 7)

    ; byte to word conversion
    test3(a1, 8)
    test2(a1, 9)

    ; word to byte conversion
    test1(b1, 1234)


end

