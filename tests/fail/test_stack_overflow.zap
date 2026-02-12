; Test: Expression too complex for RPN stack
; Should fail with stack overflow error

byte result @40000 = 0

proc main()
    byte a = 1
    byte b = 2
    byte c = 3
    byte d = 4
    byte e = 5
    byte f = 6
    byte g = 7
    byte h = 8
    
    ; Very deeply nested expression that requires many spill slots
    ; This should exceed the 4-slot limit of MATH_STACK
    result = (((a + b) * (c + d)) + ((e + f) * (g + h))) + (((a * b) + (c * d)) * ((e * f) + (g * h)))
end
