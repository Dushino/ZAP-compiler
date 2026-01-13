; math tests
; test_math_1.zap

const byte c1 = 3



proc math1(byte b1, byte b2)
    byte r, a, b, c
    
    r = b1 + 0
    r = b1 - 0
    r = b1 + 1
    r = b1 - 1
    b = c1
    a = r + 3 * b * (r + 1)
end


; main -----------------------------------------
proc main()
    math1(1, 2)    

end

