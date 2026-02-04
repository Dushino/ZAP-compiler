; Test default parameters

byte result @40000 = 0
byte x      @40001 = 0

func byte test1(byte a, byte b=5)
    result = a + b
    return result
end

func byte test2(byte a, byte b, byte c=30)
    result = a + b + c
    return result   
end

func byte add(byte x, byte y=10)
    return x + y
end

proc main()
    
    ; Test 1: Call with all args
    result = test1(1, 2)                    ; 3
    ; Expected: result = 1 + 2 = 3
    
    ; Test 2: Call with partial args (use default)
    result = result + test1(4)          ; 3 + 9 = 12
    ; Expected: result = 4 + 5 = 9
    
    ; Test 3: Function call with all args
    x = add(2, 8)                       ; 2 + 8 = 10
    ; Expected: x = 2 + 8 = 10
    
    ; Test 4: Function call with partial args
    x = x + add(3)                          ; 10 + 13 = 23 $17
    ; Expected: x = 3 + 10 = 13
    
    ; Test 5: Multiple parameters with defaults
    result = result + test2(1, 2, 3)        ; 12 + 6 = 18
    ; Expected: result = 1 + 2 + 3 = 6
    
    result = result + test2(4, 5)           ; 18 + 39 = 57  $39
    
end
