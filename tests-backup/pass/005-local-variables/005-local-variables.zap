; local variables


const byte c1 = $55
const byte c2 = $aa

byte a1, a2

proc test1(byte p1, word p2)
    a1 = p1
    a2 = p2
end


; main -----------------------------------------
proc main()
    byte a1, a2
    a1 = c1
    test1(a1, c2)
end

