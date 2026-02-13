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

    cls()
    PLAYF2 = COLOR_GREEN3 + 2
    putchar('H')
    putchar('i')    
    putchar('!')
    putchar(' ')
    
    ch = getchar()
    while ch != 27
        switch ch

            default
                putx(ch)
                putchar(' ')
                putchar(' ')
                break
        end
        ch = getchar()
    end 

    PLAYF4 = COLOR_BLUE1  + 2

end
