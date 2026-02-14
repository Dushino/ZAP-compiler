; test_stdio.zap
; working area for testing random parts of stdio.zap

.define ATARI
.include "lib/stdio.zap"

struct MyStruct
    byte a
    byte b
    byte c
end


proc getcmd()
    const byte CMD_SIZE = 16


    byte ch
    ch = getchar()
    while ch == 0
        ch = getchar()
    end
    return ch
end


proc main()

    byte ch
    byte ^ptr
    byte msg1[] = "1. Hello World! "        ; BSS segment
    const byte msg2[] = "2. Hello World! "   ; CODE segment
    byte inbuf[15]  ; BSS segment

    cls()

    PLAYF2 = COLOR_GREEN3 + 4
    puts(msg1)
    putchar('\n')    
    puts(msg2)
    putchar('\n')
    puts("3. Hello World!\n")    
    ch = gets(inbuf, 15)
    putx(ch)
    puts("\n\t1\t123\t1234\n")
    puts(inbuf)

    PLAYF2 = COLOR_GREEN3 + 0
end
