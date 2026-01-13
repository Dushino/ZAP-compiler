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

; main -----------------------------------------
proc main()
    byte a1
    word b1
    a1 = a4 + a5 + 5
    test1(a1, 8)
    test2(a1, 7)
    b1 = a4 + a5 + 6
end

