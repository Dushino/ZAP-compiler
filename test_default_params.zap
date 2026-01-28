; Test default parameters

byte result @40000 = 0

proc test1(byte a, byte b=5)
    result = a + b
end

proc test2(byte a, byte b, byte c=30)
    result = a + b + c
end

func byte add(byte x, byte y=10)
    return x + y
end

proc main()
    byte x = 0
    
    ; Test 1: Call with all args
    test1(1, 2)
    ; Expected: result = 1 + 2 = 3
    
    ; Test 2: Call with partial args (use default)
    test1(4)
    ; Expected: result = 4 + 5 = 9
    
    ; Test 3: Function call with all args
    x = add(2, 8)
    ; Expected: x = 2 + 8 = 10
    
    ; Test 4: Function call with partial args
    x = add(3)
    ; Expected: x = 3 + 10 = 13
    
    ; Test 5: Multiple parameters with defaults
    test2(1, 2, 3)
    ; Expected: result = 1 + 2 + 3 = 6
    
    test2(4, 5)
    ; Expected: result = 4 + 5 + 30 = 39
end
