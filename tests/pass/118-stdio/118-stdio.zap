
byte ^curptr = 40000

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


proc main()

    byte ch
    byte msg1[] = "ABCDEF"        ; BSS segment
    const byte msg2[] = "123456"   ; CODE segment

    puts(msg1)    
    puts(msg2)
    
end
