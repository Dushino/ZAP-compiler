; Test: Moderately complex expression that should fit in MATH_STACK

byte result @40000 = 0

proc main()
    byte a = 1
    byte b = 2
    byte c = 3
    byte d = 4
    byte e = 5
    byte f = 6
    
    ; This is complex but should fit within 4 spill slots
    result = ((a + b) * (c + d)) + ((e + f) * 2)
end
