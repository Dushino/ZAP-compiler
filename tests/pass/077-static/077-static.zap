; testing CPU target as a symbol
; result should be 1 for both CPU types, but manual trests must be done for each CPU

byte result @40000 = 0


func byte helper() 
    static byte a = 1
    a = a + 1
    return a
end


proc main()
    result = helper()
    result = helper()
    result = helper()    
end
