word result1 @40000 = $1234
word result2 @40002 = $2345
word result3 @40004 = $2345
word result4 @40006 = $2345


struct MyStruct
    byte a
    word b
    byte c
end

MyStruct ms

proc main()
       
    result1 = sizeof(MyStruct)
    result2 = sizeof(ms)
    
end
