byte result1 @40000 = 42
byte result2 @40001 = 42
byte result3 @40002 = 42
byte result4 @40003 = 42
byte result5 @40004 = 42
byte result6 @40005 = 42


proc main()
    
    const word a = $1234
    word b = $2345
    byte ^ptr = 40000    
    
    result1 = low(a)
    result2 = high(a)

    result3 = low(b)
    result4 = high(b)   

    result5 = low(ptr)
    result6 = high(ptr)   

end
