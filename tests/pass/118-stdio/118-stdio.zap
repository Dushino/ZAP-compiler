; just a test for random compiler features

byte ^curptr = 40000


enum MyEnum
    A = 1
    B = 2
    C = 3
end


struct MyStruct
    byte a
    byte b
    word c
    byte ^ptr
    MyEnum e
end



proc putchar(byte ch)
    curptr^ = ch
    curptr = curptr + 1        
end



/*
    puts - print null-terminated string to the screen
*/
proc puts(byte ^str)
    byte ch

    ch = str^
    while ch != 0
        putchar(ch)
        str = str + 1
        ch = str^
    end
end

func word test1(MyStruct s)
    
    return s.a + s.b + s.c + s.ptr + s.e
end


proc main()

    byte ch
    byte msg1[] = "ABCDEF"          ; BSS segment
    const byte msg2[] = "123456"    ; CODE segment
    
    MyStruct s1
    const MyStruct s2 = {1, 2, 1234, 40000, MyEnum.B}
    word rv

    ;puts(msg1)    
    ;puts(msg2)
    
    ; s1 = {1, 2, 1234, 40000, MyEnum.B}
    rv = test1(s2)
    putchar(low(rv))    ; should be 41239 / 256 = $17
    putchar(high(rv))    ; should be 41239 % 256 = $A1

    ;rv = test1(s2)
    ;putchar(low(rv))    ; should be 41238 / 256 = $17
    ;putchar(high(rv))    ; should be 41238 % 256 = $A1

    ;rv = test1({1, 2, 1234, 40000, MyEnum.B})
    ;putchar(low(rv))    ; should be 41239 / 256 = $17
    ;putchar(high(rv))    ; should be 41239 % 256 = $A1
    
end
