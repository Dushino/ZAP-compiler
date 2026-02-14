; test_stdio.zap
; working area for testing random parts of stdio.zap

.define ATARI
.include "lib/stdio.zap"


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
    byte msg1[] = "1. Hello World! "        ; BSS segment
    const byte msg2[] = "2. Hello World!"   ; CODE segment

    cls()
    PLAYF2 = COLOR_GREEN3 + 4
    puts(msg1)    
    puts(msg2)
    puts("3. Hello World!")
    PLAYF2 = COLOR_GREEN3 + 12
end
