byte res_if @40000 = 0
byte res_while @40001 = 0
byte res_switch @40002 = 0
byte res_arr @40003 = 0
byte res_precedence @40004 = 0

proc main()
    byte a = 2
    byte b = 3
    byte c = 4
    byte i = 0
    byte arr[10]
    byte tmp_val = 0
    
    ; IF condition with complex expression
    ; Using temp variable to avoid parser complexity
    ; IF condition with complex expression
    ; Using temp variable to avoid parser complexity
    tmp_val = (a + b) * 2
    if tmp_val > c + 5
        res_if = 1
    else
        res_if = 2
    end
    
    ; WHILE condition
    while i * 2 < 10
        i = i + 1
    end
    res_while = i
    
    ; SWITCH expression
    switch (a * b) + 1
        case 7
            res_switch = 1
            break
        default
            res_switch = 2
    end
    
    ; Array index
    arr[7] = 88
    res_arr = arr[a * b + 1]
    
    ; Precedence
    ; Precedence
    if a + b * c == 14
         res_precedence = 1
    else
         res_precedence = 2
    end
end
